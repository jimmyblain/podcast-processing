"""Show setup through the CLI, using real PCM audio and isolated saved defaults."""
import json
import wave
import os
import select
import subprocess
import sys
import time
import pytest

from podcast_processor.cli import app
from test_workspace import runner
from test_workspace import inspect
from test_episode_workflow import full_services, recording
from setup_audio import LINKS, transitions


def setup_state():
    result = runner.invoke(app, ['inspect-setup', '--json'])
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads(result.output)


def test_setup_preserves_decay_measures_audio_and_waits_for_listening(tmp_path):
    originals, content = transitions(tmp_path)
    before = {path.name: path.read_bytes() for path in originals.iterdir()}
    result = runner.invoke(app, ['setup', '--transitions', str(originals), '--prepare-only'])
    assert result.exit_code == 0, (result.output, result.exception)
    assert 'Listen' in result.output and 'not approved' in result.output
    setup = setup_state()
    assert setup['approved_at'] is None
    assert setup['profile']['links'] == LINKS
    assert setup['profile']['promotional_text'] is None
    for prepared in setup['transitions'].values():
        with wave.open(str(tmp_path / 'show-setup' / prepared['path']), 'rb') as audio:
            assert audio.getframerate() == 8000
            assert audio.getnframes() == 28000
            assert audio.readframes(audio.getnframes()) == content + b'\0' * 4 * 20000
        assert prepared['duration'] == '3.5'
        assert prepared['retained_frames'] == 8000
        assert prepared['ending_silence_frames'] == 20000
    assert {path.name: path.read_bytes() for path in originals.iterdir()} == before
    assert runner.invoke(app, ['setup', '--no-play'], input='n\n').exit_code == 1
    assert setup_state() == setup
    result = runner.invoke(app, ['setup', '--no-play'], input='y\n')
    assert result.exit_code == 0, (result.output, result.exception)
    approved = setup_state()
    assert approved['approved_at']
    assert approved['revision'] == setup['revision']
    assert approved['transitions'] == setup['transitions']
    result = runner.invoke(app, ['setup', '--no-play'])
    assert result.exit_code == 0 and 'already approved' in result.output
    assert setup_state() == approved


def test_two_new_episodes_reuse_approved_show_setup_and_pin_evidence(tmp_path, full_services, monkeypatch):
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--ending-silence', '2', '--no-play'], input='y\n').exit_code == 0
    approved = setup_state()
    # The saved setup, not its original location, supplies ordinary episodes.
    for path in originals.iterdir():
        path.unlink()
    states = []
    for index in (1, 2):
        directory = tmp_path / f'episode-{index}'
        directory.mkdir()
        workspace = directory / 'workspace'
        result = runner.invoke(app, ['process', str(recording(directory, value=index)),
                                     '--workspace', str(workspace), '--solo'])
        assert result.exit_code == 0, (result.output, result.exception)
        state = inspect(workspace)
        states.append(state)
        assert state['show_profile'] == approved['profile']
        assert state['show_setup_revision'] == approved['revision']
        snapshot = state['evidence']['show-setup.json']
        assert json.loads((workspace / snapshot['path']).read_bytes()) == approved
        plan = json.loads((workspace / 'current/section-plan.json').read_bytes())
        assert plan['evidence']['settings']['transition_ending_silence'] == '2.0'
        for role in ('episode_start', 'transition_in', 'transition_out'):
            measured = plan['evidence'][role]
            assert measured['duration'] == '3'
            assert measured['ending_silence'] == '2.0'
            assert measured['basis'] == 'verified'
            assert measured['prepared_revision'] == approved['transitions'][role]['sha256']
            assert 'PCM frames' in measured['evidence']
        description = (workspace / 'current/description.md').read_text()
        assert all(link in description for link in LINKS)
        assert setup_state() == approved
    assert states[0]['episode_id'] != states[1]['episode_id']
    # Resume uses the episode's consumed evidence even when no global setup remains.
    monkeypatch.setenv('PODCAST_SHOW_SETUP', str(tmp_path / 'missing-setup'))
    workspace = tmp_path / 'episode-1/workspace'
    calls = list(full_services)
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    after = inspect(workspace)
    assert after['artifacts'] == states[0]['artifacts']
    assert after['evidence']['show-setup.json'] == states[0]['evidence']['show-setup.json']
    assert after['transcription_operations'] == states[0]['transcription_operations']
    assert full_services == calls


def test_setup_after_partial_processing_resumes_without_repeating_paid_work(tmp_path, full_services):
    workspace = tmp_path / 'episode'
    assert runner.invoke(app, ['process', str(recording(tmp_path)), '--workspace', str(workspace), '--solo']).exit_code == 1
    before = inspect(workspace)
    calls = list(full_services)
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--no-play'], input='y\n').exit_code == 0
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    after = inspect(workspace)
    assert after['show_setup_revision'] == setup_state()['revision']
    assert after['transcription_operations'] == before['transcription_operations']
    assert after['publishing_operations'] == before['publishing_operations']
    for name in ('transcript.json', 'description.md', 'titles.json', 'chapters.txt'):
        assert after['artifacts'][name] == before['artifacts'][name]
    assert full_services == calls


def test_asset_change_requires_new_approval_while_existing_episode_keeps_its_setup(tmp_path, full_services):
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--no-play'], input='y\n').exit_code == 0
    approved = setup_state()
    workspace = tmp_path / 'episode'
    assert runner.invoke(app, ['process', str(recording(tmp_path)), '--workspace', str(workspace), '--solo']).exit_code == 0
    before = inspect(workspace)
    asset = originals / 'transition-in.WAV'
    with wave.open(str(asset), 'wb') as audio:
        audio.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        audio.writeframes(b'\x01\0' * 16000 + b'\0' * 80000)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--prepare-only']).exit_code == 0
    changed = setup_state()
    assert changed['approved_at'] is None
    assert changed['transitions']['transition_in']['duration'] == '4.5'
    assert changed['revision'] != approved['revision']
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    resumed = inspect(workspace)
    assert resumed['show_setup_revision'] == approved['revision']
    assert resumed['artifacts'] == before['artifacts']
    assert runner.invoke(app, ['setup', '--no-play'], input='y\n').exit_code == 0
    directory = tmp_path / 'next'
    directory.mkdir()
    next_workspace = directory / 'episode'
    assert runner.invoke(app, ['process', str(recording(directory, value=1)), '--workspace', str(next_workspace), '--solo']).exit_code == 0
    assert inspect(next_workspace)['show_setup_revision'] == changed['revision']


def test_explicit_silence_change_prepares_new_files_for_listening(tmp_path):
    originals, content = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--no-play'], input='y\n').exit_code == 0
    approved = setup_state()
    result = runner.invoke(app, ['setup', '--ending-silence', '2', '--prepare-only'])
    assert result.exit_code == 0, (result.output, result.exception)
    changed = setup_state()
    assert changed['approved_at'] is None
    assert changed['revision'] != approved['revision']
    assert changed['ending_silence'] == '2.0'
    for name, asset in changed['transitions'].items():
        with wave.open(str(tmp_path / 'show-setup' / asset['path']), 'rb') as audio:
            assert audio.getnframes() == 24000
            assert audio.readframes(audio.getnframes()) == content + b'\0' * 4 * 16000
        assert asset['duration'] == '3'
        assert (tmp_path / 'show-setup' / approved['transitions'][name]['path']).is_file()
    assert runner.invoke(app, ['setup', '--no-play'], input='y\n').exit_code == 0
    assert setup_state()['revision'] == changed['revision']


def test_changed_setup_manifest_cannot_bypass_listening_approval(tmp_path):
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--prepare-only']).exit_code == 0
    pointer = tmp_path / 'show-setup/current.json'
    data = json.loads(pointer.read_bytes())
    data['approved_at'] = 'not a real listening approval'
    pointer.write_text(json.dumps(data))
    result = runner.invoke(app, ['inspect-setup', '--json'])
    assert result.exit_code == 1
    assert 'hash' in result.output.lower()


def test_an_operator_cannot_approve_files_replaced_during_listening(tmp_path):
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--prepare-only']).exit_code == 0
    waiting = subprocess.Popen([sys.executable, '-m', 'podcast_processor', 'setup', '--no-play'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output = b''
        deadline = time.monotonic() + 10
        assert waiting.stdout is not None
        while b'recurring use?' not in output and time.monotonic() < deadline:
            if select.select([waiting.stdout], [], [], .1)[0]:
                output += os.read(waiting.stdout.fileno(), 65536)
        assert b'recurring use?' in output, output
        assert runner.invoke(app, ['setup', '--ending-silence', '2', '--prepare-only']).exit_code == 0
        changed = setup_state()
        stdout, stderr = waiting.communicate(b'y\n', timeout=10)
        assert waiting.returncode == 1, (stdout, stderr)
        assert b'changed during listening' in stdout
        assert setup_state() == changed and changed['approved_at'] is None
    finally:
        if waiting.poll() is None:
            waiting.kill()
        waiting.wait(timeout=5)


def test_interrupted_setup_keeps_the_last_complete_approved_version(tmp_path):
    originals, _ = transitions(tmp_path)
    assert runner.invoke(app, ['setup', '--transitions', str(originals), '--no-play'], input='y\n').exit_code == 0
    approved = setup_state()
    script = '''
import os
from pathlib import Path
from podcast_processor.cli import app
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current.json':
        os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    crashed = subprocess.run([sys.executable, '-c', script, 'setup', '--ending-silence', '2', '--prepare-only'],
                             capture_output=True, timeout=10)
    assert crashed.returncode == 73, crashed.stderr
    assert setup_state() == approved
    assert runner.invoke(app, ['setup', '--ending-silence', '2', '--prepare-only']).exit_code == 0
    assert setup_state()['approved_at'] is None
    for asset in approved['transitions'].values():
        assert (tmp_path / 'show-setup' / asset['path']).is_file()


@pytest.mark.parametrize('setup_status', ['missing', 'unapproved', 'damaged'])
def test_missing_or_unapproved_setup_is_partial_with_usable_publishing(tmp_path, full_services, setup_status):
    if setup_status != 'missing':
        originals, _ = transitions(tmp_path)
        options = ['--prepare-only'] if setup_status == 'unapproved' else ['--no-play']
        assert runner.invoke(app, ['setup', '--transitions', str(originals), *options], input='y\n').exit_code == 0
        if setup_status == 'damaged':
            setup = setup_state()
            (tmp_path / 'show-setup' / setup['transitions']['episode_start']['path']).write_bytes(b'damaged')
    workspace = tmp_path / 'episode'
    result = runner.invoke(app, ['process', str(recording(tmp_path)), '--workspace', str(workspace), '--solo'])
    assert result.exit_code == 1, (result.output, result.exception)
    state = inspect(workspace)
    assert state['runs'][-1]['status'] == 'partial'
    assert 'Needs setup: run podcast-process setup' in result.output
    assert {'description.md', 'titles.json', 'chapters.txt'} <= state['artifacts'].keys()
    plan = json.loads((workspace / 'current/section-plan.json').read_bytes())
    assert plan['status'] == 'needs-setup'
    assert plan['proposal'] is None
    assert all(plan['evidence'][role] is None for role in ('episode_start', 'transition_in', 'transition_out'))
    assert not any('No pair' in reason or 'below required' in reason for reason in plan['reasons'])
