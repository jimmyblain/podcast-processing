"""Mapping and optional corrections through the public CLI, with saved evidence."""
import json

import httpx
import pytest

from podcast_processor.cli import app
from test_managed_transcription import PRIMARY, managed, replace_responses, service
from test_workspace import authority, inspect, make_media, runner


def transcript(workspace):
    return json.loads((workspace / 'current/transcript.json').read_bytes())


def correction_file(workspace, changes):
    path = workspace.parent / 'corrections.json'
    path.unlink(missing_ok=True)
    result = runner.invoke(app, ['corrections-template', str(workspace), '--output', str(path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(path.read_text())
    payload['changes'] = changes
    path.write_text(json.dumps(payload))
    return path


def correct(workspace, changes):
    path = correction_file(workspace, changes)
    result = runner.invoke(app, ['correct', str(workspace), str(path)])
    assert result.exit_code == 0, (result.output, result.exception)
    return transcript(workspace)


def episode_from_turns(tmp_path, monkeypatch, turns):
    options = authority(tmp_path)
    (tmp_path / 'episode.json').write_text(json.dumps({'solo': False, 'participants': [
        {'name': 'Lish Speaks', 'role': 'host'}, {'name': 'Erica Campbell', 'role': 'guest'}]}))
    tokens = [(speaker, word) for speaker, text in turns for word in text.split()]
    words = [{'text': word, 'speaker': speaker, 'start': 10 + i * 900 / len(tokens),
              'end': 10 + (i + 0.8) * 900 / len(tokens)} for i, (speaker, word) in enumerate(tokens)]
    payload = {**PRIMARY, 'words': words}
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json=payload, request=req)
                      if req.method == 'GET' else res)
    workspace = tmp_path / 'episode'
    source = make_media(tmp_path / 'recording.wav')
    result = runner.invoke(app, ['transcribe', str(source), '--workspace', str(workspace), *options])
    assert result.exit_code == 0, (result.output, result.exception)
    return workspace


def test_unknown_mapping_completes_without_prompt_and_can_be_reread(tmp_path, service):
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, result.output
    before = inspect(workspace)
    result = runner.invoke(app, ['map-participants', str(workspace)])
    assert result.exit_code == 0, result.output
    assert all(s['participant'] is None for s in transcript(workspace)['speakers'])
    report = (workspace / 'current/completion-report.md').read_text()
    assert 'Optional correction' in report and '00:00' in report
    assert 'anonymous' in report and 'transcript.txt' in report
    assert 'relabel' in report
    assert inspect(workspace)['artifacts']['transcript.json'] == before['artifacts']['transcript.json']
    assert len(service) == 3


def test_supported_introductions_map_repeated_voices_without_taking_name_mentions(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('B', "I'm Lish Speaks. Welcome, Erica Campbell!"),
        ('A', 'Thank you for having me.'),
        ('B', 'Erica Campbell, um, um, I mean, tell us about singing.'),
        ('A', "Well, I started singing with my sisters."),
        ('B', 'Yes, ' + 'we can start again, ' * 30),
    ])
    result = transcript(workspace)
    names = {s['id']: s['participant'] for s in result['speakers']}
    assert [names[t['speaker']] for t in result['segments']] == [
        'Lish Speaks', 'Erica Campbell', 'Lish Speaks', 'Erica Campbell', 'Lish Speaks']
    assert 'um, um, I mean,' in result['segments'][2]['text']
    readable = (workspace / 'current/transcript.txt').read_text()
    assert '[00:00] Lish Speaks:' in readable and 'Erica Campbell:' in readable
    assert max(map(len, readable.splitlines())) <= 100
    assert len(result['segments']) == 5
    assert all(s['identity_evidence'] for s in result['speakers'])
    assert any(a['stage_version'].startswith('managed-words') for a in inspect(workspace)['evidence'].values())
    assert len(service) == 3


def test_relabel_preserves_words_times_original_bytes_and_rereads_without_asr(tmp_path, service):
    workspace, _ = managed(tmp_path)
    before = transcript(workspace)
    state = inspect(workspace)
    original = (workspace / 'current/transcript.json').read_bytes()
    changed = correct(workspace, [{'op': 'relabel', 'speaker': before['speakers'][0]['id'], 'participant': 'Lish Speaks'}])
    assert changed['words'] == before['words'] and changed['segments'] == before['segments']
    assert changed['speakers'][0]['participant'] == 'Lish Speaks'
    assert changed['speakers'][0]['identity_status'] == 'corrected'
    assert changed['revision'] != before['revision']
    assert changed['lineage'][-1]['base_revision'] == before['revision']
    assert changed['lineage'][-1]['base_sha256'] == state['artifacts']['transcript.json']['sha256']
    assert (workspace / state['artifacts']['transcript.json']['path']).read_bytes() == original
    assert any(a['name'].startswith('corrections-') for a in inspect(workspace)['evidence'].values())
    assert managed(tmp_path)[1].exit_code == 0
    assert transcript(workspace) == changed
    assert len(service) == 3
    stale = runner.invoke(app, ['correct', str(workspace), str(tmp_path / 'corrections.json')])
    assert stale.exit_code == 1 and 'base' in stale.output.lower()
    assert transcript(workspace) == changed


def test_merge_duplicate_voices_preserves_turn_and_word_references(tmp_path, service):
    workspace, _ = managed(tmp_path)
    before = transcript(workspace)
    source, target = [s['id'] for s in before['speakers']]
    after = correct(workspace, [{'op': 'merge', 'speaker': source, 'into': target}])
    assert [s['id'] for s in after['speakers']] == [target]
    assert all(t['speaker'] == target for t in after['segments'])
    assert all(w['speaker'] == target for w in after['words'])
    assert [t['id'] for t in after['segments']] == [t['id'] for t in before['segments']]
    assert [w['id'] for w in after['words']] == [w['id'] for w in before['words']]
    assert len(service) == 3


def test_separate_selected_turns_keeps_other_voice_assignments_and_all_words(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [('B', "I'm Lish Speaks."), ('A', 'Yes.'), ('B', 'A different voice.')])
    before = transcript(workspace)
    after = correct(workspace, [{'op': 'separate', 'turn_ids': [before['segments'][2]['id']]}])
    new_speaker = after['segments'][2]['speaker']
    assert new_speaker not in {s['id'] for s in before['speakers']}
    assert after['segments'][:2] == before['segments'][:2]
    assert next(s for s in after['speakers'] if s['id'] == new_speaker)['participant'] is None
    assert [w['word'] for w in after['words']] == [w['word'] for w in before['words']]
    assert all(w['speaker'] == new_speaker for w in after['words'] if w['turn_id'] == before['segments'][2]['id'])
    assert len(service) == 3


def test_passage_correction_keeps_surrounding_evidence_but_invalidates_replaced_alignment(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [('A', 'Um, I sing with friends.')])
    before = transcript(workspace)
    after = correct(workspace, [{'op': 'replace', 'turn_id': before['segments'][0]['id'],
        'first_word': before['words'][4]['id'], 'last_word': before['words'][4]['id'], 'text': 'my sisters.'}])
    assert after['segments'][0]['text'] == 'Um, I sing with my sisters.'
    assert after['words'][:4] == before['words'][:4]
    assert [w['word'] for w in after['words'][4:]] == ['my', 'sisters.']
    assert all(w['start'] is None and w['end'] is None and not w['timing_usable'] for w in after['words'][4:])
    assert not after['segments'][0]['timing_usable']
    assert after['segments'][0]['start'] == before['segments'][0]['start']
    assert after['segments'][0]['end'] == before['segments'][0]['end']
    assert 'alignment' in (workspace / 'current/completion-report.md').read_text().lower()
    assert len(service) == 3


def test_split_at_supported_word_start_preserves_text_order_and_word_times(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [('A', 'Well, yes. I agree.')])
    before = transcript(workspace)
    after = correct(workspace, [{'op': 'split', 'turn_id': before['segments'][0]['id'], 'before_word': before['words'][2]['id']}])
    assert [t['text'] for t in after['segments']] == ['Well, yes.', 'I agree.']
    assert after['segments'][1]['start'] == before['words'][2]['start']
    assert after['segments'][0]['end'] == before['words'][1]['end']
    assert [w['id'] for w in after['words']] == [w['id'] for w in before['words']]
    assert [(w['start'], w['end']) for w in after['words']] == [(w['start'], w['end']) for w in before['words']]
    assert all(w['turn_id'] == after['segments'][1]['id'] for w in after['words'][2:])
    assert len(service) == 3


def test_source_checked_word_timing_updates_containing_turn_and_keeps_overlap(tmp_path, service):
    workspace, _ = managed(tmp_path)
    before = transcript(workspace)
    after = correct(workspace, [{'op': 'retime', 'word_id': before['words'][1]['id'],
        'start': 0.2, 'end': 0.6, 'evidence': 'Operator listened to this source interval.'}])
    assert after['words'][1]['timing_usable']
    assert after['segments'][1]['start'] == 0.2 and after['segments'][1]['end'] == 0.6
    assert {k: v for k, v in after['segments'][0].items() if k != 'overlaps'} == {
        k: v for k, v in before['segments'][0].items() if k != 'overlaps'}
    assert after['segments'][1]['start'] < after['segments'][0]['end']
    assert after['segments'][1]['overlaps'] == [after['segments'][0]['id']]
    assert [w['word'] for w in after['words']] == [w['word'] for w in before['words']]
    invalid_path = correction_file(workspace, [{'op': 'retime', 'word_id': after['words'][1]['id'],
        'start': 0.2, 'end': 1.1, 'evidence': 'Outside the recording.'}])
    result = runner.invoke(app, ['correct', str(workspace), str(invalid_path)])
    assert result.exit_code == 1 and 'source' in result.output.lower()
    assert transcript(workspace) == after
    assert len(service) == 3


def publishing_service(monkeypatch):
    from podcast_processor.llm import ClaudeClient
    calls = []
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        if 'thumbnail_text' in prompt:
            return '[{"title":"One Honest Conversation","thumbnail_text":"Start Here"}]'
        if 'start_time' in prompt:
            return '[{"start_time":0,"title":"The conversation"}]'
        return 'An honest conversation about starting again.'
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    return calls


def test_timing_correction_supersedes_chapters_and_reuses_actual_text_consumers(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace, _ = managed(tmp_path)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    before = inspect(workspace)
    word = transcript(workspace)['words'][0]
    correct(workspace, [{'op': 'retime', 'word_id': word['id'], 'start': 0.05, 'end': 0.3, 'evidence': 'Source listening.'}])
    after = inspect(workspace)
    assert after['artifacts']['description.md'] == before['artifacts']['description.md']
    assert after['artifacts']['titles.json'] == before['artifacts']['titles.json']
    assert 'chapters.txt' not in after['artifacts'] and not (workspace / 'current/chapters.txt').exists()
    assert len(calls) == 3 and len(service) == 3
    assert 'not regenerated' in (workspace / 'current/completion-report.md').read_text()
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    assert inspect(workspace)['artifacts']['description.md'] == before['artifacts']['description.md']


def test_unclear_important_wording_is_explicit_and_excluded_from_publishing(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('B', "I'm Lish Speaks."), ('A', 'I [inaudible] support that dangerous treatment.'),
        ('B', 'Um, um, listening matters.')])
    saved = transcript(workspace)
    assert '[inaudible]' in saved['segments'][1]['text']
    assert not saved['segments'][1]['quotation_usable']
    assert '[inaudible]' in (workspace / 'current/transcript.txt').read_text()
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    assert all('dangerous treatment' not in prompt for prompt in calls)
    assert all('Um, um, listening matters.' in prompt for prompt in calls)
    assert 'unclear wording' in (workspace / 'current/completion-report.md').read_text().lower()


def test_fresh_transcription_scopes_every_reference_to_new_evidence(tmp_path, service):
    workspace, _ = managed(tmp_path)
    before = transcript(workspace)
    stale = correction_file(workspace, [{'op': 'relabel', 'speaker': before['speakers'][0]['id'], 'participant': 'Lish Speaks'}])
    assert managed(tmp_path, '--fresh')[1].exit_code == 0
    after = transcript(workspace)
    for key in ('speakers', 'segments', 'words'):
        assert not {x['id'] for x in before[key]} & {x['id'] for x in after[key]}
    assert runner.invoke(app, ['correct', str(workspace), str(stale)]).exit_code == 1
    assert len(service) == 6


def test_corrected_intro_reconsiders_automatic_identity_and_invalidates_attribution(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace = episode_from_turns(tmp_path, monkeypatch, [('B', "I'm Lish Speaks."), ('A', 'Welcome.'), ('B', 'Thank you.')])
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    before = transcript(workspace)
    after = correct(workspace, [{'op': 'replace', 'turn_id': before['segments'][0]['id'],
        'first_word': before['words'][1]['id'], 'last_word': before['words'][2]['id'], 'text': 'Erica Campbell.'}])
    speaker = after['segments'][0]['speaker']
    assert next(s for s in after['speakers'] if s['id'] == speaker)['participant'] == 'Erica Campbell'
    assert 'Erica Campbell: Thank you.' in (workspace / 'current/transcript.txt').read_text()
    assert all(name not in inspect(workspace)['artifacts'] for name in ('description.md', 'titles.json', 'chapters.txt'))
    assert len(calls) == 3 and len(service) == 3


@pytest.mark.parametrize('turns,expected', [
    ([('A', 'Erica Campbell is here.'), ('B', 'Yes, thank you.')], [None, None]),
    ([('A', "I'm Lish Speaks."), ('B', 'Hello.'), ('A', "I'm Erica Campbell.")], [None, None]),
    ([('A', 'My name is Erica Campbell.'), ('B', "It's your girl, Lish Speaks.")], ['Erica Campbell', 'Lish Speaks']),
])
def test_only_supported_introductions_assign_confirmed_identities(tmp_path, service, monkeypatch, turns, expected):
    workspace = episode_from_turns(tmp_path, monkeypatch, turns)
    assert [s['participant'] for s in transcript(workspace)['speakers']] == expected
    assert inspect(workspace)['runs'][-1]['status'] == 'completed'


@pytest.mark.parametrize('change', [
    {'op': 'relabel', 'speaker': 'missing', 'participant': 'Lish Speaks'},
    {'op': 'separate', 'turn_ids': ['missing']},
    {'op': 'merge', 'speaker': 'missing', 'into': 'missing'},
    {'op': 'replace', 'turn_id': 'missing', 'first_word': 'missing', 'last_word': 'missing', 'text': 'No.'},
    {'op': 'split', 'turn_id': 'missing', 'before_word': 'missing'},
    {'op': 'retime', 'word_id': 'missing', 'start': 0, 'end': 0.1, 'evidence': 'Checked.'},
])
def test_invalid_references_leave_all_current_artifacts_unchanged(tmp_path, service, change):
    workspace, _ = managed(tmp_path)
    before = inspect(workspace)
    path = correction_file(workspace, [change])
    result = runner.invoke(app, ['correct', str(workspace), str(path)])
    assert result.exit_code == 1 and ('reference' in result.output or 'existing' in result.output)
    assert inspect(workspace)['artifacts'] == before['artifacts']
    assert len(service) == 3


def test_attribution_change_supersedes_publishing_and_preserves_direct_copy_edit(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace, _ = managed(tmp_path)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    edit = b'An operator edited publishing copy; this is not a source fact.'
    (workspace / 'current/description.md').write_bytes(edit)
    before = transcript(workspace)
    correct(workspace, [{'op': 'relabel', 'speaker': before['speakers'][0]['id'], 'participant': 'Lish Speaks'}])
    state = inspect(workspace)
    assert all(n not in state['artifacts'] for n in ('description.md', 'titles.json', 'chapters.txt'))
    saved_edit = next(a for a in state['history'] if a['status'] == 'human-edited')
    assert (workspace / saved_edit['path']).read_bytes() == edit
    assert transcript(workspace)['segments'] == before['segments']
    assert state['episode_metadata']['participants'] == [{'name': 'Lish Speaks', 'role': 'host', 'biography': None, 'links': []}]
    assert len(calls) == 3 and len(service) == 3


def test_named_guest_intro_allows_brief_greeting_exchange_before_acknowledgment(tmp_path, service, monkeypatch):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('A', "It's your girl, Lish Speaks. I'm sitting with Erica Campbell."),
        ('B', 'Hi.'), ('A', 'Hello.'), ('B', 'Thank you for having me.'), ('A', 'Welcome.')])
    assert [s['participant'] for s in transcript(workspace)['speakers']] == ['Lish Speaks', 'Erica Campbell']


def test_readable_recovery_keeps_corrected_transcript_and_identity(tmp_path, service):
    workspace, _ = managed(tmp_path)
    before = transcript(workspace)
    corrected = correct(workspace, [{'op': 'relabel', 'speaker': before['speakers'][0]['id'], 'participant': 'Lish Speaks'}])
    artifact = inspect(workspace)['artifacts']['transcript.json']
    (workspace / 'current/transcript.txt').unlink()
    assert managed(tmp_path)[1].exit_code == 0
    assert transcript(workspace) == corrected
    assert inspect(workspace)['artifacts']['transcript.json'] == artifact
    assert 'Lish Speaks:' in (workspace / 'current/transcript.txt').read_text()
    assert len(service) == 3


@pytest.mark.parametrize('field', ['source_revision', 'transcript_revision', 'transcript_sha256'])
def test_each_incompatible_base_is_rejected_before_any_artifact_changes(tmp_path, service, field):
    workspace, _ = managed(tmp_path)
    before = inspect(workspace)
    path = correction_file(workspace, [])
    payload = json.loads(path.read_text())
    payload[field] = 'different-base'
    path.write_text(json.dumps(payload))
    result = runner.invoke(app, ['correct', str(workspace), str(path)])
    assert result.exit_code == 1 and 'Incompatible correction base' in result.output
    assert inspect(workspace) == before


def test_interrupted_correction_never_exposes_mixed_versions_and_retry_is_local(tmp_path, service, monkeypatch):
    import os
    workspace, _ = managed(tmp_path)
    before = inspect(workspace)
    saved = transcript(workspace)
    path = correction_file(workspace, [{'op': 'relabel', 'speaker': saved['speakers'][0]['id'], 'participant': 'Lish Speaks'}])
    replace = os.replace
    def fail_current(source, destination):
        if str(destination).endswith('/current'):
            raise OSError('Injected snapshot switch failure.')
        return replace(source, destination)
    monkeypatch.setattr(os, 'replace', fail_current)
    assert runner.invoke(app, ['correct', str(workspace), str(path)]).exit_code == 1
    assert inspect(workspace) == before
    assert transcript(workspace) == saved
    monkeypatch.setattr(os, 'replace', replace)
    assert runner.invoke(app, ['correct', str(workspace), str(path)]).exit_code == 0
    assert transcript(workspace)['speakers'][0]['participant'] == 'Lish Speaks'
    assert len(service) == 3


def test_changed_actual_asr_hint_uses_a_new_request_fingerprint(tmp_path, service, monkeypatch):
    import copy
    from podcast_processor.managed_providers import BASELINES
    workspace, _ = managed(tmp_path)
    before = inspect(workspace)
    configured = copy.deepcopy(BASELINES['assemblyai'])
    configured['settings']['keyterms_prompt'] = ['Lish Speaks']
    monkeypatch.setitem(BASELINES, 'assemblyai', configured)
    assert managed(tmp_path)[1].exit_code == 0
    after = inspect(workspace)
    assert len(after['transcription_operations']) == 2
    assert after['transcription_operations'][1]['dependencies']['requests'] != before['transcription_operations'][0]['dependencies']['requests']
    assert json.loads(service[4].content)['keyterms_prompt'] == ['Lish Speaks']
    assert len(service) == 6


@pytest.mark.parametrize('marker', ['[unclear]', '[unclear: not. ]'])
def test_unclear_sentence_does_not_suppress_a_continuous_solo_turn(tmp_path, service, monkeypatch, marker):
    calls = publishing_service(monkeypatch)
    workspace = episode_from_turns(tmp_path, monkeypatch, [('A',
        f"I'm Lish Speaks. Today we discuss boundaries. I {marker} endorse that treatment. Listening matters.")])
    saved = transcript(workspace)
    assert len(saved['segments']) == 1
    assert saved['speakers'][0]['participant'] == 'Lish Speaks'
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    assert all('Today we discuss boundaries.' in p and 'Listening matters.' in p for p in calls)
    assert all('endorse that treatment' not in p for p in calls)


def test_timing_correction_reconsiders_guest_introduction_evidence(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('A', "I'm Lish Speaks. Welcome, Erica Campbell!"), ('B', 'Thank you for having me.')])
    before = transcript(workspace)
    assert before['speakers'][1]['participant'] == 'Erica Campbell'
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    guest_word = next(w for w in before['words'] if w['turn_id'] == before['segments'][1]['id'])
    after = correct(workspace, [{'op': 'retime', 'word_id': guest_word['id'], 'start': 0, 'end': 0.1,
                                'evidence': 'The response overlaps the introduction; association is uncertain.'}])
    assert after['speakers'][1]['participant'] is None
    assert 'titles.json' not in inspect(workspace)['artifacts']
    assert len(calls) == 3 and len(service) == 3


def test_edit_inside_excluded_sentence_reuses_unchanged_publishing_text(tmp_path, service, monkeypatch):
    calls = publishing_service(monkeypatch)
    workspace = episode_from_turns(tmp_path, monkeypatch, [('A',
        "I'm Lish Speaks. I [unclear] endorse that treatment. Listening matters.")])
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake']).exit_code == 0
    state = inspect(workspace)
    before = transcript(workspace)
    word = next(w for w in before['words'] if w['word'] == 'treatment.')
    correct(workspace, [{'op': 'replace', 'turn_id': word['turn_id'], 'first_word': word['id'],
                          'last_word': word['id'], 'text': 'approach.'}])
    after = inspect(workspace)
    for name in ('description.md', 'titles.json'):
        assert after['artifacts'][name] == state['artifacts'][name]
    assert len(calls) == 3 and len(service) == 3


@pytest.mark.parametrize('response,expected', [
    ('Hello. Thank you for having me. I [unclear] agree.', 'Erica Campbell'),
    ('I [unclear] agree. Thank you for having me.', None),
])
def test_guest_acknowledgment_uses_clear_opening_before_later_uncertainty(tmp_path, service, monkeypatch, response, expected):
    workspace = episode_from_turns(tmp_path, monkeypatch, [
        ('A', "I'm Lish Speaks. Welcome, Erica Campbell!"), ('B', response)])
    assert transcript(workspace)['speakers'][1]['participant'] == expected
