"""Crash and ownership checks cross a real process/persistence boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from podcast_processor.cli import app
from test_managed_transcription import PRIMARY, BACKUP, service, managed
from test_workspace import authority, inspect, make_media, runner

SCRIPT = '''
import json, os, sys, time
from pathlib import Path
import httpx
if sys.argv[1] == 'no-local-ml':
    sys.modules['faster_whisper'] = None
from podcast_processor.cli import app
mode, control = sys.argv[1:3]
del sys.argv[1:3]
control = Path(control)
def send(client, request, **kwargs):
    with (control / 'calls').open('a') as stream:
        stream.write(request.method + ' ' + request.url.path + '\\n')
        stream.flush()
        os.fsync(stream.fileno())
    if request.url.path == '/v2/upload':
        body = {'upload_url': 'https://cdn.assemblyai.com/test.flac'}
    elif request.url.path == '/v2/transcript':
        if mode == 'during-submit':
            os._exit(73)
        body = {'id': 'primary-job', 'status': 'queued'}
    elif request.url.path == '/v1/listen':
        body = json.loads((control / 'backup.json').read_text())
    else:
        if mode == 'lock':
            (control / 'ready').touch()
            time.sleep(30)
        body = json.loads((control / 'primary.json').read_text())
    return httpx.Response(200, json=body, request=request)
httpx.Client.send = send
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_bytes())
        attempts = state['transcription_operations'][0]['attempts']
        trigger = (mode == 'accepted' and attempts and attempts[0]['job_id']
                   or mode == 'raw' and state['evidence']
                   or mode == 'normalized' and 'transcript.json' in state['artifacts']
                   or mode == 'backup-accepted' and len(attempts) == 2 and attempts[1]['job_id'])
        if trigger:
            # Simulate death immediately after a committed accepted ID for Deepgram.
            if mode == 'backup-accepted':
                replace(src, dst)
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''


def launch(tmp_path, mode, *, background=False):
    (tmp_path / 'primary.json').write_text(json.dumps(PRIMARY if mode != 'backup-accepted' else
        {'id': 'primary-job', 'status': 'error', 'error': 'controlled'}))
    (tmp_path / 'backup.json').write_text(json.dumps(BACKUP))
    source = make_media(tmp_path / 'recording.wav')
    command = [sys.executable, '-c', SCRIPT, mode, str(tmp_path), 'transcribe', str(source),
               '--workspace', str(tmp_path / 'episode'), *authority(tmp_path)]
    if background:
        return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.run(command, capture_output=True, timeout=15)


@pytest.mark.parametrize('mode', ['accepted', 'raw', 'normalized', 'backup-accepted'])
def test_crash_recovers_accepted_ids_and_successful_responses_without_new_jobs(tmp_path, service, mode):
    crashed = launch(tmp_path, mode)
    assert crashed.returncode == 73, crashed.stderr
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    assert before['runs'][-1]['status'] == 'interrupted'
    _, resumed = managed(tmp_path)
    assert resumed.exit_code == 0, (resumed.output, resumed.exception)
    after = inspect(workspace)
    assert after['transcription_operations'][0]['id'] == before['transcription_operations'][0]['id']
    assert all(request.method == 'GET' for request in service)
    assert json.loads((workspace / 'current/transcript.json').read_bytes())['words']


def test_simultaneous_invocation_cannot_buy_a_second_job_and_dead_writer_releases_lock(tmp_path, service):
    process = launch(tmp_path, 'lock', background=True)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / 'ready').exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / 'ready').exists()
        result = runner.invoke(app, ['transcribe', str(tmp_path / 'episode')])
        assert result.exit_code == 1
        assert 'Active operation' in result.output
        assert not service
    finally:
        process.kill()
        process.wait(timeout=5)
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert all(request.method == 'GET' for request in service)


def test_process_death_during_submission_reserves_slot_and_reconciles(tmp_path, service, monkeypatch):
    import httpx
    crashed = launch(tmp_path, 'during-submit')
    assert crashed.returncode == 73
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    assert before['transcription_operations'][0]['attempts'][0]['status'] == 'intent'
    original = httpx.Client.send
    def send(client, request, **kwargs):
        if request.method == 'GET' and request.url.path == '/v2/transcript':
            service.append(request)
            return httpx.Response(200, json={'transcripts': [{'id': 'primary-job',
                'audio_url': 'https://cdn.assemblyai.com/test.flac'}]}, request=request)
        return original(client, request, **kwargs)
    monkeypatch.setattr(httpx.Client, 'send', send)
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert all(r.method == 'GET' for r in service)
    assert len(inspect(workspace)['transcription_operations'][0]['attempts']) == 1


def test_local_write_failure_preserves_raw_and_never_retranscribes(tmp_path, service, monkeypatch):
    replace = os.replace
    failed = [False]
    def fail(src, dst):
        if Path(dst).name == 'current' and not failed[0] and (Path(src).resolve() / 'transcript.json').exists():
            failed[0] = True
            raise OSError('controlled disk failure')
        return replace(src, dst)
    monkeypatch.setattr(os, 'replace', fail)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 1
    before = inspect(workspace)
    assert before['evidence']
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert len(service) == 3
    assert inspect(workspace)['runs'][-1]['status'] == 'completed'


@pytest.mark.parametrize('corruption', [{}, {'body': 12, 'sha256': 'bad'}, {'body': 'e30=', 'sha256': 'bad'}])
def test_corrupt_recovery_receipt_reports_partial_without_new_jobs(tmp_path, service, corruption):
    assert launch(tmp_path, 'accepted').returncode == 73
    workspace = tmp_path / 'episode'
    receipt = next((workspace / 'receipts').rglob('submission.json'))
    receipt.write_text(json.dumps(corruption))
    _, result = managed(tmp_path)
    assert result.exit_code == 1
    # Read the last committed public state before inspect can mark a running run interrupted.
    state = json.loads((workspace / 'current/state.json').read_bytes())
    assert state['runs'][-1]['status'] == 'partial'
    assert state['transcription_operations'][0]['attempts'][0]['reserved_usd'] > 0
    assert not service


def test_managed_operation_does_not_require_local_ml_installation(tmp_path, service):
    result = launch(tmp_path, 'no-local-ml')
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'episode/current/transcript.json').exists()
