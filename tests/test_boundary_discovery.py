"""Production cut discovery through the public episode workflow, with controlled services.

Speech and editorial responses are synthetic; these tests establish no real audio safety.
"""
import json
from decimal import Decimal

import httpx
import pytest

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient
from publishing_responses import compatible_response
from test_episode_workflow import recording
from test_workspace import inspect, runner

pytestmark = pytest.mark.usefixtures('approved_show_setup')


def conversation():
    words = []
    for start, text in [
        (0, "I'm Lish Speaks. Today we talk about finding courage."),
        (590, 'That is how I finally learned to trust myself.'),
        (610, 'Now let us talk about building stronger friendships.'),
        (1290, 'Listening to each other made our friendship stronger.'),
        (1310, 'Next I want to share how prayer changed my mornings.'),
        (2050, 'Thank you for listening. See you next time.'),
    ]:
        for index, word in enumerate(text.split()):
            words.append({'text': word, 'start': (start + index * .5) * 1000,
                          'end': (start + index * .5 + .4) * 1000, 'speaker': 'A'})
    return words


@pytest.fixture
def discovery_services(monkeypatch):
    calls = []
    def send(client, request, **kwargs):
        calls.append(request.method + ' ' + request.url.path)
        if request.url.path == '/v2/upload':
            body = {'upload_url': 'https://cdn.assemblyai.com/discovery.flac'}
        elif request.method == 'POST':
            body = {'id': 'discovery-job', 'status': 'queued'}
        else:
            body = {'id': 'discovery-job', 'status': 'completed', 'words': conversation()}
        return httpx.Response(200, json=body, request=request)
    def generate(self, prompt, max_tokens=4096):
        calls.append(prompt.splitlines()[0])
        if prompt.startswith('STAGE: section-discovery'):
            context = json.loads(prompt.split('Evidence and authoritative inputs:\n')[1].split('\nRepair')[0])
            # The controlled semantic service chooses by discussion content, using
            # only IDs and excerpts actually supplied by the production discovery stage.
            choices = [gap for gap in context['opportunities']
                       if gap['before_text'].endswith(('trust myself.', 'friendship stronger.'))]
            return json.dumps({'summary': 'Reviewed the conversation for complete topic changes.',
                'candidates': [{'boundary_id': gap['id'], 'complete_thought': True,
                    'natural_topic_boundary': True, 'strength': 3,
                    'reason': 'The preceding reflection concludes before the next topic begins.'}
                    for gap in choices]})
        if prompt.startswith('STAGE: chapters'):
            context = json.loads(prompt.split('Evidence and authoritative inputs:\n')[1].split('\nRepair')[0])
            turns = [t for t in context['turns'] if t['start_time'] >= 590]
            chosen = [turns[0], next(t for t in turns if t['start_time'] >= 1290)]
            return json.dumps([{'start_time': 0, 'title': 'Courage', 'boundary_id': 'anchor', 'reason': 'Anchor'},
                *[{'start_time': t['start_time'], 'title': f'Topic {i}', 'boundary_id': t['boundary_id'],
                   'reason': 'Synthetic topic change'} for i, t in enumerate(chosen)]])
        return compatible_response(prompt)
    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(ClaudeClient, 'generate', generate)
    monkeypatch.setenv('ASSEMBLYAI_API_KEY', 'fixture-primary')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-discovery')
    return calls


def new_episode(tmp_path, duration=2100):
    workspace = tmp_path / 'episode'
    result = runner.invoke(app, ['process', str(recording(tmp_path, duration)), '--workspace', str(workspace), '--solo'])
    return workspace, result


def outcome(workspace):
    return json.loads((workspace / 'current/section-plan.json').read_bytes())


def test_normal_process_discovers_unequal_natural_parts_and_reuses_the_proposal(tmp_path, discovery_services):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    plan = outcome(workspace)
    assert plan['status'] == 'valid'
    assert plan['discovery']['status'] == 'completed'
    proposal = plan['proposal']
    assert [cut['time'] for cut in proposal['boundaries']] == ['602.2', '1301.95']
    assert [Decimal(part['finished_duration']) for part in proposal['sections']] == [Decimal('610.7'), Decimal('708.25'), Decimal('801.55')]
    assert proposal['sections'][0]['source_start'] == '0'
    assert Decimal(proposal['sections'][-1]['source_end']) == 2100
    assert all(cut['basis'] == 'transcript-supported' and cut['safe_start'] is None for cut in proposal['boundaries'])
    assert all(cut['support']['before_word_ids'] and cut['support']['after_word_ids'] for cut in proposal['boundaries'])
    before = inspect(workspace)
    assert len(before['discovery_operations']) == 1
    attempt = before['discovery_operations'][0]['attempts'][0]
    assert attempt['status'] == 'validated'
    assert (workspace / attempt['response_path']).is_file()
    assert 'independent' in ' '.join(proposal['limitations'])
    calls = list(discovery_services)
    resumed = runner.invoke(app, ['process', str(workspace)])
    assert resumed.exit_code == 0, resumed.output
    after = inspect(workspace)
    assert after['artifacts'] == before['artifacts']
    assert after['discovery_operations'] == before['discovery_operations']
    assert discovery_services == calls


@pytest.mark.parametrize('timing', ['unknown', 'uncertain', 'isolated-turn', 'overlap'])
def test_discovery_seeks_supported_alternatives_around_isolated_bad_timing(tmp_path, discovery_services, monkeypatch, timing):
    original = conversation
    def degraded():
        words = original()
        last = next(w for w in words if w['text'] == 'myself.')
        if timing == 'unknown':
            last.update(start=None, end=None)
        elif timing in ('uncertain', 'isolated-turn'):
            last['end'] = last['start']
            if timing == 'isolated-turn':
                last['speaker'] = 'B'
        else:
            last['end'] = 615000
        extra = []
        for start, text in [(640, 'That practice helped me learn to trust myself.'),
                            (670, 'Now we can explore the work of friendship.')]:
            for i, word in enumerate(text.split()):
                extra.append({'text': word, 'start': (start + i * .5) * 1000,
                              'end': (start + i * .5 + .4) * 1000, 'speaker': 'A'})
        insertion = next(i for i, w in enumerate(words) if w['start'] == 1290000)
        words[insertion:insertion] = extra
        return words
    monkeypatch.setattr(__import__(__name__), 'conversation', degraded)
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, (result.output, result.exception)
    plan = outcome(workspace)
    assert plan['status'] == 'valid'
    assert [b['time'] for b in plan['proposal']['boundaries']] == ['656.95', '1301.95']
    state = inspect(workspace)
    candidates = json.loads((workspace / state['evidence']['section-candidates.json']['path']).read_bytes())
    assert candidates['rejected_opportunities']
    assert 'STAGE: section-discovery' in discovery_services


def test_corrected_transcript_invalidates_discovery_and_replans_without_transcribing(tmp_path, discovery_services):
    from test_participant_corrections import correct
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, result.output
    before = inspect(workspace)
    transcript = json.loads((workspace / 'current/transcript.json').read_bytes())
    word = next(w for w in transcript['words'] if w['word'] == 'myself.')
    correct(workspace, [{'op': 'retime', 'word_id': word['id'], 'start': 594, 'end': 595,
                        'evidence': 'Synthetic corrected word timing.'}])
    corrected = inspect(workspace)
    assert 'section-candidates.json' not in corrected['evidence']
    assert 'section-boundaries.json' not in corrected['artifacts']
    assert runner.invoke(app, ['plan', str(workspace)]).exit_code == 0
    after = inspect(workspace)
    assert outcome(workspace)['status'] == 'valid'
    assert outcome(workspace)['proposal']['boundaries'][0]['time'] == '602.5'
    assert len(after['discovery_operations']) == 2
    assert after['transcription_operations'] == before['transcription_operations']
    assert after['publishing_operations'] == before['publishing_operations']
    assert discovery_services.count('POST /v2/transcript') == 1


@pytest.mark.parametrize('failure', ['provider', 'invalid-response', 'invented-source-review'])
def test_failed_discovery_is_partial_bounded_and_never_claims_a_completed_search(tmp_path, discovery_services, monkeypatch, failure):
    original = ClaudeClient.generate
    requests = []
    def fail(self, prompt, max_tokens=4096):
        if not prompt.startswith('STAGE: section-discovery'):
            return original(self, prompt, max_tokens)
        requests.append(prompt)
        if failure == 'provider':
            raise RuntimeError('Controlled provider outage')
        if failure == 'invalid-response':
            return '{broken'
        response = json.loads(original(self, prompt, max_tokens))
        response['candidates'][0]['basis'] = 'source-reviewed'
        return json.dumps(response)
    monkeypatch.setattr(ClaudeClient, 'generate', fail)
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 1
    plan = outcome(workspace)
    assert plan['reason_code'] == 'discovery-failed'
    assert plan['discovery']['status'] == 'failed'
    assert 'No pair' not in ' '.join(plan['reasons'])
    assert len(requests) == 3
    before = inspect(workspace)
    assert {'description.md', 'titles.json', 'chapters.txt', 'transcript.json'} <= before['artifacts'].keys()
    assert 'section-boundaries.json' not in before['artifacts']
    assert 'section-candidates.json' not in before['evidence']
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 1
    assert len(requests) == 3
    assert inspect(workspace)['discovery_operations'] == before['discovery_operations']
    monkeypatch.setattr(ClaudeClient, 'generate', original)
    assert runner.invoke(app, ['plan', str(workspace), '--fresh']).exit_code == 0
    assert outcome(workspace)['status'] == 'valid'
    after = inspect(workspace)
    assert [len(op['attempts']) for op in after['discovery_operations']] == [3, 1]
    assert after['publishing_operations'] == before['publishing_operations']
    assert after['transcription_operations'] == before['transcription_operations']


def test_missing_key_can_resume_discovery_without_a_new_allowance(tmp_path, discovery_services, monkeypatch):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    result = runner.invoke(app, ['plan', str(workspace), '--fresh'])
    assert result.exit_code == 1
    assert outcome(workspace)['reason_code'] == 'discovery-failed'
    failed = inspect(workspace)
    assert failed['discovery_operations'][-1]['attempts'] == []
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-restored')
    assert runner.invoke(app, ['plan', str(workspace)]).exit_code == 0
    after = inspect(workspace)
    assert len(after['discovery_operations']) == 2
    assert len(after['discovery_operations'][-1]['attempts']) == 1
    assert after['publishing_operations'] == before['publishing_operations']


def test_completed_search_with_insufficient_cuts_is_not_a_provider_failure(tmp_path, discovery_services, monkeypatch):
    original = ClaudeClient.generate
    def insufficient(self, prompt, max_tokens=4096):
        if prompt.startswith('STAGE: section-discovery'):
            return json.dumps({'summary': 'The conversation continues without supported topic breaks.', 'candidates': []})
        return original(self, prompt, max_tokens)
    monkeypatch.setattr(ClaudeClient, 'generate', insufficient)
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, result.output
    plan = outcome(workspace)
    assert plan['status'] == 'unavailable'
    assert plan['reason_code'] == 'insufficient-boundaries'
    assert plan['discovery']['status'] == 'completed'
    before = inspect(workspace)
    assert runner.invoke(app, ['process', str(workspace)]).exit_code == 0
    assert inspect(workspace)['discovery_operations'] == before['discovery_operations']


@pytest.mark.parametrize('missing_setup', [False, True])
def test_duration_impossibility_and_missing_setup_explain_why_discovery_did_not_run(tmp_path, discovery_services, monkeypatch, missing_setup):
    if missing_setup:
        monkeypatch.setenv('PODCAST_SHOW_SETUP', str(tmp_path / 'no-setup'))
    workspace, result = new_episode(tmp_path, duration=3400 if not missing_setup else 2100)
    assert result.exit_code == (1 if missing_setup else 0), result.output
    plan = outcome(workspace)
    assert plan['reason_code'] == ('missing-setup' if missing_setup else 'duration-impossible')
    assert plan['discovery']['status'] == 'not-run'
    assert 'No pair' not in ' '.join(plan['reasons'])
    assert 'STAGE: section-discovery' not in discovery_services
    state = inspect(workspace)
    assert not state['discovery_operations']
    assert 'description.md' in state['artifacts']


def test_transition_recalculation_reuses_discovered_candidates_and_independent_outputs(tmp_path, discovery_services):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    evidence = outcome(workspace)['evidence']
    # Exercise the explicit advanced input path with actual production-discovered
    # candidates; no test-authored list bypasses candidate production.
    evidence['episode_start']['duration'] = '13.5'
    path = tmp_path / 'changed-transitions.json'
    path.write_text(json.dumps(evidence))
    assert runner.invoke(app, ['plan', str(workspace), '--evidence', str(path)]).exit_code == 0
    after = inspect(workspace)
    assert after['evidence']['section-candidates.json'] == before['evidence']['section-candidates.json']
    assert after['discovery_operations'] == before['discovery_operations']
    assert after['publishing_operations'] == before['publishing_operations']
    assert after['transcription_operations'] == before['transcription_operations']
    assert Decimal(outcome(workspace)['proposal']['sections'][0]['finished_duration']) == Decimal('620.7')


def test_damaged_candidate_artifact_recovers_from_the_saved_response_without_paid_work(tmp_path, discovery_services):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0
    before = inspect(workspace)
    candidates = before['evidence']['section-candidates.json']
    (workspace / candidates['path']).write_bytes(b'broken derived candidate artifact')
    calls = list(discovery_services)
    result = runner.invoke(app, ['process', str(workspace)])
    assert result.exit_code == 0, result.output
    assert outcome(workspace)['status'] == 'valid'
    after = inspect(workspace)
    assert after['discovery_operations'] == before['discovery_operations']
    assert discovery_services == calls
    recovered = after['evidence']['section-candidates.json']
    assert recovered['sha256'] == candidates['sha256']
    assert recovered['id'] != candidates['id']


def test_individual_transition_overhead_can_make_the_split_impossible(tmp_path, discovery_services):
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0
    evidence = outcome(workspace)['evidence']
    # Aggregate source + overhead still fits 3 * 1080, but section 1 cannot fit
    # even an empty source part alongside this prepared opening.
    evidence['episode_start']['duration'] = '1080'
    path = tmp_path / 'oversized-opening.json'
    path.write_text(json.dumps(evidence))
    assert runner.invoke(app, ['plan', str(workspace), '--evidence', str(path)]).exit_code == 0
    assert outcome(workspace)['reason_code'] == 'duration-impossible'
    assert 'section-boundaries.json' not in inspect(workspace)['artifacts']


@pytest.mark.parametrize('word_text,start,end', [('That', 620000, 620000), ('That', 620000, None),
                                               ('let', None, 580000)])
def test_contradictory_uncertain_timing_cannot_be_hidden_by_neighboring_words(tmp_path, discovery_services, monkeypatch, word_text, start, end):
    original = conversation
    def contradictory():
        words = original()
        word = next(w for w in words if w['text'] == word_text)
        # Retained partial/zero-length timing contradicts which side of the
        # proposed cut this word would occupy by transcript order.
        word.update(start=start, end=end)
        return words
    monkeypatch.setattr(__import__(__name__), 'conversation', contradictory)
    workspace, result = new_episode(tmp_path)
    assert result.exit_code == 0, result.output
    plan = outcome(workspace)
    assert plan['status'] == 'unavailable'
    assert plan['reason_code'] == 'insufficient-boundaries'
    assert plan['discovery']['status'] == 'completed'
    assert 'section-boundaries.json' not in inspect(workspace)['artifacts']
