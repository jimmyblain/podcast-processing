"""Full CLI crash/concurrency tests: real processes, controlled providers and disk."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from test_episode_workflow import recording
from test_workspace import authority, inspect

SCRIPT = r'''
import json, os, socket, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_episode_workflow import primary_words, full_response
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
mode, control = sys.argv[1:3]
del sys.argv[1:3]
control = Path(control)
def record(call):
    with (control / 'calls').open('a') as stream:
        stream.write(call + '\n')
        stream.flush()
        os.fsync(stream.fileno())
def forbidden(*args, **kwargs):
    raise AssertionError('Uncontrolled network call')
socket.socket.connect = forbidden
def send(client, request, **kwargs):
    record(request.method + ' ' + request.url.path)
    if request.url.path == '/v2/upload':
        body = {'upload_url': 'https://cdn.assemblyai.com/fixture.flac'}
    elif request.url.path == '/v2/transcript' and request.method == 'POST':
        if mode == 'submission':
            os._exit(73)
        body = {'id': 'full-job', 'status': 'queued'}
    elif request.url.path == '/v2/transcript' and request.method == 'GET':
        body = {'transcripts': [{'id': 'full-job', 'audio_url': 'https://cdn.assemblyai.com/fixture.flac'}]}
    else:
        body = {'id': 'full-job', 'status': 'completed', 'words': primary_words()}
    return httpx.Response(200, json=body, request=request)
def publish(self, prompt, max_tokens=4096):
    record(prompt.splitlines()[0])
    if mode == 'lock-publishing':
        (control / 'ready').touch()
        time.sleep(30)
    return full_response(prompt)
httpx.Client.send = send
ClaudeClient.generate = publish
replace = os.replace
def interrupted(src, dst):
    if mode == 'response' and Path(dst).parent.name == 'publishing-responses':
        os._exit(73)  # Fully flushed temporary response, before rename/manifest.
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_bytes())
        ops = state['transcription_operations']
        op = ops[-1] if ops else {}
        attempts = op.get('attempts', [])
        trigger = (mode == 'inspection' and not op.get('transport')
            or mode == 'preparation' and op.get('transport')
            or mode == 'accepted' and attempts and attempts[0]['job_id']
            or mode == 'raw' and any(n.startswith('raw-') for n in state['evidence'])
            or mode == 'normalization' and any(n.startswith('normalized-') for n in state['evidence'])
            or mode == 'mapping' and 'transcript.json' in state['artifacts']
            or mode == 'body' and 'description-body.json' in state['evidence']
            or mode == 'titles' and 'titles.json' in state['artifacts']
            or mode == 'chapters' and 'chapters.json' in state['evidence']
            or mode == 'assembly' and 'description.md' in state['artifacts']
            or mode == 'planning' and 'section-plan.json' in state['artifacts'])
        if trigger:
            if mode == 'inspection':
                replace(src, dst)
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
# Interrupt an actual output write before it is complete; it must never become current.
open_path = Path.open
class PartialWrite:
    def __init__(self, stream):
        self.stream = stream
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def write(self, data):
        self.stream.write(data[:len(data) // 2])
        self.stream.flush()
        os.fsync(self.stream.fileno())
        os._exit(73)
def opened(path, *args, **kwargs):
    stream = open_path(path, *args, **kwargs)
    if mode == 'temporary' and path.name == 'titles.json' and args and args[0] == 'xb':
        return PartialWrite(stream)
    return stream
Path.open = opened
app()
'''


def launch(tmp_path, mode, *, resume=False, background=False):
    workspace = tmp_path / 'episode'
    args = [str(workspace)] if resume else [str(recording(tmp_path)), '--workspace', str(workspace), *authority(tmp_path)]
    env = {**os.environ, 'ASSEMBLYAI_API_KEY': 'fixture-primary', 'DEEPGRAM_API_KEY': 'fixture-backup',
           'ANTHROPIC_API_KEY': 'fixture-publishing'}
    command = [sys.executable, '-c', SCRIPT, mode, str(tmp_path), 'process', *args]
    if background:
        return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    return subprocess.run(command, capture_output=True, timeout=20, env=env)


@pytest.mark.parametrize('mode', ['inspection', 'preparation', 'submission', 'accepted', 'raw', 'normalization',
                                 'mapping', 'response', 'body', 'titles', 'chapters', 'assembly', 'planning', 'temporary'])
def test_full_restart_at_every_checkpoint_recovers_without_duplicate_paid_work(tmp_path, mode):
    crashed = launch(tmp_path, mode)
    assert crashed.returncode == 73, crashed.stderr.decode()
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    resumed = launch(tmp_path, 'resume', resume=True)
    assert resumed.returncode == 0, (resumed.stdout.decode(), resumed.stderr.decode())
    after = inspect(workspace)
    assert after['runs'][-1]['status'] == 'completed'
    assert after['transcription_operations'][0]['id'] == before['transcription_operations'][0]['id']
    assert after['transcription_operations'][0]['deadline_at'] == before['transcription_operations'][0]['deadline_at']
    calls = (tmp_path / 'calls').read_text().splitlines()
    assert calls.count('POST /v2/transcript') == 1
    assert all(calls.count('STAGE: ' + stage) == 1 for stage in ('body', 'titles', 'chapters'))
    assert (workspace / 'current/chapters.txt').read_text().strip() in (workspace / 'current/description.md').read_text()
    assert len(json.loads((workspace / 'current/titles.json').read_bytes())) == 15


def test_two_full_cli_processes_share_one_owner_through_publishing(tmp_path):
    first = launch(tmp_path, 'lock-publishing', background=True)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / 'ready').exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert (tmp_path / 'ready').exists()
        before = (tmp_path / 'calls').read_bytes()
        second = launch(tmp_path, 'resume', resume=True)
        assert second.returncode == 1
        assert b'Active operation' in second.stdout
        assert (tmp_path / 'calls').read_bytes() == before
    finally:
        first.kill()
        first.wait(timeout=5)
    resumed = launch(tmp_path, 'resume', resume=True)
    assert resumed.returncode == 0, resumed.stdout.decode()
    state = inspect(tmp_path / 'episode')
    assert len(state['transcription_operations'][0]['attempts']) == 1
    assert [a['status'] for a in state['publishing_operations'][0]['attempts']] == ['failed', 'validated']
    assert state['publishing_operations'][0]['attempts'][0]['usage']['actual'] is None
