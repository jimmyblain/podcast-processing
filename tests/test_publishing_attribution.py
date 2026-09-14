"""Attribution enforcement at the public publishing operation and service boundary."""
import json

import pytest

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from publishing_responses import compatible_response
from test_workspace import authority, inspect, runner
from test_managed_transcription import service
from test_participant_corrections import correct, episode_from_turns, transcript


def anonymous_episode(tmp_path, guest='Erica Campbell'):
    options = authority(tmp_path)
    (tmp_path / 'episode.json').write_text(json.dumps({'solo': False, 'participants': [
        {'name': 'Lish Speaks', 'role': 'host'}, {'name': guest, 'role': 'guest'}]}))
    path = tmp_path / 'timed.json'
    path.write_text(json.dumps({'duration': 70, 'segments': [
        {'start': 0, 'end': 20, 'text': 'I lost my business. It was hard to start over.'},
        {'start': 20.5, 'end': 44, 'text': 'Listening matters.'},
        {'start': 45, 'end': 70, 'text': 'I learned to ask for help.'}]}))
    result = runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), *options])
    assert result.exit_code == 0, result.output
    return next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())


def test_unresolved_story_ownership_requires_repair_while_other_stages_complete(tmp_path, monkeypatch):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        stage = prompt.splitlines()[0]
        calls.append(prompt)
        data = json.loads(compatible_response(prompt))
        if stage == 'STAGE: body':
            data['overview'] = ('This episode features Lish Speaks and Erica Campbell. '
                                'Explore starting over and asking for help.')
            if 'Repair' not in prompt:
                data['hook'] = 'Erica Campbell reveals how she lost her business.'
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = anonymous_episode(tmp_path)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake'])
    assert result.exit_code == 0, result.output
    body_calls = [p for p in calls if p.startswith('STAGE: body')]
    assert len(body_calls) == 2 and 'attribution' in body_calls[-1].lower()
    description = (workspace / 'current/description.md').read_text()
    assert 'reveals how she lost' not in description
    assert 'Lish Speaks and Erica Campbell' in description and 'asking for help' in description
    before = inspect(workspace)
    assert [a['status'] for a in before['publishing_operations'][0]['attempts']] == ['invalid', 'validated']
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    assert len(calls) == 4


@pytest.mark.parametrize('stage,field,copy', [
    ('body', 'hook', 'Erica Campbell reveals how she lost her business.'),
    ('body', 'hook', "Erika's secret to starting over"),
    ('body', 'hook', 'The guest shares a painful business failure.'),
    ('body', 'hook', 'She lost everything before starting over.'),
    ('body', 'hook', 'We lost everything before starting over.'),
    ('body', 'hook', 'Erica Campbell: "I lost my business."'),
    ('body', 'overview', 'This episode features Lish Speaks and Erica Campbell. Her business collapsed.'),
    ('titles', 'title', "Campbell's painful loss"),
    ('titles', 'thumbnail_text', 'Erica Lost Everything'),
    ('titles', 'reasoning', 'The guest describes a devastating failure.'),
    ('titles', 'subject', 'Erica Campbell grieving a lost business'),
    ('chapters', 'title', "Erica's business failure"),
])
def test_unsupported_attribution_exhausts_only_its_stage_and_cannot_reset_on_resume(
        tmp_path, monkeypatch, stage, field, copy):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        kind = prompt.splitlines()[0].split(': ')[1]
        calls.append(kind)
        data = json.loads(compatible_response(prompt))
        if kind == stage:
            target = data if stage == 'body' else data[0]['visual_direction'] if field == 'subject' else data[0]
            target[field] = copy
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = anonymous_episode(tmp_path)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 1
    saved = inspect(workspace)
    assert calls.count(stage) == 3 and len(calls) == 5
    assert all('Attribution:' in a['error'] for op in saved['publishing_operations'] if op['stage'] == stage
               for a in op['attempts'])
    if stage != 'titles':
        assert 'titles.json' in saved['artifacts']
    if stage != 'chapters':
        assert 'chapters.txt' in saved['artifacts']
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 1
    assert len(calls) == 5


def test_named_quote_requires_that_participants_own_clear_sentence_and_reconsiders_corrections(
        tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('A', "I'm Lish Speaks. Welcome, Erica Campbell! I lost my business."),
        ('B', 'Thank you for having me. I learned to ask for help.'),
        ('A', 'Listening matters.'),
    ])
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        data = json.loads(compatible_response(prompt))
        if prompt.startswith('STAGE: body'):
            data['hook'] = ('Erica Campbell: "I learned to ask for help."' if 'Repair' in prompt
                            else 'Erica Campbell: "I lost my business."')
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 1  # Short source: no chapters.
    saved = inspect(workspace)
    body = saved['evidence']['description-body.json']
    assert json.loads((workspace / body['path']).read_bytes())['hook'] == 'Erica Campbell: "I learned to ask for help."'
    assert len([p for p in calls if p.startswith('STAGE: body')]) == 2
    before = transcript(workspace)
    guest = next(s['id'] for s in before['speakers'] if s['participant'] == 'Erica Campbell')
    corrected = correct(workspace, [{'op': 'relabel', 'speaker': guest, 'participant': None}])
    assert corrected['segments'] == before['segments'] and corrected['words'] == before['words']
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 1
    after = inspect(workspace)
    assert 'description-body.json' not in after['evidence']
    assert 'titles.json' in after['artifacts']
    assert len(service) == 3


def test_punctuated_participant_names_cannot_bypass_unsupported_story_validation(tmp_path, monkeypatch):
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        data = json.loads(compatible_response(prompt))
        if prompt.startswith('STAGE: body'):
            data['hook'] = "Mary-Jane O'Neill lost everything to bankruptcy."
        return json.dumps(data)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    workspace = anonymous_episode(tmp_path, guest="Mary-Jane O'Neill")
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake'])
    assert result.exit_code == 1, result.output
    assert 'description-body.json' not in inspect(workspace)['evidence']
    assert len([p for p in calls if p.startswith('STAGE: body')]) == 3
