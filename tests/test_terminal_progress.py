"""Operator feedback through the CLI with controlled media/provider boundaries."""
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import time

import httpx
import pytest

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from test_episode_workflow import full_services, process
from test_workspace import runner
from test_publishing_package import episode, publishing
from test_boundary_discovery import discovery_services, new_episode


def test_progress_precedes_preparation_and_provider_calls(tmp_path, full_services, approved_show_setup, monkeypatch):
    run = subprocess.run
    send = httpx.Client.send
    observed = []

    def prepare(*args, **kwargs):
        output = sys.stderr.buffer.getvalue().decode()
        assert 'Starting process:' in output
        assert str(tmp_path / 'recording.wav') in output
        assert 'Preparing audio' in output
        observed.append('preparation')
        return run(*args, **kwargs)

    def request(client, request, **kwargs):
        expected = ('Uploading audio' if request.url.path == '/v2/upload' else
                    'Waiting for transcription' if request.method == 'GET' else 'Submitting transcription')
        assert expected in sys.stderr.buffer.getvalue().decode()
        observed.append(expected)
        return send(client, request, **kwargs)

    monkeypatch.setattr(subprocess, 'run', prepare)
    monkeypatch.setattr(httpx.Client, 'send', request)
    result = process(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert observed
    for stage in ('Processing speaker information', 'Generating description', 'Generating title',
                  'Generating chapters', 'Planning sections'):
        assert stage in result.stderr
    assert '\r' not in result.stderr and '\x1b' not in result.stderr
    state = runner.invoke(app, ['inspect', str(tmp_path / 'episode'), '--json'])
    assert json.loads(state.stdout)['runs'][-1]['status'] == 'completed'
    assert not state.stderr


def test_concise_completion_preserves_recovered_retry_and_timing_diagnostics(
        tmp_path, full_services, approved_show_setup, monkeypatch):
    send = httpx.Client.send
    publish = ClaudeClient.generate
    chapters = []

    def request(client, request, **kwargs):
        response = send(client, request, **kwargs)
        if request.method == 'GET':
            data = response.json()
            for word in data['words'][-2:]:
                word['end'] = word['start']
            return httpx.Response(200, json=data, request=request)
        return response

    def generate(client, prompt, **kwargs):
        client.response_metadata = {'usage': {'input_tokens': 1234}, 'request_id': 'internal-request-id'}
        if prompt.startswith('STAGE: chapters'):
            chapters.append(prompt)
            if len(chapters) == 1:
                return '[]'
        return publish(client, prompt, **kwargs)

    monkeypatch.setattr(httpx.Client, 'send', request)
    monkeypatch.setattr(ClaudeClient, 'generate', generate)
    result = process(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert 'Status: completed' in result.stdout
    assert 'Ready: timed transcript, description, title/thumbnail concepts, YouTube chapters' in result.stdout
    assert 'Sections unavailable: duration constraints' in result.stdout
    assert 'Recovered: chapters succeeded after 1 retry' in result.stdout
    assert 'Precision notes: 2 words' in result.stdout
    assert 'Next: use the ready publishing outputs' in result.stdout
    assert len(result.stdout.splitlines()) <= 15
    assert 'Retrying chapters' in result.stderr
    for raw in ('input_tokens', 'internal-request-id', 'word-', 'Corrections', 'Transcription usage'):
        assert raw not in result.output
    report = tmp_path / 'episode/current/completion-report.md'
    assert str(report) in result.stdout
    diagnostic = report.read_text()
    assert 'input_tokens' in diagnostic and 'invalid' in diagnostic
    assert 'Chapters require 3–10' in diagnostic
    assert 'timing' in diagnostic
    assert len(chapters) == 2
    fresh = process(tmp_path, '--only', 'chapters', '--fresh')
    assert fresh.exit_code == 0, fresh.output
    assert 'Recovered: chapters' not in fresh.stdout  # Earlier retries are now historical.


def test_generate_summary_explains_missing_required_outputs_without_repeating_requests(tmp_path, publishing):
    workspace = episode(tmp_path, duration=None, segments=[{'text': 'Listen with care.'}])
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fixture'])
    assert result.exit_code == 1, result.output
    assert 'Status: partial' in result.stdout
    assert 'Ready: timed transcript, title/thumbnail concepts' in result.stdout
    assert 'Missing required outputs: description.md, chapters.txt' in result.stdout
    assert 'Chapters unavailable: preserved timing cannot support three natural chapters' in result.stdout
    assert 'Description unavailable: a complete description requires chapters' in result.stdout
    assert 'Supply usable timed-transcript evidence' in result.stdout
    assert 'Detailed report:' in result.stdout
    assert len(publishing) == 2
    resumed = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fixture'])
    assert resumed.exit_code == 1 and len(publishing) == 2
    assert 'Reused' in resumed.stderr


def test_exhausted_generation_is_actionable_and_not_reported_as_recovered(tmp_path, publishing, monkeypatch):
    workspace = episode(tmp_path)
    publish = ClaudeClient.generate
    attempts = []

    def generate(client, prompt, **kwargs):
        if prompt.startswith('STAGE: chapters'):
            attempts.append(prompt)
            raise RuntimeError('Controlled provider outage')
        return publish(client, prompt, **kwargs)

    monkeypatch.setattr(ClaudeClient, 'generate', generate)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fixture'])
    assert result.exit_code == 1, result.output
    assert 'Chapters unavailable: three publishing attempts exhausted' in result.stdout
    assert 'unchanged resume cannot retry' in result.stdout
    assert 'Recovered:' not in result.stdout
    assert 'provider/interrupted request failure' in result.stderr
    assert len(attempts) == 3
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fixture']).exit_code == 1
    assert len(attempts) == 3


def test_unattempted_planning_is_partial_and_requests_matching_evidence(
        tmp_path, full_services, approved_show_setup):
    workspace = episode(tmp_path)
    result = runner.invoke(app, ['process', str(workspace)])
    assert result.exit_code == 1, result.output
    assert 'Status: partial' in result.stdout
    assert 'Sections incomplete: source/timing evidence is missing or inconsistent' in result.stdout
    assert 'Discovery not run' in result.stdout
    assert 'Supply matching source and timed-transcript evidence' in result.stdout
    assert 'No pair' not in result.output
    state = json.loads(runner.invoke(app, ['inspect', str(workspace), '--json']).stdout)
    assert state['runs'][-1]['status'] == 'partial'
    assert next(run for run in reversed(state['runs']) if run['operation'] == 'plan')['status'] == 'partial'
    assert {'description.md', 'titles.json', 'chapters.txt'} <= state['artifacts'].keys()
    calls = list(full_services)
    resumed = runner.invoke(app, ['process', str(workspace)])
    assert resumed.exit_code == 1 and full_services == calls
    assert 'Reused section-planning checkpoint' in resumed.stderr


def test_redirected_transcribe_keeps_elapsed_feedback_during_a_blocked_upload(tmp_path, full_services, monkeypatch):
    from test_episode_workflow import recording
    send = httpx.Client.send

    def request(client, request, **kwargs):
        if request.url.path == '/v2/upload':
            # Observe feedback while the external call is still blocked, not after
            # completion. Real time keeps the heartbeat independent of ASR clocks.
            deadline = time.monotonic() + 12
            while 'Still working: Uploading audio' not in sys.stderr.buffer.getvalue().decode():
                assert time.monotonic() < deadline, 'No elapsed feedback during the blocked upload'
                time.sleep(.05)
            assert 'elapsed]' in sys.stderr.buffer.getvalue().decode()
        return send(client, request, **kwargs)

    monkeypatch.setattr(httpx.Client, 'send', request)
    workspace = tmp_path / 'episode'
    result = runner.invoke(app, ['transcribe', str(recording(tmp_path)), '--solo', '--workspace', str(workspace)])
    assert result.exit_code == 0, (result.output, result.exception)
    assert 'Status: completed' in result.stdout
    assert 'Next: generate the publishing package' in result.stdout
    assert full_services == ['POST /v2/upload', 'POST /v2/transcript', 'GET /v2/transcript/full-job']
    assert '\x1b' not in result.output and '\r' not in result.output
    state = runner.invoke(app, ['inspect', str(workspace), '--json'])
    assert not state.stderr and json.loads(state.stdout)['runs'][-1]['operation'] == 'transcribe'


@pytest.mark.parametrize('missing', ['transition_in', 'source'])
def test_standalone_plan_returns_non_success_for_missing_prerequisites(tmp_path, missing):
    from test_section_planning import episode as planning_episode
    workspace, evidence = planning_episode(tmp_path)
    if missing == 'source':
        evidence['source']['fingerprint'] = None
    else:
        evidence[missing] = None
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps(evidence))
    result = runner.invoke(app, ['plan', str(workspace), '--evidence', str(path)])
    assert result.exit_code == 1, result.output
    state = json.loads(runner.invoke(app, ['inspect', str(workspace), '--json']).stdout)
    assert state['runs'][-1]['status'] == 'partial'
    assert runner.invoke(app, ['plan', str(workspace)]).exit_code == 1


def test_terminal_elapsed_display_updates_before_transcription_finishes(tmp_path):
    from test_episode_workflow import recording
    script = '''
import httpx, sys, time
from podcast_processor.cli import app
from test_managed_transcription import PRIMARY
def send(client, request, **kwargs):
    if request.url.path == '/v2/upload':
        time.sleep(2.5)
        body = {'upload_url': 'https://example.test/audio'}
    elif request.method == 'POST' and request.url.path == '/v2/transcript':
        body = {'id': 'primary-job', 'status': 'queued'}
    elif request.url.path == '/v2/transcript/primary-job':
        body = PRIMARY
    else:
        raise AssertionError('Unexpected provider call')
    return httpx.Response(200, json=body, request=request)
httpx.Client.send = send
app(['transcribe', sys.argv[1], '--workspace', sys.argv[2], '--solo'])
'''
    master, slave = pty.openpty()
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parent), 'TERM': 'xterm',
           'ASSEMBLYAI_API_KEY': 'fixture', 'DEEPGRAM_API_KEY': 'fixture'}
    child = subprocess.Popen([sys.executable, '-c', script, str(recording(tmp_path)), str(tmp_path / 'episode')],
                             stdout=subprocess.PIPE, stderr=slave, env=env)
    os.close(slave)
    output = b''
    try:
        deadline = time.monotonic() + 10
        while b'00:01 elapsed' not in output:
            assert time.monotonic() < deadline, output.decode(errors='replace')
            assert child.poll() is None, output.decode(errors='replace')
            if select.select([master], [], [], .1)[0]:
                output += os.read(master, 65536)
        assert child.poll() is None  # The elapsed update precedes provider completion.
        stdout, _ = child.communicate(timeout=10)
        assert child.returncode == 0, stdout.decode()
        assert b'Status: completed' in stdout and b'\x1b' not in stdout
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
        os.close(master)


def test_early_failure_is_acknowledged_and_actionable(tmp_path):
    result = runner.invoke(app, ['process', str(tmp_path / 'missing.wav'), '--solo'])
    assert result.exit_code == 1
    assert 'Starting process:' in result.stderr
    assert 'Status: failed' in result.stdout
    assert 'missing.wav' in result.stdout
    assert 'Next:' in result.stdout


def test_discovery_failure_summary_names_missing_credentials(tmp_path, discovery_services, approved_show_setup, monkeypatch):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, result.output
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    assert runner.invoke(app, ['plan', str(workspace), '--fresh']).exit_code == 1
    result = runner.invoke(app, ['process', str(workspace)])
    assert result.exit_code == 1, result.output
    assert 'Sections failed: Anthropic API key required' in result.stdout
    assert 'configure ANTHROPIC_API_KEY' in result.stdout
    assert 'No completed search' in result.stdout
    assert '--fresh' not in result.stdout


def test_default_transcribe_failure_displays_saved_report(tmp_path, full_services, monkeypatch):
    from test_episode_workflow import recording
    run = subprocess.run
    def fail_preparation(command, **kwargs):
        if command[0] == 'ffmpeg':
            raise OSError('Controlled preparation failure')
        return run(command, **kwargs)
    source = recording(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, 'run', fail_preparation)
    result = runner.invoke(app, ['transcribe', str(source), '--solo'])
    assert result.exit_code == 1, result.output
    report = next((tmp_path / 'output/episodes').glob('*/current/completion-report.md'))
    assert str(report) in result.stdout
    assert not full_services


def test_pinned_planning_evidence_requires_updating_its_missing_transitions(
        tmp_path, discovery_services, approved_show_setup):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, result.output
    evidence = json.loads((workspace / 'current/section-plan.json').read_text())['evidence']
    evidence['transition_in'] = None
    path = tmp_path / 'planning.json'
    path.write_text(json.dumps(evidence))
    calls = list(discovery_services)
    result = runner.invoke(app, ['process', str(workspace), '--evidence', str(path)])
    assert result.exit_code == 1, result.output
    assert 'transition_in' in result.stdout
    assert 'supply corrected --evidence FILE' in result.stdout
    assert discovery_services == calls
