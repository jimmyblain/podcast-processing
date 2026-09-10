"""Structured publishing copy and a durable, publishing-only attempt ledger."""
import re

from pydantic import Field, field_validator

from .workspace_models import Record


class CopyRecord(Record):
    @field_validator('*')
    @classmethod
    def nonempty_strings(cls, value):
        if isinstance(value, str) and (not value.strip() or '\n' in value or '\r' in value):
            raise ValueError('Copy fields must contain nonempty single-line text.')
        return value


class DescriptionBody(CopyRecord):
    hook: str
    overview: str
    takeaways: list[str] = Field(min_length=3, max_length=5)
    question: str
    invitation: str
    notes: list[str] = Field(default_factory=list)

    def render(self) -> str:
        if any(not item.strip() or '\n' in item or '\r' in item for item in self.takeaways):
            raise ValueError('Takeaways must be nonempty single-line text.')
        return '\n\n'.join([self.hook, self.overview, 'In this episode:\n' + '\n'.join('• ' + t for t in self.takeaways),
                             self.question + ' ' + self.invitation])


class VisualDirection(CopyRecord):
    subject: str
    expression: str
    composition: str


class TitleConcept(CopyRecord):
    title: str = Field(max_length=100)
    category: str
    thumbnail_text: str
    visual_direction: VisualDirection
    reasoning: str

    @field_validator('title')
    @classmethod
    def portable_title(cls, value: str) -> str:
        if '<' in value or '>' in value:
            raise ValueError('Titles cannot contain angle brackets.')
        return value

    @field_validator('thumbnail_text')
    @classmethod
    def short_overlay(cls, value: str) -> str:
        if not 2 <= len(value.split()) <= 4:
            raise ValueError('Thumbnail overlay requires 2–4 words.')
        return value


class PublishingChapter(CopyRecord):
    start_time: float = Field(ge=0, strict=True)
    title: str
    boundary_id: str
    reason: str

    @field_validator('title')
    @classmethod
    def plain_label(cls, value: str) -> str:
        if re.match(r'^(?:[#•*\-]|\d+:\d{2}|\d+[.)]\s)', value) or '`' in value:
            raise ValueError('Chapter labels must be plain titles, without timestamp, heading or bullet markup.')
        return value


def timestamp(seconds: float) -> str:
    value = int(seconds)
    if value >= 3600:
        return f'{value // 3600}:{value % 3600 // 60:02d}:{value % 60:02d}'
    return f'{value // 60:02d}:{value % 60:02d}'
