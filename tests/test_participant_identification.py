"""Fresh participant evidence through public operations, without pre-mapped voices."""
import json

import pytest

from podcast_processor.cli import app
from test_managed_transcription import service
from test_participant_corrections import episode_from_turns, transcript
from test_workspace import inspect, runner
from test_episode_workflow import full_services, recording


def test_host_role_and_recognition_variation_map_episode_local_voices(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('B', 'I nearly gave up on that project.'),
        ('A', "Welcome back to my podcast, I'll Just Let Myself In. "
              'The person I have here today inspires me. Without further ado, Erika Campbell.'),
        ('B', 'Welcome. Hi, sweetheart.'),
        ('A', 'Welcome.'),
        ('B', "Thank you so much for having me. I'm excited to be here."),
        ('A', 'Erica Campbell, tell us more about starting again.'),
        ('B', 'I learned to ask for help.'),
    ])
    saved = transcript(workspace)
    names = {s['id']: s['participant'] for s in saved['speakers']}
    assert [names[t['speaker']] for t in saved['segments']] == [
        'Erica Campbell', 'Lish Speaks', 'Erica Campbell', 'Lish Speaks',
        'Erica Campbell', 'Lish Speaks', 'Erica Campbell']
    guest = saved['speakers'][0]
    assert any(e['recognized_name'] == 'Erika Campbell' and e['participant'] == 'Erica Campbell'
               for e in guest['associations'])
    assert all(s['identity_evidence'] and s['identity_uncertainty'] for s in saved['speakers'])
    assert 'Erika Campbell.' in saved['segments'][1]['text']
    before = inspect(workspace)
    assert runner.invoke(app, ['map-participants', str(workspace)]).exit_code == 0
    assert inspect(workspace)['artifacts']['transcript.json'] == before['artifacts']['transcript.json']
    assert transcript(workspace) == saved
    assert len(service) == 3


@pytest.mark.usefixtures('approved_show_setup')
def test_new_interview_process_maps_automatic_recognition_before_publishing(tmp_path, full_services, monkeypatch):
    import test_episode_workflow
    words = []
    for speaker, start, text in [
        ('B', 0, 'I learned to ask for help.'),
        ('A', 6, "Welcome to my podcast, I'll Just Let Myself In. Without further ado, Ashley Muhammad."),
        ('B', 14, 'Hi. Thank you so much for having me.'),
        ('A', 20.5, 'What helped you start again?'),
        ('B', 45, 'I learned to keep practicing.'),
    ]:
        for i, word in enumerate(text.split()):
            words.append({'text': word, 'speaker': speaker, 'start': (start + .3 * i) * 1000,
                          'end': (start + .3 * i + .2) * 1000})
    monkeypatch.setattr(test_episode_workflow, 'primary_words', lambda: words)
    workspace = tmp_path / 'episode'
    source = recording(tmp_path)
    result = runner.invoke(app, ['process', str(source), '--workspace', str(workspace), '--guest', 'Ashlee Mohammed'])
    assert result.exit_code == 0, result.output
    saved = transcript(workspace)
    assert [s['participant'] for s in saved['speakers']] == ['Ashlee Mohammed', 'Lish Speaks']
    assert 'Ashlee Mohammed' in (workspace / 'current/description.md').read_text()
    assert all(c != 'STAGE: discovery' for c in full_services)  # Short source is duration-infeasible.
    before = inspect(workspace)
    calls = list(full_services)
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    assert inspect(workspace)['artifacts'] == before['artifacts']
    assert full_services == calls


@pytest.mark.parametrize('turns,expected', [
    ([('A', 'Erica Campbell is here.'), ('B', 'Yes, thank you.')], [None, None]),
    ([('A', "I'm your host, Lish Speaks. Erica Campbell changed my life."),
      ('B', 'I am glad.')], ['Lish Speaks', None]),
    ([('A', "I'm Lish Speaks. Welcome, Erica Campbell."),
      ('B', 'Thank you for having me. My name is Lish Speaks.')], ['Lish Speaks', None]),
    ([('A', "I'm Lish Speaks. My name is Erica Campbell. Welcome, Erica Campbell."),
      ('B', 'Thank you for having me.')], [None, None]),
    ([('A', "I'm Lish Speaks. Welcome, Erica Campbell."),
      ('B', 'Hello.'), ('C', 'Thank you for having me.')], ['Lish Speaks', None, None]),
    ([('A', "I'm Lish Speaks. I'm Erica Campbell's biggest fan."),
      ('B', "I'm Erica Campbell's friend.")], ['Lish Speaks', None]),
])
def test_uncertainty_stays_with_unsupported_or_conflicting_voices(tmp_path, service, monkeypatch, turns, expected):
    workspace = episode_from_turns(tmp_path, monkeypatch, turns)
    saved = transcript(workspace)
    assert [s['participant'] for s in saved['speakers']] == expected
    assert all(s['identity_uncertainty'] for s in saved['speakers'])
    assert len(service) == 3


def test_guest_mapping_loses_support_when_its_introducing_host_becomes_uncertain(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('B', "I'm Lish Speaks. Welcome, Erica Campbell."),
        ('C', 'Thank you for having me.'),
        ('A', "I'm Lish Speaks. Welcome, Erica Campbell."),
        ('B', 'Thank you for having me.'),
    ])
    saved = transcript(workspace)
    assert [s['participant'] for s in saved['speakers']] == [None, None, 'Lish Speaks']
    assert saved['speakers'][1]['identity_status'] == 'uncertain'
    assert saved['speakers'][1]['identity_evidence']


def test_short_guest_names_require_exact_support_in_the_dialogue(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('A', "I'm Lish Speaks. Welcome, Jon."), ('B', 'Thank you for having me.')], guests=('John',))
    assert [s['participant'] for s in transcript(workspace)['speakers']] == ['Lish Speaks', None]
