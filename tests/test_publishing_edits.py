"""Operator edits through public inspection, resume and replacement operations."""
import hashlib
import json
import subprocess
import sys
import pytest

from podcast_processor.cli import app
from test_publishing_package import episode, generate, publishing, runner
from test_workspace import inspect


def test_description_edit_stays_current_through_inspection_and_resume(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    path = workspace / 'current/description.md'
    original = path.read_bytes()
    edited = b'An operator-written opening.\r\n\r\n' + original
    path.write_bytes(edited)

    state = inspect(workspace)
    assert path.read_bytes() == edited
    artifact = state['artifacts']['description.md']
    assert artifact['status'] == 'human-edited'
    assert artifact['sha256'] == hashlib.sha256(edited).hexdigest()
    assert (workspace / artifact['path']).read_bytes() == edited
    assert (workspace / before['artifacts']['description.md']['path']).read_bytes() == original
    assert state['publishing_issues'] == {}

    assert generate(workspace).exit_code == 0
    assert path.read_bytes() == edited
    runner.invoke(app, ['process', str(workspace)])
    resumed = inspect(workspace)
    assert path.read_bytes() == edited
    assert resumed['artifacts']['description.md'] == artifact
    assert resumed['artifacts']['transcript.json'] == before['artifacts']['transcript.json']
    assert resumed['episode_metadata'] == before['episode_metadata']
    assert len(publishing) == 3


@pytest.mark.parametrize('edit_description', [False, True])
def test_chapter_conflict_preserves_both_copies_without_choosing_a_winner(tmp_path, publishing, edit_description):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    chapters = b'00:00 Operator opening\r\n00:20 Listen with care\r\n00:45 Prayer and practice\r\n'
    description = (workspace / 'current/description.md').read_bytes()
    if edit_description:
        description = description.replace(b'Honest conversation', b'Different operator opening')
        (workspace / 'current/description.md').write_bytes(description)
    (workspace / 'current/chapters.txt').write_bytes(chapters)
    state = inspect(workspace)
    assert (workspace / 'current/chapters.txt').read_bytes() == chapters
    assert (workspace / 'current/description.md').read_bytes() == description
    for name in ('chapters.txt', 'description.md'):
        assert 'conflict' in ' '.join(state['publishing_issues'][name]).lower()
    assert generate(workspace).exit_code == 1
    assert (workspace / 'current/chapters.txt').read_bytes() == chapters
    assert (workspace / 'current/description.md').read_bytes() == description
    assert len(publishing) == 3

    # Matching manual labels settle the conflict without manufacturing source evidence.
    description = description.replace(b'Different operator opening' if edit_description else b'Honest conversation',
                                      b'Operator opening')
    (workspace / 'current/description.md').write_bytes(description)
    assert inspect(workspace)['publishing_issues'] == {}
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3


@pytest.mark.parametrize('edited, issue', [
    (b'\xff\x00\r\nUnchanged operator bytes', 'UTF-8'),
    (b'x' * 5001, '5,000'),
], ids=['invalid-utf8', 'too-long'])
def test_invalid_description_is_preserved_and_reported_without_paid_repair(tmp_path, publishing, edited, issue):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/description.md'
    path.write_bytes(edited)
    state = inspect(workspace)
    assert path.read_bytes() == edited
    assert issue in ' '.join(state['publishing_issues']['description.md'])
    assert state['runs'][-1]['status'] == 'partial'
    assert issue in (workspace / 'current/completion-report.md').read_text()
    result = generate(workspace)
    assert result.exit_code == 1, result.output
    assert 'description' not in result.output.split('Ready: ')[1].splitlines()[0]
    assert path.read_bytes() == edited
    assert len(publishing) == 3


def test_changed_episode_evidence_keeps_edits_stale_until_explicit_replacement(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    edits = {}
    for name in ('description.md', 'titles.json', 'chapters.txt'):
        path = workspace / 'current' / name
        edits[name] = path.read_bytes() + b'\r\n'
        path.write_bytes(edits[name])
    edited_state = inspect(workspace)
    transcript_path = tmp_path / 'timed.json'
    transcript = json.loads(transcript_path.read_text())
    transcript['segments'][0]['text'] += ' A different opening topic.'
    transcript_path.write_text(json.dumps(transcript))
    result = runner.invoke(app, ['import', str(transcript_path), '--workspace', str(workspace),
                                '--root', str(tmp_path / 'episodes')])
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    for name, data in edits.items():
        assert (workspace / 'current' / name).read_bytes() == data
        assert 'stale' in ' '.join(state['publishing_issues'][name]).lower()
    assert generate(workspace).exit_code == 1
    assert len(publishing) == 3
    for name, data in edits.items():
        assert (workspace / 'current' / name).read_bytes() == data

    assert generate(workspace, '--fresh').exit_code == 0
    replaced = inspect(workspace)
    assert replaced['publishing_issues'] == {}
    assert len(publishing) == 6
    for name, data in edits.items():
        artifact = edited_state['artifacts'][name]
        assert (workspace / artifact['path']).read_bytes() == data
        assert artifact in replaced['history']
        assert replaced['artifacts'][name]['status'] == 'completed'
    chapters = (workspace / 'current/chapters.txt').read_text()
    assert chapters.strip() in (workspace / 'current/description.md').read_text()


@pytest.mark.parametrize('name, edited, issue', [
    ('titles.json', b'{unfinished', 'JSON'),
    ('titles.json', b'[]\r\n', 'fifteen'),
    ('chapters.txt', b'00:00 Only one chapter\r\n', '3\u201310'),
    ('chapters.txt', b'00:00 One\n00:05 Two\n00:45 Three\n', 'ten seconds'),
    ('chapters.txt', b'00:00 One\n00:20 Two\n00:65 Three\n', 'Invalid chapter timestamp'),
], ids=['invalid-json', 'missing-titles', 'missing-chapters', 'short-chapter', 'bad-timestamp'])
def test_invalid_title_and_chapter_edits_are_reported_without_rewriting(tmp_path, publishing, name, edited, issue):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    (workspace / 'current' / name).write_bytes(edited)
    state = inspect(workspace)
    assert issue in ' '.join(state['publishing_issues'][name])
    assert generate(workspace).exit_code == 1
    assert (workspace / 'current' / name).read_bytes() == edited
    assert len(publishing) == 3


def test_matching_invalid_chapter_edits_do_not_leave_description_ready(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    edits = {}
    for name in ('description.md', 'chapters.txt'):
        path = workspace / 'current' / name
        edits[name] = path.read_bytes().replace(b'00:20', b'00:05')
        path.write_bytes(edits[name])
    state = inspect(workspace)
    for name in edits:
        assert 'ten seconds' in ' '.join(state['publishing_issues'][name])
    result = generate(workspace)
    assert result.exit_code == 1, result.output
    assert 'description' not in result.output.split('Ready: ')[1].splitlines()[0]
    for name, data in edits.items():
        assert (workspace / 'current' / name).read_bytes() == data
    assert len(publishing) == 3


def test_edited_artifact_corruption_is_reported_without_erasing_delivered_copy(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/titles.json'
    edited = path.read_bytes() + b'\r\n'
    path.write_bytes(edited)
    state = inspect(workspace)
    (workspace / state['artifacts']['titles.json']['path']).write_bytes(b'corrupt history')
    state = inspect(workspace)
    assert path.read_bytes() == edited
    assert 'verification' in ' '.join(state['publishing_issues']['titles.json'])
    assert generate(workspace).exit_code == 1
    assert path.read_bytes() == edited
    assert len(publishing) == 3


@pytest.mark.parametrize('name', ['description.md', 'chapters.txt'])
def test_corrupt_structured_chapter_evidence_cannot_validate_a_preserved_edit(tmp_path, publishing, name):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current' / name
    edited = path.read_bytes() + b'\r\n'
    path.write_bytes(edited)
    state = inspect(workspace)
    (workspace / state['evidence']['chapters.json']['path']).write_bytes(b'corrupt evidence')
    state = inspect(workspace)
    assert 'verification' in ' '.join(state['publishing_issues'][name])
    assert path.read_bytes() == edited
    assert state['runs'][-1]['status'] == 'partial'
    assert len(publishing) == 3


def test_explicit_replacement_is_selective_and_edits_never_enter_future_prompts(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    description = b'Operator-only invented biography.\r\n\r\n' + (workspace / 'current/description.md').read_bytes()
    (workspace / 'current/description.md').write_bytes(description)
    title_path = workspace / 'current/titles.json'
    concepts = json.loads(title_path.read_bytes())
    concepts[0]['title'] = 'Operator-only personal claim'
    titles = json.dumps(concepts, indent=4).encode() + b'\r\n'
    title_path.write_bytes(titles)
    edited = inspect(workspace)
    assert edited['publishing_issues'] == {}
    assert generate(workspace, '--only', 'titles', '--fresh').exit_code == 0
    assert len(publishing) == 4
    assert (workspace / 'current/description.md').read_bytes() == description
    assert generate(workspace, '--only', 'description', '--fresh').exit_code == 0
    assert len(publishing) == 5
    after = inspect(workspace)
    assert after['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert after['artifacts']['transcript.json'] == before['artifacts']['transcript.json']
    assert all('Operator-only' not in prompt for prompt in publishing[3:])
    for name, data in [('description.md', description), ('titles.json', titles)]:
        assert (workspace / edited['artifacts'][name]['path']).read_bytes() == data
        assert after['artifacts'][name]['status'] == 'completed'


def test_explicit_labels_can_restore_saved_labels_while_preserving_edited_description(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    description = b'Operator opening.\r\n\r\n' + (workspace / 'current/description.md').read_bytes()
    (workspace / 'current/description.md').write_bytes(description)
    chapter_path = workspace / 'current/chapters.txt'
    original = chapter_path.read_bytes()
    edited = original.replace(b'Honest conversation', b'Conflicting operator title')
    chapter_path.write_bytes(edited)
    before = inspect(workspace)
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps(['Honest conversation', 'Listen with care', 'Prayer and practice']))
    result = generate(workspace, '--chapter-labels', str(labels))
    assert result.exit_code == 0, result.output
    assert chapter_path.read_bytes() == original
    assert (workspace / 'current/description.md').read_bytes() == description
    assert inspect(workspace)['publishing_issues'] == {}
    assert (workspace / before['artifacts']['chapters.txt']['path']).read_bytes() == edited
    assert len(publishing) == 3


@pytest.mark.parametrize('after_switch', [False, True], ids=['before-commit', 'after-commit'])
def test_inspection_crash_recovers_exact_edit_and_missing_current_copy(tmp_path, publishing, after_switch):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/titles.json'
    edited = path.read_bytes() + b'\r\n'
    path.write_bytes(edited)
    script = '''
import json, os, sys
from pathlib import Path
from podcast_processor.cli import app
after_switch = sys.argv.pop(1) == 'True'
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_bytes())
        if state['artifacts']['titles.json']['status'] == 'human-edited':
            if after_switch:
                replace(src, dst)
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    result = subprocess.run([sys.executable, '-c', script, str(after_switch), 'inspect', str(workspace), '--json'],
                            capture_output=True, timeout=15)
    assert result.returncode == 73, result.stderr
    state = inspect(workspace)
    assert path.read_bytes() == edited
    artifact = state['artifacts']['titles.json']
    assert artifact['status'] == 'human-edited'
    assert len([a for a in state['history'] if a['status'] == 'human-edited']) == 1
    path.unlink()
    assert generate(workspace).exit_code == 0
    assert path.read_bytes() == edited
    assert inspect(workspace)['artifacts']['titles.json'] == artifact
    assert len(publishing) == 3


def test_explicit_regeneration_crash_recovers_receipt_and_retains_prior_edit(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/titles.json'
    edited = path.read_bytes() + b'\r\n'
    path.write_bytes(edited)
    before = inspect(workspace)
    script = '''
import json, os, sys
from pathlib import Path
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
sys.path.insert(0, str(Path('tests').resolve()))
from publishing_responses import response_for
ClaudeClient.generate = lambda self, prompt, max_tokens=4096: response_for(prompt)
replace = os.replace
def interrupted(src, dst):
    if Path(dst).name == 'current':
        state = json.loads((Path(src).resolve() / 'state.json').read_bytes())
        titles = state['artifacts'].get('titles.json')
        if titles and titles['status'] == 'completed':
            os._exit(73)
    return replace(src, dst)
os.replace = interrupted
app()
'''
    result = subprocess.run([sys.executable, '-c', script, 'generate', str(workspace),
                             '--only', 'titles', '--fresh', '--api-key', 'test-key'],
                            capture_output=True, timeout=15)
    assert result.returncode == 73, result.stderr
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3  # The child received the only new provider response.
    after = inspect(workspace)
    assert sum(len(op['attempts']) for op in after['publishing_operations']) == 4
    artifact = before['artifacts']['titles.json']
    assert (workspace / artifact['path']).read_bytes() == edited
    assert artifact in after['history']
    assert after['artifacts']['titles.json']['status'] == 'completed'
