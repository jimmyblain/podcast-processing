"""CLI interface for podcast processing."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Settings, WhisperModel, get_settings
from .generators import generate_all_content
from .llm import ClaudeClient, LLMError
from .models import GeneratedContent, Transcript
from .transcriber import TranscriptionError, WhisperLocalTranscriber

app = typer.Typer(
    name="podcast-process",
    help="Process podcast audio to generate YouTube-ready content.",
    no_args_is_help=True,
)
console = Console()


def _save_outputs(
    output_dir: Path,
    transcript: Transcript,
    content: GeneratedContent | None = None,
) -> None:
    """Save all outputs to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save transcript JSON
    transcript_json = output_dir / "transcript.json"
    with open(transcript_json, "w") as f:
        json.dump(transcript.model_dump(), f, indent=2)
    console.print(f"  [dim]Saved:[/] {transcript_json}")

    # Save transcript plain text
    transcript_txt = output_dir / "transcript.txt"
    with open(transcript_txt, "w") as f:
        f.write(transcript.full_text)
    console.print(f"  [dim]Saved:[/] {transcript_txt}")

    if content:
        # Save description
        if content.description:
            desc_file = output_dir / "description.md"
            with open(desc_file, "w") as f:
                f.write(content.description)
            console.print(f"  [dim]Saved:[/] {desc_file}")

        # Save titles
        if content.titles:
            titles_file = output_dir / "titles.json"
            with open(titles_file, "w") as f:
                json.dump([t.model_dump() for t in content.titles], f, indent=2)
            console.print(f"  [dim]Saved:[/] {titles_file}")

        # Save chapters
        if content.chapters:
            chapters_file = output_dir / "chapters.txt"
            with open(chapters_file, "w") as f:
                for chapter in content.chapters:
                    f.write(chapter.to_youtube_format() + "\n")
            console.print(f"  [dim]Saved:[/] {chapters_file}")


def _display_summary(transcript: Transcript, content: GeneratedContent | None) -> None:
    """Display a summary of the generated content."""
    console.print("\n")

    # Transcript info
    duration_min = int(transcript.duration // 60)
    duration_sec = int(transcript.duration % 60)
    console.print(
        Panel(
            f"Duration: {duration_min}m {duration_sec}s\n"
            f"Segments: {len(transcript.segments)}\n"
            f"Words: {len(transcript.words)}\n"
            f"Language: {transcript.language}",
            title="Transcript",
            border_style="blue",
        )
    )

    if content and content.titles:
        # Show titles
        table = Table(title="Generated Titles", show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Title", style="cyan")
        table.add_column("Thumbnail", style="yellow")

        for i, title in enumerate(content.titles[:5], 1):  # Show first 5
            table.add_row(str(i), title.title, title.thumbnail_text)

        if len(content.titles) > 5:
            table.add_row("...", f"(+{len(content.titles) - 5} more in titles.json)", "")

        console.print(table)

    if content and content.chapters:
        # Show chapters
        table = Table(title="Chapters", show_header=True, header_style="bold")
        table.add_column("Time", style="green", width=10)
        table.add_column("Title", style="cyan")

        for chapter in content.chapters:
            table.add_row(chapter.timestamp, chapter.title)

        console.print(table)


@app.command()
def process(
    audio_file: Annotated[
        Path, typer.Argument(help="Path to the podcast audio file")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory"),
    ] = None,
    whisper_model: Annotated[
        WhisperModel,
        typer.Option("--whisper-model", "-m", help="Whisper model to use"),
    ] = "medium",
    chapters: Annotated[
        int,
        typer.Option("--chapters", "-c", help="Number of chapters to generate"),
    ] = 10,
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key"),
    ] = None,
) -> None:
    """Process a podcast audio file to generate YouTube content.

    Transcribes the audio and generates description, titles, and chapters.
    """
    settings = get_settings()

    # Resolve API key
    resolved_api_key = api_key or settings.anthropic_api_key
    if not resolved_api_key:
        console.print(
            "[bold red]Error:[/] Anthropic API key required. "
            "Set ANTHROPIC_API_KEY environment variable or use --api-key."
        )
        raise typer.Exit(1)

    # Resolve output directory
    output_dir = output or settings.default_output_dir / audio_file.stem

    console.print(
        Panel(
            f"[bold]Audio:[/] {audio_file}\n"
            f"[bold]Output:[/] {output_dir}\n"
            f"[bold]Whisper Model:[/] {whisper_model}\n"
            f"[bold]Chapters:[/] {chapters}",
            title="Podcast Processor",
            border_style="green",
        )
    )

    try:
        # Transcribe
        transcriber = WhisperLocalTranscriber(model_name=whisper_model)
        transcript = transcriber.transcribe(audio_file)

        # Generate content
        client = ClaudeClient(api_key=resolved_api_key, model=settings.claude_model)
        content = generate_all_content(client, transcript, chapter_count=chapters)

        # Save outputs
        console.print("\n[bold blue]Saving outputs...[/]")
        _save_outputs(output_dir, transcript, content)

        # Display summary
        _display_summary(transcript, content)

        console.print(
            f"\n[bold green]Done![/] All files saved to: {output_dir}"
        )

    except TranscriptionError as e:
        console.print(f"[bold red]Transcription error:[/] {e}")
        raise typer.Exit(1)
    except LLMError as e:
        console.print(f"[bold red]LLM error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def transcribe(
    audio_file: Annotated[
        Path, typer.Argument(help="Path to the podcast audio file")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory"),
    ] = None,
    whisper_model: Annotated[
        WhisperModel,
        typer.Option("--whisper-model", "-m", help="Whisper model to use"),
    ] = "medium",
) -> None:
    """Transcribe a podcast audio file (no LLM calls).

    Only generates transcript files, skips content generation.
    """
    settings = get_settings()

    # Resolve output directory
    output_dir = output or settings.default_output_dir / audio_file.stem

    console.print(
        Panel(
            f"[bold]Audio:[/] {audio_file}\n"
            f"[bold]Output:[/] {output_dir}\n"
            f"[bold]Whisper Model:[/] {whisper_model}",
            title="Transcribe Only",
            border_style="blue",
        )
    )

    try:
        # Transcribe
        transcriber = WhisperLocalTranscriber(model_name=whisper_model)
        transcript = transcriber.transcribe(audio_file)

        # Save outputs (transcript only)
        console.print("\n[bold blue]Saving transcript...[/]")
        _save_outputs(output_dir, transcript, content=None)

        # Display summary
        _display_summary(transcript, content=None)

        console.print(
            f"\n[bold green]Done![/] Transcript saved to: {output_dir}"
        )

    except TranscriptionError as e:
        console.print(f"[bold red]Transcription error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def generate(
    transcript_file: Annotated[
        Path, typer.Argument(help="Path to transcript.json file")
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output directory"),
    ] = None,
    chapters: Annotated[
        int,
        typer.Option("--chapters", "-c", help="Number of chapters to generate"),
    ] = 10,
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key"),
    ] = None,
) -> None:
    """Generate content from an existing transcript.

    Reads a transcript.json file and generates description, titles, and chapters.
    Useful when you already have a transcript and want to regenerate content.
    """
    settings = get_settings()

    # Resolve API key
    resolved_api_key = api_key or settings.anthropic_api_key
    if not resolved_api_key:
        console.print(
            "[bold red]Error:[/] Anthropic API key required. "
            "Set ANTHROPIC_API_KEY environment variable or use --api-key."
        )
        raise typer.Exit(1)

    if not transcript_file.exists():
        console.print(f"[bold red]Error:[/] Transcript file not found: {transcript_file}")
        raise typer.Exit(1)

    # Resolve output directory
    output_dir = output or transcript_file.parent

    console.print(
        Panel(
            f"[bold]Transcript:[/] {transcript_file}\n"
            f"[bold]Output:[/] {output_dir}\n"
            f"[bold]Chapters:[/] {chapters}",
            title="Generate from Transcript",
            border_style="yellow",
        )
    )

    try:
        # Load transcript
        with open(transcript_file) as f:
            transcript_data = json.load(f)
        transcript = Transcript.model_validate(transcript_data)

        console.print(
            f"[bold blue]Loaded transcript:[/] {len(transcript.segments)} segments, "
            f"{transcript.duration:.1f}s duration"
        )

        # Generate content
        client = ClaudeClient(api_key=resolved_api_key, model=settings.claude_model)
        content = generate_all_content(client, transcript, chapter_count=chapters)

        # Save outputs (content only, transcript already exists)
        console.print("\n[bold blue]Saving outputs...[/]")
        _save_outputs(output_dir, transcript, content)

        # Display summary
        _display_summary(transcript, content)

        console.print(
            f"\n[bold green]Done![/] Content saved to: {output_dir}"
        )

    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error parsing transcript:[/] {e}")
        raise typer.Exit(1)
    except LLMError as e:
        console.print(f"[bold red]LLM error:[/] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
