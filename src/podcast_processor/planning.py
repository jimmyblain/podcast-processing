"""Deterministic planning from explicit natural-cut and prepared-duration evidence."""
from decimal import Decimal
from itertools import combinations
from pathlib import Path

from .participants import current_transcript
from .planning_models import (
    FinishedSection, NaturalBoundary, PlanningEvidence, PlanningOutcome, SectionProposal,
)
from .workspace import Workspace, digest, identifier, now, ownership
from .workspace_models import PreservedSegment, PreservedTranscript, PreservedWord, Run, WorkspaceState

VERSION = 'section-planner-v1'
PLAN_FILES = ('section-plan.json', 'section-boundaries.json')
LIMITATIONS = [
    'No transition preparation, trimming, media cutting, stitching or export was performed.',
    'Natural-boundary assertions are supplied evidence, not inferred from punctuation or waveform silence.',
    'Source-audited point error <=1.0 second and cuts inside independently reviewed safe intervals remain pending evaluation.',
]


def boundary_problem(boundary: NaturalBoundary, transcript: PreservedTranscript, duration: Decimal) -> str | None:
    if not boundary.complete_thought or not boundary.natural_topic_boundary:
        return 'Incomplete thought or unsupported natural topic boundary.'
    if not 0 < boundary.time < duration:
        return 'Boundary must be internal to the original source timeline.'
    if boundary.basis == 'source-reviewed' and (
            boundary.safe_start is None or boundary.safe_end is None
            or not 0 <= boundary.safe_start <= boundary.time <= boundary.safe_end <= duration):
        return 'Source-reviewed evidence requires a containing safe interval on the source timeline.'
    words = transcript.words
    indices = {word.id: index for index, word in enumerate(words) if word.id is not None}
    before_index, after_index = indices.get(boundary.before_word), indices.get(boundary.after_word)
    if before_index is None or after_index is None or after_index != before_index + 1:
        return 'Boundary must reference consecutive words in the corrected timed transcript.'
    before, after = words[before_index], words[after_index]
    if any(not w.timing_usable or w.timing_uncertainty or w.start is None or w.end is None for w in (before, after)):
        return 'Adjacent word timing is unknown or uncertain.'
    assert before.end is not None and after.start is not None
    if not Decimal(str(before.end)) <= boundary.time <= Decimal(str(after.start)):
        return 'Cut crosses adjacent speech or does not lie between the referenced words.'
    turns = {turn.id: turn for turn in transcript.segments}
    for index, word in enumerate(words):
        if word.timing_usable and not word.timing_uncertainty and word.start is not None and word.end is not None:
            if ((index <= before_index and Decimal(str(word.end)) > boundary.time)
                    or (index >= after_index and Decimal(str(word.start)) < boundary.time)):
                return 'Cut crosses overlapping or out-of-order word evidence.'
        else:
            turn = turns.get(word.turn_id)
            if (turn is None or turn.start is None or turn.end is None
                    or (index <= before_index and Decimal(str(turn.end)) > boundary.time)
                    or (index >= after_index and Decimal(str(turn.start)) < boundary.time)):
                return 'Uncertain word timing cannot be bounded away from this cut.'
    for turn in transcript.segments:
        if not turn.word_ids and (turn.start is None or turn.end is None
                                 or Decimal(str(turn.start)) < boundary.time < Decimal(str(turn.end))):
            return 'Unaligned speech could cross this cut.'
    return None


def propose(evidence: PlanningEvidence, transcript: PreservedTranscript,
            state: WorkspaceState, dependencies: dict[str, str]) -> PlanningOutcome:
    reasons: list[str] = []
    limitations = list(LIMITATIONS)
    source = evidence.source
    actual_source = next(s for s in state.sources if s.id == state.source_revision)
    if source.revision != state.source_revision:
        reasons.append('Source revision does not match the current episode.')
    if evidence.transcript_sha256 != state.artifacts['transcript.json'].sha256:
        reasons.append('Boundary evidence references a stale corrected timed transcript; supply matching evidence.')
    if source.basis == 'unknown' or not source.evidence.strip() or not source.fingerprint or source.duration is None:
        reasons.append('Original-source identity/duration evidence is unavailable.')
    if actual_source.fingerprint and source.fingerprint != actual_source.fingerprint:
        reasons.append('Source fingerprint does not match preserved original-source identity.')
    if transcript.provenance.source_fingerprint and source.fingerprint != transcript.provenance.source_fingerprint:
        reasons.append('Timed transcript source correspondence does not match the supplied fingerprint.')
    recorded_duration = (actual_source.properties or {}).get('format', {}).get('duration')
    if recorded_duration is not None and source.duration != Decimal(str(recorded_duration)):
        reasons.append('Supplied source duration differs from the preserved original-source duration.')
    if transcript.duration is not None and source.duration is not None and source.duration != Decimal(str(transcript.duration)):
        reasons.append('Timed transcript duration differs from the original-source duration; source offsets are unsupported.')
    intervals: list[PreservedSegment | PreservedWord] = [*transcript.segments, *transcript.words]
    if source.duration is not None and any(
            bound is not None and Decimal(str(bound)) > source.duration
            for interval in intervals for bound in (interval.start, interval.end)):
        reasons.append('Timed transcript evidence extends outside the original-source duration.')
    if source.basis == 'fixture':
        limitations.append('Source identity/duration use labeled fixture assumptions; this is not verified real audio quality.')
    assets = {'episode_start': evidence.episode_start, 'transition_in': evidence.transition_in, 'transition_out': evidence.transition_out}
    for name, asset in assets.items():
        problem = asset.problem() if asset else 'Prepared transition evidence is unavailable.'
        if problem:
            reasons.append(f'{name}: {problem}')
        if asset and asset.basis == 'fixture':
            limitations.append(f'{name}: prepared duration is a fixture assumption, not a measured real asset.')
    closing = evidence.transition_out
    overhead: list[Decimal | None] = []
    limits: list[tuple[Decimal, Decimal] | None] = []
    settings = evidence.settings
    for opening in (evidence.episode_start, evidence.transition_in, evidence.transition_in):
        budget = (opening.duration + settings.pause + closing.duration
                  if opening and closing and opening.duration is not None and closing.duration is not None else None)
        overhead.append(budget)
        limits.append((settings.minimum - budget, settings.maximum - budget) if budget is not None else None)
    duration = source.duration
    if duration is not None:
        excess = duration - 3 * settings.maximum
        if excess > 0:
            reasons.append(f'Source alone exceeds three {settings.maximum}-second finished sections by {excess} seconds before overhead.')
        if all(budget is not None for budget in overhead):
            total = duration + sum(budget for budget in overhead if budget is not None)
            if total > 3 * settings.maximum:
                reasons.append(f'Source plus transition/pause overhead totals {total} seconds, exceeding capacity {3 * settings.maximum} by {total - 3 * settings.maximum}.')
            if total < 3 * settings.minimum:
                reasons.append(f'Source plus transition/pause overhead totals {total} seconds, below required {3 * settings.minimum} by {3 * settings.minimum - total}.')
    supported = []
    rejected = {}
    seen = set()
    for boundary in evidence.boundaries:
        if boundary.id in seen:
            reasons.append(f'Duplicate boundary identity: {boundary.id}.')
        seen.add(boundary.id)
        problem = boundary_problem(boundary, transcript, duration) if duration is not None else 'Unknown source duration.'
        if problem:
            rejected[boundary.id] = problem
        else:
            supported.append(boundary)
    proposal = None
    best_score = None
    if not reasons and duration is not None:
        for first, second in combinations(sorted(supported, key=lambda b: (b.time, b.id)), 2):
            endpoints = [Decimal(0), first.time, second.time, duration]
            sections = []
            for index in range(3):
                budget = overhead[index]
                assert budget is not None
                part = endpoints[index + 1] - endpoints[index]
                if part <= 0 or not settings.minimum <= part + budget <= settings.maximum:
                    break
                opening = evidence.episode_start if index == 0 else evidence.transition_in
                assert opening and opening.duration is not None and closing and closing.duration is not None
                sections.append(FinishedSection(number=index + 1, source_start=endpoints[index], source_end=endpoints[index + 1],
                    part_duration=part, opening='episode_start' if index == 0 else 'transition_in',
                    opening_duration=opening.duration, pause=settings.pause, closing_duration=closing.duration,
                    finished_duration=part + budget))
            if len(sections) != 3:
                continue
            durations = [section.finished_duration for section in sections]
            score = (-min(first.strength, second.strength), -(first.strength + second.strength), max(durations) - min(durations))
            if best_score is None or score < best_score:
                best_score = score
                selected_limits = [*limitations]
                if any(b.basis == 'fixture' for b in (first, second)):
                    selected_limits.append('Selected natural cuts are synthetic fixture assumptions; arithmetic success does not establish real audio quality.')
                proposal = SectionProposal(evidence=evidence, boundaries=[first, second], sections=sections, limitations=selected_limits)
        if proposal is None:
            reasons.append(f'No pair among {len(supported)} supported natural boundaries meets all three source-part duration budgets. No cut was forced.')
    return PlanningOutcome(status='valid' if proposal else 'unavailable', evidence=evidence, dependencies=dependencies,
        overhead=overhead, source_part_limits=limits, reasons=reasons, rejected_boundaries=rejected,
        limitations=proposal.limitations if proposal else limitations, proposal=proposal)


def plan_episode(path: Path, evidence_path: Path | None = None) -> WorkspaceState:
    workspace = Workspace(path)
    with ownership(workspace.path, 'plan episode sections'):
        state = workspace.read()
        workspace.reconcile(state)
        transcript = current_transcript(workspace, state)
        if evidence_path is not None:
            evidence = PlanningEvidence.model_validate_json(evidence_path.read_bytes())
        else:
            previous = next((run.inputs['evidence'] for run in reversed(state.runs)
                             if run.operation == 'plan' and 'evidence' in run.inputs), None)
            if previous:
                evidence = PlanningEvidence.model_validate(previous)
            else:
                from .planning_models import SourceEvidence
                source = next(s for s in state.sources if s.id == state.source_revision)
                measured = (source.properties or {}).get('format', {}).get('duration')
                duration = Decimal(str(measured)) if measured is not None else (
                    Decimal(str(transcript.duration)) if transcript.duration else None)
                verified = bool(source.fingerprint and measured is not None)
                evidence = PlanningEvidence(source=SourceEvidence(revision=source.id,
                    fingerprint=source.fingerprint, duration=duration,
                    basis='verified' if verified else 'unknown',
                    evidence='Preserved source inspection.' if verified else ''),
                    transcript_sha256=state.artifacts['transcript.json'].sha256)
        dependencies = {'source_revision': state.source_revision, 'transcript': state.artifacts['transcript.json'].sha256,
                        'planning_evidence': digest(evidence.model_dump_json().encode()), 'planner': VERSION}
        prior = state.artifacts.get('section-plan.json')
        if prior and prior.dependencies == dependencies:
            outcome = PlanningOutcome.model_validate_json(workspace.artifact_bytes(prior))
            if outcome.proposal is None or 'section-boundaries.json' in state.artifacts:
                return state
        run = Run(id=identifier(), operation_id=identifier(), operation='plan', status='running', started_at=now(),
                  inputs={'evidence': evidence.model_dump(mode='json'), 'dependencies': dependencies})
        state.runs.append(run)
        for name in PLAN_FILES:
            state.artifacts.pop(name, None)
        workspace.commit(state)
        outcome = propose(evidence, transcript, state, dependencies)
        workspace.add_artifact(state, 'section-plan.json', outcome.model_dump_json(indent=2).encode(), dependencies, VERSION)
        if outcome.proposal:
            workspace.add_artifact(state, 'section-boundaries.json', outcome.proposal.model_dump_json(indent=2).encode(), dependencies, VERSION)
        run.status, run.finished_at = 'completed', now()
        run.limitations = outcome.limitations + outcome.reasons
        workspace.commit(state)
        return state


def planning_report(workspace: Workspace, state: WorkspaceState) -> str:
    artifact = state.artifacts.get('section-plan.json')
    if artifact is None:
        return 'Section planning: no current outcome.\n'
    result = PlanningOutcome.model_validate_json(workspace.artifact_bytes(artifact))
    evidence = result.evidence
    lines = [f'Section planning: {result.status}.', f'Original-source duration: {evidence.source.duration} seconds.',
             f'Finished-section limits: {evidence.settings.minimum}–{evidence.settings.maximum} seconds inclusive.',
             f'Separate pause before every transition-out: {evidence.settings.pause} seconds.']
    for index, (budget, bounds) in enumerate(zip(result.overhead, result.source_part_limits), 1):
        lines.append(f'Section {index}: transition/pause overhead {budget if budget is not None else "unknown"}; source-part budget {bounds if bounds else "unknown"}.')
    if result.proposal:
        for part in result.proposal.sections:
            lines.append(f'Section {part.number}: source [{part.source_start}, {part.source_end}]; '
                         f'D{part.number} = {part.opening_duration} + {part.part_duration} + {part.pause} + {part.closing_duration} = {part.finished_duration} seconds.')
    lines.extend(result.reasons)
    lines.extend(f'Boundary {key}: {value}' for key, value in result.rejected_boundaries.items())
    lines.extend(result.limitations)
    return '\n'.join(lines) + '\n'
