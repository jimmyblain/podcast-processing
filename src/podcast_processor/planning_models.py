"""Explicit evidence and exact duration contracts for source-relative planning."""
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .workspace_models import Record


class SourceEvidence(Record):
    revision: str
    fingerprint: str | None = None
    duration: Decimal | None = Field(default=None, gt=0)
    basis: Literal['verified', 'fixture', 'unknown'] = 'unknown'
    evidence: str = ''


class PreparedTransition(Record):
    asset_revision: str
    prepared_revision: str | None = None
    duration: Decimal | None = Field(default=None, gt=0)
    ending_silence: Decimal | None = Field(default=None, ge=0)
    preserves_decay: bool = False
    replaces_excess_tail: bool = False
    basis: Literal['verified', 'fixture', 'unknown'] = 'unknown'
    evidence: str = ''

    def problem(self) -> str | None:
        if (not self.asset_revision.strip() or not self.prepared_revision or not self.prepared_revision.strip()
                or self.duration is None or self.basis == 'unknown' or not self.evidence.strip()):
            return 'Verified prepared-duration evidence or labeled fixture assumptions are unavailable.'
        if (self.ending_silence != Decimal('2.5') or self.duration < Decimal('2.5')
                or not self.preserves_decay or not self.replaces_excess_tail):
            return ('Preparation must preserve decay and replace excess dead space with a total '
                    '2.5-second ending silence, already included once.')
        return None


class PlanningSettings(Record):
    pause: Decimal = Field(default=Decimal('1.5'), ge=0)
    minimum: Decimal = Field(default=Decimal('600'), gt=0)
    maximum: Decimal = Field(default=Decimal('1080'), gt=0)

    @model_validator(mode='after')
    def ordered(self) -> 'PlanningSettings':
        if self.minimum > self.maximum:
            raise ValueError('Section minimum exceeds maximum.')
        return self


class NaturalBoundary(Record):
    id: str = Field(min_length=1)
    time: Decimal = Field(gt=0)
    before_word: str
    after_word: str
    complete_thought: bool
    natural_topic_boundary: bool
    reason: str = Field(min_length=1, pattern=r'\S')
    basis: Literal['transcript-supported', 'source-reviewed', 'fixture']
    # Editorial strength is considered before duration similarity.
    strength: int = Field(default=1, ge=1, le=3)
    safe_start: Decimal | None = Field(default=None, ge=0)
    safe_end: Decimal | None = Field(default=None, ge=0)


class PlanningEvidence(Record):
    schema_version: Literal[1] = 1
    source: SourceEvidence
    transcript_sha256: str
    episode_start: PreparedTransition | None = None
    transition_in: PreparedTransition | None = None
    transition_out: PreparedTransition | None = None
    settings: PlanningSettings = Field(default_factory=PlanningSettings)
    boundaries: list[NaturalBoundary] = Field(default_factory=list)


class FinishedSection(Record):
    number: int = Field(ge=1, le=3)
    source_start: Decimal = Field(ge=0)
    source_end: Decimal = Field(gt=0)
    part_duration: Decimal = Field(gt=0)
    opening: Literal['episode_start', 'transition_in']
    opening_duration: Decimal = Field(gt=0)
    pause: Decimal = Field(ge=0)
    closing_duration: Decimal = Field(ge=0)
    finished_duration: Decimal = Field(gt=0)


class SectionProposal(Record):
    # Version 1 remains readable as historical evidence of the earlier assembly rule.
    schema_version: Literal[1, 2] = 2
    evidence: PlanningEvidence
    boundaries: list[NaturalBoundary] = Field(min_length=2, max_length=2)
    sections: list[FinishedSection] = Field(min_length=3, max_length=3)
    limitations: list[str]

    @model_validator(mode='after')
    def valid_assembly(self) -> 'SectionProposal':
        evidence = self.evidence
        if (evidence.source.duration is None or not evidence.source.fingerprint
                or evidence.source.basis == 'unknown' or not evidence.source.evidence.strip()):
            raise ValueError('A proposal requires explicit original-source identity/duration evidence.')
        for asset in (evidence.episode_start, evidence.transition_in, evidence.transition_out):
            if asset is None or asset.problem():
                raise ValueError(asset.problem() if asset else 'Prepared transition evidence is unavailable.')
        if any(not b.complete_thought or not b.natural_topic_boundary for b in self.boundaries):
            raise ValueError('Cuts require complete thoughts and natural topic boundaries.')
        if any(b not in evidence.boundaries for b in self.boundaries):
            raise ValueError('Selected boundaries must retain their input evidence.')
        endpoints = [Decimal(0), *(b.time for b in self.boundaries), evidence.source.duration]
        for index, section in enumerate(self.sections):
            opening_name = 'episode_start' if index == 0 else 'transition_in'
            opening = evidence.episode_start if index == 0 else evidence.transition_in
            closing = evidence.transition_out
            if opening is None or closing is None or opening.duration is None or closing.duration is None:
                raise ValueError('Explicit prepared transition durations are required.')
            has_closing = index < 2 or self.schema_version == 1
            closing_duration = closing.duration if has_closing else Decimal(0)
            pause = evidence.settings.pause if has_closing else Decimal(0)
            if (section.number != index + 1 or section.source_start != endpoints[index]
                    or section.source_end != endpoints[index + 1]
                    or section.part_duration != section.source_end - section.source_start):
                raise ValueError('Exactly three ordered parts must cover the source once with exact adjacency.')
            if (section.opening != opening_name or section.opening_duration != opening.duration
                    or section.closing_duration != closing_duration or section.pause != pause
                    or section.finished_duration != section.opening_duration + section.part_duration + section.pause + section.closing_duration):
                raise ValueError('Finished duration must include the explicit opening, part, separate pause and closing.')
            if not evidence.settings.minimum <= section.finished_duration <= evidence.settings.maximum:
                raise ValueError('Finished section is outside the inclusive duration limits.')
        return self


class PlanningOutcome(Record):
    schema_version: Literal[1, 2] = 2
    status: Literal['valid', 'unavailable']
    evidence: PlanningEvidence
    dependencies: dict[str, str]
    overhead: list[Decimal | None]
    source_part_limits: list[tuple[Decimal, Decimal] | None]
    reasons: list[str]
    rejected_boundaries: dict[str, str]
    limitations: list[str]
    proposal: SectionProposal | None = None

    @model_validator(mode='after')
    def consistent(self) -> 'PlanningOutcome':
        if (self.status == 'valid') != (self.proposal is not None):
            raise ValueError('Only valid outcomes may contain a proposal.')
        if self.status == 'unavailable' and not self.reasons:
            raise ValueError('Unavailable planning must explain its limiting conditions.')
        return self
