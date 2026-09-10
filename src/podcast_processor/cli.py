"""CLI interface for podcast processing."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import WhisperModel, get_settings
from .operations import generate_legacy, load_legacy_transcript, transcribe_legacy
from .workspace import WorkspaceError
from .llm import LLMError
from .models import GeneratedContent, Transcript
from .transcriber import TranscriptionError

app = typer.Typer(
    name="podcast-process",
    help="Process podcast audio to generate YouTube-ready content.",
    no_args_is_help=True,
)
console = Console()


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

    # Step 1: Transcribe the audio. This is the slow, expensive part (it runs
    # the Whisper model locally), so we protect it in its own try/except.
    try:
        transcript = transcribe_legacy(audio_file, output_dir, whisper_model)
    except TranscriptionError as e:
        console.print(f"[bold red]Transcription error:[/] {e}")
        raise typer.Exit(1)

    # Step 3: Generate the YouTube content (description, titles, chapters) via
    # the Claude API. If this fails, we point the user at the saved transcript
    # so they can pick up exactly where they left off without re-transcribing.
    try:
        content = generate_legacy(transcript, output_dir, resolved_api_key, settings.claude_model, chapters)
    except LLMError as e:
        console.print(f"[bold red]LLM error:[/] {e}")
        transcript_path = output_dir / "transcript.json"
        console.print(
            "\n[yellow]Good news:[/] your transcript was already saved before "
            "this error, so no transcription work was lost.\n"
            "Once the issue is resolved, resume content generation with:\n"
            f"  [bold]podcast-process generate \"{transcript_path}\"[/]"
        )
        raise typer.Exit(1)

    # Display summary
    _display_summary(transcript, content)

    console.print(
        f"\n[bold green]Done![/] All files saved to: {output_dir}"
    )


@app.command()
def transcribe(
    audio_file: Annotated[Path, typer.Argument(help="Recording or managed episode workspace")],
    output: Annotated[Optional[Path], typer.Option("-o", "--output")] = None,
    whisper_model: Annotated[WhisperModel, typer.Option("--whisper-model", "-m")] = "medium",
    workspace: Annotated[Optional[Path], typer.Option()] = None,
    show_profile: Annotated[Optional[Path], typer.Option()] = None,
    metadata: Annotated[Optional[Path], typer.Option()] = None,
    fresh: Annotated[bool, typer.Option()] = False,
    local: Annotated[bool, typer.Option(help="Explicit legacy local transcription")] = False,
    allowance: Annotated[float, typer.Option(help="Transcription allowance in USD, at most 3")] = 3,
    deadline: Annotated[float, typer.Option(help="Seconds from operation start, at most 900")] = 900,
) -> None:
    """Transcribe an English episode with managed services; never generate publishing text.

    Resume by passing its workspace. Use --fresh for a new recorded allowance.
    Legacy -o/-m usage remains available; new managed recordings require authority files.
    """
    settings = get_settings()
    try:
        if local or (output is not None and workspace is None and show_profile is None and metadata is None):
            transcript = transcribe_legacy(audio_file, output or settings.default_output_dir / audio_file.stem, whisper_model)
            _display_summary(transcript, None)
            return
        from .managed import transcribe_episode
        from .managed_models import TranscriptionPolicy
        from .workspace_models import ShowProfile, EpisodeMetadata
        state = transcribe_episode(audio_file, workspace_path=workspace or output,
            show_profile=ShowProfile.model_validate_json(show_profile.read_bytes()) if show_profile else None,
            metadata=EpisodeMetadata.model_validate_json(metadata.read_bytes()) if metadata else None,
            primary_key=settings.assemblyai_api_key, backup_key=settings.deepgram_api_key,
            policy=TranscriptionPolicy(allowance_usd=allowance, deadline_seconds=deadline,
                primary_reservation_per_hour=settings.transcription_primary_reservation_per_hour,
                backup_reservation_per_hour=settings.transcription_backup_reservation_per_hour), fresh=fresh)
        destination = workspace or output or (audio_file if audio_file.is_dir() else
                      Path('output/episodes') / f'episode-{state.episode_id}')
        typer.echo(f"Workspace: {destination.resolve()}")
        typer.echo(f"Episode {state.episode_id}: {state.runs[-1].status}")
        typer.echo(state.transcription_operations[-1].outcome or '')
        if state.runs[-1].status != 'completed':
            raise typer.Exit(1)
    except (WorkspaceError, OSError, ValueError, TranscriptionError) as error:
        typer.echo(f"Error: {error}")
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
    if transcript_file.is_dir():
        from .operations import generate_episode
        from .workspace import Workspace
        if output is not None:
            typer.echo("Error: versioned generation writes to the workspace; omit --output.")
            raise typer.Exit(1)
        settings = get_settings()
        try:
            state = generate_episode(transcript_file, api_key or settings.anthropic_api_key,
                                     settings.claude_model, chapters)
            typer.echo(Workspace(transcript_file).report(state))
            if state.runs[-1].status != 'completed':
                raise typer.Exit(1)
            return
        except (WorkspaceError, OSError, ValueError) as error:
            typer.echo(f"Error: {error}")
            raise typer.Exit(1)

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
        transcript = load_legacy_transcript(transcript_file)

        console.print(
            f"[bold blue]Loaded transcript:[/] {len(transcript.segments)} segments, "
            f"{transcript.duration:.1f}s duration"
        )

        # Generate content
        content = generate_legacy(transcript, output_dir, resolved_api_key, settings.claude_model, chapters)

        # Display summary
        _display_summary(transcript, content)

        console.print(
            f"\n[bold green]Done![/] Content saved to: {output_dir}"
        )

    except (ValueError, WorkspaceError, OSError) as e:
        console.print(f"Error parsing transcript: {e}", markup=False)
        raise typer.Exit(1)
    except LLMError as e:
        console.print(f"[bold red]LLM error:[/] {e}")
        raise typer.Exit(1)


@app.command("import")
def import_command(
    transcript_file: Path,
    root: Annotated[Path, typer.Option(help="Versioned workspace collection")] = Path("output/episodes"),
    source: Annotated[Optional[Path], typer.Option()] = None,
    copy_source: Annotated[bool, typer.Option("--copy-source")] = False,
    workspace: Annotated[Optional[Path], typer.Option(help="Explicit existing episode to update")] = None,
    show_profile: Annotated[Optional[Path], typer.Option()] = None,
    metadata: Annotated[Optional[Path], typer.Option()] = None,
) -> None:
    """Explicitly import preserved data without transcription or paid calls."""
    from .operations import import_episode
    from .workspace import WorkspaceError
    try:
        from .workspace_models import ShowProfile, EpisodeMetadata
        profile = ShowProfile.model_validate_json(show_profile.read_bytes()) if show_profile else None
        episode = EpisodeMetadata.model_validate_json(metadata.read_bytes()) if metadata else None
        path = import_episode(transcript_file, root, source, copy_source, workspace, profile, episode)
        console.print(str(path), markup=False)
    except (WorkspaceError, OSError, ValueError) as error:
        console.print(f"Error: {error}", markup=False)
        raise typer.Exit(1)


@app.command("map-participants")
def map_participants_command(workspace: Path) -> None:
    """Associate supported participant identities using saved episode evidence."""
    from .participants import map_episode
    from .workspace import Workspace
    try:
        typer.echo(Workspace(workspace).report(map_episode(workspace)))
    except (WorkspaceError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(1)


@app.command("corrections-template")
def corrections_template_command(workspace: Path, output: Annotated[Optional[Path], typer.Option()] = None) -> None:
    """Create an optional JSON corrections file pinned to the current source and transcript."""
    from .corrections import corrections_template
    try:
        data = corrections_template(workspace)
        if output:
            with output.open('xb') as stream:
                stream.write(data)
            typer.echo(str(output))
        else:
            typer.echo(data.decode())
    except (WorkspaceError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(1)


@app.command("correct")
def correct_command(workspace: Path, corrections: Path) -> None:
    """Apply optional exact-base corrections without retranscription."""
    from .corrections import correct_episode
    from .workspace import Workspace
    try:
        typer.echo(Workspace(workspace).report(correct_episode(workspace, corrections)))
    except (WorkspaceError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(1)


@app.command("inspect")
def inspect_command(
    workspace: Path,
    as_json: Annotated[bool, typer.Option("--json", help="Print committed structured state")] = False,
) -> None:
    """Read current usable outputs and recover interrupted writes."""
    from .operations import inspect_episode
    from .workspace import Workspace, WorkspaceError
    try:
        state = inspect_episode(workspace)
        typer.echo(state.model_dump_json(indent=2) if as_json else Workspace(workspace).report(state))
    except (WorkspaceError, OSError, ValueError) as error:
        console.print(f"Error: {error}", markup=False)
        raise typer.Exit(1)


@app.command("attach-source")
def attach_source_command(workspace: Path, source: Path,
                          copy_source: Annotated[bool, typer.Option("--copy-source")] = False) -> None:
    """Reattach matching media or create a new source revision for changed bytes."""
    from .operations import attach_source
    from .workspace import WorkspaceError
    try:
        state = attach_source(workspace, source, copy_source)
        typer.echo(f"Episode {state.episode_id}: source revision {state.source_revision}")
    except (WorkspaceError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(1)


@app.command("check-source")
def check_source_command(workspace: Path) -> None:
    """Verify a media-dependent operation can access the exact recording bytes."""
    from .operations import check_source
    from .workspace import WorkspaceError
    try:
        typer.echo(str(check_source(workspace)))
    except (WorkspaceError, OSError, ValueError) as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
