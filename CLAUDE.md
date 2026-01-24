# Podcast Processor

A CLI tool that processes podcast audio files to generate YouTube-ready content: transcription, descriptions, viral titles with thumbnail text, and chapters.

## Directory Structure

```
src/podcast_processor/
├── __init__.py       # Package initialization
├── __main__.py       # Entry point for `python -m podcast_processor`
├── cli.py            # Typer CLI with process, transcribe, generate commands
├── config.py         # Settings via pydantic-settings, loads from .env
├── models.py         # Pydantic models: Transcript, Chapter, Title, etc.
├── transcriber.py    # WhisperLocalTranscriber using faster-whisper
├── generators.py     # Content generation functions (description, titles, chapters)
├── llm.py            # ClaudeClient wrapper for Anthropic API
└── prompts.py        # Prompt templates for content generation
```

## Development Setup

```bash
# Create venv and install in editable mode
uv venv && uv pip install -e .

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires FFmpeg: `brew install ffmpeg`

## Configuration

Set `ANTHROPIC_API_KEY` in `.env` or environment:

```bash
export ANTHROPIC_API_KEY=your-key
```

## Running the CLI

```bash
# Activate venv first
source .venv/bin/activate

# Full processing (transcribe + generate all content)
podcast-process process episode.mp3

# Transcribe only (no API calls)
podcast-process transcribe episode.mp3

# Generate from existing transcript
podcast-process generate output/episode/transcript.json

# With options
podcast-process process episode.mp3 -o ./output -m medium -c 10
```

## Testing

No test framework is currently configured. To add tests:

```bash
uv pip install pytest
pytest tests/
```

## Key Architectural Decisions

- **Local transcription**: Uses faster-whisper for privacy and cost savings (no API calls for transcription)
- **Word-level timestamps**: Enables accurate chapter timestamps aligned to speech
- **Pydantic models**: Strong typing for all data structures (Transcript, Chapter, Title, GeneratedContent)
- **Retry logic**: ClaudeClient uses tenacity for automatic retries with exponential backoff
- **Lazy model loading**: Whisper model loads on first transcription to reduce startup time
- **Modular commands**: Separate CLI commands for transcribe-only and generate-from-transcript workflows
- **Rich console output**: Progress spinners and formatted tables for user feedback

## CLI Commands

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: transcribe audio + generate all content |
| `transcribe` | Transcribe only (no Claude API calls) |
| `generate` | Generate content from existing transcript.json |

## Output Files

| File | Description |
|------|-------------|
| `transcript.json` | Full transcript with word-level timestamps |
| `transcript.txt` | Plain text transcript |
| `description.md` | YouTube description |
| `titles.json` | 10 title variations with thumbnail text |
| `chapters.txt` | YouTube-ready chapter format |
