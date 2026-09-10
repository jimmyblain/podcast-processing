"""Faithful words in provider order; vendor turn bounds are not precise evidence."""
import math
import re
from typing import Any

from .managed_models import ProviderName, Transport
from .workspace import digest, json_bytes
from .workspace_models import (DetectedSpeaker, ImportProvenance, PreservedSegment,
                               PreservedTranscript, PreservedWord, unclear_wording)

NORMALIZATION_VERSION = 'managed-words-v2'


def records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError('Unsupported provider record array.')
    return value


def mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError('Unsupported provider object.')
    return value


def normalize(raw: dict[str, Any], provider: ProviderName, transport: Transport,
              source_revision: str, raw_hash: str, request: dict[str, Any], operation_id: str) -> PreservedTranscript:
    revision = digest(json_bytes([raw_hash, source_revision, operation_id, NORMALIZATION_VERSION]))
    if provider == 'assemblyai':
        native_words = records(raw.get('words'))
        fallback_text = raw.get('text') or ' '.join(u.get('text') or '' for u in records(raw.get('utterances')))
        scale = 1000
    else:
        channels = records(mapping(raw.get('results')).get('channels'))
        alternatives = records(channels[0].get('alternatives')) if channels else []
        native_words = records(alternatives[0].get('words')) if alternatives else []
        fallback_text = alternatives[0].get('transcript', '') if alternatives else ''
        scale = 1
    if not native_words and isinstance(fallback_text, str):
        native_words = [{'text' if provider == 'assemblyai' else 'word': token}
                        for token in re.findall(r'\[[^]]*\]|<[^>]*>|\S+', fallback_text)]
    words: list[PreservedWord] = []
    turns: list[PreservedSegment] = []
    annotations: list[dict[str, Any]] = []
    speakers: dict[str, DetectedSpeaker] = {}
    def number(value: Any) -> float | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            return float(value)
        return None
    for index, native in enumerate(native_words):
        text = native.get('text') if provider == 'assemblyai' else native.get('punctuated_word', native.get('word'))
        if not isinstance(text, str) or not text.strip():
            continue
        markup = re.findall(r'\[[^]]*\]|<[^>]*>|♪[^♪]*♪', text)
        for annotation in markup:
            annotations.append({'evidence_index': index, 'text': annotation, 'kind': 'provider-annotation'})
            if not unclear_wording(annotation):
                text = text.replace(annotation, '').strip()
        if not text:
            continue
        start, end = number(native.get('start')), number(native.get('end'))
        start = start / scale if start is not None else None
        end = end / scale if end is not None else None
        usable = start is not None and end is not None and 0 <= start < end <= transport.duration
        uncertainty = [] if usable else ['Missing, zero-length, reversed or out-of-source word bounds; unusable for precise cuts.']
        # Invalid intervals remain in raw evidence, never masquerading as known bounds.
        if start is not None and not 0 <= start <= transport.duration:
            start = None
        if end is not None and not 0 <= end <= transport.duration:
            end = None
        if start is not None and end is not None and end < start:
            start = end = None
        label = native.get('speaker')
        speaker = None
        if isinstance(label, (str, int)):
            if str(label) not in speakers:
                speakers[str(label)] = DetectedSpeaker(id=f'{revision}:s{len(speakers)}', label=f'Speaker {label}')
            speaker = speakers[str(label)].id
        if not turns or turns[-1].speaker != speaker:
            turns.append(PreservedSegment(id=f'{revision}:t{len(turns)}', text='', speaker=speaker))
        turn = turns[-1]
        word = PreservedWord(id=f'{revision}:w{index}', word=text, start=start, end=end,
                             turn_id=turn.id, speaker=speaker, evidence_index=index,
                             timing_usable=usable, timing_uncertainty=uncertainty,
                             recognition_confidence=number(native.get('confidence')),
                             speaker_confidence=number(native.get('speaker_confidence')),
                             confidence_source=provider)
        words.append(word)
        turn.word_ids.append(word.id or '')
        turn.text = (turn.text + ' ' + text).strip()
        if usable:
            turn.start = min(turn.start, start) if turn.start is not None else start  # type: ignore[type-var]
            turn.end = max(turn.end, end) if turn.end is not None else end  # type: ignore[type-var]
        if uncertainty:
            turn.uncertainty = ['Contains words with unusable timing.']
    for turn in turns:
        turn.timing_usable = turn.start is not None and turn.end is not None and not turn.uncertainty
        turn.quotation_usable = not unclear_wording(turn.text)
    transcript = PreservedTranscript(revision=revision, segments=turns, words=words,
        duration=transport.duration, language='en', annotations=annotations,
        speakers=list(speakers.values()),
        provenance=ImportProvenance(source_path=transport.path, original_hash=raw_hash,
            original_schema=provider, source_fingerprint=transport.source_fingerprint,
            settings={'request': request, 'source_revision': source_revision, 'transport': transport.model_dump(),
                      'normalization_version': NORMALIZATION_VERSION, 'operation_id': operation_id}, timing_confidence=None))
    transcript.refresh_overlaps()
    return transcript
