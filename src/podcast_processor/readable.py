"""Local documents derived from the same immutable data as structured handoffs."""
import re
from decimal import Decimal
from pathlib import Path

from .planning_models import PlanningOutcome
from .publishing_models import validate_title_concepts
from .workspace import Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import Artifact, Run, WorkspaceState

VERSION = 'readable-handoff-v1'


def render_episode(path: Path, *, replace_title_edits: bool = False) -> WorkspaceState:
    workspace = Workspace(path)
    with ownership(workspace.path, 'render readable documents'):
        state = workspace.read()
        workspace.reconcile(state)
        if replace_title_edits and state.is_edited('titles.md'):
            source = state.artifacts.get('titles.json')
            if source is None:
                raise WorkspaceError('Readable title edit retained: no current structured title data to render.')
            validate_title_concepts(workspace.artifact_bytes(source).decode('utf-8'))
            state.runs.append(Run(id=identifier(), operation_id=identifier(), operation='render', status='completed',
                                  started_at=now(), finished_at=now(), inputs={'replace_title_edits': True}))
            state.artifacts.pop('titles.md')
            workspace.commit(state)
        return state


def plain(text: str) -> str:
    """Keep supplied copy literal when displayed as Markdown."""
    return re.sub(r'([\\`*_\[\]<>|])', r'\\\1', ' '.join(text.splitlines()))


def source_note(artifact: Artifact) -> str:
    return (f'\n## Source version\n\n[{artifact.name}]({artifact.name}) · version `{artifact.id}` '
            f'· SHA-256 `{artifact.sha256}`\n')


def render_titles(workspace: Workspace, state: WorkspaceState, source: Artifact) -> str:
    lines = ['# Title and thumbnail concepts', '']
    issues = state.publishing_issues.get('titles.json', [])
    lines.append('Status: Needs attention. ' + ' '.join(plain(issue) for issue in issues)
                 if issues else 'Status: Current' + (' operator-edited title data.' if source.status == 'human-edited' else '.'))
    try:
        concepts = validate_title_concepts(workspace.artifact_bytes(source).decode('utf-8'))
    except ValueError:
        lines.extend(['', 'Readable concepts unavailable: titles.json does not contain fifteen valid title concepts.',
                      'Next: correct the title data; the exact operator file is preserved.'])
    else:
        for index, concept in enumerate(concepts, 1):
            lines.extend(['', f'## Concept {index}', '', f'**Title:** {plain(concept.title)}', '',
                          f'**Thumbnail overlay:** {plain(concept.thumbnail_text)}', '',
                          f'- **Subject:** {plain(concept.visual_direction.subject)}',
                          f'- **Expression:** {plain(concept.visual_direction.expression)}',
                          f'- **Composition:** {plain(concept.visual_direction.composition)}', '',
                          f'**Why this pairing works:** {plain(concept.reasoning)}', '',
                          f'**Category:** {plain(concept.category)}'])
    return '\n'.join(lines) + '\n' + source_note(source)


def clock_time(value: Decimal) -> str:
    """Exact source timestamp, retaining the saved fractional seconds."""
    whole = int(value)
    fraction = format(value - whole, 'f').rstrip('0').removeprefix('0').rstrip('.')
    prefix = f'{whole // 3600}:{whole % 3600 // 60:02d}' if whole >= 3600 else f'{whole // 60:02d}'
    return f'{prefix}:{whole % 60:02d}{fraction}'


def duration(value: Decimal) -> str:
    seconds = format(value % 60, 'f')
    if '.' in seconds:
        seconds = seconds.rstrip('0').rstrip('.')
    return f'{int(value // 60)} min {seconds} s' if value >= 60 else f'{seconds} s'


def render_plan(workspace: Workspace, state: WorkspaceState, source: Artifact) -> str:
    outcome = PlanningOutcome.model_validate_json(workspace.artifact_bytes(source))
    lines = ['# Three-section proposal', '', f'Status: {outcome.status}.', '',
             'Proposal only; no audio has been exported.']
    proposal = outcome.proposal
    if proposal:
        lines.extend(['', 'Source ranges are timestamps in the original recording. '
                      'Expected finished lengths include the prepared transitions and applicable pauses.', '',
                      f'Finished length target: {duration(outcome.evidence.settings.minimum)} to '
                      f'{duration(outcome.evidence.settings.maximum)} per section.', '',
                      '| Section | Original recording range | Source part length | Expected finished length |',
                      '| --- | --- | --- | --- |'])
        for part in proposal.sections:
            lines.append(f'| {part.number} | {clock_time(part.source_start)} – {clock_time(part.source_end)} '
                         f'| {duration(part.part_duration)} | {duration(part.finished_duration)} |')
        lines.extend(['', 'The three consecutive parts cover the entire original recording once.', '',
                      '## Transitions included', ''])
        for part in proposal.sections:
            opening = 'episode opening' if part.opening == 'episode_start' else 'section opening'
            closing = (f', closing pause {duration(part.pause)}, closing transition {duration(part.closing_duration)}'
                       if part.closing_duration else '; original episode ending, with no added closing pause or transition')
            lines.append(f'- **Section {part.number}:** {opening} {duration(part.opening_duration)}{closing}.')
        if proposal.schema_version == 2:
            lines.extend(['', 'Section 3 retains the original episode ending after its opening transition.'])
        else:
            lines.extend(['', 'Historical assembly rule: this saved proposal includes a closing transition on section 3. '
                          'Run plan to evaluate the current ending rule.'])
        lines.extend(['', 'Prepared transition lengths already include their ending silence.', '', '## Why these cuts', ''])
        for index, boundary in enumerate(proposal.boundaries, 1):
            lines.extend([f'### Cut {index} · {clock_time(boundary.time)} in the original recording', '',
                          plain(boundary.reason), '', f'Evidence: {boundary.basis}.', ''])
        if any(boundary.basis == 'transcript-supported' for boundary in proposal.boundaries):
            lines.append('Transcript-supported cuts are suggestions; audio safety has not been independently verified.')
        if any(boundary.basis == 'fixture' for boundary in proposal.boundaries):
            lines.append('Fixture cuts use synthetic assumptions; they do not establish real audio safety.')
    else:
        from .completion import section_summary
        planning_run = next((run for run in reversed(state.runs) if run.operation == 'plan'), None)
        supplied = bool(planning_run and planning_run.inputs.get('explicit_evidence', True))
        summary = section_summary(outcome, supplied_evidence=supplied)
        reasons = outcome.reasons
        if (outcome.reason_code == 'duration-impossible' and outcome.evidence.source.duration is not None
                and len(outcome.overhead) == 3 and all(value is not None for value in outcome.overhead)):
            total = outcome.evidence.source.duration + sum((value for value in outcome.overhead if value is not None), Decimal(0))
            settings = outcome.evidence.settings
            if not settings.minimum * 3 <= total <= settings.maximum * 3:
                summary = ('Sections unavailable: duration constraints. The combined finished length would be '
                           f'{duration(total)}; three sections allow a total of '
                           f'{duration(settings.minimum * 3)} to {duration(settings.maximum * 3)}. '
                           f'Original recording length: {duration(outcome.evidence.source.duration)}.')
                reasons = []
        lines.extend(['', plain(summary), '', *[plain(reason) for reason in reasons if reason not in summary]])
        if 'Next:' not in summary:
            actions = {
                'missing-setup': 'run podcast-process setup, then process this workspace.',
                'duration-impossible': 'use the independent publishing outputs. A three-part proposal requires revised duration limits or transition settings.',
                'insufficient-boundaries': 'use the independent publishing outputs. Revisit planning only with additional supported boundary evidence or revised constraints.',
                'source-unavailable': 'supply matching source and corrected timed-transcript evidence, then run plan again.',
                'invalid-evidence': 'correct the supplied planning evidence, then run plan again.',
            }
            lines.extend(['', 'Next: ' + actions.get(outcome.reason_code or '', 'resolve the failure described in completion-report.md before resuming planning.')])
    if outcome.limitations:
        lines.extend(['', '## Evidence limitations', '', *['- ' + plain(item) for item in outcome.limitations]])
    return '\n'.join(lines) + '\n' + source_note(source)


def save_document(workspace: Workspace, state: WorkspaceState, name: str, document: str,
                  dependencies: dict[str, str]) -> bool:
    prior = state.artifacts.get(name)
    data = document.encode()
    if prior and prior.stage_version == VERSION and prior.dependencies == dependencies and prior.sha256 == digest(data):
        return False
    workspace.add_artifact(state, name, data, dependencies, VERSION)
    return True


def sync_titles(workspace: Workspace, state: WorkspaceState) -> bool:
    source = state.artifacts.get('titles.json')
    if state.is_edited('titles.md'):
        return False
    if source is None:
        return state.artifacts.pop('titles.md', None) is not None
    dependencies = {'titles_version': source.id, 'titles_sha256': source.sha256,
                    'issues': digest(json_bytes(state.publishing_issues.get('titles.json', [])))}
    return save_document(workspace, state, 'titles.md', render_titles(workspace, state, source), dependencies)


def sync_readable(workspace: Workspace, state: WorkspaceState) -> bool:
    """Version local views; unchanged data reuses the exact document artifact."""
    changed = sync_titles(workspace, state)
    source = state.artifacts.get('section-plan.json')
    if source is None:
        return (state.artifacts.pop('section-plan.md', None) is not None) or changed
    proposal = state.artifacts.get('section-boundaries.json')
    dependencies = {'plan_version': source.id, 'plan_sha256': source.sha256}
    if proposal:
        dependencies.update(proposal_version=proposal.id, proposal_sha256=proposal.sha256)
    return save_document(workspace, state, 'section-plan.md', render_plan(workspace, state, source), dependencies) or changed
