"""Discovery request/response and proposal recovery across real CLI process death."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_episode_workflow import recording
from test_workspace import inspect

pytestmark = pytest.mark.usefixtures('approved_show_setup')

SCRIPT = r'''
import json, os, socket, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path.cwd() / 'tests'))
from test_boundary_discovery import discovery_services
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
mode, control = sys.argv[1:3]
del sys.argv[1:3]
control = Path(control)
patch = pytest.MonkeyPatch()
calls = discovery_services.__wrapped__(patch)
def forbidden(*args, **kwargs):
    raise AssertionError('Uncontrolled network request')
socket.socket.connect = forbidden
generate = ClaudeClient.generate
def preserved_call(self, prompt, max_tokens=4096):
    with (control / 'requests').open('a') as stream:
        stream.write(prompt.splitlines()[0] + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    if mode == 'requested' and prompt.startswith('STAGE: section-discovery'):
        os._exit(73)
    return generate(self, prompt, max_tokens)
ClaudeClient.generate = preserved_call
replace = os.replace
def interrupted(src, dst):
    if mode == 'response' and Path(dst).parent.name == 'discovery-responses':
        os._exit(73)
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_bytes())
        if (mode == 'candidates' and 'section-candidates.json' in state['evidence']
                or mode == 'proposal' and 'section-boundaries.json' in state['artifacts']):
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''


def launch(tmp_path, mode, *, resume=False):
    workspace = tmp_path / 'episode'
    args = [str(workspace)] if resume else [str(recording(tmp_path, 2100)), '--workspace', str(workspace), '--solo']
    return subprocess.run([sys.executable, '-c', SCRIPT, mode, str(tmp_path), 'process', *args],
                          capture_output=True, timeout=35, env=os.environ.copy())


@pytest.mark.parametrize('mode', ['requested', 'response', 'candidates', 'proposal'])
def test_resume_preserves_discovery_receipts_and_attempt_allowance(tmp_path, mode):
    crashed = launch(tmp_path, mode)
    assert crashed.returncode == 73, (crashed.stdout.decode(), crashed.stderr.decode())
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    resumed = launch(tmp_path, 'resume', resume=True)
    assert resumed.returncode == 0, (resumed.stdout.decode(), resumed.stderr.decode())
    after = inspect(workspace)
    plan = json.loads((workspace / 'current/section-plan.json').read_bytes())
    assert plan['status'] == 'valid'
    assert len(after['discovery_operations']) == 1
    assert after['discovery_operations'][0]['id'] == before['discovery_operations'][0]['id']
    attempts = after['discovery_operations'][0]['attempts']
    assert [a['status'] for a in attempts] == (['failed', 'validated'] if mode == 'requested' else ['validated'])
    assert attempts[0]['usage']['actual'] is None
    requests = (tmp_path / 'requests').read_text().splitlines()
    assert requests.count('STAGE: section-discovery') == (2 if mode == 'requested' else 1)
    assert all(requests.count('STAGE: ' + stage) == 1 for stage in ('body', 'titles', 'chapters'))
    assert after['transcription_operations'] == before['transcription_operations']
    for attempt in attempts:
        if attempt['status'] == 'validated':
            assert (workspace / attempt['response_path']).is_file()
