"""Audio transcription using faster-whisper."""

from pathlib import Path

from faster_whisper import WhisperModel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import WhisperModel as WhisperModelType
from .models import Transcript, TranscriptSegment, WordTimestamp

console = Console()

SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm"}


class TranscriptionError(Exception):
    """Error during transcription."""

    pass


class WhisperLocalTranscriber:
    """Transcribe audio using local faster-whisper model."""

    def __init__(
        self,
        model_name: WhisperModelType = "medium",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        """Initialize the transcriber.

        Args:
            model_name: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type (auto, int8, float16, float32)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        """Load the Whisper model lazily."""
        if self._model is None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(
                    f"Loading Whisper model '{self.model_name}'...", total=None
                )
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
        return self._model

    def transcribe(
        self,
        audio_path: Path | str,
        language: str | None = None,
    ) -> Transcript:
        """Transcribe an audio file.

        Args:
            audio_path: Path to the audio file
            language: Language code (e.g., 'en'). Auto-detect if None.

        Returns:
            Transcript with segments and word-level timestamps
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
            raise TranscriptionError(
                f"Unsupported audio format: {audio_path.suffix}. "
                f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )

        model = self._load_model()

        console.print(f"[bold blue]Transcribing:[/] {audio_path.name}")

        segments_list: list[TranscriptSegment] = []
        words_list: list[WordTimestamp] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Transcribing audio...", total=None)

            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                word_timestamps=True,
                vad_filter=True,
            )

            detected_language = info.language
            duration = info.duration

            for segment in segments:
                segments_list.append(
                    TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text,
                    )
                )

                if segment.words:
                    for word in segment.words:
                        words_list.append(
                            WordTimestamp(
                                word=word.word,
                                start=word.start,
                                end=word.end,
                                probability=word.probability,
                            )
                        )

                progress.update(
                    task,
                    description=f"Transcribing... {segment.end:.1f}s / {duration:.1f}s",
                )

        console.print(
            f"[bold green]Transcription complete![/] "
            f"Duration: {duration:.1f}s, Language: {detected_language}"
        )

        return Transcript(
            segments=segments_list,
            words=words_list,
            language=detected_language,
            duration=duration,
        )
