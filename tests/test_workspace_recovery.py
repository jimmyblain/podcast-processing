import json
import subprocess
import sys
import time

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from publishing_responses import compatible_response
from test_workspace import FIXTURE, authority, imported, inspect, runner


def test_interrupted_import_recovers_one_workspace_without_truncated_outputs(tmp_path):
    script = '''
import os, sys
from pathlib import Path
from podcast_processor.cli import app
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current' and (Path(src).resolve() / 'transcript.json').exists():
        os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    result = subprocess.run([sys.executable, '-c', script, 'import', str(FIXTURE), '--root', str(tmp_path / 'episodes')],
                            capture_output=True, timeout=15)
    assert result.returncode == 73
    workspace = next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())
    assert not (workspace / 'current/transcript.json').exists()
    assert inspect(workspace)['runs'][-1]['status'] == 'interrupted'
    recovered = imported(tmp_path)
    assert recovered == workspace
    assert len([p for p in (tmp_path / 'episodes').iterdir() if p.is_dir()]) == 1
    assert json.loads((workspace / 'current/transcript.json').read_text())['segments'][0]['text'].startswith('Well, well,')


def test_active_writer_is_reported_and_killed_owner_releases_workspace(tmp_path):
    workspace = imported(tmp_path, *authority(tmp_path))
    marker = tmp_path / 'ready'
    script = '''
import sys, time
from pathlib import Path
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
marker = Path(sys.argv.pop(1))
def paused(self, prompt, max_tokens=4096):
    marker.write_text('ready')
    time.sleep(30)
    return 'unused'
ClaudeClient.generate = paused
app()
'''
    process = subprocess.Popen([sys.executable, '-c', script, str(marker), 'generate', str(workspace), '--api-key', 'fake'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        contender = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake'])
        assert contender.exit_code == 1
        assert 'Active operation' in contender.output
        assert 'generate publishing' in contender.output
    finally:
        process.kill()
        process.wait(timeout=5)
    assert inspect(workspace)['runs'][-1]['status'] == 'interrupted'
    assert (workspace / 'current/transcript.json').exists()


def test_response_checkpoint_survives_crash_before_output_commit(tmp_path, monkeypatch):
    workspace = imported(tmp_path, *authority(tmp_path))
    script = '''
import os
from pathlib import Path
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
import sys
sys.path.insert(0, str(Path('tests').resolve()))
from publishing_responses import compatible_response
ClaudeClient.generate = lambda self, prompt, max_tokens=4096: compatible_response(prompt)
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current' and (Path(src).resolve() / 'description.md').exists():
        os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    result = subprocess.run([sys.executable, '-c', script, 'generate', str(workspace), '--api-key', 'fake'],
                            capture_output=True, timeout=15)
    assert result.returncode == 73
    before = inspect(workspace)
    assert 'description.md' not in before['artifacts']
    assert 'description-body.json' in before['evidence']
    calls = []

    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        return compatible_response(prompt)

    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake'])
    assert result.exit_code == 0, result.output
    assert len(calls) == 0
    assert 'Lish Speaks' in (workspace / 'current/description.md').read_text()
    assert inspect(workspace)['artifacts']['transcript.json']['id'] == before['artifacts']['transcript.json']['id']


def test_hash_mismatch_is_unavailable_and_direct_edits_survive_in_history(tmp_path):
    workspace = imported(tmp_path)
    before = inspect(workspace)
    (workspace / 'current/transcript.json').write_text('{truncated')
    state = inspect(workspace)
    assert 'transcript.json' not in state['artifacts']
    assert not (workspace / 'current/transcript.json').exists()
    assert state['runs'][-1]['status'] == 'partial'
    edits = [artifact for artifact in state['history'] if artifact['status'] == 'human-edited']
    assert len(edits) == 1
    assert (workspace / edits[0]['path']).read_bytes() == b'{truncated'
    assert (workspace / before['artifacts']['transcript.json']['path']).read_bytes().startswith(b'{')
    imported(tmp_path)
    assert (workspace / 'current/transcript.json').exists()


def test_crash_after_last_output_can_finalize_without_service_calls(tmp_path):
    workspace = imported(tmp_path, *authority(tmp_path))
    script = '''
import json, os
from pathlib import Path
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
import sys
sys.path.insert(0, str(Path('tests').resolve()))
from publishing_responses import compatible_response
def publish(self, prompt, max_tokens=4096):
    return compatible_response(prompt)
ClaudeClient.generate = publish
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_text())
        if state['runs'][-1]['operation'] == 'generate' and state['runs'][-1]['status'] == 'completed':
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    result = subprocess.run([sys.executable, '-c', script, 'generate', str(workspace), '--api-key', 'fake'],
                            capture_output=True, timeout=15)
    assert result.returncode == 73
    interrupted = inspect(workspace)
    assert interrupted['runs'][-1]['status'] == 'interrupted'
    assert 'chapters.txt' in interrupted['artifacts']
    result = runner.invoke(app, ['generate', str(workspace)])
    assert result.exit_code == 0, result.output
    recovered = inspect(workspace)
    assert recovered['runs'][-1]['status'] == 'completed'
    assert recovered['artifacts'] == interrupted['artifacts']


def test_identical_import_repairs_missing_companions_without_replacing_transcript(tmp_path, monkeypatch):
    workspace = imported(tmp_path, *authority(tmp_path))

    def publish(self, prompt, max_tokens=4096):
        return compatible_response(prompt)

    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    before = inspect(workspace)
    (workspace / 'current/transcript.txt').unlink()
    (workspace / 'current/import-original.json').unlink()
    imported(tmp_path)
    after = inspect(workspace)
    assert (workspace / 'current/transcript.txt').exists()
    assert (workspace / 'current/import-original.json').read_bytes() == FIXTURE.read_bytes()
    for name in ('description.md', 'titles.json', 'chapters.txt'):
        assert after['artifacts'][name]['id'] == before['artifacts'][name]['id']
    assert after['artifacts']['transcript.json']['id'] == before['artifacts']['transcript.json']['id']
    assert after['runs'][-1]['status'] == 'completed'
