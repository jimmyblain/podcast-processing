"""Episode-local participant evidence and nonblocking uncertainty reporting."""
from pathlib import Path
import re

from .workspace import Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import EpisodeMetadata, PreservedTranscript, Run, TranscriptChange, WorkspaceState, unclear_wording
from .transcript_content import supersede_consumers
from .speech import clear_opening, supported_text

MAPPING_VERSION = 'participant-introductions-v1'


def map_supported(transcript: PreservedTranscript, metadata: EpisodeMetadata,
                  source_revision: str) -> PreservedTranscript:
    """Use explicit introduction evidence; label order and roster size prove no identity."""
    inputs = digest(json_bytes([MAPPING_VERSION, [(p.name, p.role) for p in metadata.participants],
                               [(t.id, t.speaker, t.text, t.quotation_usable, t.start, t.end) for t in transcript.segments]]))
    if transcript.mapping_inputs == inputs:
        return transcript
    result = transcript.model_copy(deep=True)
    candidates: dict[str, dict[str, list[str]]] = {s.id: {} for s in result.speakers}
    confirmed = {p.name for p in metadata.participants}
    for speaker in result.speakers:
        if speaker.participant is not None and speaker.participant not in confirmed:
            speaker.participant, speaker.identity_status = None, 'uncertain'
        if speaker.identity_status != 'corrected':
            speaker.participant, speaker.identity_status, speaker.identity_evidence = None, 'unresolved', []
    for turn in result.segments:
        if turn.speaker not in candidates:
            continue
        text = supported_text(turn).replace('’', "'")
        for participant in metadata.participants:
            name = re.escape(participant.name)
            if re.search(r"(?:^|[.!?]\s+)(?:(?:hi|hello|hey|well)[,!]?\s+)?"
                         r"(?:(?:I'm|I am)(?: your (?:girl|host))?|my name is|it's your (?:girl|host))[,]?\s+" + name + r'\b', text, re.I):
                candidates[turn.speaker].setdefault(participant.name, []).append(turn.id or 'unknown turn')
    # A named welcome from a supported host followed by a guest acknowledging the
    # invitation is stronger than either a name mention or the roster alone.
    for position, introduction in enumerate(result.segments):
        if (introduction.speaker not in candidates
                or set(candidates[introduction.speaker]) != {'Lish Speaks'} or introduction.end is None):
            continue
        guests = [p.name for p in metadata.participants if p.role == 'guest' and re.search(
            r"(?:welcome[,!]?\s+|(?:my guest|joining me|here with me)(?: today)?(?: is)?\s+|I'm sitting with\s+)"
            + re.escape(p.name) + r'\b', supported_text(introduction).replace('’', "'"), re.I)]
        if len(guests) != 1:
            continue
        responding_speaker = None
        for turn in result.segments[position + 1:position + 5]:
            opening = clear_opening(turn)
            if (not opening or turn.start is None or turn.start < introduction.end
                    or turn.start - introduction.end > 15 or turn.speaker not in candidates):
                break
            if turn.speaker != introduction.speaker:
                if responding_speaker is not None and responding_speaker != turn.speaker:
                    break
                responding_speaker = turn.speaker
                if re.match(r'(?:(?:well|hi|hello)[,.!]?\s+)?thank(?:s| you)\b.*\b(?:having|inviting) me\b', opening, re.I):
                    candidates[turn.speaker].setdefault(guests[0], []).extend([
                        introduction.id or 'unknown turn', turn.id or 'unknown turn'])
                    break
            if not re.fullmatch(r'(?:hi|hello|welcome|thank you|thanks)[.,! ]*', turn.text.strip(), re.I):
                break
    changes = []
    for speaker in result.speakers:
        if speaker.identity_status == 'corrected':
            continue
        evidence = candidates[speaker.id]
        if len(evidence) == 1:
            speaker.participant = next(iter(evidence))
            speaker.identity_status = 'supported'
            speaker.identity_evidence = evidence[speaker.participant]
        elif evidence:
            speaker.identity_status = 'uncertain'
            speaker.identity_evidence = [ref for refs in evidence.values() for ref in refs]
        changes.append(speaker.model_dump())
    result.mapping_inputs = inputs
    result.revision = digest(json_bytes([transcript.revision, inputs, changes]))
    result.lineage.append(TranscriptChange(base_revision=transcript.revision,
        base_sha256=digest(json_bytes(transcript.model_dump())), source_revision=source_revision,
        revision=result.revision, component=MAPPING_VERSION, input_hash=inputs, changes=changes))
    return result


def current_transcript(workspace: Workspace, state: WorkspaceState) -> PreservedTranscript:
    artifact = state.artifacts.get('transcript.json')
    if artifact is None:
        raise WorkspaceError('No current timed transcript; import or transcribe the episode first.')
    return PreservedTranscript.model_validate_json(workspace.artifact_bytes(artifact))


def map_episode(path: Path) -> WorkspaceState:
    workspace = Workspace(path)
    with ownership(workspace.path, 'map participants'):
        state = workspace.read()
        workspace.reconcile(state)
        if state.episode_metadata is None:
            raise WorkspaceError('Mapping requires confirmed episode metadata.')
        original = current_transcript(workspace, state)
        mapped = map_supported(original, state.episode_metadata, state.source_revision)
        if mapped != original or 'transcript.txt' not in state.artifacts:
            state.runs.append(Run(id=identifier(), operation_id=identifier(), operation='map-participants',
                status='completed', started_at=now(), finished_at=now(), inputs={'source_revision': state.source_revision}))
            if mapped != original:
                save_mapped(workspace, state, mapped)
            ensure_readable(workspace, state)
            workspace.commit(state)
        return state


def ensure_readable(workspace: Workspace, state: WorkspaceState) -> bool:
    if 'transcript.txt' in state.artifacts:
        return False
    transcript = current_transcript(workspace, state)
    workspace.add_artifact(state, 'transcript.txt', transcript.readable().encode(),
                           state.artifacts['transcript.json'].dependencies, 'readable-transcript-v2')
    state.runs[-1].limitations.append('Recovered readable output from the current timed transcript, preserving corrections.')
    return True


def save_mapped(workspace: Workspace, state: WorkspaceState, mapped: PreservedTranscript) -> None:
    dependencies = {**state.artifacts['transcript.json'].dependencies, 'mapping': mapped.mapping_inputs or ''}
    superseded = supersede_consumers(state, current_transcript(workspace, state), mapped)
    state.runs[-1].limitations.append(f'Superseded: {", ".join(superseded) or "none"}. Publishing artifacts were not regenerated.')
    for name, data in [('transcript.json', json_bytes(mapped.model_dump())),
                       ('transcript.txt', mapped.readable().encode())]:
        workspace.add_artifact(state, name, data, dependencies, MAPPING_VERSION)


def uncertainty_report(transcript: PreservedTranscript) -> str:
    lines = []
    participants = {s.id: s.participant for s in transcript.speakers}
    words = {w.id: w for w in transcript.words}
    seen = set()
    for turn in transcript.segments:
        if turn.overlaps:
            lines.append(f'- Overlapping source speech at {turn.start}, turn {turn.id}; overlaps {", ".join(turn.overlaps)}. '
                         'Affected: timed transcript and precise boundaries. Fallback: retain overlapping intervals and '
                         'supported labels; uncertain ownership stays anonymous. Optional correction: separate selected turn_ids '
                         'or retime a source-checked word; no missing dialogue is inferred.')
        if not turn.quotation_usable or unclear_wording(turn.text):
            marker = next((words[ref] for ref in turn.word_ids if ref in words and unclear_wording(words[ref].word)), None)
            location = (f'word {marker.id}, source {marker.start}' if marker is not None and marker.start is not None
                        else f'unknown word time; turn starts at {turn.start if turn.start is not None else "unknown"}')
            offset = turn.text.find(marker.word) if marker is not None else max(turn.text.find('['), turn.text.find('<'), 0)
            passage = turn.text[max(0, offset - 50):offset + 100]
            lines.append(f'- Unclear wording at {location}, '
                         f'turn {turn.id or "unknown"}: {passage} Affected: quotations and factual publishing promises. '
                         'Fallback: keep the explicit marker in the timed transcript; exclude this passage from publishing '
                         'and use reliable surrounding discussion. Optional correction: replace the affected word range '
                         'with source-supported wording, or retain [unclear].')
        if turn.uncertainty:
            lines.append(f'- Turn {turn.id or "unknown"}, source {turn.start if turn.start is not None else "unknown"}: '
                         f'{"; ".join(turn.uncertainty)} Affected: word alignment and precise timing consumers. '
                         'Fallback: retain surrounding source intervals; do not infer precise word times. '
                         'Optional correction: check source audio and use retime with a word_id, start, end and evidence.')
        if participants.get(turn.speaker or '') is None and turn.speaker not in seen:
            seen.add(turn.speaker)
            seconds = int(turn.start or 0)
            stamp = f'{seconds // 60:02d}:{seconds % 60:02d}' if turn.start is not None else 'unknown time'
            example = (f'{{"op":"relabel","speaker":"{turn.speaker}","participant":"Lish Speaks"}} '
                       '(only with supported identity).' if turn.speaker is not None else
                       f'{{"op":"separate","turn_ids":["{turn.id}"]}} to create an anonymous speaker.'
                       if turn.id is not None else 'Legacy evidence lacks stable correction references.')
            lines.append(f'- Unresolved identity at {stamp}, turn {turn.id or "unknown"}: {turn.text[:120]} '
                         'Affected: transcript.txt and attribution consumers. Fallback: anonymous labels and neutral '
                         'topic-based attribution. Optional correction: '
                         + example)
    return '\n'.join(lines)
