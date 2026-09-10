"""Source-relative planning through the CLI and its exported proposal contract.

All durations, word positions and editorial judgments here are synthetic fixtures.
They cannot establish natural-cut accuracy on real audio.
"""
import json
from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from podcast_processor.cli import app
from podcast_processor.planning_models import SectionProposal
from test_workspace import authority, inspect, runner


def episode(tmp_path, duration='2100', cuts=('600', '1300'), mutate=None):
    positions = [Decimal('30'), *(Decimal(cut) + 5 for cut in cuts)]
    ends = [*(Decimal(cut) - 1 for cut in cuts), Decimal(duration) - 10]
    words = [{'id': f'w{i}', 'word': f'Topic{i}.', 'start': float(start), 'end': float(end),
              'turn_id': f't{i}', 'speaker': 'A', 'timing_usable': True}
             for i, (start, end) in enumerate(zip(positions, ends))]
    data = {'schema_version': 2, 'revision': 'synthetic-timing-v1', 'duration': float(duration),
            'speakers': [{'id': 'A'}], 'words': words,
            'segments': [{'id': f't{i}', 'text': word['word'], 'start': word['start'], 'end': word['end'],
                          'word_ids': [word['id']], 'speaker': 'A', 'timing_usable': True}
                         for i, word in enumerate(words)],
            'provenance': {'source_path': 'synthetic-original.wav', 'original_hash': 'synthetic',
                           'original_schema': 'synthetic-v2', 'source_fingerprint': 'fixture-source'}}
    if mutate:
        mutate(data)
    path = tmp_path / 'timed.json'
    path.write_text(json.dumps(data))
    result = runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), *authority(tmp_path)])
    assert result.exit_code == 0, result.output
    workspace = next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())
    state = inspect(workspace)
    evidence = {'source': {'revision': state['source_revision'], 'fingerprint': 'fixture-source',
                           'duration': duration, 'basis': 'fixture', 'evidence': 'Synthetic source assumption'},
                'transcript_sha256': state['artifacts']['transcript.json']['sha256'],
                'boundaries': [{'id': f'b{i}', 'time': cut, 'before_word': f'w{i}', 'after_word': f'w{i + 1}',
                                'complete_thought': True, 'natural_topic_boundary': True,
                                'reason': 'Synthetic complete thought and topic change', 'basis': 'fixture'}
                               for i, cut in enumerate(cuts)]}
    for name, duration in [('episode_start', '10'), ('transition_in', '5'), ('transition_out', '5')]:
        evidence[name] = {'asset_revision': f'{name}-fixture', 'prepared_revision': f'{name}-prepared-fixture',
                          'duration': duration, 'ending_silence': '2.5', 'preserves_decay': True,
                          'replaces_excess_tail': True, 'basis': 'fixture', 'evidence': 'Synthetic prepared duration'}
    return workspace, evidence


def plan(workspace, evidence):
    path = workspace.parent / 'planning.json'
    path.write_text(json.dumps(evidence))
    result = runner.invoke(app, ['plan', str(workspace), '--evidence', str(path)])
    assert result.exit_code == 0, (result.output, result.exception)
    return json.loads((workspace / 'current/section-plan.json').read_bytes())


def test_unequal_sections_keep_original_offsets_music_pauses_and_source_tail(tmp_path):
    workspace, evidence = episode(tmp_path)
    before = inspect(workspace)
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'valid'
    proposal = SectionProposal.model_validate_json((workspace / 'current/section-boundaries.json').read_bytes())
    assert [(s.source_start, s.source_end) for s in proposal.sections] == [(0, 600), (600, 1300), (1300, 2100)]
    assert [s.finished_duration for s in proposal.sections] == [Decimal('616.5'), Decimal('711.5'), Decimal('805')]
    assert outcome['overhead'] == ['16.5', '11.5', '5']
    assert outcome['source_part_limits'] == [['583.5', '1063.5'], ['588.5', '1068.5'], ['595', '1075']]
    assert all(item in inspect(workspace)['artifacts'].items() for item in before['artifacts'].items())
    assert 'synthetic' in ' '.join(proposal.limitations).lower()
    assert 'pending evaluation' in (workspace / 'current/completion-report.md').read_text()
    first = inspect(workspace)
    assert plan(workspace, evidence) == outcome
    assert inspect(workspace)['artifacts'] == first['artifacts']
    assert inspect(workspace)['publishing_operations'] == []


def test_final_section_runs_to_original_end_without_added_pause_or_transition_out(tmp_path):
    workspace, evidence = episode(tmp_path, duration='2375')
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'valid'
    final = outcome['proposal']['sections'][2]
    assert final['source_start'] == '1300'
    assert final['source_end'] == '2375'
    assert final['opening_duration'] == '5'
    assert final['pause'] == '0'
    assert final['closing_duration'] == '0'
    assert final['finished_duration'] == '1080'
    assert outcome['overhead'] == ['16.5', '11.5', '5']
    assert outcome['proposal']['schema_version'] == 2
    assert 'no added closing pause or transition-out' in (workspace / 'current/completion-report.md').read_text()


def test_historical_proposal_remains_readable_without_allowing_old_ending_in_new_proposals(tmp_path):
    workspace, evidence = episode(tmp_path)
    historical = deepcopy(plan(workspace, evidence)['proposal'])
    historical['schema_version'] = 1
    historical['sections'][2].update(pause='1.5', closing_duration='5', finished_duration='811.5')
    assert SectionProposal.model_validate(historical).sections[2].finished_duration == Decimal('811.5')
    historical['schema_version'] = 2
    with pytest.raises(ValidationError):
        SectionProposal.model_validate(historical)


@pytest.mark.parametrize('duration,cuts,expected', [
    ('2100', ('583.5', '1300'), ['600', '728', '805']),
    ('2400', ('1063.5', '1700'), ['1080', '648', '705']),
    ('1900', ('600', '1188.5'), ['616.5', '600', '716.5']),
    ('2300', ('600', '1668.5'), ['616.5', '1080', '636.5']),
    ('1895', ('600', '1300'), ['616.5', '711.5', '600']),
    ('2375', ('600', '1300'), ['616.5', '711.5', '1080']),
])
def test_each_finished_section_accepts_inclusive_limits(tmp_path, duration, cuts, expected):
    workspace, evidence = episode(tmp_path, duration, cuts)
    result = plan(workspace, evidence)
    assert result['status'] == 'valid'
    assert [Decimal(p['finished_duration']) for p in result['proposal']['sections']] == list(map(Decimal, expected))


@pytest.mark.parametrize('duration,cuts', [
    ('2100', ('583.499999', '1300')), ('2400', ('1063.500001', '1700')),
    ('1900', ('600', '1188.499999')), ('2300', ('600', '1668.500001')),
    ('1894.999999', ('600', '1300')), ('2375.000001', ('600', '1300')),
])
def test_just_outside_each_finished_section_limit_never_exposes_proposal(tmp_path, duration, cuts):
    workspace, evidence = episode(tmp_path, duration, cuts)
    result = plan(workspace, evidence)
    assert result['status'] == 'unavailable'
    assert 'No pair' in ' '.join(result['reasons'])
    assert 'section-boundaries.json' not in inspect(workspace)['artifacts']
    assert not (workspace / 'current/section-boundaries.json').exists()


@pytest.mark.parametrize('duration,expected', [
    ('3369.842358', '129.842358 seconds before overhead'),
    ('3220', 'exceeding capacity 3240 by 13'),
    ('1700', 'below required 1800 by 67'),
])
def test_impossibility_explains_source_and_transition_budgets(tmp_path, duration, expected):
    workspace, evidence = episode(tmp_path, duration, ('600', '1200'))
    original = inspect(workspace)['artifacts']
    result = plan(workspace, evidence)
    assert result['status'] == 'unavailable'
    assert expected in ' '.join(result['reasons'])
    assert result['evidence']['source']['duration'] == duration
    assert result['overhead'] == ['16.5', '11.5', '5']
    assert all(item in inspect(workspace)['artifacts'].items() for item in original.items())
    assert 'section-boundaries.json' not in inspect(workspace)['artifacts']
    assert inspect(workspace)['runs'][-1]['status'] == 'completed'


@pytest.mark.parametrize('field,value', [
    ('duration', None), ('prepared_revision', None), ('basis', 'unknown'), ('evidence', ''),
    ('ending_silence', None), ('ending_silence', '5'), ('preserves_decay', False),
    ('replaces_excess_tail', False),
])
def test_missing_or_unprepared_transition_evidence_is_reported(tmp_path, field, value):
    workspace, evidence = episode(tmp_path)
    evidence['transition_out'][field] = value
    result = plan(workspace, evidence)
    assert result['status'] == 'unavailable'
    assert any('transition_out' in reason for reason in result['reasons'])
    if field == 'duration':
        assert result['overhead'] == [None, None, '5']


@pytest.mark.parametrize('field,value', [('duration', None), ('fingerprint', None), ('basis', 'unknown'),
                                        ('fingerprint', 'another-source'), ('duration', '2101'), ('revision', 'old')])
def test_missing_or_mismatched_original_source_evidence_is_reported(tmp_path, field, value):
    workspace, evidence = episode(tmp_path)
    evidence['source'][field] = value
    result = plan(workspace, evidence)
    assert result['status'] == 'unavailable'
    assert result['reasons']


@pytest.mark.parametrize('mutation', ['unknown', 'uncertain', 'overlap', 'incomplete', 'not-natural', 'inside-word', 'safe-interval'])
def test_unsupported_cut_evidence_is_never_used(tmp_path, mutation):
    def mutate(data):
        if mutation == 'unknown':
            data['words'][1].update(start=None, end=None, timing_usable=False)
        elif mutation == 'uncertain':
            data['words'][1]['timing_uncertainty'] = ['Unknown alignment precision']
        elif mutation == 'overlap':
            data['words'][1]['start'] = 598
            data['segments'][1]['start'] = 598
    workspace, evidence = episode(tmp_path, mutate=mutate)
    if mutation == 'incomplete':
        evidence['boundaries'][0]['complete_thought'] = False
    elif mutation == 'not-natural':
        evidence['boundaries'][0]['natural_topic_boundary'] = False
    elif mutation == 'inside-word':
        evidence['boundaries'][0]['time'] = '598'
    elif mutation == 'safe-interval':
        evidence['boundaries'][0].update(basis='source-reviewed', safe_start='601', safe_end='604')
    result = plan(workspace, evidence)
    assert result['status'] == 'unavailable'
    assert result['rejected_boundaries']['b0']


def test_selects_supported_alternative_and_prioritizes_natural_strength_over_equality(tmp_path):
    workspace, evidence = episode(tmp_path, cuts=('600', '700', '1300', '1400'))
    # The equal 700/700/700 source split is valid but has weaker natural evidence.
    for index in (0, 2):
        evidence['boundaries'][index]['strength'] = 3
    outcome = plan(workspace, evidence)
    assert [b['time'] for b in outcome['proposal']['boundaries']] == ['600', '1300']
    # Removing one natural-cut assertion chooses another supported pair immediately.
    evidence['boundaries'][0]['complete_thought'] = False
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'valid'
    assert [b['time'] for b in outcome['proposal']['boundaries']] == ['700', '1300']


@pytest.mark.parametrize('change', ['gap', 'repetition', 'truncation', 'extra-part', 'opening', 'pause', 'tail', 'duration', 'missing-asset'])
def test_public_proposal_contract_rejects_invalid_coverage_and_accounting(tmp_path, change):
    workspace, evidence = episode(tmp_path)
    data = deepcopy(plan(workspace, evidence)['proposal'])
    if change == 'gap':
        data['sections'][1]['source_start'] = '601'
    elif change == 'repetition':
        data['sections'][1]['source_start'] = '599'
    elif change == 'truncation':
        data['sections'][2]['source_end'] = '2099'
    elif change == 'extra-part':
        data['sections'].append(data['sections'][-1])
    elif change == 'opening':
        data['sections'][1]['opening_duration'] = '10'
    elif change == 'pause':
        data['sections'][0]['pause'] = '0'
    elif change == 'tail':
        data['evidence']['transition_out']['ending_silence'] = '5'
    elif change == 'missing-asset':
        data['evidence']['transition_out']['duration'] = None
    else:
        data['sections'][0]['finished_duration'] = '619'
    with pytest.raises(ValidationError):
        SectionProposal.model_validate(data)


@pytest.mark.parametrize('change', ['asset', 'prepared-revision', 'duration', 'pause', 'minimum', 'maximum'])
def test_planning_input_changes_preserve_independent_publishing_and_transcript(tmp_path, monkeypatch, change):
    from podcast_processor.llm import ClaudeClient
    from publishing_responses import response_for
    calls = []
    def generate(self, prompt, max_tokens=4096):
        calls.append(prompt)
        return response_for(prompt)
    monkeypatch.setattr(ClaudeClient, 'generate', generate)
    workspace, evidence = episode(tmp_path)
    result = runner.invoke(app, ['generate', str(workspace), '--only', 'titles', '--api-key', 'fake'])
    # Selected titles are usable, while the unrequested complete package is partial.
    assert result.exit_code == 1, result.output
    assert 'titles.json' in inspect(workspace)['artifacts']
    plan(workspace, evidence)
    before = inspect(workspace)
    if change == 'asset':
        evidence['episode_start']['asset_revision'] = 'replacement-source-asset'
    elif change == 'prepared-revision':
        evidence['episode_start']['prepared_revision'] = 'replacement-preparation'
    elif change == 'duration':
        evidence['episode_start']['duration'] = '1000'
    else:
        evidence['settings'] = {'pause': '2', 'minimum': '610', 'maximum': '1070'}
        evidence['settings'] = {change: evidence['settings'][change]}
    outcome = plan(workspace, evidence)
    after = inspect(workspace)
    assert after['artifacts']['section-plan.json']['id'] != before['artifacts']['section-plan.json']['id']
    for name in ('titles.json', 'transcript.json', 'transcript.txt', 'import-original.json'):
        assert after['artifacts'][name] == before['artifacts'][name]
    assert len(calls) == 1
    assert after['publishing_operations'] == before['publishing_operations']
    assert after['transcription_operations'] == before['transcription_operations']
    assert plan(workspace, evidence) == outcome
    assert inspect(workspace)['artifacts'] == after['artifacts']
    if change == 'duration':
        assert outcome['status'] == 'unavailable'
        assert 'section-boundaries.json' not in after['artifacts']
        assert not (workspace / 'current/section-boundaries.json').exists()
        assert (workspace / before['artifacts']['section-boundaries.json']['path']).is_file()


def test_correction_invalidates_boundary_evidence_and_leaves_copy_reusable(tmp_path, monkeypatch):
    from podcast_processor.llm import ClaudeClient
    from publishing_responses import response_for
    from test_participant_corrections import correct
    monkeypatch.setattr(ClaudeClient, 'generate', lambda self, prompt, max_tokens=4096: response_for(prompt))
    workspace, evidence = episode(tmp_path)
    assert runner.invoke(app, ['generate', str(workspace), '--only', 'titles', '--api-key', 'fake']).exit_code == 1
    assert 'titles.json' in inspect(workspace)['artifacts']
    plan(workspace, evidence)
    before = inspect(workspace)
    correct(workspace, [{'op': 'retime', 'word_id': 'w1', 'start': 605, 'end': 1298,
                         'evidence': 'Synthetic correction for invalidation acceptance'}])
    corrected = inspect(workspace)
    assert 'section-plan.json' not in corrected['artifacts']
    assert 'section-boundaries.json' not in corrected['artifacts']
    assert corrected['artifacts']['titles.json'] == before['artifacts']['titles.json']
    assert corrected['artifacts']['import-original.json'] == before['artifacts']['import-original.json']
    stale = plan(workspace, evidence)
    assert stale['status'] == 'unavailable'
    assert 'stale corrected timed transcript' in ' '.join(stale['reasons'])
    evidence['transcript_sha256'] = corrected['artifacts']['transcript.json']['sha256']
    assert plan(workspace, evidence)['status'] == 'valid'


def test_unknown_word_timing_uses_another_supported_natural_boundary(tmp_path):
    def mutate(data):
        data['words'][0].update(start=None, end=None, timing_usable=False)
    workspace, evidence = episode(tmp_path, cuts=('600', '700', '1300', '1400'), mutate=mutate)
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'valid'
    assert 'timing is unknown' in outcome['rejected_boundaries']['b0']
    assert [b['time'] for b in outcome['proposal']['boundaries']] == ['700', '1400']


@pytest.mark.parametrize('filename', ['section-plan.json', 'section-boundaries.json'])
def test_direct_edits_preserved_without_leaving_validity_claims(tmp_path, filename):
    workspace, evidence = episode(tmp_path)
    plan(workspace, evidence)
    edited = b'\xff\x00 Directly edited planning evidence\r\n'
    (workspace / 'current' / filename).write_bytes(edited)
    recovered = inspect(workspace)
    assert 'section-boundaries.json' not in recovered['artifacts']
    assert 'section-plan.json' not in recovered['artifacts']
    saved_edit = next(a for a in recovered['history'] if a['status'] == 'human-edited')
    assert (workspace / saved_edit['path']).read_bytes() == edited
    assert plan(workspace, evidence)['status'] == 'valid'


def test_missing_transition_and_natural_candidates_finish_without_review(tmp_path):
    workspace, evidence = episode(tmp_path)
    evidence['transition_in'] = None
    evidence['boundaries'] = []
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'unavailable'
    assert outcome['overhead'] == ['16.5', None, None]
    assert 'transition_in' in ' '.join(outcome['reasons'])


def test_invalid_configuration_preserves_previous_valid_output(tmp_path):
    workspace, evidence = episode(tmp_path)
    plan(workspace, evidence)
    before = inspect(workspace)
    evidence['settings'] = {'minimum': 1100, 'maximum': 1080}
    path = workspace.parent / 'invalid.json'
    path.write_text(json.dumps(evidence))
    result = runner.invoke(app, ['plan', str(workspace), '--evidence', str(path)])
    assert result.exit_code == 1
    assert inspect(workspace)['artifacts'] == before['artifacts']


def test_timing_outside_explicit_source_duration_cannot_support_a_proposal(tmp_path):
    def mutate(data):
        data['duration'] = None
        data['words'][-1]['end'] = 2110
        data['segments'][-1]['end'] = 2110
    workspace, evidence = episode(tmp_path, mutate=mutate)
    outcome = plan(workspace, evidence)
    assert outcome['status'] == 'unavailable'
    assert 'outside the original-source duration' in ' '.join(outcome['reasons'])
