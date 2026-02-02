# Podcast Processor

A CLI tool that processes podcast audio files to generate YouTube-ready content: transcription, description, viral titles with thumbnail text, and chapters.

## Features

- **Local transcription** using faster-whisper with word-level timestamps
- **AI-powered content generation** using Claude for descriptions, titles, and chapters
- **Multiple output formats** ready for YouTube upload
- **Flexible workflow** - transcribe only, generate from existing transcript, or full pipeline

## Requirements

- Python 3.10+
- FFmpeg (install via `brew install ffmpeg` on macOS)
- Anthropic API key

## Installation

```bash
# Clone the repository
git clone https://github.com/jimmyblain/podcast-processing.git
cd podcast-processing

# Create virtual environment and install
uv venv && uv pip install -e .

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Create a `.env` file with your Anthropic API key and optional model override:

```bash
cp .env.example .env
# Edit .env and add your API key (and optional CLAUDE_MODEL)
```

Or set the environment variable directly:

```bash
export ANTHROPIC_API_KEY=your-api-key-here
export CLAUDE_MODEL=claude-sonnet-4-5  # default alias; override with pinned if desired
```

## Usage

Activate the virtual environment first:

```bash
source .venv/bin/activate
```

### Full Processing

Process an audio file to generate all content (transcription + description + titles + chapters):

```bash
podcast-process process episode.mp3
```

With options:

```bash
podcast-process process episode.mp3 \
  --output ./my-output \
  --whisper-model medium \
  --chapters 10
```

### Transcribe Only

Generate only the transcript (no API calls to Claude):

```bash
podcast-process transcribe episode.mp3
```

### Generate from Existing Transcript

If you already have a transcript and want to regenerate content:

```bash
podcast-process generate output/episode/transcript.json
```

## Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output directory | `./output/<filename>` |
| `--whisper-model` | `-m` | Whisper model size | `medium` |
| `--chapters` | `-c` | Number of chapters to generate | `10` |
| `--api-key` | | Anthropic API key | from env |

### Whisper Models

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `tiny` | 39M | Fastest | Lower |
| `base` | 74M | Fast | Basic |
| `small` | 244M | Moderate | Good |
| `medium` | 769M | Slower | Better |
| `large-v3` | 1.5G | Slowest | Best |

## Output Files

After processing, you'll find these files in the output directory:

| File | Description |
|------|-------------|
| `transcript.json` | Full transcript with word-level timestamps |
| `transcript.txt` | Plain text transcript |
| `description.md` | YouTube description with hook, summary, and CTA |
| `titles.json` | 10 viral title variations with thumbnail text |
| `chapters.txt` | YouTube-ready chapter format |

### Example Output

**chapters.txt:**
```
00:00 Introduction - Welcome and Episode Overview
02:34 The Problem with Traditional Approaches
08:15 Solution #1: The New Framework
15:42 Real-World Case Study
23:18 Common Mistakes to Avoid
```

**titles.json:**
```json
[
  {
    "title": "I Tried This for 30 Days - Here's What Happened",
    "thumbnail_text": "30 DAYS LATER",
    "reasoning": "Personal story + curiosity gap"
  }
]
```

## Supported Audio Formats

- MP3
- WAV
- M4A
- FLAC
- OGG
- WebM

## License

MIT
