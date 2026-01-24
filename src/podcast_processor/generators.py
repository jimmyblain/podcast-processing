"""Content generators for description, titles, and chapters."""

import json
import re

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .llm import ClaudeClient
from .models import Chapter, GeneratedContent, Title, Transcript
from .prompts import CHAPTERS_PROMPT, DESCRIPTION_PROMPT, TITLES_PROMPT

console = Console()


class GenerationError(Exception):
    """Error during content generation."""

    pass


def _format_transcript_with_timestamps(transcript: Transcript) -> str:
    """Format transcript with timestamps for chapter generation."""
    lines = []
    for segment in transcript.segments:
        minutes = int(segment.start // 60)
        seconds = int(segment.start % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        lines.append(f"{timestamp} {segment.text.strip()}")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    """Extract JSON array from text that might contain other content."""
    # Try to find JSON array in the response
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        return match.group(0)
    return text


def _truncate_transcript(transcript: Transcript, max_chars: int = 50000) -> str:
    """Truncate transcript to fit within token limits."""
    full_text = transcript.full_text
    if len(full_text) <= max_chars:
        return full_text
    # Truncate and add indicator
    return full_text[:max_chars] + "\n\n[... transcript truncated for length ...]"


def generate_description(client: ClaudeClient, transcript: Transcript) -> str:
    """Generate a YouTube description from the transcript.

    Args:
        client: Claude API client
        transcript: The podcast transcript

    Returns:
        Generated description text
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating description...", total=None)

        prompt = DESCRIPTION_PROMPT.format(
            transcript=_truncate_transcript(transcript),
        )

        description = client.generate(prompt, temperature=0.7)

    console.print("[bold green]Description generated!")
    return description.strip()


def generate_titles(client: ClaudeClient, transcript: Transcript) -> list[Title]:
    """Generate viral title variations from the transcript.

    Args:
        client: Claude API client
        transcript: The podcast transcript

    Returns:
        List of 10 title variations with thumbnail text
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating titles...", total=None)

        prompt = TITLES_PROMPT.format(
            transcript=_truncate_transcript(transcript),
        )

        response = client.generate(prompt, temperature=0.8)

    try:
        json_str = _extract_json(response)
        titles_data = json.loads(json_str)

        titles = [
            Title(
                title=t.get("title", ""),
                thumbnail_text=t.get("thumbnail_text", ""),
                reasoning=t.get("reasoning", ""),
            )
            for t in titles_data
        ]

        console.print(f"[bold green]Generated {len(titles)} titles!")
        return titles

    except json.JSONDecodeError as e:
        raise GenerationError(f"Failed to parse titles JSON: {e}\nResponse: {response}")


def generate_chapters(
    client: ClaudeClient,
    transcript: Transcript,
    chapter_count: int = 10,
) -> list[Chapter]:
    """Generate chapters with timestamps from the transcript.

    Args:
        client: Claude API client
        transcript: The podcast transcript
        chapter_count: Target number of chapters

    Returns:
        List of chapters with timestamps
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating chapters...", total=None)

        # Format transcript with timestamps for better chapter alignment
        transcript_with_ts = _format_transcript_with_timestamps(transcript)

        # Truncate if needed
        if len(transcript_with_ts) > 50000:
            transcript_with_ts = (
                transcript_with_ts[:50000]
                + "\n\n[... transcript truncated for length ...]"
            )

        prompt = CHAPTERS_PROMPT.format(
            transcript_with_timestamps=transcript_with_ts,
            chapter_count=chapter_count,
        )

        response = client.generate(prompt, temperature=0.5)

    try:
        json_str = _extract_json(response)
        chapters_data = json.loads(json_str)

        chapters = [
            Chapter(
                start_time=c.get("start_time", 0.0),
                title=c.get("title", ""),
                description=c.get("description", ""),
            )
            for c in chapters_data
        ]

        # Sort by start time
        chapters.sort(key=lambda c: c.start_time)

        # Ensure first chapter starts at 0
        if chapters and chapters[0].start_time > 0:
            chapters[0].start_time = 0.0

        console.print(f"[bold green]Generated {len(chapters)} chapters!")
        return chapters

    except json.JSONDecodeError as e:
        raise GenerationError(
            f"Failed to parse chapters JSON: {e}\nResponse: {response}"
        )


def generate_all_content(
    client: ClaudeClient,
    transcript: Transcript,
    chapter_count: int = 10,
) -> GeneratedContent:
    """Generate all content (description, titles, chapters) from transcript.

    Args:
        client: Claude API client
        transcript: The podcast transcript
        chapter_count: Target number of chapters

    Returns:
        GeneratedContent with all generated content
    """
    console.print("\n[bold blue]Generating YouTube content...[/]\n")

    description = generate_description(client, transcript)
    titles = generate_titles(client, transcript)
    chapters = generate_chapters(client, transcript, chapter_count)

    return GeneratedContent(
        description=description,
        titles=titles,
        chapters=chapters,
    )
