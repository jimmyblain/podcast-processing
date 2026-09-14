"""Episode-local participant evidence and nonblocking uncertainty reporting."""
from difflib import SequenceMatcher
from pathlib import Path
import re

from .workspace import Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import EpisodeMetadata, ParticipantAssociation, PreservedTranscript, Run, TranscriptChange, WorkspaceState, unclear_wording
from .transcript_content import supersede_consumers
from .speech import clear_opening, supported_text

MAPPING_VERSION = 'participant-dialogue-v2'


def recognized_participants(text: str, names: list[str]) -> list[tuple[str, str]]:
    """Resolve a name only inside an introduction, requiring a unique close match.

    Full-name spelling variation is recognition evidence, never a transcript edit.
    Short first names must match exactly and uniquely in the approved roster.
    """
    tokens = re.findall(r"[\w'-]+", text)
    matches = []
    for name in names:
        official = re.findall(r"[\w'-]+", name)
        if not official:
            continue
        if any(token.casefold().endswith("'s") or token.endswith("'") for token in tokens[:len(official)]):
            continue  # “I'm Erica Campbell's friend” names somebody else.
        spoken = ' '.join(tokens[:len(official)])
        ratios = [SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
                  for a, b in zip(tokens, official)]
        if (len(official) > 1 and len(tokens) >= len(official) and all(r >= .72 for r in ratios[:len(official)])
                and SequenceMatcher(None, spoken.casefold(), name.casefold()).ratio() >= .8):
            matches.append((name, spoken))
        elif tokens and tokens[0].casefold() == official[0].casefold() and (
                len(tokens) == 1 or text[len(tokens[0]):].lstrip().startswith(('.', ',', '!', '?'))):
            matches.append((name, tokens[0]))
    return matches


def map_supported(transcript: PreservedTranscript, metadata: EpisodeMetadata,
                  source_revision: str) -> PreservedTranscript:
    """Combine introductions and response evidence; keep conflicting voices anonymous."""
    if not transcript.speakers:
        return transcript
    inputs = digest(json_bytes([MAPPING_VERSION, [(p.name, p.role) for p in metadata.participants],
                               [(t.id, t.speaker, t.text, t.quotation_usable, t.start, t.end) for t in transcript.segments],
                               [(s.id, s.participant) for s in transcript.speakers if s.identity_status == 'corrected']]))
    if transcript.mapping_inputs == inputs:
        return transcript
    result = transcript.model_copy(deep=True)
    speakers = {s.id: s for s in result.speakers}
    confirmed = [p.name for p in metadata.participants]
    host = next(p.name for p in metadata.participants if p.role == 'host')
    for speaker in result.speakers:
        if speaker.participant is not None and speaker.participant not in confirmed:
            speaker.participant, speaker.identity_status = None, 'uncertain'
        if speaker.identity_status != 'corrected':
            speaker.participant, speaker.identity_status, speaker.identity_evidence = None, 'unresolved', []
            speaker.associations, speaker.identity_uncertainty = [], []

    def record(speaker_id: str, evidence: ParticipantAssociation) -> None:
        if speakers[speaker_id].identity_status != 'corrected':
            speakers[speaker_id].associations.append(evidence)

    def identities(speaker_id: str) -> set[str]:
        speaker = speakers[speaker_id]
        if speaker.identity_status == 'corrected':
            return {speaker.participant} if speaker.participant else set()
        return {a.participant for a in speaker.associations}

    for turn in result.segments:
        if turn.speaker not in speakers:
            continue
        text = supported_text(turn).replace('’', "'")
        for self_intro in re.finditer(
                r"(?:^|[.!?]\s+)(?:(?:hi|hello|hey|well)[,!]?\s+)?"
                r"(?:(?:I'm|I am)(?: your (?:girl|host))?|my name is|it's your (?:girl|host))[,]?\s+", text, re.I):
            matches = recognized_participants(text[self_intro.end():], confirmed)
            for name, recognized in matches:
                record(turn.speaker, ParticipantAssociation(participant=name, kind='self-introduction',
                    turn_ids=[turn.id] if turn.id else [], recognized_name=recognized,
                    reason='First-person introduction matches an approved participant; spelling alone is not identity evidence.'))
        # A hosting claim is useful even without the host saying their own name.
        # Restrict it to an opening and the approved show's explicit identity.
        if (turn.start is not None and turn.start <= 300
                and re.search(r"\bwelcome\b", text, re.I)
                and (re.search(r"\bmy podcast\b", text, re.I)
                     or re.search(r"\b(?:I'm|I am) your host\b", text, re.I))
                and re.search(r"\bI'll Just Let Myself In\b", text, re.I)):
            record(turn.speaker, ParticipantAssociation(participant=host, kind='host-role',
                turn_ids=[turn.id] if turn.id else [],
                reason='Opening welcomes the audience to the approved show and explicitly claims the hosting role.'))

    # Resolve host support before considering a guest response. A conflicting host
    # introduction must not become evidence for somebody else's confident label.
    supported_hosts = {speaker_id for speaker_id in speakers if identities(speaker_id) == {host}}
    for position, introduction in enumerate(result.segments):
        if (introduction.speaker not in supported_hosts
                or introduction.end is None):
            continue
        text = supported_text(introduction).replace('’', "'")
        guest_matches = []
        for welcome in re.finditer(
                r"(?:\bwelcome[,!]?\s+|\b(?:my guest|joining me|here with me)(?: today)?(?: is)?\s+|"
                r"\bI'm sitting with\s+|\bwithout further ado[,]?\s+|\bplease welcome\s+)", text, re.I):
            guest_matches.extend(recognized_participants(text[welcome.end():],
                                 [p.name for p in metadata.participants if p.role == 'guest']))
        if len({name for name, _ in guest_matches}) != 1:
            continue
        guest, recognized = guest_matches[0]
        responding_speaker = None
        for offset, turn in enumerate(result.segments[position + 1:position + 5], start=1):
            opening = clear_opening(turn)
            if (not opening or turn.start is None or turn.start < introduction.end
                    or turn.start - introduction.end > 15 or turn.speaker not in speakers):
                break
            if turn.speaker != introduction.speaker:
                if responding_speaker is not None and responding_speaker != turn.speaker:
                    break
                responding_speaker = turn.speaker
                if re.search(r"(?:^|[.!?]\s+)(?:(?:well|hi|hello)[,.!]?\s+)?"
                             r"thank(?:s| you)(?: so much)?\s+for (?:having|inviting) me\b", opening, re.I):
                    host_evidence = speakers[introduction.speaker].associations
                    refs = [ref for evidence in host_evidence for ref in evidence.turn_ids]
                    refs.extend(t.id for t in result.segments[position:position + offset + 1] if t.id)
                    record(turn.speaker, ParticipantAssociation(participant=guest, kind='guest-response',
                        turn_ids=list(dict.fromkeys(refs)), recognized_name=recognized,
                        host_speaker_id=introduction.speaker,
                        reason='Supported host introduces one guest; the other voice acknowledges the invitation '
                               'within four turns and fifteen source seconds. Later turns retain that voice identity.'))
                    break
            if not re.fullmatch(r'(?:(?:hi|hello|welcome|thank you|thanks|sweetheart|dear|friend)[.,! ]*)+', turn.text.strip(), re.I):
                break

    changes = []
    for speaker in result.speakers:
        if speaker.identity_status == 'corrected':
            continue
        names = identities(speaker.id)
        for association in speaker.associations:
            if association.host_speaker_id and identities(association.host_speaker_id) != {host}:
                association.uncertainty = 'The introducing host has conflicting identity evidence; this response cannot establish identity.'
        speaker.identity_evidence = list(dict.fromkeys(ref for a in speaker.associations for ref in a.turn_ids))
        if len(names) == 1 and any(a.uncertainty is None for a in speaker.associations):
            speaker.participant = next(iter(names))
            speaker.identity_status = 'supported'
            speaker.identity_uncertainty = ['Transcript-context support, not independent voice verification; '
                                            'subsequent attribution relies on consistent episode-local diarization.']
        elif names:
            speaker.identity_status = 'uncertain'
            speaker.identity_uncertainty = ['Conflicting participant or introducing-host evidence; keep this voice anonymous.']
        else:
            speaker.identity_uncertainty = ['No sufficient introduction/response evidence; roster and vendor label order prove no identity.']
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
    # Older schema-v2 bytes omit newly optional evidence fields. Their exact saved
    # hash, rather than a reserialization with defaults, identifies this base.
    mapped.lineage[-1].base_sha256 = state.artifacts['transcript.json'].sha256
    dependencies = {**state.artifacts['transcript.json'].dependencies, 'mapping': mapped.mapping_inputs or ''}
    superseded = supersede_consumers(state, current_transcript(workspace, state), mapped)
    state.runs[-1].limitations.append(f'Superseded: {", ".join(superseded) or "none"}. Publishing artifacts were not regenerated.')
    for name, data in [('transcript.json', json_bytes(mapped.model_dump())),
                       ('transcript.txt', mapped.readable().encode())]:
        workspace.add_artifact(state, name, data, dependencies, MAPPING_VERSION)


def uncertainty_report(transcript: PreservedTranscript) -> str:
    lines = []
    for speaker in transcript.speakers:
        if speaker.identity_uncertainty:
            lines.append(f'- Participant evidence for {speaker.label or speaker.id}: '
                         f'{speaker.participant or "anonymous"} ({speaker.identity_status}). '
                         + ' '.join(speaker.identity_uncertainty)
                         + (f' Evidence turns: {", ".join(speaker.identity_evidence)}.' if speaker.associations else ''))
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
