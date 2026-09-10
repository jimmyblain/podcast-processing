"""Managed transcription acceptance through the CLI and real persisted workspace."""
import json
from pathlib import Path

import httpx
import pytest

from podcast_processor.cli import app
from test_workspace import authority, inspect, make_media, runner


PRIMARY = {'id': 'primary-job', 'status': 'completed', 'speech_model_used': 'universal-3-5-pro',
           'words': [{'text': 'Well,', 'start': 100, 'end': 300, 'speaker': 'A', 'confidence': 0.9},
                     {'text': 'well.', 'start': 350, 'end': 500, 'speaker': 'B', 'confidence': 0.8}],
           'utterances': [{'text': 'Well, well.', 'start': 0, 'end': 900, 'speaker': 'A'}]}
BACKUP = {'metadata': {'request_id': 'backup-job'}, 'results': {'channels': [{'alternatives': [
    {'transcript': 'Um, yes.', 'words': [
        {'word': 'um', 'punctuated_word': 'Um,', 'start': 0.1, 'end': 0.3, 'speaker': 0, 'confidence': 0.7, 'speaker_confidence': 0.6},
        {'word': 'yes', 'punctuated_word': 'Yes.', 'start': 0.2, 'end': 0.4, 'speaker': 1, 'confidence': 0.9, 'speaker_confidence': 0.8}]}]}],
    'utterances': [{'speaker': 0, 'start': 0, 'end': 0.9, 'transcript': 'Um, yes.'}]}}


@pytest.fixture
def service(monkeypatch):
    calls = []
    def send(client, request, **kwargs):
        calls.append(request)
        if request.url.path == '/v2/upload':
            return httpx.Response(200, json={'upload_url': 'https://cdn.assemblyai.com/test.flac'}, request=request)
        if request.url.path == '/v2/transcript' and request.method == 'POST':
            return httpx.Response(200, json={'id': 'primary-job', 'status': 'queued'}, request=request)
        if request.url.path == '/v2/transcript/primary-job':
            return httpx.Response(200, json=PRIMARY, request=request)
        if request.url.path == '/v1/listen':
            return httpx.Response(200, json=BACKUP, request=request)
        raise AssertionError(str(request.url))
    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setenv('ASSEMBLYAI_API_KEY', 'fake-primary')
    monkeypatch.setenv('DEEPGRAM_API_KEY', 'fake-backup')
    return calls


def managed(tmp_path, *options):
    workspace = tmp_path / 'episode'
    if (workspace / 'current').exists():
        args = ['transcribe', str(workspace), *options]
    else:
        source = make_media(tmp_path / 'recording.wav')
        args = ['transcribe', str(source), '--workspace', str(workspace), *authority(tmp_path), *options]
    result = runner.invoke(app, args)
    return workspace, result


def test_managed_operation_preserves_evidence_and_reuses_completed_artifacts(tmp_path, service):
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    state = inspect(workspace)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    assert [w['word'] for w in transcript['words']] == ['Well,', 'well.']
    labels = {s['id']: s['label'] for s in transcript['speakers']}
    assert [labels[s['speaker']] for s in transcript['segments']] == ['Speaker A', 'Speaker B']
    assert transcript['segments'][0]['start'] == 0.1
    assert transcript['speakers'][0]['participant'] is None
    assert state['runs'][-1]['status'] == 'completed'
    assert len(state['transcription_operations']) == 1
    assert state['transcription_operations'][0]['attempts'][0]['job_id'] == 'primary-job'
    assert any(a['name'].startswith('raw-') for a in state['evidence'].values())
    assert 'Lish Speaks:' not in (workspace / 'current/transcript.txt').read_text()
    _, resumed = managed(tmp_path)
    assert resumed.exit_code == 0, resumed.output
    assert inspect(workspace)['artifacts'] == state['artifacts']
    assert len(service) == 3
    request = json.loads(service[1].content)
    assert request['speech_models'] == ['universal-3-5-pro']
    assert request['format_text'] is False and request['disfluencies'] is True
    assert service[1].url.host == 'api.eu.assemblyai.com'


def replace_responses(monkeypatch, transform):
    original = httpx.Client.send
    def send(client, request, **kwargs):
        response = original(client, request, **kwargs)
        return transform(request, response)
    monkeypatch.setattr(httpx.Client, 'send', send)


def test_failed_primary_uses_backup_word_labels_and_preserves_overlap(tmp_path, service, monkeypatch):
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json={
        'id': 'primary-job', 'status': 'error', 'error': 'controlled processing failure'}, request=req)
        if req.method == 'GET' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    labels = {s['id']: s['label'] for s in transcript['speakers']}
    assert [labels[t['speaker']] for t in transcript['segments']] == ['Speaker 0', 'Speaker 1']
    assert transcript['segments'][1]['start'] < transcript['segments'][0]['end']
    assert transcript['words'][0]['recognition_confidence'] == 0.7
    assert transcript['words'][0]['speaker_confidence'] == 0.6
    operation = inspect(workspace)['transcription_operations'][0]
    assert [a['status'] for a in operation['attempts']] == ['failed', 'completed']
    assert all(a['actual_usd'] is None for a in operation['attempts'])
    request = service[-1]
    assert request.url.params['diarize_model'] == 'v2'
    assert request.url.params['multichannel'] == 'false'
    assert request.url.params['mip_opt_out'] == 'true'
    report = (workspace / 'current/completion-report.md').read_text()
    assert 'backup' in report.lower()
    assert 'reserved' in report.lower() and 'unknown' in report.lower()


def test_sparse_unusable_timing_and_annotations_do_not_buy_backup(tmp_path, service, monkeypatch):
    payload = {**PRIMARY, 'words': [PRIMARY['words'][0],
        {'text': 'um,', 'start': 400, 'end': 400, 'speaker': 'A'},
        {'text': 'I', 'start': 700, 'end': 600, 'speaker': 'A'},
        {'text': 'mean,', 'start': None, 'end': None, 'speaker': 'A'},
        {'text': '[music]', 'start': 800, 'end': 900, 'speaker': 'A'},
        {'text': 'really.', 'start': 600, 'end': 900, 'speaker': 'B'}]}
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json=payload, request=req)
                      if req.method == 'GET' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    assert [w['word'] for w in transcript['words']] == ['Well,', 'um,', 'I', 'mean,', 'really.']
    assert [w['timing_usable'] for w in transcript['words']] == [True, False, False, False, True]
    assert transcript['words'][2]['start'] is None
    assert len(transcript['annotations']) == 1
    assert '[music]' not in (workspace / 'current/transcript.txt').read_text()
    assert len(service) == 3


def test_recoverable_text_without_word_array_is_kept_as_imprecise(tmp_path, service, monkeypatch):
    payload = {**PRIMARY, 'words': [], 'text': 'Um, I mean, well, yes.', 'utterances': []}
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json=payload, request=req)
                      if req.method == 'GET' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    assert transcript['segments'][0]['text'] == 'Um, I mean, well, yes.'
    assert transcript['segments'][0]['start'] is None
    assert transcript['segments'][0]['timing_usable'] is False
    assert len(service) == 3


def test_ambiguous_primary_reconciles_known_upload_without_rebuying(tmp_path, service, monkeypatch):
    original = httpx.Client.send
    def send(client, request, **kwargs):
        if request.url.path == '/v2/transcript' and request.method == 'GET':
            service.append(request)
            return httpx.Response(200, json={'transcripts': [{'id': 'primary-job',
                'audio_url': 'https://cdn.assemblyai.com/test.flac', 'status': 'completed'}]}, request=request)
        response = original(client, request, **kwargs)
        if request.url.path == '/v2/transcript' and request.method == 'POST':
            raise httpx.ReadTimeout('accepted but response lost', request=request)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    operation = inspect(workspace)['transcription_operations'][0]
    assert len(operation['attempts']) == 1
    assert operation['attempts'][0]['job_id'] == 'primary-job'
    assert operation['attempts'][0]['reconciliations'] == 1
    assert len([r for r in service if r.method == 'POST' and r.url.path == '/v2/transcript']) == 1


@pytest.fixture
def clock(monkeypatch):
    import time
    current = [time.time()]
    sleeps = []
    monkeypatch.setattr(time, 'time', lambda: current[0])
    def sleep(seconds):
        sleeps.append(seconds)
        current[0] += seconds
    monkeypatch.setattr(time, 'sleep', sleep)
    return current, sleeps


def test_unresolved_submissions_keep_two_reserved_slots_across_resumes(tmp_path, service, monkeypatch, clock):
    original = httpx.Client.send
    def send(client, request, **kwargs):
        if request.url.path == '/v2/transcript' and request.method == 'GET':
            service.append(request)
            return httpx.Response(200, json={'transcripts': []}, request=request)
        response = original(client, request, **kwargs)
        if request.url.path in ('/v2/transcript', '/v1/listen') and request.method == 'POST':
            raise httpx.ReadTimeout('possibly accepted', request=request)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 1
    first = inspect(workspace)['transcription_operations'][0]
    assert [a['status'] for a in first['attempts']] == ['ambiguous', 'ambiguous']
    assert all(a['reserved_usd'] > 0 and a['actual_usd'] is None for a in first['attempts'])
    for _ in range(5):
        assert managed(tmp_path)[1].exit_code == 1
    after = inspect(workspace)['transcription_operations'][0]
    assert after['deadline_at'] == first['deadline_at']
    assert len(after['attempts']) == 2
    assert len([r for r in service if r.method == 'POST' and r.url.path != '/v2/upload']) == 2


@pytest.mark.parametrize('status', [401, 403, 400])
def test_auth_or_configuration_failure_is_explicit_and_never_retries_or_uses_backup(tmp_path, service, monkeypatch, clock, status):
    replace_responses(monkeypatch, lambda req, res: httpx.Response(status, json={'error': 'controlled'}, request=req)
                      if req.url.path == '/v2/transcript' and req.method == 'POST' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 1
    assert f'HTTP {status}' in result.output
    for _ in range(3):
        assert managed(tmp_path)[1].exit_code == 1
    operation = inspect(workspace)['transcription_operations'][0]
    assert len(operation['attempts']) == 1
    assert operation['attempts'][0]['submissions'] == 1
    assert len([r for r in service if r.url.path == '/v1/listen']) == 0


def test_demonstrably_rejected_submission_retries_once_within_original_slot(tmp_path, service, monkeypatch, clock):
    posts = []
    def transform(req, res):
        if req.url.path == '/v2/transcript' and req.method == 'POST':
            posts.append(req)
            if len(posts) == 1:
                return httpx.Response(429, json={'error': 'rate limited, not accepted'}, request=req)
        return res
    replace_responses(monkeypatch, transform)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    operation = inspect(workspace)['transcription_operations'][0]
    assert len(operation['attempts']) == 1
    assert operation['attempts'][0]['submissions'] == 2
    assert len(posts) == 2
    assert clock[1] == [2]


def test_transient_status_reads_back_off_and_recover_same_job(tmp_path, service, monkeypatch, clock):
    reads = []
    def transform(req, res):
        if req.method == 'GET':
            reads.append(req)
            if len(reads) <= 2:
                return httpx.Response(503, request=req)
        return res
    replace_responses(monkeypatch, transform)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    operation = inspect(workspace)['transcription_operations'][0]
    assert operation['attempts'][0]['submissions'] == 1
    assert operation['attempts'][0]['reads'] == 3
    assert clock[1] == [2, 4]


def test_deadline_persists_and_completed_job_is_recovered_after_expiry(tmp_path, service, monkeypatch, clock):
    complete = [False]
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json={
        'id': 'primary-job', 'status': 'processing'}, request=req)
        if req.method == 'GET' and not complete[0] else res)
    workspace, result = managed(tmp_path, '--deadline', '5')
    assert result.exit_code == 1
    first = inspect(workspace)['transcription_operations'][0]
    assert first['elapsed_seconds'] >= 5
    complete[0] = True
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    after = inspect(workspace)['transcription_operations'][0]
    assert after['deadline_at'] == first['deadline_at']
    assert after['attempts'][0]['submissions'] == 1
    assert len(after['attempts']) == 1


def test_exhausted_transient_reads_can_download_later_completed_job(tmp_path, service, monkeypatch, clock):
    complete = [False]
    replace_responses(monkeypatch, lambda req, res: httpx.Response(503, request=req)
                      if req.method == 'GET' and not complete[0] else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 1
    first = inspect(workspace)['transcription_operations'][0]
    assert first['attempts'][0]['reads'] == 4
    complete[0] = True
    clock[0][0] = first['deadline_at'] + 1
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    assert inspect(workspace)['transcription_operations'][0]['attempts'][0]['submissions'] == 1


def test_insufficient_allowance_denies_submission_and_resume_does_not_refill(tmp_path, service, clock):
    workspace, result = managed(tmp_path, '--allowance', '0.0001')
    assert result.exit_code == 1
    assert not service
    first = inspect(workspace)['transcription_operations'][0]
    assert first['attempts'] == []
    _, result = managed(tmp_path, '--allowance', '3')
    assert result.exit_code == 1
    assert not service
    after = inspect(workspace)['transcription_operations'][0]
    assert after['policy'] == first['policy']
    assert after['deadline_at'] == first['deadline_at']


def test_ambiguous_primary_charge_can_prevent_backup(tmp_path, service, monkeypatch, clock):
    original = httpx.Client.send
    def send(client, request, **kwargs):
        if request.url.path == '/v2/transcript' and request.method == 'GET':
            service.append(request)
            return httpx.Response(200, json={'transcripts': []}, request=request)
        response = original(client, request, **kwargs)
        if request.url.path == '/v2/transcript' and request.method == 'POST':
            raise httpx.ReadTimeout('possibly accepted', request=request)
        return response
    monkeypatch.setattr(httpx.Client, 'send', send)
    workspace, result = managed(tmp_path, '--allowance', '0.0005')
    assert result.exit_code == 1
    op = inspect(workspace)['transcription_operations'][0]
    assert len(op['attempts']) == 1
    assert op['attempts'][0]['status'] == 'ambiguous'
    assert op['attempts'][0]['reserved_usd'] > 0
    assert not any(r.url.path == '/v1/listen' for r in service)


def test_fresh_operation_retains_old_ledger_and_replaces_artifact_references(tmp_path, service):
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    _, result = managed(tmp_path, '--fresh')
    assert result.exit_code == 0, (result.output, result.exception)
    after = inspect(workspace)
    assert len(after['transcription_operations']) == 2
    assert after['transcription_operations'][0] == before['transcription_operations'][0]
    assert after['artifacts']['transcript.json']['id'] != before['artifacts']['transcript.json']['id']
    assert before['artifacts']['transcript.json'] in after['history']
    assert len(service) == 6
    old = json.loads((workspace / before['artifacts']['transcript.json']['path']).read_bytes())
    new = json.loads((workspace / 'current/transcript.json').read_bytes())
    assert old['revision'] != new['revision']


def test_normalization_change_reuses_raw_response_without_source_or_services(tmp_path, service, monkeypatch):
    from podcast_processor import normalization
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    (tmp_path / 'recording.wav').unlink()
    for path in (workspace / 'media').iterdir():
        path.unlink()
    monkeypatch.setattr(normalization, 'NORMALIZATION_VERSION', 'managed-words-test-v2')
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    after = inspect(workspace)
    assert len(service) == 3
    assert after['artifacts']['transcript.json']['id'] != before['artifacts']['transcript.json']['id']
    assert all(after['evidence'][name] == artifact for name, artifact in before['evidence'].items())
    assert len(after['transcription_operations']) == 1


def test_transport_preserves_source_samples_and_timeline(tmp_path, service):
    import hashlib
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    op = inspect(workspace)['transcription_operations'][0]
    transport = op['transport']
    assert transport['source_fingerprint'] == hashlib.sha256((tmp_path / 'recording.wav').read_bytes()).hexdigest()
    assert transport['submitted_fingerprint'] == hashlib.sha256((workspace / transport['path']).read_bytes()).hexdigest()
    assert transport['equivalence'] == 'verified'
    assert transport['timeline_offset_seconds'] == 0
    assert transport['duration'] == 1


def test_unusable_primary_and_backup_report_unavailable_with_both_raw_results(tmp_path, service, monkeypatch):
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200,
        json={'id': 'primary-job', 'status': 'completed', 'words': []} if req.method == 'GET'
        else {'metadata': {'request_id': 'backup-job'}, 'results': {}}, request=req)
        if req.method == 'GET' or req.url.path == '/v1/listen' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 1
    state = inspect(workspace)
    assert state['artifacts'] == {}
    assert len(state['evidence']) == 2
    assert [a['status'] for a in state['transcription_operations'][0]['attempts']] == ['unusable', 'unusable']
    assert managed(tmp_path)[1].exit_code == 1
    assert len(service) == 4


def test_103_zero_duration_words_remain_faithful_without_triggering_backup(tmp_path, service, monkeypatch):
    payload = {**PRIMARY, 'words': [PRIMARY['words'][0]] + [
        {'text': 'um,', 'start': 500, 'end': 500, 'speaker': 'A'} for _ in range(103)]}
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json=payload, request=req)
                      if req.method == 'GET' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    assert sum(not w['timing_usable'] for w in transcript['words']) == 103
    assert len(transcript['words']) == 104
    assert len(service) == 3


@pytest.mark.parametrize('provider', ['assemblyai', 'deepgram'])
def test_local_cached_comparison_replays_full_word_evidence(tmp_path, service, monkeypatch, provider):
    """Optional private corpus replay; silence is transport scaffolding, not source truth."""
    import wave
    payload_path = Path('output/provider-comparison-erica-campbell') / f'{provider}-response.json'
    if not payload_path.exists():
        pytest.skip('Private comparison cache is intentionally not committed')
    payload = json.loads(payload_path.read_bytes())
    source = tmp_path / 'recording.wav'
    with wave.open(str(source), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\0\0' * (8000 * 3370))
    def transform(req, res):
        if req.method == 'GET':
            return httpx.Response(200, json=payload if provider == 'assemblyai' else
                {'id': 'primary-job', 'status': 'error'}, request=req)
        if req.url.path == '/v1/listen':
            return httpx.Response(200, json=payload, request=req)
        return res
    replace_responses(monkeypatch, transform)
    workspace = tmp_path / 'episode'
    result = runner.invoke(app, ['transcribe', str(source), '--workspace', str(workspace), *authority(tmp_path)])
    assert result.exit_code == 0, (result.output, result.exception)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    native = payload['words'] if provider == 'assemblyai' else payload['results']['channels'][0]['alternatives'][0]['words']
    normalized = {w['evidence_index']: w for w in transcript['words']}
    scale = 1000 if provider == 'assemblyai' else 1
    for index, word in enumerate(native):
        if index not in normalized:
            assert any(a['evidence_index'] == index for a in transcript['annotations'])
            continue
        result_word = normalized[index]
        labels = {s['id']: s['label'] for s in transcript['speakers']}
        assert labels[result_word['speaker']] == f"Speaker {word['speaker']}"
        assert result_word['start'] == word['start'] / scale
        assert result_word['end'] == word['end'] / scale
    if provider == 'assemblyai':
        assert sum(not w['timing_usable'] for w in transcript['words']) == 103
        early = [u for u in payload['utterances'] if u['words'][0]['start'] - u['start'] > 1000]
        assert len(early) == 3
        for utterance in early:
            first_word = next(w for w in transcript['words'] if w['start'] == utterance['words'][0]['start'] / 1000)
            turn = next(t for t in transcript['segments'] if t['id'] == first_word['turn_id'])
            assert turn['start'] <= first_word['start'] <= turn['end']
    else:
        mixed = [u for u in payload['results']['utterances'] if len({w['speaker'] for w in u['words']}) > 1]
        assert len(mixed) == 153
        assert sum(w['speaker'] != u['speaker'] for u in mixed for w in u['words']) == 939
    assert len(service) == (3 if provider == 'assemblyai' else 4)


def test_source_and_request_changes_invalidate_transcription_and_keep_old_ledgers(tmp_path, service, monkeypatch):
    import copy
    from podcast_processor.managed_providers import BASELINES
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    source = make_media(tmp_path / 'replacement.wav', 1)
    result = runner.invoke(app, ['transcribe', str(source), '--workspace', str(workspace)])
    assert result.exit_code == 0, result.output
    changed = inspect(workspace)
    assert changed['source_revision'] != before['source_revision']
    assert len(changed['transcription_operations']) == 2
    assert changed['artifacts']['transcript.json']['id'] != before['artifacts']['transcript.json']['id']
    baseline = copy.deepcopy(BASELINES['assemblyai'])
    baseline['settings']['punctuate'] = False
    monkeypatch.setitem(BASELINES, 'assemblyai', baseline)
    _, result = managed(tmp_path)
    assert result.exit_code == 0, result.output
    assert len(inspect(workspace)['transcription_operations']) == 3
    assert len(service) == 9


def test_renormalization_failure_cannot_report_previous_completion(tmp_path, service, monkeypatch):
    import os
    from podcast_processor import normalization
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    monkeypatch.setattr(normalization, 'NORMALIZATION_VERSION', 'managed-words-test-v2')
    original = os.replace
    failed = [False]
    def replace(src, dst):
        if Path(dst).name == 'current' and (Path(src).resolve() / 'transcript.txt').exists() and not failed[0]:
            failed[0] = True
            raise OSError('controlled failure')
        return original(src, dst)
    monkeypatch.setattr(os, 'replace', replace)
    _, result = managed(tmp_path)
    assert result.exit_code == 1
    assert inspect(workspace)['runs'][-1]['status'] == 'partial'


def test_transcription_reuse_reports_its_own_completion_after_other_stage_fails(tmp_path, service, monkeypatch):
    from podcast_processor.llm import ClaudeClient, LLMError
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0
    def fail(*args, **kwargs):
        raise LLMError('controlled publishing failure')
    monkeypatch.setattr(ClaudeClient, 'generate', fail)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'fake'])
    assert result.exit_code == 1
    _, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    state = inspect(workspace)
    assert state['runs'][-1]['operation'] == 'transcribe'
    assert state['runs'][-1]['status'] == 'completed'
    assert len(service) == 3


def test_invalid_primary_shape_is_preserved_and_backup_completes(tmp_path, service, monkeypatch):
    payload = {'id': 'primary-job', 'status': 'completed', 'words': {'unexpected': 'schema'}}
    replace_responses(monkeypatch, lambda req, res: httpx.Response(200, json=payload, request=req)
                      if req.method == 'GET' else res)
    workspace, result = managed(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    state = inspect(workspace)
    assert len([a for a in state['evidence'].values() if a['name'].startswith('raw-')]) == 2
    assert state['transcription_operations'][0]['attempts'][0]['status'] == 'unusable'
    assert any(json.loads((workspace / a['path']).read_bytes()) == payload for a in state['evidence'].values())


def test_transport_stops_starting_subprocesses_at_shared_deadline(tmp_path, service, monkeypatch, clock):
    import subprocess
    original = subprocess.run
    preparation = []
    def run(command, **kwargs):
        result = original(command, **kwargs)
        if command[0] == 'ffmpeg':
            preparation.append(command)
            clock[0][0] += 6
        return result
    monkeypatch.setattr(subprocess, 'run', run)
    workspace, result = managed(tmp_path, '--deadline', '5')
    assert result.exit_code == 1
    assert len(preparation) == 1
    assert not service
    assert inspect(workspace)['runs'][-1]['status'] == 'partial'
