"""Strict, versioned records for preserved episode work."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


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

    @model_validator(mode='after')
    def bounds(self) -> 'PreservedSegment':
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError('Segment end precedes start.')
        return self


class PreservedWord(Record):
    word: str
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    probability: float | None = None


class ImportProvenance(Record):
    source_path: str
    original_hash: str
    original_schema: str
    source_fingerprint: str | None = None
    settings: dict[str, Any] | None = None
    timing_confidence: str | None = None


class PreservedTranscript(Record):
    schema_version: Literal[2] = 2
    segments: list[PreservedSegment]
    words: list[PreservedWord] = Field(default_factory=list)
    language: str | None = None
    duration: float | None = Field(default=None, ge=0)
    provenance: ImportProvenance

    @property
    def has_timing(self) -> bool:
        return bool(self.segments) and self.duration is not None and self.duration > 0 and all(
            s.start is not None and s.end is not None and s.start < s.end <= self.duration
            for s in self.segments
        )

    def readable(self) -> str:
        lines = []
        for segment in self.segments:
            stamp = 'unknown time'
            if segment.start is not None:
                seconds = int(segment.start)
                stamp = f'{seconds // 60:02d}:{seconds % 60:02d}'
            lines.append(f'[{stamp}] {segment.speaker or "Unknown speaker"}: {segment.text}')
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
