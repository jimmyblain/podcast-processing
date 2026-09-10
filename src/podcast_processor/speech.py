"""Clear sentence evidence without changing persisted speaker-turn semantics."""
import re

from .workspace_models import PreservedSegment, PreservedWord, unclear_wording


def clear_sentence_spans(turn: PreservedSegment) -> list[tuple[int, int]]:
    if not unclear_wording(turn.text):
        return [(0, len(turn.text))] if turn.quotation_usable else []
    spans = []
    start = 0
    # Punctuation inside an uncertainty marker cannot end the surrounding sentence.
    boundaries = [match.end() for match in re.finditer(r'\[[^]]*\]|<[^>]*>|[.!?](?=\s|$)', turn.text)
                  if match.group()[0] not in '[<']
    for end in [*boundaries, len(turn.text)]:
        while start < end and turn.text[start].isspace():
            start += 1
        if start < end and not unclear_wording(turn.text[start:end]):
            spans.append((start, end))
        start = end
    return spans


def supported_text(turn: PreservedSegment) -> str:
    return ' '.join(turn.text[start:end] for start, end in clear_sentence_spans(turn))


def clear_opening(turn: PreservedSegment) -> str:
    end = 0
    for start, stop in clear_sentence_spans(turn):
        if turn.text[end:start].strip():
            break
        end = stop
    return turn.text[:end]


def supported_passages(turn: PreservedSegment, words: dict[str, PreservedWord]) -> list[PreservedSegment]:
    spans = clear_sentence_spans(turn)
    if spans == [(0, len(turn.text))]:
        return [turn]
    members = [words[ref] for ref in turn.word_ids if ref in words]
    offsets = []
    cursor = 0
    for word in members:
        offsets.append((cursor, cursor + len(word.word), word))
        cursor += len(word.word) + 1
    aligned_text = ' '.join(w.word for w in members) == turn.text
    passages = []
    for start, end in spans:
        selected = [w for left, right, w in offsets if start <= left and right <= end] if aligned_text else []
        # A readable sentence boundary is not a precise source position by itself.
        source_start = selected[0].start if selected and selected[0].timing_usable else None
        source_end = selected[-1].end if selected and selected[-1].timing_usable else None
        if source_start is not None and source_end is not None and source_end <= source_start:
            source_start = source_end = None
        passages.append(PreservedSegment(text=turn.text[start:end], speaker=turn.speaker,
            start=source_start, end=source_end, quotation_usable=True))
    return passages
