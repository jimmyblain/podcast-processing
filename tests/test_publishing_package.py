"""Public publishing acceptance using controlled external publishing responses."""
import json

import pytest
from typer.testing import CliRunner

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from test_workspace import authority, inspect

runner = CliRunner()
SDK_GENERATE = ClaudeClient.generate


from publishing_responses import response_for


@pytest.fixture
def publishing(monkeypatch):
    calls = []
    def generate(self, prompt, max_tokens=4096):
        calls.append(prompt)
        return response_for(prompt)
    monkeypatch.setattr(ClaudeClient, 'generate', generate)
    return calls


def episode(tmp_path, *, duration=70, segments=None):
    path = tmp_path / 'timed.json'
    path.write_text(json.dumps({'duration': duration, 'segments': segments or [
        {'start': 0, 'end': 20, 'text': "I'm Lish Speaks. Name your feelings before an honest conversation."},
        {'start': 20.5, 'end': 44, 'text': 'Listen with care before preparing your reply.'},
        {'start': 45, 'end': duration, 'text': 'Prayer helps me find words. Practice speaking with care.'}]}))
    result = runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), *authority(tmp_path)])
    assert result.exit_code == 0, result.output
    return next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())


def generate(workspace, *args):
    return runner.invoke(app, ['generate', str(workspace), '--api-key', 'secret-test-token', *args])


def test_complete_package_is_shared_grounded_and_reused_without_media(tmp_path, publishing):
    workspace = episode(tmp_path)
    original = inspect(workspace)['artifacts']['transcript.json']
    result = generate(workspace)
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    description = (workspace / 'current/description.md').read_text()
    chapters = (workspace / 'current/chapters.txt').read_text()
    assert chapters == '00:00 Honest conversation\n00:20 Listen with care\n00:45 Prayer and practice\n'
    assert chapters.strip() in description
    assert description.index('Lish Speaks') < description.index('Name your feelings') < description.index('Which conversation') < description.index('00:00')
    titles = json.loads((workspace / 'current/titles.json').read_text())
    assert len(titles) == 15 and len({t['title'] for t in titles}) == 15
    assert all(2 <= len(t['thumbnail_text'].split()) <= 4 for t in titles)
    assert state['artifacts']['description.md']['dependencies']['chapters_version'] == state['artifacts']['chapters.txt']['id']
    assert state['artifacts']['transcript.json'] == original
    assert len(publishing) == 3
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3
    assert inspect(workspace)['artifacts'] == state['artifacts']
    assert all('secret-test-token' not in p.read_text() for p in workspace.rglob('*.json'))


def test_titles_only_fresh_and_chapter_labels_are_independent(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    assert generate(workspace, '--only', 'titles', '--fresh').exit_code == 0
    after = inspect(workspace)
    assert len(publishing) == 4
    assert after['artifacts']['titles.json']['id'] != before['artifacts']['titles.json']['id']
    for name in ('description.md', 'chapters.txt', 'transcript.json'):
        assert after['artifacts'][name] == before['artifacts'][name]
    labels = tmp_path / 'labels.json'
    labels.write_text(json.dumps(['Start with honesty', 'Hear the other person', 'Faith in practice']))
    assert generate(workspace, '--chapter-labels', str(labels)).exit_code == 0
    labeled = inspect(workspace)
    assert len(publishing) == 4
    assert '00:20 Hear the other person' in (workspace / 'current/description.md').read_text()
    assert labeled['artifacts']['description.md']['dependencies']['chapters_version'] == labeled['artifacts']['chapters.txt']['id']
    assert labeled['artifacts']['titles.json'] == after['artifacts']['titles.json']
    assert generate(workspace).exit_code == 0
    assert inspect(workspace)['artifacts'] == labeled['artifacts']
    assert len(publishing) == 4


@pytest.mark.parametrize('stage,change', [
    ('titles', lambda data: data[:14]),
    ('titles', lambda data: [{**t, 'title': 'Same title'} for t in data]),
    ('titles', lambda data: [{**t, 'title': ('A title' if i == 0 else 'a title!!!' if i == 1 else t['title'])} for i, t in enumerate(data)]),
    ('titles', lambda data: [{**t, 'title': 'x' * 101} for t in data]),
    ('titles', lambda data: [{**t, 'title': '<' + t['title']} for t in data]),
    ('titles', lambda data: [{**t, 'thumbnail_text': 'One'} for t in data]),
    ('titles', lambda data: [{**t, 'thumbnail_text': 'One two three four five'} for t in data]),
    ('titles', lambda data: [{**t, 'reasoning': ''} for t in data]),
    ('titles', lambda data: [{**t, 'visual_direction': {'subject': 'Lish', 'expression': 'Warm'}} for t in data]),
    ('body', lambda data: {**data, 'takeaways': ['One', 'Two']}),
    ('body', lambda data: {**data, 'overview': 'Someone talks about life.'}),
    ('body', lambda data: {**data, 'hook': 'x' * 5001}),
    ('body', lambda data: {**data, 'hook': 'Go to https://invented.example.com'}),
    ('body', lambda data: {**data, 'question': 'One? Two?'}),
    ('chapters', lambda data: data[:2]),
    ('chapters', lambda data: [{**c, 'start_time': 1} if i == 0 else c for i, c in enumerate(data)]),
    ('chapters', lambda data: [data[0], data[2], data[1]]),
    ('chapters', lambda data: [data[0], data[1], data[1]]),
    ('chapters', lambda data: [{**c, 'start_time': 1000} if i == 2 else c for i, c in enumerate(data)]),
    ('chapters', lambda data: [{**c, 'title': 'Title\nSubtitle'} for c in data]),
    ('chapters', lambda data: [{**c, 'title': ' '} for c in data]),
    ('chapters', lambda data: [{**c, 'title': '- Heading'} for c in data]),
    ('chapters', lambda data: [{**c, 'boundary_id': 'made-up'} for c in data]),
])
def test_invalid_required_outputs_exhaust_once_and_keep_other_work(tmp_path, monkeypatch, stage, change):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        kind = prompt.splitlines()[0].split(': ')[1]
        calls.append(kind)
        data = json.loads(response_for(prompt))
        return json.dumps(change(data) if kind == stage else data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 1
    state = inspect(workspace)
    assert state['runs'][-1]['status'] == 'partial'
    assert calls.count(stage) == 3 and len(calls) == 5
    assert generate(workspace).exit_code == 1
    assert len(calls) == 5
    assert inspect(workspace)['artifacts'] == state['artifacts']
    if stage == 'chapters':
        assert 'description-body.json' in state['evidence']
        assert 'description.md' not in state['artifacts']
        assert 'chapters.txt' not in state['artifacts']
        assert 'titles.json' in state['artifacts']
    elif stage == 'titles':
        assert 'description.md' in state['artifacts'] and 'chapters.txt' in state['artifacts']
    else:
        assert 'chapters.txt' in state['artifacts'] and 'titles.json' in state['artifacts']


def test_invalid_response_repairs_within_shared_allowance_and_accepts_category_flexibility(tmp_path, monkeypatch):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        if 'STAGE: titles' in prompt:
            data = json.loads(response_for(prompt))
            if sum('STAGE: titles' in p for p in calls) == 1:
                return 'not JSON'
            data[5]['category'] = 'topic/benefit'
            return json.dumps(data)
        return response_for(prompt)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    assert len(calls) == 4
    assert 'Validation feedback' in calls[2]
    ledger = next(op for op in inspect(workspace)['publishing_operations'] if op['stage'] == 'titles')
    assert [a['status'] for a in ledger['attempts']] == ['invalid', 'validated']


def test_chapter_retry_identifies_each_mismatched_time_without_accepting_it(tmp_path, monkeypatch):
    def publish(self, prompt, max_tokens=4096):
        data = json.loads(response_for(prompt))
        if 'STAGE: chapters' in prompt:
            feedback = prompt.split('Validation feedback:\n')[-1] if 'Validation feedback:\n' in prompt else ''
            # The provider can repair both numeric mistakes from actionable feedback.
            if not ('turn-1' in feedback and '20.5' in feedback
                    and 'turn-2' in feedback and '45.0' in feedback):
                data[1]['start_time'] = 20.4
                data[2]['start_time'] = 43.0
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    assert (workspace / 'current/chapters.txt').read_text() == (
        '00:00 Honest conversation\n00:20 Listen with care\n00:45 Prayer and practice\n')
    ledger = next(op for op in inspect(workspace)['publishing_operations'] if op['stage'] == 'chapters')
    assert [a['status'] for a in ledger['attempts']] == ['invalid', 'validated']
    assert generate(workspace).exit_code == 0


def test_edited_outputs_preserved_as_exact_bytes_and_never_used_as_facts(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    previous = inspect(workspace)
    edited = b'\xff\x00\nInvented sponsor and biography\r\n'
    (workspace / 'current/description.md').write_bytes(edited)
    assert generate(workspace).exit_code == 0
    state = inspect(workspace)
    edit = next(a for a in state['history'] if a['status'] == 'human-edited')
    assert (workspace / edit['path']).read_bytes() == edited
    assert edit['sha256'] != previous['artifacts']['description.md']['sha256']
    assert 'Preserved direct edit' in (workspace / 'current/completion-report.md').read_text()
    assert len(publishing) == 3
    assert all('Invented sponsor' not in p for p in publishing)


def test_saved_successful_response_recovers_after_artifact_write_failure(tmp_path, publishing, monkeypatch):
    from podcast_processor import workspace as storage
    original = storage.write_file
    def fail_titles(path, data):
        if path.name == 'titles.json' and 'artifacts' in path.parts:
            raise OSError('Injected artifact write failure')
        return original(path, data)
    workspace = episode(tmp_path)
    monkeypatch.setattr(storage, 'write_file', fail_titles)
    assert generate(workspace).exit_code == 1
    state = inspect(workspace)
    assert 'description.md' in state['artifacts'] and 'titles.json' not in state['artifacts']
    assert len(publishing) == 3
    monkeypatch.setattr(storage, 'write_file', original)
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3
    recovered = inspect(workspace)
    assert recovered['artifacts']['description.md'] == state['artifacts']['description.md']
    assert len(next(op for op in recovered['publishing_operations'] if op['stage'] == 'titles')['attempts']) == 1


def test_approved_links_and_promotion_only_reassemble_description(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    profile_path = tmp_path / 'show.json'
    profile = json.loads(profile_path.read_text())
    profile.update(links=['https://example.com/approved'], promotional_text='An approved recurring invitation.')
    profile_path.write_text(json.dumps(profile))
    result = runner.invoke(app, ['import', str(tmp_path / 'timed.json'), '--workspace', str(workspace),
                                '--root', str(tmp_path / 'episodes'), '--show-profile', str(profile_path)])
    assert result.exit_code == 0, result.output
    imported = inspect(workspace)
    assert 'description.md' not in imported['artifacts']
    assert imported['artifacts']['titles.json'] == before['artifacts']['titles.json']
    assert imported['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3
    assert (workspace / 'current/description.md').read_text().endswith('https://example.com/approved\n\nAn approved recurring invitation.\n')


def test_complete_description_limit_includes_supplied_extras(tmp_path, publishing):
    workspace = episode(tmp_path)
    profile = json.loads((tmp_path / 'show.json').read_text())
    profile['promotional_text'] = 'x' * 4900
    (tmp_path / 'show.json').write_text(json.dumps(profile))
    assert runner.invoke(app, ['import', str(tmp_path / 'timed.json'), '--root', str(tmp_path / 'episodes'),
                              '--show-profile', str(tmp_path / 'show.json')]).exit_code == 0
    assert generate(workspace).exit_code == 1
    state = inspect(workspace)
    assert 'description.md' not in state['artifacts']
    assert 'description-body.json' in state['evidence']
    assert '5,000' in (workspace / 'current/completion-report.md').read_text()
    assert generate(workspace).exit_code == 1
    assert len(publishing) == 3


def test_edited_chapters_cannot_leave_a_complete_description_under_old_version(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    (workspace / 'current/chapters.txt').write_text('00:00 A direct edit\n')
    state = inspect(workspace)
    assert 'chapters.txt' not in state['artifacts']
    assert 'description.md' not in state['artifacts']
    assert not (workspace / 'current/description.md').exists()
    assert generate(workspace).exit_code == 0
    assert len(publishing) == 3


def test_invalid_local_labels_fail_the_request_without_discarding_valid_package(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    labels = tmp_path / 'bad-labels.json'
    labels.write_text('["only one"]')
    result = generate(workspace, '--chapter-labels', str(labels))
    assert result.exit_code == 1
    assert inspect(workspace)['artifacts'] == before['artifacts']
    assert len(publishing) == 3


def test_title_only_keeps_previously_requested_chapter_limit(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace, '--chapters', '3').exit_code == 0
    before = inspect(workspace)
    result = generate(workspace, '--only', 'titles', '--fresh')
    assert result.exit_code == 0, result.output
    after = inspect(workspace)
    for name in ('description.md', 'chapters.txt', 'transcript.json'):
        assert after['artifacts'][name] == before['artifacts'][name]
    assert len(publishing) == 4


def test_real_sdk_retry_behavior_and_usage_are_bounded_and_persisted(tmp_path, monkeypatch):
    import httpx
    calls = []
    def send(self, request, **kwargs):
        payload = json.loads(request.content)
        prompt = payload['messages'][0]['content']
        stage = prompt.splitlines()[0].split(': ')[1]
        calls.append(stage)
        if stage == 'titles':
            return httpx.Response(429, json={'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'Controlled rate limit'}}, request=request)
        return httpx.Response(200, headers={'request-id': 'req-fixture'}, json={
            'id': 'msg-fixture', 'type': 'message', 'role': 'assistant', 'model': 'returned-model-fixture',
            'content': [{'type': 'text', 'text': response_for(prompt)}], 'stop_reason': 'end_turn',
            'usage': {'input_tokens': 321, 'output_tokens': 123}}, request=request)
    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(ClaudeClient, 'generate', SDK_GENERATE)
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 1
    state = inspect(workspace)
    assert calls == ['body', 'titles', 'titles', 'titles', 'chapters']
    assert generate(workspace).exit_code == 1
    assert len(calls) == 5
    for op in state['publishing_operations']:
        for attempt in op['attempts']:
            assert attempt['request']['sdk_max_retries'] == 0
            assert attempt['request']['model']
            assert attempt['started_at'] and attempt['finished_at']
            if op['stage'] != 'titles':
                assert attempt['returned_model'] == 'returned-model-fixture'
                assert attempt['request_id'] == 'req-fixture' and attempt['response_id'] == 'msg-fixture'
                assert attempt['usage']['actual']['input_tokens'] == 321
                assert attempt['response_hash']
    assert state['transcription_operations'] == []


@pytest.mark.parametrize('starts,duration,valid', [
    ([0, 10, 20], 30, True),
    ([0, 10, 20], 29.999, False),
    ([0, 9.999, 20], 40, False),
    ([0, 10.9, 20.1], 40, False),
    ([0, 3599.9, 3610.1], 3621, True),
])
def test_chapters_enforce_precise_and_rendered_intervals_and_hour_format(tmp_path, monkeypatch, starts, duration, valid):
    def publish(self, prompt, max_tokens=4096):
        if 'STAGE: chapters' in prompt:
            return json.dumps([{'start_time': start, 'title': label, 'boundary_id': 'anchor' if i == 0 else f'turn-{i}',
                                'reason': 'The next supported discussion topic begins here.'}
                               for i, (start, label) in enumerate(zip(starts, ['Opening', 'Listening', 'Practice']))])
        return response_for(prompt)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path, duration=duration, segments=[
        {'start': start, 'end': start + 1, 'text': text} for start, text in zip(starts, ['Speak with care.', 'Listen.', 'Practice.'])])
    assert generate(workspace).exit_code == (0 if valid else 1)
    state = inspect(workspace)
    assert ('chapters.txt' in state['artifacts']) == valid
    if valid and duration > 3600:
        assert (workspace / 'current/chapters.txt').read_text() == '00:00 Opening\n59:59 Listening\n1:00:10 Practice\n'


def test_crash_after_receipt_before_manifest_reuses_response_in_new_process(tmp_path, monkeypatch):
    import subprocess
    import sys
    workspace = episode(tmp_path)
    script = '''
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path('tests').resolve()))
from publishing_responses import response_for
from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
ClaudeClient.generate = lambda self, prompt, max_tokens=4096: response_for(prompt)
replace = os.replace
def crash(source, destination):
    if Path(destination).name == 'current':
        data = json.loads((Path(source).resolve() / 'state.json').read_text())
        operations = data.get('publishing_operations', [])
        if operations and operations[0]['attempts'] and operations[0]['attempts'][0]['status'] == 'responded':
            os._exit(73)
    return replace(source, destination)
os.replace = crash
app()
'''
    result = subprocess.run([sys.executable, '-c', script, 'generate', str(workspace), '--api-key', 'fake'],
                            capture_output=True, timeout=15)
    assert result.returncode == 73
    interrupted = inspect(workspace)
    attempt = interrupted['publishing_operations'][0]['attempts'][0]
    assert attempt['status'] == 'requested'
    assert (workspace / attempt['response_path']).exists()
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt.splitlines()[0])
        return response_for(prompt)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    assert generate(workspace).exit_code == 0
    assert calls == ['STAGE: titles', 'STAGE: chapters']
    assert len(inspect(workspace)['publishing_operations'][0]['attempts']) == 1


def test_uncertainty_uses_other_supported_boundaries_and_separate_conflict_report(tmp_path, monkeypatch):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        data = json.loads(response_for(prompt))
        if 'STAGE: body' in prompt:
            data['notes'] = ['A spoken schedule conflicts with current supplied context; the unverified plug was omitted.']
        if 'STAGE: chapters' in prompt:
            data[1].update(start_time=30, boundary_id='turn-2')
            data[2].update(start_time=50, boundary_id='turn-3')
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path, duration=70, segments=[
        {'start': 0, 'end': 10, 'text': 'Name your feelings before a conversation.'},
        {'text': 'I [unclear] endorse an unsafe treatment.'},
        {'start': 30, 'end': 45, 'text': 'Listen before preparing your reply.'},
        {'start': 50, 'end': 70, 'text': 'Prayer helps me find my words.'}])
    assert generate(workspace).exit_code == 0
    assert all('unsafe treatment' not in p for p in calls)
    assert all('Anonymous speaker' in p and 'neutral' in p for p in calls)
    report = (workspace / 'current/completion-report.md').read_text()
    copy = (workspace / 'current/description.md').read_text()
    assert 'conflicts with current supplied context' in report and 'unclear wording' in report.lower()
    assert 'conflicts with current supplied context' not in copy and 'review' not in copy.lower()


@pytest.mark.parametrize('field,expected_calls', [('voice', ['body', 'titles']), ('angle', ['body', 'titles'])])
def test_changed_editorial_inputs_only_invalidate_actual_consumers(tmp_path, publishing, field, expected_calls):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    filename = 'show.json' if field == 'voice' else 'episode.json'
    path = tmp_path / filename
    data = json.loads(path.read_text())
    data[field] = 'Focus on listening with care.'
    path.write_text(json.dumps(data))
    option = '--show-profile' if field == 'voice' else '--metadata'
    assert runner.invoke(app, ['import', str(tmp_path / 'timed.json'), '--root', str(tmp_path / 'episodes'), option, str(path)]).exit_code == 0
    imported = inspect(workspace)
    assert 'titles.json' not in imported['artifacts'] and 'description.md' not in imported['artifacts']
    assert imported['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert generate(workspace).exit_code == 0
    assert [p.splitlines()[0].split(': ')[1] for p in publishing[3:]] == expected_calls


def test_chapter_titles_can_begin_with_a_topic_number(tmp_path, monkeypatch):
    def publish(self, prompt, max_tokens=4096):
        data = json.loads(response_for(prompt))
        if 'STAGE: chapters' in prompt:
            data[1]['title'] = '5 Ways to Listen'
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    assert '00:20 5 Ways to Listen' in (workspace / 'current/chapters.txt').read_text()


def test_description_only_fresh_reuses_shared_chapters(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    assert generate(workspace, '--only', 'description', '--fresh').exit_code == 0
    after = inspect(workspace)
    assert len(publishing) == 4
    assert after['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert after['artifacts']['titles.json'] == before['artifacts']['titles.json']


def test_single_speaker_turn_can_use_supported_sentence_boundaries(tmp_path, monkeypatch):
    workspace = episode(tmp_path)
    state = inspect(workspace)
    saved = json.loads((workspace / 'current/transcript.json').read_bytes())
    words = [
        {'id': 'w0', 'word': 'Honesty.', 'start': 0, 'end': 5},
        {'id': 'w1', 'word': 'Listening.', 'start': 20, 'end': 30},
        {'id': 'w2', 'word': 'Prayer.', 'start': 45, 'end': 60}]
    saved.update(revision='single-turn', speakers=[{'id': 'A', 'participant': 'Lish Speaks'}],
        segments=[{'id': 't0', 'speaker': 'A', 'start': 0, 'end': 70, 'timing_usable': True,
                   'text': 'Honesty. Listening. Prayer.', 'word_ids': ['w0', 'w1', 'w2']}],
        words=[{**w, 'speaker': 'A', 'turn_id': 't0', 'timing_usable': True} for w in words])
    path = tmp_path / 'single-turn.json'
    path.write_text(json.dumps(saved))
    assert runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), '--workspace', str(workspace)]).exit_code == 0
    def publish(self, prompt, max_tokens=4096):
        data = json.loads(response_for(prompt))
        if 'STAGE: chapters' in prompt:
            data[1].update(start_time=20, boundary_id='word-w1')
            data[2].update(start_time=45, boundary_id='word-w2')
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    assert generate(workspace).exit_code == 0
    assert '00:20 Listen with care' in (workspace / 'current/chapters.txt').read_text()


def test_partial_response_receipt_recovers_without_blocking_independent_outputs(tmp_path, publishing, monkeypatch):
    from podcast_processor import publishing as provider
    original = provider.write_file
    failed = False
    def partial_write(path, data):
        nonlocal failed
        if not failed:
            failed = True
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data[:12])
            raise OSError('Interrupted response receipt write')
        return original(path, data)
    workspace = episode(tmp_path)
    monkeypatch.setattr(provider, 'write_file', partial_write)
    assert generate(workspace).exit_code == 1
    first = inspect(workspace)
    assert 'titles.json' in first['artifacts'] and 'chapters.txt' in first['artifacts']
    assert first['runs'][-1]['status'] == 'partial'
    result = generate(workspace)
    assert result.exit_code == 0, result.output
    assert len(publishing) == 4
    final = inspect(workspace)
    assert final['artifacts']['titles.json'] == first['artifacts']['titles.json']
    assert final['artifacts']['chapters.txt'] == first['artifacts']['chapters.txt']
    assert [a['status'] for a in final['publishing_operations'][0]['attempts']] == ['failed', 'validated']


@pytest.mark.parametrize('local', [False, True])
def test_duplicate_chapter_labels_are_unavailable_or_rejected_locally(tmp_path, publishing, monkeypatch, local):
    workspace = episode(tmp_path)
    if local:
        assert generate(workspace).exit_code == 0
        before = inspect(workspace)
        labels = tmp_path / 'duplicates.json'
        labels.write_text('["Same chapter", "same chapter!", "Different"]')
        result = generate(workspace, '--chapter-labels', str(labels))
        assert result.exit_code == 1
        assert inspect(workspace)['artifacts'] == before['artifacts']
    else:
        def publish(self, prompt, max_tokens=4096):
            data = json.loads(response_for(prompt))
            if 'STAGE: chapters' in prompt:
                data[0]['title'], data[1]['title'] = 'Same chapter', 'same chapter!'
            return json.dumps(data)
        monkeypatch.setattr(ClaudeClient, 'generate', publish)
        assert generate(workspace).exit_code == 1
        state = inspect(workspace)
        assert 'chapters.txt' not in state['artifacts'] and 'description.md' not in state['artifacts']
        assert len(next(op for op in state['publishing_operations'] if op['stage'] == 'chapters')['attempts']) == 3
