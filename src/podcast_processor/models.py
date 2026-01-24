"""Pydantic data models for podcast processing."""

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A segment of transcribed audio with timing information."""

    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text content")


class WordTimestamp(BaseModel):
    """Word-level timestamp information."""

    word: str = Field(description="The transcribed word")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    probability: float = Field(description="Confidence score")


class Transcript(BaseModel):
    """Complete transcript with segments and metadata."""

    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="List of transcript segments",
    )
    words: list[WordTimestamp] = Field(
        default_factory=list,
        description="Word-level timestamps",
    )
    language: str = Field(default="en", description="Detected language")
    duration: float = Field(default=0.0, description="Total duration in seconds")

    @property
    def full_text(self) -> str:
        """Get the complete transcript as plain text."""
        return " ".join(seg.text.strip() for seg in self.segments)

    def get_text_at_time(self, time_seconds: float) -> str | None:
        """Get the text being spoken at a specific time."""
        for segment in self.segments:
            if segment.start <= time_seconds <= segment.end:
                return segment.text
        return None


class Chapter(BaseModel):
    """A chapter/section in the podcast."""

    start_time: float = Field(description="Start time in seconds")
    title: str = Field(description="Chapter title")
    description: str = Field(default="", description="Optional chapter description")

    @property
    def timestamp(self) -> str:
        """Format start time as HH:MM:SS or MM:SS."""
        total_seconds = int(self.start_time)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def to_youtube_format(self) -> str:
        """Format as YouTube chapter string."""
        if self.description:
            return f"{self.timestamp} {self.title} - {self.description}"
        return f"{self.timestamp} {self.title}"


class Title(BaseModel):
    """A generated title with thumbnail text."""

    title: str = Field(description="The video title")
    thumbnail_text: str = Field(description="Short text for thumbnail overlay")
    reasoning: str = Field(default="", description="Why this title works")


class GeneratedContent(BaseModel):
    """All generated content for a podcast episode."""

    description: str = Field(default="", description="YouTube description")
    titles: list[Title] = Field(default_factory=list, description="Generated titles")
    chapters: list[Chapter] = Field(
        default_factory=list, description="Generated chapters"
    )


class ProcessingResult(BaseModel):
    """Complete result of processing a podcast."""

    source_file: str = Field(description="Original audio file path")
    transcript: Transcript = Field(description="Full transcript")
    content: GeneratedContent = Field(description="Generated content")
