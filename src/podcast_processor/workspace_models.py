"""Strict, versioned records for preserved episode work."""
from typing import Any, Literal
import textwrap
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .managed_models import TranscriptionOperation


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


def unclear_wording(text: str) -> bool:
    return bool(re.search(r'[\[<][^\]>]*(?:unclear|inaudible|unintelligible|crosstalk|unknown)[^\]>]*[\]>]', text, re.I))


class ShowProfile(Record):
    schema_version: Literal[2] = 2
    approved: Literal[True]
    name: Literal["I'll Just Let Myself In"]
    host: Literal['Lish Speaks']
    audience: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    links: list[str] = Field(default_factory=list)
    promotional_text: str | None = None


class Participant(Record):
    name: str = Field(min_length=1, pattern=r'\S')
    role: Literal['host', 'guest']
    biography: str | None = None
    links: list[str] = Field(default_factory=list)


class EpisodeMetadata(Record):
    schema_version: Literal[2] = 2
    solo: bool
    participants: list[Participant]
    angle: str | None = None
    links: list[str] = Field(default_factory=list)
    sponsors: list[str] = Field(default_factory=list)
    current_context: str | None = None

    @model_validator(mode='after')
    def confirmed_participants(self) -> 'EpisodeMetadata':
        hosts = [p.name for p in self.participants if p.role == 'host']
        guests = [p for p in self.participants if p.role == 'guest']
        if hosts != ['Lish Speaks']:
            raise ValueError('The confirmed host must be Lish Speaks.')
        if self.solo == bool(guests):
            raise ValueError('Supply confirmed guest names or explicit solo status.')
        names = [p.name.strip().casefold() for p in self.participants]
        if len(set(names)) != len(names):
            raise ValueError('Participant names must be distinct.')
        return self


class PreservedSegment(Record):
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    text: str
    speaker: str | None = None
    id: str | None = None
    word_ids: list[str] = Field(default_factory=list)
    timing_usable: bool = False
    uncertainty: list[str] = Field(default_factory=list)
    quotation_usable: bool = True
    overlaps: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def bounds(self) -> 'PreservedSegment':
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError('Segment end precedes start.')
        if unclear_wording(self.text):
            self.quotation_usable = False
        return self


class PreservedWord(Record):
    word: str
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    probability: float | None = None
    id: str | None = None
    turn_id: str | None = None
    speaker: str | None = None
    timing_usable: bool = False
    timing_uncertainty: list[str] = Field(default_factory=list)
    recognition_confidence: float | None = None
    speaker_confidence: float | None = None
    confidence_source: str | None = None
    evidence_index: int | None = None


class ImportProvenance(Record):
    source_path: str
    original_hash: str
    original_schema: str
    source_fingerprint: str | None = None
    settings: dict[str, Any] | None = None
    timing_confidence: str | None = None


class DetectedSpeaker(Record):
    id: str
    label: str | None = None
    participant: str | None = None
    identity_status: Literal['unresolved', 'supported', 'corrected', 'uncertain'] = 'unresolved'
    identity_evidence: list[str] = Field(default_factory=list)


class TranscriptChange(Record):
    base_revision: str | None
    base_sha256: str
    source_revision: str
    revision: str
    component: str
    input_hash: str
    changes: list[dict[str, Any]]


class PreservedTranscript(Record):
    schema_version: Literal[2] = 2
    segments: list[PreservedSegment]
    words: list[PreservedWord] = Field(default_factory=list)
    language: str | None = None
    duration: float | None = Field(default=None, ge=0)
    provenance: ImportProvenance
    revision: str | None = None
    speakers: list[DetectedSpeaker] = Field(default_factory=list)
    annotations: list[dict[str, Any]] = Field(default_factory=list)
    mapping_inputs: str | None = None
    lineage: list[TranscriptChange] = Field(default_factory=list)

    @model_validator(mode='after')
    def structural_checks(self) -> 'PreservedTranscript':
        # Missing legacy references remain unknown. Supplied references must agree.
        for records in (self.segments, self.words, self.speakers):
            ids = [record.id for record in records if record.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate timed-transcript record references.')
        turns = {t.id: t for t in self.segments if t.id is not None}
        words = {w.id: w for w in self.words if w.id is not None}
        speakers = {s.id for s in self.speakers}
        intervals: list[PreservedSegment | PreservedWord] = [*self.segments, *self.words]
        for interval in intervals:
            if interval.start is not None and interval.end is not None and interval.end < interval.start:
                raise ValueError('Record end precedes start.')
            if self.duration is not None and any(bound is not None and bound > self.duration for bound in (interval.start, interval.end)):
                raise ValueError('Known interval is outside the source duration.')
            if interval.timing_usable and (interval.start is None or interval.end is None or interval.start >= interval.end):
                raise ValueError('Usable timing requires a positive known interval.')
            if self.revision is not None and interval.speaker is not None and interval.speaker not in speakers:
                raise ValueError('Unknown speaker reference in timed transcript.')
        assigned = []
        for turn in self.segments:
            for ref in turn.word_ids:
                if ref not in words or words[ref].turn_id != turn.id or words[ref].speaker != turn.speaker:
                    raise ValueError('Word and containing turn references disagree.')
                assigned.append(ref)
        if len(assigned) != len(set(assigned)):
            raise ValueError('A word is referenced by multiple turns.')
        for word in self.words:
            if word.turn_id is None:
                continue
            containing_turn = turns.get(word.turn_id)
            if containing_turn is None or word.id not in containing_turn.word_ids:
                raise ValueError('Word has no matching containing containing_turn.')
            if word.timing_usable and (containing_turn.start is None or containing_turn.end is None or word.start is None or word.end is None
                                       or not containing_turn.start <= word.start < word.end <= containing_turn.end):
                raise ValueError('Usable word timing must fit its containing containing_turn.')
        return self

    def refresh_overlaps(self) -> None:
        active: list[PreservedSegment] = []
        for turn in self.segments:
            turn.overlaps = []
        for turn in sorted((t for t in self.segments if t.start is not None and t.end is not None), key=lambda t: t.start or 0):
            assert turn.start is not None and turn.end is not None
            active = [other for other in active if other.end is not None and other.end > turn.start]
            if turn.end <= turn.start:
                continue
            for other in active:
                if other.id is not None and turn.id is not None:
                    other.overlaps.append(turn.id)
                    turn.overlaps.append(other.id)
            active.append(turn)

    @property
    def has_timing(self) -> bool:
        return bool(self.segments) and self.duration is not None and self.duration > 0 and all(
            s.start is not None and s.end is not None and s.start < s.end <= self.duration
            for s in self.segments
        )

    def readable(self) -> str:
        lines = []
        names = {s.id: s.participant or s.label or s.id for s in self.speakers}
        for segment in self.segments:
            stamp = 'unknown time'
            if segment.start is not None:
                seconds = int(segment.start)
                stamp = f'{seconds // 60:02d}:{seconds % 60:02d}'
            label = names.get(segment.speaker or '') or segment.speaker or 'Unknown speaker'
            lines.append(textwrap.fill(f'[{stamp}] {label}: {segment.text}', width=100,
                                       subsequent_indent='  ', break_long_words=False, break_on_hyphens=False))
        return '\n\n'.join(lines) + '\n'


class SourceRevision(Record):
    id: str
    fingerprint: str | None = None
    locator: str | None = None
    copied_path: str | None = None
    properties: dict[str, Any] | None = None
    created_at: str


class Artifact(Record):
    id: str
    name: str
    path: str
    sha256: str
    schema_version: int = 2
    stage_version: str
    dependencies: dict[str, str]
    run_id: str
    created_at: str
    status: Literal['completed', 'human-edited'] = 'completed'


class Run(Record):
    id: str
    operation_id: str
    operation: str
    status: Literal['running', 'completed', 'partial', 'failed', 'interrupted']
    started_at: str
    finished_at: str | None = None
    inputs: dict[str, Any]
    missing: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PublishingAttempt(Record):
    id: str
    started_at: str
    finished_at: str | None = None
    status: Literal['requested', 'responded', 'invalid', 'failed', 'validated'] = 'requested'
    request: dict[str, Any]
    response_path: str
    response_hash: str | None = None
    returned_model: str | None = None
    request_id: str | None = None
    response_id: str | None = None
    usage: dict[str, Any] = Field(default_factory=lambda: {'actual': None, 'estimated': None, 'reserved': None})
    error: str | None = None


class PublishingOperation(Record):
    id: str
    stage: str
    dependencies: dict[str, str]
    created_at: str
    attempts: list[PublishingAttempt] = Field(default_factory=list)


class WorkspaceState(Record):
    schema_version: Literal[2] = 2
    episode_id: str
    name: str
    source_revision: str
    sources: list[SourceRevision]
    show_profile: ShowProfile | None = None
    episode_metadata: EpisodeMetadata | None = None
    input_revision: str
    import_hash: str
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    evidence: dict[str, Artifact] = Field(default_factory=dict)
    history: list[Artifact] = Field(default_factory=list)
    runs: list[Run] = Field(default_factory=list)
    publishing_operations: list[PublishingOperation] = Field(default_factory=list)
    transcription_operations: list[TranscriptionOperation] = Field(default_factory=list)
