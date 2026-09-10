"""Publishing evidence views and hashes of the inputs each consumer actually uses."""
from .models import Transcript, TranscriptSegment
from .speech import supported_passages, supported_text
from .workspace import digest, json_bytes
from .workspace_models import PreservedTranscript, WorkspaceState


def publishing_transcript(preserved: PreservedTranscript, *, timed: bool = False) -> Transcript:
    names = {s.id: s.participant for s in preserved.speakers}
    labels = {s.id: s.label or s.id for s in preserved.speakers}
    segments: list[TranscriptSegment] = []
    previous_label = None
    words = {w.id: w for w in preserved.words if w.id is not None}
    for turn in (passage for segment in preserved.segments for passage in supported_passages(segment, words)):
        if timed and (turn.start is None or turn.end is None):
            previous_label = None
            continue
        label = names.get(turn.speaker or '') or (
            f'Anonymous speaker ({labels[turn.speaker]})' if turn.speaker in labels else 'Anonymous speaker')
        if not timed and segments and label == previous_label:
            segments[-1].text += ' ' + turn.text
        else:
            segments.append(TranscriptSegment(start=turn.start or 0, end=turn.end or 0,
                                               text=f'{label}: {turn.text}'))
        previous_label = label
    return Transcript(segments=segments, language=preserved.language or 'unknown', duration=preserved.duration or 0)


def transcript_inputs(transcript: PreservedTranscript) -> dict[str, str]:
    """Keep attribution/text consumers independent of source timing and artifact IDs."""
    return {
        'transcript_text': digest(json_bytes(' '.join(text for t in transcript.segments if (text := supported_text(t))))),
        'transcript_attribution': digest(json_bytes(publishing_transcript(transcript).full_text)),
        'transcript_timing': digest(json_bytes({
            'duration': transcript.duration,
            'turns': [(t.start, t.end, t.timing_usable, t.word_ids) for t in transcript.segments],
            'words': [(w.start, w.end, w.timing_usable) for w in transcript.words]})),
    }


def supersede_consumers(state: WorkspaceState, before: PreservedTranscript,
                        after: PreservedTranscript) -> list[str]:
    old, new = transcript_inputs(before), transcript_inputs(after)
    changed = {key for key in old if old[key] != new[key]}
    superseded: list[str] = []
    old_transcript = state.artifacts['transcript.json'].sha256
    invalid_hashes = {old_transcript}
    while True:
        removed = []
        for name, artifact in state.artifacts.items():
            if name in ('transcript.json', 'transcript.txt', 'import-original.json'):
                continue
            if (any(key in artifact.dependencies for key in changed)
                    or any(value in invalid_hashes for value in artifact.dependencies.values())):
                removed.append(name)
                invalid_hashes.add(artifact.sha256)
        if not removed:
            break
        for name in removed:
            state.artifacts.pop(name)
        superseded.extend(removed)
    return superseded
