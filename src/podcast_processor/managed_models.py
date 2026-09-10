"""Persisted managed transcription evidence and allowances (USD, source seconds)."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

ProviderName = Literal['assemblyai', 'deepgram']


class TranscriptionPolicy(Record):
    deadline_seconds: float = Field(default=900, gt=0, le=900)
    allowance_usd: float = Field(default=3, gt=0, le=3)
    # Conservative admission policy, deliberately not a quote or observed bill.
    primary_reservation_per_hour: float = Field(default=1.50, gt=0)
    backup_reservation_per_hour: float = Field(default=1.50, gt=0)
    read_attempts: int = Field(default=4, ge=1, le=10)
    submission_attempts: int = Field(default=2, ge=1, le=3)


class Transport(Record):
    source_fingerprint: str
    submitted_fingerprint: str
    path: str
    duration: float = Field(gt=0)
    decoded_sha256: str
    transformation: str = 'FLAC, first audio stream; no trimming, resampling or channel changes'
    equivalence: Literal['verified'] = 'verified'
    timeline_offset_seconds: Literal[0] = 0


class TranscriptionAttempt(Record):
    id: str
    provider: ProviderName
    request: dict[str, Any]
    status: Literal['intent', 'accepted', 'ambiguous', 'rejected', 'failed', 'completed', 'unusable', 'blocked'] = 'intent'
    job_id: str | None = None
    submitted_at: float
    updated_at: float
    submissions: int = 0
    reads: int = 0
    transient_reads: int = 0
    reconciliations: int = 0
    estimated_usd: float = Field(ge=0)
    reserved_usd: float = Field(ge=0)
    actual_usd: float | None = Field(default=None, ge=0)
    raw_artifact: str | None = None
    error: str | None = None


class TranscriptionOperation(Record):
    id: str
    dependencies: dict[str, str]
    policy: TranscriptionPolicy
    started_at: float
    deadline_at: float
    elapsed_seconds: float = 0
    transport: Transport | None = None
    upload_url: str | None = None
    attempts: list[TranscriptionAttempt] = Field(default_factory=list)
    status: Literal['running', 'completed', 'partial', 'unavailable'] = 'running'
    outcome: str | None = None
