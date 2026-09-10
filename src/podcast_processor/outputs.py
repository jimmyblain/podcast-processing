"""Persistence for the original unversioned commands."""

import json
from pathlib import Path
from rich.console import Console
from .models import GeneratedContent, Transcript

console = Console()

def save_outputs(
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
