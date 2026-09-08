from pathlib import Path

from typer.testing import CliRunner

from podcast_processor.cli import app
from podcast_processor.llm import ClaudeClient, LLMError


def test_legacy_generation_failure_preserves_existing_transcript(tmp_path, monkeypatch):
    original = Path('tests/fixtures/legacy-transcript.json').read_bytes()
    transcript = tmp_path / 'transcript.json'
    transcript.write_bytes(original)

    def fail(*args, **kwargs):
        raise LLMError('controlled publishing failure')

    monkeypatch.setattr(ClaudeClient, 'generate', fail)
    result = CliRunner().invoke(app, ['generate', str(transcript), '--api-key', 'test-key'])
    assert result.exit_code == 1
    assert transcript.read_bytes() == original


def test_legacy_process_saves_transcript_before_publishing_failure(tmp_path, monkeypatch):
    from podcast_processor.models import Transcript
    from podcast_processor.transcriber import WhisperLocalTranscriber

    transcript = Transcript.model_validate_json(Path('tests/fixtures/legacy-transcript.json').read_bytes())
    monkeypatch.setattr(WhisperLocalTranscriber, 'transcribe', lambda *args: transcript)

    def fail(*args, **kwargs):
        raise LLMError('controlled late failure')

    monkeypatch.setattr(ClaudeClient, 'generate', fail)
    result = CliRunner().invoke(app, ['process', str(tmp_path / 'synthetic.wav'), '-o', str(tmp_path / 'output'), '--api-key', 'fake'])
    assert result.exit_code == 1
    assert Transcript.model_validate_json((tmp_path / 'output/transcript.json').read_bytes()) == transcript
    assert 'no transcription work was lost' in ' '.join(result.output.split())
