"""Discover or consume natural-cut evidence, then validate exact section durations."""
from decimal import Decimal
from itertools import combinations
from pathlib import Path

from .progress import progress
from .participants import current_transcript
from .planning_models import (
    DiscoveryOutcome, FinishedSection, NaturalBoundary, PlanningEvidence, PlanningOutcome, PlanningReason, SectionProposal,
)
from .workspace import Workspace, digest, identifier, now, ownership
from .workspace_models import PreservedSegment, PreservedTranscript, PreservedWord, Run, WorkspaceState

VERSION = 'section-planner-v5'
PLAN_FILES = ('section-plan.json', 'section-boundaries.json')
LIMITATIONS = [
    'Section planning performs no media cutting, stitching or export.',
    'Transcript-supported suggestions include semantic judgments and checked word gaps, not independently reviewed source safety. Punctuation, silence or model assertions alone do not verify safe audio cuts.',
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
            lower, upper = (turn.start, turn.end) if turn else (None, None)
            # A containing turn can be very long. Same-turn reliable neighbors
            # bound an isolated unknown word without assigning it precise timing.
            # Include the entire anchor word, so no inferred gap becomes a cut.
            for direction in (-1, 1):
                neighbor_index = index + direction
                while 0 <= neighbor_index < len(words):
                    neighbor = words[neighbor_index]
                    if not word.turn_id or neighbor.turn_id != word.turn_id:
                        break
                    if (neighbor.timing_usable and not neighbor.timing_uncertainty
                            and neighbor.start is not None and neighbor.end is not None):
                        if direction == -1:
                            lower = max(lower, neighbor.start) if lower is not None else neighbor.start
                        else:
                            upper = min(upper, neighbor.end) if upper is not None else neighbor.end
                        break
                    neighbor_index += direction
            # A zero-length provider word can occupy its own unbounded turn.
            # Its retained coarse position, bracketed by two reliable words,
            # localizes uncertainty without making that word a precise cut anchor.
            if (word.start is not None and word.end is not None and 0 < index < len(words) - 1):
                left, right = words[index - 1], words[index + 1]
                if (left.timing_usable and right.timing_usable and not left.timing_uncertainty
                        and not right.timing_uncertainty and left.start is not None and left.end is not None
                        and right.start is not None and right.end is not None
                        and left.start <= word.start <= word.end <= right.end
                        and left.end <= right.start):
                    lower = max(lower, left.start) if lower is not None else left.start
                    upper = min(upper, right.end) if upper is not None else right.end
            # Retained uncertain positions may contradict word order or nearby
            # anchors. Never narrow them out of the possible source interval.
            for position in (word.start, word.end):
                if position is not None:
                    if lower is not None:
                        lower = min(lower, position)
                    if upper is not None:
                        upper = max(upper, position)
            if ((index <= before_index and (upper is None or Decimal(str(upper)) > boundary.time))
                    or (index >= after_index and (lower is None or Decimal(str(lower)) < boundary.time))):
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
    reason_code: PlanningReason | None = 'source-unavailable' if reasons else None
    assets = {'episode_start': evidence.episode_start, 'transition_in': evidence.transition_in, 'transition_out': evidence.transition_out}
    needs_setup = False
    for name, asset in assets.items():
        problem = asset.problem(evidence.settings.transition_ending_silence) if asset else 'Prepared transition evidence is unavailable.'
        if problem:
            needs_setup = True
            reasons.append(f'{name}: {problem}')
        if asset and asset.basis == 'fixture':
            limitations.append(f'{name}: prepared duration is a fixture assumption, not a measured real asset.')
    closing = evidence.transition_out
    overhead: list[Decimal | None] = []
    limits: list[tuple[Decimal, Decimal] | None] = []
    settings = evidence.settings
    for index, opening in enumerate((evidence.episode_start, evidence.transition_in, evidence.transition_in)):
        budget = None
        if opening and opening.duration is not None:
            if index == 2:
                budget = opening.duration
            elif closing and closing.duration is not None:
                budget = opening.duration + settings.pause + closing.duration
        overhead.append(budget)
        limits.append((settings.minimum - budget, settings.maximum - budget) if budget is not None else None)
    duration = source.duration
    if duration is not None and not needs_setup:
        before_duration_reasons = len(reasons)
        excess = duration - 3 * settings.maximum
        if excess > 0:
            reasons.append(f'Source alone exceeds three {settings.maximum}-second finished sections by {excess} seconds before overhead.')
        if all(budget is not None for budget in overhead):
            total = duration + sum(budget for budget in overhead if budget is not None)
            if total > 3 * settings.maximum:
                reasons.append(f'Source plus transition/pause overhead totals {total} seconds, exceeding capacity {3 * settings.maximum} by {total - 3 * settings.maximum}.')
            if total < 3 * settings.minimum:
                reasons.append(f'Source plus transition/pause overhead totals {total} seconds, below required {3 * settings.minimum} by {3 * settings.minimum - total}.')
        for index, budget in enumerate(overhead, 1):
            if budget is not None and budget >= settings.maximum:
                reasons.append(f'Section {index} transition/pause overhead {budget} leaves no positive source-part budget.')
        if all(bounds is not None for bounds in limits):
            minimum_source = sum(max(Decimal(0), bounds[0]) for bounds in limits if bounds is not None)
            strict_minimum = any(bounds is not None and bounds[0] <= 0 for bounds in limits)
            if duration < minimum_source or duration == minimum_source and strict_minimum:
                reasons.append(f'Source duration {duration} cannot supply three positive parts within their individual minimum budgets ({minimum_source} seconds).')
        if len(reasons) > before_duration_reasons and reason_code is None:
            reason_code = 'duration-impossible'
    supported = []
    rejected = {}
    seen = set()
    for boundary in evidence.boundaries:
        if boundary.id in seen:
            reason_code = reason_code or 'invalid-evidence'
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
                    opening_duration=opening.duration, pause=settings.pause if index < 2 else Decimal(0),
                    closing_duration=closing.duration if index < 2 else Decimal(0),
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
            reason_code = 'insufficient-boundaries'
            reasons.append(f'No pair among {len(supported)} supported natural boundaries meets all three source-part duration budgets. No cut was forced.')
    if needs_setup:
        reason_code = 'missing-setup'
        from .show_setup import NEEDS_SETUP
        reasons.insert(0, NEEDS_SETUP)
    return PlanningOutcome(reason_code=reason_code, status='valid' if proposal else 'needs-setup' if needs_setup else 'unavailable', evidence=evidence, dependencies=dependencies,
        overhead=overhead, source_part_limits=limits, reasons=reasons, rejected_boundaries=rejected,
        limitations=proposal.limitations if proposal else limitations, proposal=proposal)


def plan_episode(path: Path, evidence_path: Path | None = None, *, api_key: str = '',
                 model: str = 'claude-opus-4-8', fresh: bool = False) -> WorkspaceState:
    progress('Planning sections')
    workspace = Workspace(path)
    with ownership(workspace.path, 'plan episode sections'):
        state = workspace.read()
        workspace.reconcile(state)
        transcript = current_transcript(workspace, state)
        explicit_evidence = evidence_path is not None
        if evidence_path is not None:
            evidence = PlanningEvidence.model_validate_json(evidence_path.read_bytes())
        else:
            from .show_setup import episode_setup, planning_transitions
            setup = episode_setup(workspace, state)
            previous_run = next((run for run in reversed(state.runs)
                             if run.operation == 'plan' and 'evidence' in run.inputs), None)
            if previous_run and previous_run.inputs.get('explicit_evidence', True):
                evidence = PlanningEvidence.model_validate(previous_run.inputs['evidence'])
                explicit_evidence = previous_run.inputs.get('explicit_evidence', any(
                    asset is not None for asset in (evidence.episode_start, evidence.transition_in, evidence.transition_out)))
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
            if setup and not explicit_evidence:
                # Keep source/boundary evidence independent of prepared audio.
                # Explicit evidence files still support historical fixture studies.
                evidence = evidence.model_copy(update=planning_transitions(setup))
                evidence.settings.transition_ending_silence = setup.ending_silence
        discovery = DiscoveryOutcome()
        if not explicit_evidence:
            preliminary = propose(evidence, transcript, state, {})
            if preliminary.reason_code == 'insufficient-boundaries':
                from .discovery import discover
                boundaries, discovery = discover(workspace, state, transcript, evidence.source, api_key, model, fresh)
                evidence = evidence.model_copy(update={'boundaries': boundaries})
            else:
                discovery = DiscoveryOutcome(summary='Discovery not run: ' + ' '.join(preliminary.reasons))
        dependencies = {'source_revision': state.source_revision, 'transcript': state.artifacts['transcript.json'].sha256,
                        'planning_evidence': digest(evidence.model_dump_json().encode()), 'planner': VERSION,
                        'discovery': digest(discovery.model_dump_json().encode())}
        prior = state.artifacts.get('section-plan.json')
        if prior and prior.dependencies == dependencies:
            outcome = PlanningOutcome.model_validate_json(workspace.artifact_bytes(prior))
            if outcome.proposal is None or 'section-boundaries.json' in state.artifacts:
                from .completion import section_summary
                progress('Reused section-planning checkpoint')
                progress(section_summary(outcome, supplied_evidence=explicit_evidence))
                return state
        run = Run(id=identifier(), operation_id=identifier(), operation='plan', status='running', started_at=now(),
                  inputs={'evidence': evidence.model_dump(mode='json'), 'dependencies': dependencies,
                          'explicit_evidence': explicit_evidence})
        state.runs.append(run)
        for name in PLAN_FILES:
            state.artifacts.pop(name, None)
        workspace.commit(state)
        outcome = propose(evidence, transcript, state, dependencies)
        outcome.discovery = discovery
        if discovery.status == 'failed':
            outcome.status, outcome.reason_code = 'unavailable', 'discovery-failed'
            outcome.reasons = [discovery.summary]
            outcome.proposal = None
        workspace.add_artifact(state, 'section-plan.json', outcome.model_dump_json(indent=2).encode(), dependencies, VERSION)
        if outcome.proposal:
            workspace.add_artifact(state, 'section-boundaries.json', outcome.proposal.model_dump_json(indent=2).encode(), dependencies, VERSION)
        run.status, run.finished_at = ('partial' if outcome.requires_action else 'completed'), now()
        from .completion import section_summary
        progress(section_summary(outcome, supplied_evidence=explicit_evidence))
        run.limitations = outcome.limitations + outcome.reasons
        workspace.commit(state)
        return state


def planning_report(workspace: Workspace, state: WorkspaceState) -> str:
    artifact = state.artifacts.get('section-plan.json')
    if artifact is None:
        return 'Section planning: no current outcome.\n'
    result = PlanningOutcome.model_validate_json(workspace.artifact_bytes(artifact))
    if result.status == 'needs-setup':
        from .show_setup import NEEDS_SETUP
        return f'Section planning: needs-setup.\n{NEEDS_SETUP}\n'
    evidence = result.evidence
    lines = [f'Section planning: {result.status}.', f'Original-source duration: {evidence.source.duration} seconds.',
             f'Finished-section limits: {evidence.settings.minimum}–{evidence.settings.maximum} seconds inclusive.',
             f'Separate pause before every transition-out: {evidence.settings.pause} seconds.']
    if result.schema_version == 2:
        lines.append('Section 3 plays through the original episode ending, with no added closing pause or transition-out.')
    for index, (budget, bounds) in enumerate(zip(result.overhead, result.source_part_limits), 1):
        lines.append(f'Section {index}: transition/pause overhead {budget if budget is not None else "unknown"}; source-part budget {bounds if bounds else "unknown"}.')
    if result.proposal:
        for part in result.proposal.sections:
            lines.append(f'Section {part.number}: source [{part.source_start}, {part.source_end}]; '
                         f'D{part.number} = {part.opening_duration} + {part.part_duration} + {part.pause} + {part.closing_duration} = {part.finished_duration} seconds.')
    lines.append(f'Candidate discovery: {result.discovery.status}. {result.discovery.summary}')
    lines.extend(result.reasons)
    lines.extend(f'Boundary {key}: {value}' for key, value in result.rejected_boundaries.items())
    lines.extend(result.limitations)
    return '\n'.join(lines) + '\n'
