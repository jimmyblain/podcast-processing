"""Concise operator outcomes; the workspace report retains the full evidence."""
from .participants import current_transcript
from .planning_models import PlanningOutcome
from .workspace import Workspace
from .workspace_models import WorkspaceState


def section_summary(outcome: PlanningOutcome, *, supplied_evidence: bool = False) -> str:
    if outcome.status == 'valid':
        return 'Sections ready: three-part proposal (section-boundaries.json).'
    if outcome.status == 'needs-setup':
        missing = [name for name in ('episode_start', 'transition_in', 'transition_out')
                   if any(reason.startswith(name + ':') for reason in outcome.reasons)]
        action = ('Next: supply corrected --evidence FILE with approved prepared transitions when processing this workspace.'
                  if supplied_evidence else 'Needs setup: run podcast-process setup, then process this workspace.')
        return ('Sections need setup: ' + (', '.join(missing) or 'approved prepared transitions')
                + '. Discovery not run. ' + action)
    if outcome.reason_code == 'duration-impossible':
        return 'Sections unavailable: duration constraints. ' + outcome.reasons[0]
    if outcome.reason_code == 'insufficient-boundaries':
        search = 'Completed search' if outcome.discovery.status == 'completed' else 'Supplied boundary evaluation'
        return f'Sections unavailable: {search} could not support a valid three-part split. No cuts forced.'
    if outcome.reason_code == 'source-unavailable':
        return ('Sections incomplete: source/timing evidence is missing or inconsistent. Discovery not run. '
                + outcome.reasons[0] + ' Supply matching source and timed-transcript evidence before continuing.')
    if outcome.reason_code == 'invalid-evidence':
        return 'Sections incomplete: supplied planning evidence is invalid. Correct the evidence before continuing.'
    if outcome.discovery.status == 'failed':
        cause = outcome.discovery.summary.removeprefix('Candidate discovery failed: ')
        if 'API key required' in cause:
            action = 'Next: configure ANTHROPIC_API_KEY, then resume this workspace; the existing allowance is retained.'
        elif 'three discovery attempts exhausted' in cause:
            action = ('Next: resolve the provider/output failure in the report before explicitly authorizing --fresh; '
                      'unchanged resume cannot retry.')
        else:
            action = 'Next: correct the reported local/evidence failure before resuming this workspace.'
        return f'Sections failed: {cause} {action}'
    return 'Sections incomplete: no completed supported planning outcome. Check the saved report for missing prerequisites.'


def completion_summary(workspace: Workspace, state: WorkspaceState) -> str:
    run = state.runs[-1]
    names = [('transcript.txt', 'timed transcript'), ('description.md', 'description'),
             ('titles.json', 'title/thumbnail concepts'), ('chapters.txt', 'YouTube chapters')]
    ready = [label for name, label in names if name in state.artifacts and name not in state.publishing_issues
             and not (name == 'titles.json' and 'titles.md' in state.publishing_issues)]
    lines = [f'Status: {run.status}', 'Ready: ' + (', '.join(ready) or 'none')]
    for name, issues in state.publishing_issues.items():
        lines.append(f'{name} retained: ' + ' '.join(issues))
    if run.operation == 'process':
        artifact = state.artifacts.get('section-plan.json')
        if artifact:
            planning_run = next((item for item in reversed(state.runs) if item.operation == 'plan'), None)
            supplied = bool(planning_run and planning_run.inputs.get('explicit_evidence', True))
            lines.append(section_summary(PlanningOutcome.model_validate_json(workspace.artifact_bytes(artifact)),
                                         supplied_evidence=supplied))
        else:
            lines.append('Sections incomplete: planning did not produce an outcome; see the saved report.')
    if run.missing:
        lines.append('Missing required outputs: ' + ', '.join(run.missing))
    if 'transcript.json' in run.missing or 'transcript.txt' in run.missing:
        if state.transcription_operations:
            lines.append('Transcription unavailable: ' + (state.transcription_operations[-1].outcome or 'No usable result.'))
        else:
            lines.append('Transcription unavailable: supply or explicitly import matching timed-transcript evidence.')
    for stage, file in (('body', 'description.md'), ('titles', 'titles.json'), ('chapters', 'chapters.txt')):
        if file not in run.missing:
            continue
        label = {'body': 'Description', 'titles': 'Titles', 'chapters': 'Chapters'}[stage]
        if stage == 'body' and 'description-body.json' in state.evidence and 'chapters.txt' not in state.artifacts:
            lines.append('Description unavailable: a complete description requires chapters; body checkpoint saved.')
        elif stage == 'chapters' and any('preserved timing cannot support' in note for note in run.limitations):
            lines.append('Chapters unavailable: preserved timing cannot support three natural chapters. '
                         'Supply usable timed-transcript evidence before generating again.')
        elif any('API key required' in note and note.startswith(stage + ' unavailable') for note in run.limitations):
            lines.append(f'{label} unavailable: configure ANTHROPIC_API_KEY, then resume this workspace.')
        elif any('three publishing attempts exhausted' in note and note.startswith(stage + ' unavailable') for note in run.limitations):
            lines.append(f'{label} unavailable: three publishing attempts exhausted. Resolve the provider/output '
                         'failure in the report before explicitly authorizing --fresh; unchanged resume cannot retry.')
        else:
            lines.append(f'{label} unavailable: check the saved report for the failed or unattempted stage before continuing.')
    if any(note.startswith('Local publishing assembly unavailable:') for note in run.limitations):
        lines.append('Publishing assembly failed: check the supplied chapter labels, description length and local files in the report; correct them before continuing.')
    latest_publishing = {operation.stage: operation for operation in state.publishing_operations}
    for operation in latest_publishing.values():
        file = {'body': 'description-body.json', 'titles': 'titles.json', 'chapters': 'chapters.json'}[operation.stage]
        artifact = (state.artifacts if operation.stage == 'titles' else state.evidence).get(file)
        if (artifact and artifact.dependencies == operation.dependencies and len(operation.attempts) > 1
                and operation.attempts[-1].status == 'validated'):
            lines.append(f'Recovered: {operation.stage} succeeded after {len(operation.attempts) - 1} retry attempt(s).')
    if 'transcript.json' in state.artifacts:
        transcript = current_transcript(workspace, state)
        uncertain = sum(not word.timing_usable for word in transcript.words)
        unresolved = sum(speaker.participant is None for speaker in transcript.speakers)
        if uncertain:
            lines.append(f'Precision notes: {uncertain} words retained without usable precise timing; details saved.')
        if unresolved:
            lines.append(f'Identity notes: {unresolved} voices retain anonymous labels; optional refinement.')
    lines.extend([f'Workspace: {workspace.path}', f'Outputs: {workspace.path / "current"}',
                  f'Detailed report: {workspace.path / "current/completion-report.md"}'])
    documents = [name for name in ('titles.md', 'section-plan.md') if name in state.artifacts]
    if documents:
        lines.append('Readable documents: ' + ', '.join(documents))
    if run.status == 'completed':
        lines.append('Next: generate the publishing package with podcast-process generate "' + str(workspace.path) + '".'
                     if run.operation == 'transcribe' else 'Next: use the ready publishing outputs.')
    else:
        lines.append('Next: resolve the missing prerequisites or failed stages above; use the saved report for details.')
    return '\n'.join(lines)
