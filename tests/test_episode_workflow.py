"""Integrated episode acceptance through the CLI with real isolated persistence."""
import json
import wave

import httpx
import pytest

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from publishing_responses import compatible_response
from test_workspace import authority, inspect, runner


def primary_words():
    words = []
    for start, sentence in [(0, "I'm Lish Speaks. Name your feelings."),
                            (20.5, 'Listen with care before replying.'),
                            (45, 'Prayer helps me find words.')]:
        for index, word in enumerate(sentence.split()):
            words.append({'text': word, 'start': (start + index * .5) * 1000,
                          'end': (start + index * .5 + .4) * 1000, 'speaker': 'A'})
    return words


def full_response(prompt):
    if 'STAGE: chapters' in prompt:
        context = json.loads(prompt.split('Evidence and authoritative inputs:\n')[1].split('\nRepair')[0])
        chosen = [next(t for t in context['turns'] if t['start_time'] == start) for start in (20.5, 45)]
        return json.dumps([{'start_time': 0, 'title': 'Honest conversation', 'boundary_id': 'anchor', 'reason': 'Format anchor'},
            *[{'start_time': t['start_time'], 'title': title, 'boundary_id': t['boundary_id'], 'reason': 'Fixture topic change'}
              for t, title in zip(chosen, ['Listen with care', 'Prayer and practice'])]])
    return compatible_response(prompt)


@pytest.fixture
def full_services(monkeypatch):
    calls = []
    def send(client, request, **kwargs):
        calls.append(request.method + ' ' + request.url.path)
        if request.url.path == '/v2/upload':
            body = {'upload_url': 'https://cdn.assemblyai.com/fixture.flac'}
        elif request.method == 'POST' and request.url.path == '/v2/transcript':
            body = {'id': 'full-job', 'status': 'queued'}
        elif request.url.path == '/v2/transcript/full-job':
            body = {'id': 'full-job', 'status': 'completed', 'words': primary_words()}
        else:
            raise AssertionError(str(request.url))
        return httpx.Response(200, json=body, request=request)
    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt.splitlines()[0])
        return full_response(prompt)
    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    monkeypatch.setenv('ASSEMBLYAI_API_KEY', 'fixture-primary')
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'fixture-backup')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-publishing')
    return calls


def recording(tmp_path, duration=70, value=0):
    source = tmp_path / 'recording.wav'
    with wave.open(str(source), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(value.to_bytes(2, 'little') * (8000 * duration))
    return source


def process(tmp_path, *options):
    workspace = tmp_path / 'episode'
    args = [str(workspace)] if (workspace / 'current').exists() else [
        str(recording(tmp_path)), '--workspace', str(workspace), *authority(tmp_path)]
    return runner.invoke(app, ['process', *args, *options])


def test_full_workflow_completes_and_unchanged_resume_costs_nothing(tmp_path, full_services):
    result = process(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    assert before['runs'][-1]['operation'] == 'process'
    assert set(before['artifacts']) >= {'transcript.json', 'transcript.txt', 'description.md',
                                       'titles.json', 'chapters.txt', 'section-plan.json'}
    assert len(json.loads((workspace / 'current/titles.json').read_bytes())) == 15
    assert (workspace / 'current/chapters.txt').read_text().strip() in (workspace / 'current/description.md').read_text()
    report = (workspace / 'current/completion-report.md').read_text()
    assert 'Section planning: unavailable' in report
    assert 'Transcription usage' in report and 'Publishing usage' in report
    assert 'actual unknown' in report and 'Fresh' in report
    calls = list(full_services)
    (tmp_path / 'recording.wav').unlink()
    assert process(tmp_path).exit_code == 0
    after = inspect(workspace)
    assert after['artifacts'] == before['artifacts']
    assert after['transcription_operations'] == before['transcription_operations']
    assert full_services == calls
    assert 'Reused' in (workspace / 'current/completion-report.md').read_text()


@pytest.mark.parametrize('field,value,paid', [
    ('promotional_text', 'Listen again next week.', 0),
    ('links', ['https://example.com/approved'], 0),
    ('voice', 'Warm, candid and practical.', 2),
    ('audience', 'Listeners practicing honest conversations.', 2),
])
def test_full_profile_changes_only_regenerate_consumers(tmp_path, full_services, field, value, paid):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    profile = tmp_path / 'show.json'
    data = json.loads(profile.read_text())
    data[field] = value
    profile.write_text(json.dumps(data))
    count = len(full_services)
    result = process(tmp_path, '--show-profile', str(profile))
    assert result.exit_code == 0, result.output
    after = inspect(workspace)
    assert len(full_services) - count == paid
    for name in ('transcript.json', 'transcript.txt', 'chapters.txt', 'section-plan.json'):
        assert after['artifacts'][name] == before['artifacts'][name]
    assert after['transcription_operations'] == before['transcription_operations']


def test_imported_full_workflow_never_transcribes_and_keeps_legacy_bytes(tmp_path, full_services):
    from test_publishing_package import episode
    workspace = episode(tmp_path)
    original = (tmp_path / 'timed.json').read_bytes()
    result = runner.invoke(app, ['process', str(workspace)])
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    assert state['transcription_operations'] == []
    assert 'Imported-with-limitations' in result.output
    assert (tmp_path / 'timed.json').read_bytes() == original
    assert all(call.startswith('STAGE:') for call in full_services)


@pytest.mark.parametrize('participants', [['--solo'], ['--guest', 'Erica Campbell']])
def test_required_participants_use_approved_defaults_without_context(tmp_path, full_services, participants):
    source = recording(tmp_path)
    workspace = tmp_path / 'episode'
    result = runner.invoke(app, ['process', str(source), '--workspace', str(workspace), *participants])
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    assert 'People ready to take a chance on themselves' in state['show_profile']['audience']
    assert state['show_profile']['links'] == []
    assert state['episode_metadata']['angle'] is None
    assert len(state['episode_metadata']['participants']) == (1 if '--solo' in participants else 2)


def test_partial_chapters_keep_body_and_resume_with_selected_fresh(tmp_path, full_services, monkeypatch):
    original = ClaudeClient.generate
    def fail_chapters(self, prompt, max_tokens=4096):
        if 'STAGE: chapters' in prompt:
            full_services.append('invalid chapters')
            return '[]'
        return original(self, prompt, max_tokens)
    monkeypatch.setattr(ClaudeClient, 'generate', fail_chapters)
    result = process(tmp_path)
    assert result.exit_code == 1
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    assert before['runs'][-1]['status'] == 'partial'
    assert 'description.md' not in before['artifacts']
    body = before['evidence']['description-body.json']
    assert 'titles.json' in before['artifacts'] and 'section-plan.json' in before['artifacts']
    monkeypatch.setattr(ClaudeClient, 'generate', original)
    count = len(full_services)
    assert process(tmp_path).exit_code == 1
    assert len(full_services) == count
    assert process(tmp_path, '--only', 'chapters', '--fresh').exit_code == 0
    after = inspect(workspace)
    assert len(full_services) == count + 1
    assert after['evidence']['description-body.json'] == body
    assert after['transcription_operations'] == before['transcription_operations']
    assert after['artifacts']['titles.json'] == before['artifacts']['titles.json']


def test_full_preserves_direct_edit_exactly_before_regeneration(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    edited = b'Operator copy\r\nwith exact whitespace.  \n'
    (workspace / 'current/description.md').write_bytes(edited)
    count = len(full_services)
    result = process(tmp_path)
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    versions = [a for a in state['history'] if a['status'] == 'human-edited']
    assert len(versions) == 1
    assert (workspace / versions[0]['path']).read_bytes() == edited
    assert 'Preserved direct edit' in result.output
    assert len(full_services) == count


def test_invalid_label_input_never_reports_full_success(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    labels = tmp_path / 'labels.json'
    labels.write_text('["too few"]')
    result = process(tmp_path, '--chapter-labels', str(labels))
    assert result.exit_code == 1
    assert inspect(tmp_path / 'episode')['runs'][-1]['status'] == 'partial'


def test_failed_new_planning_input_cannot_expose_previous_valid_plan(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    old = inspect(workspace)['artifacts']['section-plan.json']
    evidence = tmp_path / 'broken-plan.json'
    evidence.write_text('{broken')
    result = process(tmp_path, '--evidence', str(evidence))
    assert result.exit_code == 1
    after = inspect(workspace)
    assert 'section-plan.json' not in after['artifacts']
    assert old in after['history']
    assert 'description.md' in after['artifacts']


def test_full_planning_valid_reuse_and_transition_only_change(tmp_path, full_services, monkeypatch):
    from test_section_planning import episode
    monkeypatch.setattr(ClaudeClient, 'generate', lambda self, prompt, max_tokens=4096: compatible_response(prompt))
    workspace, evidence = episode(tmp_path)
    # Complete mapping once, then pin supplied boundary evidence to that revision.
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    before = inspect(workspace)
    evidence['transcript_sha256'] = before['artifacts']['transcript.json']['sha256']
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps(evidence))
    result = runner.invoke(app, ['process', str(workspace), '--evidence', str(path)])
    assert result.exit_code == 0, result.output
    valid = inspect(workspace)
    proposal = json.loads((workspace / 'current/section-boundaries.json').read_bytes())
    assert [part['finished_duration'] for part in proposal['sections']] == ['616.5', '711.5', '811.5']
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    assert inspect(workspace)['artifacts'] == valid['artifacts']
    evidence['transition_in']['duration'] = '6'
    path.write_text(json.dumps(evidence))
    assert runner.invoke(app, ['process', str(workspace), '--evidence', str(path)]).exit_code == 0
    after = inspect(workspace)
    assert after['artifacts']['section-boundaries.json']['id'] != valid['artifacts']['section-boundaries.json']['id']
    for name in ('transcript.json', 'titles.json', 'description.md', 'chapters.txt'):
        assert after['artifacts'][name] == valid['artifacts'][name]
    assert after['publishing_operations'] == valid['publishing_operations']


def test_fresh_full_keeps_ledgers_and_normalization_only_reuses_raw(tmp_path, full_services, monkeypatch):
    from podcast_processor import normalization
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    assert process(tmp_path, '--fresh').exit_code == 0
    fresh = inspect(workspace)
    assert len(fresh['transcription_operations']) == 2
    assert fresh['transcription_operations'][0] == before['transcription_operations'][0]
    assert len(fresh['publishing_operations']) == 6
    assert all(artifact in fresh['history'] for artifact in before['artifacts'].values())
    count = len(full_services)
    monkeypatch.setattr(normalization, 'NORMALIZATION_VERSION', 'fixture-normalization-next')
    assert process(tmp_path).exit_code == 0
    changed = inspect(workspace)
    assert changed['artifacts']['transcript.json']['id'] != fresh['artifacts']['transcript.json']['id']
    assert len(changed['transcription_operations']) == 2
    assert not any('POST' in call for call in full_services[count:])


def test_actual_asr_hints_invalidate_transcription_request(tmp_path, full_services, monkeypatch):
    from copy import deepcopy
    from podcast_processor.managed_providers import BASELINES
    assert process(tmp_path).exit_code == 0
    before = inspect(tmp_path / 'episode')
    request = deepcopy(BASELINES['assemblyai'])
    request['settings']['keyterms_prompt'] = ['Lish Speaks']
    monkeypatch.setitem(BASELINES, 'assemblyai', request)
    assert process(tmp_path).exit_code == 0
    after = inspect(tmp_path / 'episode')
    assert len(after['transcription_operations']) == 2
    assert after['transcription_operations'][1]['attempts'][0]['request']['settings']['keyterms_prompt'] == ['Lish Speaks']
    assert after['transcription_operations'][0] == before['transcription_operations'][0]
    assert full_services.count('POST /v2/transcript') == 2


from test_managed_transcription import clock


@pytest.mark.parametrize('failure,allowance,accepted', [('failed', '3', 2), ('ambiguous', '3', 2),
    ('ambiguous', '.04', 1), ('failed', '.04', 1), ('none', '.0001', 0)])
def test_full_recovery_accounts_for_primary_backup_and_denied_reservations(tmp_path, full_services, monkeypatch, clock,
                                                                         failure, allowance, accepted):
    original = httpx.Client.send
    def send(client, request, **kwargs):
        if request.method == 'GET' and request.url.path == '/v2/transcript':
            full_services.append('GET reconciliation')
            return httpx.Response(200, json={'transcripts': []}, request=request)
        if request.url.path == '/v1/listen':
            full_services.append('POST backup')
            body = {'metadata': {'request_id': 'backup-full'}, 'results': {'channels': [{'alternatives': [{'words': [
                {'word': w['text'], 'punctuated_word': w['text'], 'start': w['start'] / 1000,
                 'end': w['end'] / 1000, 'speaker': 0} for w in primary_words()]}]}]}}
            return httpx.Response(200, json=body, request=request)
        response = original(client, request, **kwargs)
        if failure == 'ambiguous' and request.method == 'POST' and request.url.path == '/v2/transcript':
            raise httpx.ReadTimeout('possibly accepted', request=request)
        if failure == 'failed' and request.url.path == '/v2/transcript/full-job':
            return httpx.Response(200, json={'id': 'full-job', 'status': 'error'}, request=request)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    result = process(tmp_path, '--allowance', allowance)
    assert result.exit_code == (0 if accepted == 2 else 1), result.output
    before = inspect(tmp_path / 'episode')
    op = before['transcription_operations'][0]
    assert len(op['attempts']) == accepted
    assert all(a['reserved_usd'] > 0 and a['actual_usd'] is None for a in op['attempts'])
    paid = [call for call in full_services if call.startswith('POST')]
    for _ in range(2):
        assert process(tmp_path, '--allowance', '3').exit_code == result.exit_code
    after = inspect(tmp_path / 'episode')['transcription_operations'][0]
    assert after['policy'] == op['policy'] and after['deadline_at'] == op['deadline_at']
    assert [call for call in full_services if call.startswith('POST')] == paid


def test_full_resume_after_deadline_recovers_pending_remote_job(tmp_path, full_services, monkeypatch, clock):
    original = httpx.Client.send
    complete = [False]
    def send(client, request, **kwargs):
        response = original(client, request, **kwargs)
        if request.url.path == '/v2/transcript/full-job' and not complete[0]:
            return httpx.Response(200, json={'id': 'full-job', 'status': 'processing'}, request=request)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    assert process(tmp_path, '--deadline', '5').exit_code == 1
    before = inspect(tmp_path / 'episode')['transcription_operations'][0]
    assert process(tmp_path).exit_code == 1  # Still running after the local deadline.
    complete[0] = True
    assert process(tmp_path).exit_code == 0
    after = inspect(tmp_path / 'episode')['transcription_operations'][0]
    assert after['deadline_at'] == before['deadline_at']
    assert len(after['attempts']) == 1 and after['attempts'][0]['submissions'] == 1
    assert full_services.count('POST /v2/transcript') == 1


@pytest.mark.parametrize('kind', ['timing', 'text', 'speaker'])
def test_corrected_full_resume_preserves_changes_and_only_regenerates_consumers(tmp_path, full_services, kind):
    from test_participant_corrections import correct
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    word = transcript['words'][3]
    change = ({'op': 'retime', 'word_id': word['id'], 'start': word['start'] + .05, 'end': word['end'], 'evidence': 'Fixture timing correction'}
              if kind == 'timing' else {'op': 'replace', 'turn_id': word['turn_id'], 'first_word': word['id'], 'last_word': word['id'], 'text': 'Know'}
              if kind == 'text' else {'op': 'relabel', 'speaker': transcript['speakers'][0]['id'], 'participant': None})
    correct(workspace, [change])
    corrected = inspect(workspace)['artifacts']['transcript.json']
    count = len(full_services)
    result = process(tmp_path)
    assert result.exit_code == 0, result.output
    after = inspect(workspace)
    assert after['artifacts']['transcript.json'] == corrected
    assert after['transcription_operations'] == before['transcription_operations']
    if kind == 'timing':
        assert full_services[count:] == ['STAGE: chapters']
        assert after['artifacts']['titles.json'] == before['artifacts']['titles.json']
        assert after['evidence']['description-body.json'] == before['evidence']['description-body.json']
    else:
        assert full_services[count:] == ['STAGE: body', 'STAGE: titles', 'STAGE: chapters']


def test_direct_edit_is_preserved_even_when_original_artifact_is_damaged(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    original = before['artifacts']['titles.json']
    edited = b'Exact human working copy\r\n'
    (workspace / 'current/titles.json').write_bytes(edited)
    (workspace / original['path']).unlink()
    result = process(tmp_path)
    assert result.exit_code == 0, result.output
    history = inspect(workspace)['history']
    assert any(a['status'] == 'human-edited' and (workspace / a['path']).read_bytes() == edited for a in history)


def test_repaired_current_files_report_recovery_without_new_paid_calls(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    (workspace / 'current/titles.json').unlink()
    calls = list(full_services)
    result = process(tmp_path)
    assert result.exit_code == 0, result.output
    assert full_services == calls
    assert 'Recovered titles.json' in result.output
    assert inspect(workspace)['artifacts']['titles.json']['sha256'] == before['artifacts']['titles.json']['sha256']


@pytest.mark.parametrize('field,value,stages', [
    ('angle', 'Practical ways to listen.', ['body', 'titles']),
    ('current_context', 'An audience conversation about listening.', ['body', 'titles']),
    ('sponsors', ['Supplied sponsor message.'], []),
])
def test_full_episode_metadata_change_only_regenerates_actual_consumers(tmp_path, full_services, field, value, stages):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    metadata = tmp_path / 'episode.json'
    data = json.loads(metadata.read_text())
    data[field] = value
    metadata.write_text(json.dumps(data))
    count = len(full_services)
    result = process(tmp_path, '--metadata', str(metadata))
    assert result.exit_code == 0, result.output
    assert full_services[count:] == ['STAGE: ' + stage for stage in stages]
    after = inspect(workspace)
    for name in ('transcript.json', 'chapters.txt', 'section-plan.json'):
        assert after['artifacts'][name] == before['artifacts'][name]


def test_full_source_replacement_does_not_mix_old_package_after_failure(tmp_path, full_services, monkeypatch):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    source = recording(tmp_path, value=1)
    original = httpx.Client.send
    def denied(client, request, **kwargs):
        if request.method == 'POST' and request.url.path == '/v2/transcript':
            return httpx.Response(401, request=request)
        return original(client, request, **kwargs)
    monkeypatch.setattr(httpx.Client, 'send', denied)
    result = runner.invoke(app, ['process', str(source), '--workspace', str(workspace)])
    assert result.exit_code == 1
    after = inspect(workspace)
    assert after['source_revision'] != before['source_revision']
    assert after['artifacts'] == {}
    assert all(artifact in after['history'] for artifact in before['artifacts'].values())
    assert len(after['transcription_operations']) == 2
    assert 'Status: failed' in result.output


def test_inspect_reports_missing_required_planning_outcome(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    (workspace / 'current/section-plan.json').unlink()
    result = runner.invoke(app, ['inspect', str(workspace)])
    assert result.exit_code == 0
    assert 'Missing required outputs: section-plan.json' in result.output


def test_imported_plan_uses_inspected_source_duration_even_when_text_duration_unknown(tmp_path, full_services):
    source = recording(tmp_path)
    # An import with unknown transcript duration must still report the known original duration.
    path = tmp_path / 'unknown.json'
    path.write_text(json.dumps({'segments': [{'text': 'Useful words without timing.'}]}))
    result = runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), '--source', str(source), *authority(tmp_path)])
    assert result.exit_code == 0, result.output
    workspace = next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())
    result = runner.invoke(app, ['process', str(workspace)])
    assert result.exit_code == 1  # Missing chapters, but independent planning must use known source facts.
    outcome = json.loads((workspace / 'current/section-plan.json').read_bytes())
    assert outcome['evidence']['source']['duration'] == '70.000000'
    assert outcome['evidence']['source']['basis'] == 'verified'


def test_full_source_identity_reattachment_copy_replacement_and_future_schema(tmp_path, full_services, monkeypatch):
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    one, two = tmp_path / 'one', tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    first_source, second_source = recording(one), recording(two, value=1)
    first_result = runner.invoke(app, ['process', str(first_source), '--solo'])
    assert first_result.exit_code == 0, first_result.output
    second_result = runner.invoke(app, ['process', str(second_source), '--solo'])
    assert second_result.exit_code == 0, second_result.output
    first = Path(first_result.output.split('Workspace: ')[1].splitlines()[0])
    second = Path(second_result.output.split('Workspace: ')[1].splitlines()[0])
    assert first != second and first_source.name == second_source.name
    before = inspect(first)
    assert before['episode_id'] != inspect(second)['episode_id']
    paid = list(full_services)
    moved = tmp_path / 'moved.wav'
    first_source.rename(moved)
    assert runner.invoke(app, ['process', str(first)]).exit_code == 0
    assert runner.invoke(app, ['check-source', str(first)]).exit_code == 1
    assert runner.invoke(app, ['attach-source', str(first), str(moved), '--copy-source']).exit_code == 0
    attached = inspect(first)
    source = next(s for s in attached['sources'] if s['id'] == attached['source_revision'])
    assert (first / source['copied_path']).read_bytes() == moved.read_bytes()
    moved.unlink()
    assert runner.invoke(app, ['check-source', str(first)]).exit_code == 0
    assert runner.invoke(app, ['process', str(first)]).exit_code == 0
    assert inspect(first)['artifacts'] == before['artifacts']
    assert full_services == paid
    replacement = recording(one, value=2)
    result = runner.invoke(app, ['process', str(replacement), '--workspace', str(first)])
    assert result.exit_code == 0, result.output
    after = inspect(first)
    assert after['source_revision'] != before['source_revision']
    assert after['episode_id'] == before['episode_id']
    assert len(after['transcription_operations']) == 2
    transcript = json.loads((first / 'current/transcript.json').read_bytes())
    assert after['artifacts']['transcript.json']['dependencies']['source_revision'] == after['source_revision']
    assert transcript['provenance']['source_fingerprint'] == next(s['fingerprint'] for s in after['sources'] if s['id'] == after['source_revision'])
    assert (first / 'current/chapters.txt').read_text().strip() in (first / 'current/description.md').read_text()
    assert all(a in after['history'] for a in before['artifacts'].values())
    paid = list(full_services)
    state_file = first / 'current/state.json'
    future = json.loads(state_file.read_bytes())
    future['schema_version'] = 999
    state_file.write_text(json.dumps(future))
    future_bytes = state_file.read_bytes()
    rejected = runner.invoke(app, ['process', str(first)])
    assert rejected.exit_code == 1 and 'Unsupported workspace schema: 999' in rejected.output
    assert state_file.read_bytes() == future_bytes
    assert full_services == paid


def test_explicit_import_into_previously_managed_workspace_stays_authoritative(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    before = inspect(workspace)
    preserved = tmp_path / 'replacement-transcript.json'
    preserved.write_text(json.dumps({'duration': 70, 'segments': [
        {'start': 0, 'end': 20, 'text': 'Replacement opening about an honest conversation.'},
        {'start': 20.5, 'end': 44, 'text': 'Listen with care before replying.'},
        {'start': 45, 'end': 70, 'text': 'Prayer helps me find words.'}]}))
    result = runner.invoke(app, ['import', str(preserved), '--root', str(tmp_path / 'episodes'), '--workspace', str(workspace)])
    assert result.exit_code == 0, result.output
    imported = inspect(workspace)['artifacts']['transcript.json']
    result = process(tmp_path)
    assert result.exit_code == 0, result.output
    after = inspect(workspace)
    assert after['artifacts']['transcript.json'] == imported
    assert after['transcription_operations'] == before['transcription_operations']
    assert 'Replacement opening' in (workspace / 'current/transcript.txt').read_text()


def test_damaged_import_never_restores_old_asr_across_repeated_full_resumes(tmp_path, full_services):
    assert process(tmp_path).exit_code == 0
    workspace = tmp_path / 'episode'
    preserved = tmp_path / 'replacement.json'
    preserved.write_text(json.dumps({'segments': [{'text': 'Explicit replacement evidence.'}]}))
    assert runner.invoke(app, ['import', str(preserved), '--root', str(tmp_path / 'episodes'), '--workspace', str(workspace)]).exit_code == 0
    before = inspect(workspace)
    (workspace / 'current/transcript.json').unlink()
    calls = list(full_services)
    for _ in range(2):
        result = process(tmp_path)
        assert result.exit_code == 1
        after = inspect(workspace)
        assert 'transcript.json' not in after['artifacts']
        assert after['transcription_operations'] == before['transcription_operations']
    assert full_services == calls


@pytest.mark.parametrize('setting,expected', [('model', ['body', 'titles', 'chapters']), ('chapter_prompt', ['chapters'])])
def test_full_publishing_configuration_does_not_repeat_asr(tmp_path, full_services, monkeypatch, setting, expected):
    from podcast_processor.publishing_prompts import VERSIONS
    assert process(tmp_path).exit_code == 0
    before = inspect(tmp_path / 'episode')
    if setting == 'model':
        monkeypatch.setenv('CLAUDE_MODEL', 'fixture-publishing-model-v2')
    else:
        monkeypatch.setitem(VERSIONS, 'chapters', 'fixture-chapter-prompt-v2')
    count = len(full_services)
    assert process(tmp_path).exit_code == 0
    after = inspect(tmp_path / 'episode')
    assert full_services[count:] == ['STAGE: ' + stage for stage in expected]
    assert after['transcription_operations'] == before['transcription_operations']
    assert after['artifacts']['transcript.json'] == before['artifacts']['transcript.json']


def test_full_confirmed_guest_name_change_keeps_asr_and_unchanged_chapters(tmp_path, full_services):
    workspace = tmp_path / 'episode'
    source = recording(tmp_path)
    first = runner.invoke(app, ['process', str(source), '--workspace', str(workspace), '--guest', 'Erica'])
    assert first.exit_code == 0, first.output
    before = inspect(workspace)
    count = len(full_services)
    result = runner.invoke(app, ['process', str(workspace), '--guest', 'Erica Campbell'])
    assert result.exit_code == 0, result.output
    after = inspect(workspace)
    assert after['transcription_operations'] == before['transcription_operations']
    assert after['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert full_services[count:] == ['STAGE: body', 'STAGE: titles']
    assert 'Erica Campbell' in (workspace / 'current/description.md').read_text()
