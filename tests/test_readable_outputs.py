"""Readable handoffs through public episode operations and committed artifacts."""
import json
import pytest

from podcast_processor.cli import app
from test_publishing_package import episode, generate, publishing, runner
from test_workspace import inspect
from test_section_planning import episode as planning_episode, plan


def test_all_fifteen_pairings_are_readable_and_reused_from_the_committed_titles(tmp_path, publishing):
    workspace = episode(tmp_path)
    result = generate(workspace)
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    document = (workspace / 'current/titles.md').read_text()
    titles = json.loads((workspace / 'current/titles.json').read_text())
    assert document.count('## Concept ') == 15
    for index, concept in enumerate(titles, 1):
        block = document.split(f'## Concept {index}\n')[1].split('## Concept ')[0]
        for value in (concept['title'], concept['category'], concept['thumbnail_text'],
                      *concept['visual_direction'].values(), concept['reasoning']):
            assert value in block
    artifact = state['artifacts']['titles.md']
    assert artifact['dependencies']['titles_version'] == state['artifacts']['titles.json']['id']
    assert state['artifacts']['titles.json']['id'] in document
    assert 'titles.md' in result.output
    assert generate(workspace).exit_code == 0
    assert inspect(workspace)['artifacts'] == state['artifacts']
    assert len(publishing) == 3


@pytest.mark.parametrize('case,status,explanation', [
    ('missing-setup', 'needs-setup', 'Discovery not run'),
    ('duration-impossible', 'unavailable', 'duration constraints'),
    ('insufficient-boundaries', 'unavailable', 'Supplied boundary evaluation'),
    ('stale', 'unavailable', 'stale corrected timed transcript'),
])
def test_unavailable_document_has_an_honest_reason_and_next_action_without_ranges(tmp_path, case, status, explanation):
    workspace, evidence = planning_episode(tmp_path, duration='3369.842358' if case == 'duration-impossible' else '2100')
    if case == 'missing-setup':
        evidence['transition_in'] = None
    elif case == 'insufficient-boundaries':
        evidence['boundaries'] = []
    elif case == 'stale':
        evidence['transcript_sha256'] = 'old-transcript'
    outcome = plan(workspace, evidence, expected_exit=1 if case in ('missing-setup', 'stale') else 0)
    document = (workspace / 'current/section-plan.md').read_text()
    assert outcome['status'] == status
    assert f'Status: {status}' in document
    assert explanation in document
    assert 'Next:' in document
    if case == 'duration-impossible':
        assert '56 min 42.842358 s' in document
        assert '30 min 0 s to 54 min 0 s' in document
        assert '3402.842358 seconds' not in document
    assert '| Section |' not in document and '### Cut ' not in document
    assert not (workspace / 'current/section-boundaries.json').exists()
    before = inspect(workspace)
    assert runner.invoke(app, ['render', str(workspace)]).exit_code == 0
    assert inspect(workspace)['artifacts'] == before['artifacts']
    assert before['publishing_operations'] == before['transcription_operations'] == before['discovery_operations'] == []


def test_section_document_explains_source_ranges_finished_lengths_and_selected_cuts(tmp_path):
    workspace, evidence = planning_episode(tmp_path, duration='2100.125', cuts=('600.25', '1300.125'))
    evidence['boundaries'][0]['reason'] = 'The opening thought ends before the next topic begins.'
    evidence['boundaries'][1]['reason'] = 'The second topic resolves before the closing discussion.'
    outcome = plan(workspace, evidence)
    state = inspect(workspace)
    document = (workspace / 'current/section-plan.md').read_text()
    for row in ('| 1 | 00:00 – 10:00.25 | 10 min 0.25 s | 10 min 16.75 s |',
                '| 2 | 10:00.25 – 21:40.125 | 11 min 39.875 s | 11 min 51.375 s |',
                '| 3 | 21:40.125 – 35:00.125 | 13 min 20 s | 13 min 25 s |'):
        assert row in document
    assert 'original recording' in document
    assert 'Proposal only; no audio has been exported.' in document
    assert 'Section 3 retains the original episode ending' in document
    for cut in outcome['proposal']['boundaries']:
        assert cut['reason'] in document
    assert 'fixture' in document.lower()
    artifact = state['artifacts']['section-plan.md']
    assert artifact['dependencies']['plan_version'] == state['artifacts']['section-plan.json']['id']
    assert artifact['dependencies']['proposal_version'] == state['artifacts']['section-boundaries.json']['id']
    result = runner.invoke(app, ['plan', str(workspace)])
    assert result.exit_code == 0, result.output
    assert 'section-plan.md' in result.output
    assert inspect(workspace)['artifacts'] == state['artifacts']


def test_local_render_rebuilds_missing_documents_without_service_requests(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    document = (workspace / 'current/titles.md').read_bytes()
    (workspace / 'current/titles.md').unlink()
    result = runner.invoke(app, ['render', str(workspace)])
    assert result.exit_code == 0, result.output
    assert 'titles.md' in result.output
    assert (workspace / 'current/titles.md').read_bytes() == document
    after = inspect(workspace)
    assert after['artifacts']['titles.json'] == before['artifacts']['titles.json']
    for ledger in ('publishing_operations', 'transcription_operations', 'discovery_operations'):
        assert after[ledger] == before[ledger]
    assert len(publishing) == 3


def test_readable_title_edits_stay_exact_through_render_resume_and_explicit_replacement(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    before = inspect(workspace)
    path = workspace / 'current/titles.md'
    edited = b'An operator-selected title and notes.\r\n\r\n' + path.read_bytes()
    path.write_bytes(edited)
    assert runner.invoke(app, ['render', str(workspace)]).exit_code == 0
    state = inspect(workspace)
    artifact = state['artifacts']['titles.md']
    assert path.read_bytes() == edited
    assert artifact['status'] == 'human-edited'
    assert artifact['edited_from'] == before['artifacts']['titles.md']['id']
    assert 'agreement' in ' '.join(state['publishing_issues']['titles.md'])
    result = generate(workspace)
    assert result.exit_code == 1
    assert 'title/thumbnail concepts' not in result.output.split('Ready: ')[1].splitlines()[0]
    assert path.read_bytes() == edited
    assert len(publishing) == 3
    path.unlink()
    inspect(workspace)
    assert path.read_bytes() == edited
    assert generate(workspace, '--fresh', '--only', 'titles').exit_code == 0
    after = inspect(workspace)
    assert (workspace / artifact['path']).read_bytes() == edited
    assert after['artifacts']['titles.md']['status'] == 'completed'
    assert after['artifacts']['titles.md']['dependencies']['titles_version'] == after['artifacts']['titles.json']['id']
    assert after['artifacts']['description.md'] == before['artifacts']['description.md']
    assert after['artifacts']['chapters.txt'] == before['artifacts']['chapters.txt']
    assert len(publishing) == 4


def test_stale_title_data_labels_both_generated_and_edited_readable_documents(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    titles = workspace / 'current/titles.json'
    titles.write_bytes(titles.read_bytes() + b'\r\n')
    inspect(workspace)
    transcript = tmp_path / 'timed.json'
    data = json.loads(transcript.read_text())
    data['segments'][0]['text'] += ' A changed episode topic.'
    transcript.write_text(json.dumps(data))
    result = runner.invoke(app, ['import', str(transcript), '--workspace', str(workspace)])
    assert result.exit_code == 0, result.output
    document = workspace / 'current/titles.md'
    assert 'stale' in document.read_text()
    assert 'Needs attention' in document.read_text()
    edited = document.read_bytes() + b'\r\nOperator notes.\r\n'
    document.write_bytes(edited)
    state = inspect(workspace)
    assert 'stale' in ' '.join(state['publishing_issues']['titles.md'])
    assert document.read_bytes() == edited
    assert len(publishing) == 3


def test_explicit_local_rerender_replaces_readable_edits_without_new_title_generation(tmp_path, publishing):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/titles.md'
    generated = path.read_bytes()
    edited = b'Keep these exact notes in history.\r\n'
    path.write_bytes(edited)
    result = runner.invoke(app, ['render', str(workspace), '--replace-title-edits'])
    assert result.exit_code == 0, result.output
    assert path.read_bytes() == generated
    state = inspect(workspace)
    saved_edit = next(a for a in state['history'] if a['name'] == 'titles.md' and a['status'] == 'human-edited')
    assert (workspace / saved_edit['path']).read_bytes() == edited
    assert state['publishing_issues'] == {}
    assert len(publishing) == 3


@pytest.mark.parametrize('invalid', [False, True])
def test_current_structured_title_edits_update_the_readable_document_locally(tmp_path, publishing, invalid):
    workspace = episode(tmp_path)
    assert generate(workspace).exit_code == 0
    path = workspace / 'current/titles.json'
    data = json.loads(path.read_text())
    data[0]['title'] = 'An Operator Title About Listening'
    edited = b'{incomplete\r\n' if invalid else json.dumps(data).encode() + b'\r\n'
    path.write_bytes(edited)
    result = runner.invoke(app, ['render', str(workspace)])
    assert result.exit_code == 0, result.output
    state = inspect(workspace)
    document = (workspace / 'current/titles.md').read_text()
    assert path.read_bytes() == edited
    assert state['artifacts']['titles.md']['dependencies']['titles_version'] == state['artifacts']['titles.json']['id']
    if invalid:
        assert 'Readable concepts unavailable' in document
        assert '## Concept ' not in document
    else:
        assert 'An Operator Title About Listening' in document
        assert 'Current operator-edited title data' in document
    assert len(publishing) == 3


def test_corrected_planning_replaces_both_views_without_stale_ranges_or_new_copy(tmp_path, publishing):
    from test_participant_corrections import correct
    workspace, evidence = planning_episode(tmp_path)
    generate(workspace, '--only', 'titles')
    plan(workspace, evidence)
    before = inspect(workspace)
    old_document = (workspace / 'current/section-plan.md').read_bytes()
    correct(workspace, [{'op': 'retime', 'word_id': 'w1', 'start': 605, 'end': 1298,
                         'evidence': 'Synthetic timing correction'}])
    corrected = inspect(workspace)
    assert not (workspace / 'current/section-plan.md').exists()
    assert corrected['artifacts']['titles.md'] == before['artifacts']['titles.md']
    plan(workspace, evidence, expected_exit=1)
    assert 'stale corrected timed transcript' in (workspace / 'current/section-plan.md').read_text()
    evidence['transcript_sha256'] = corrected['artifacts']['transcript.json']['sha256']
    evidence['boundaries'][0]['time'] = '602'
    outcome = plan(workspace, evidence)
    assert outcome['proposal']['sections'][0]['source_end'] == '602'
    document = (workspace / 'current/section-plan.md').read_text()
    assert '| 1 | 00:00 – 10:02 | 10 min 2 s | 10 min 18.5 s |' in document
    after = inspect(workspace)
    assert after['artifacts']['section-plan.md']['dependencies']['plan_version'] == after['artifacts']['section-plan.json']['id']
    assert (workspace / before['artifacts']['section-plan.md']['path']).read_bytes() == old_document
    assert after['publishing_operations'] == before['publishing_operations']
    assert after['transcription_operations'] == before['transcription_operations']
    assert len(publishing) == 1


def test_hour_timestamps_and_transcript_supported_cuts_keep_their_evidence_label(tmp_path):
    workspace, evidence = planning_episode(tmp_path, duration='4200', cuts=('1200', '2400'))
    evidence['settings'] = {'minimum': '600', 'maximum': '2000'}
    for boundary in evidence['boundaries']:
        boundary['basis'] = 'transcript-supported'
    plan(workspace, evidence)
    document = (workspace / 'current/section-plan.md').read_text()
    assert '| 3 | 40:00 – 1:10:00 | 30 min 0 s | 30 min 5 s |' in document
    assert 'audio safety has not been independently verified' in document


def test_unavailable_plan_keeps_individual_section_limits_when_combined_length_fits(tmp_path):
    workspace, evidence = planning_episode(tmp_path)
    evidence['episode_start']['duration'] = '1100'
    outcome = plan(workspace, evidence)
    document = (workspace / 'current/section-plan.md').read_text()
    assert outcome['reason_code'] == 'duration-impossible'
    assert 'Section 1' in document
    assert 'no positive source-part budget' in document
    assert '| Section |' not in document
