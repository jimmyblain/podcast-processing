"""Content identity and verified optional copies of episode media."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from .workspace import WorkspaceError, file_hash, flush_directory, identifier, now
from .workspace_models import SourceRevision


def inspect_source(path: Path, *, deadline_at: float | None = None) -> SourceRevision:
    if not path.is_file():
        raise WorkspaceError(f'Source media missing: {path}. Reattach the recording; preserved text can still be used.')
    before = file_hash(path)
    timeout = 60.0 if deadline_at is None else min(60, deadline_at - time.time())
    if timeout <= 0:
        raise WorkspaceError('Transcription deadline exhausted during source inspection.')
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration:stream=index,codec_type,codec_name,sample_rate,channels,duration,time_base',
             '-of', 'json', str(path.resolve())], capture_output=True, text=True, check=True, timeout=timeout)
        properties = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise WorkspaceError(f'Cannot inspect source streams with ffprobe: {path}') from error
    if not any(s.get('codec_type') == 'audio' for s in properties.get('streams', [])):
        raise WorkspaceError('Source has no audio stream.')
    if file_hash(path) != before:
        raise WorkspaceError('Source changed while it was being inspected; retry with stable bytes.')
    return SourceRevision(id=identifier(), fingerprint=before, locator=str(path.resolve()),
                          properties=properties, created_at=now())


def copy_source(source: SourceRevision, workspace: Path) -> None:
    if source.locator is None or source.fingerprint is None:
        raise WorkspaceError('Cannot copy a source with unknown bytes.')
    directory = workspace / 'media'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / source.fingerprint
    if not destination.exists() or file_hash(destination) != source.fingerprint:
        temporary = directory / f'.copy-{identifier()}'
        try:
            with Path(source.locator).open('rb') as original, temporary.open('xb') as copied:
                shutil.copyfileobj(original, copied)
                copied.flush()
                os.fsync(copied.fileno())
            if file_hash(temporary) != source.fingerprint:
                raise WorkspaceError('Copied source bytes failed fingerprint verification.')
            os.replace(temporary, destination)
            flush_directory(directory)
        finally:
            temporary.unlink(missing_ok=True)
    source.copied_path = str(destination.relative_to(workspace))


def require_source(source: SourceRevision, workspace: Path) -> Path:
    candidates = [Path(source.locator)] if source.locator else []
    if source.copied_path:
        candidates.append(workspace / source.copied_path)
    for path in candidates:
        if path.is_file() and source.fingerprint and file_hash(path) == source.fingerprint:
            return path
    raise WorkspaceError('Source media missing or changed. Reattach matching bytes; preserved text operations remain available.')


def prepare_transport(source: SourceRevision, workspace: Path, deadline_at: float):
    """Convert the full first audio stream, proving sample/rate/channel equivalence."""
    from .managed_models import Transport
    def remaining() -> float:
        seconds = deadline_at - time.time()
        if seconds <= 0:
            raise WorkspaceError('Transcription deadline exhausted during transport preparation.')
        return seconds

    path = require_source(source, workspace)
    properties = source.properties or {}
    streams = [s for s in properties.get('streams', []) if s.get('codec_type') == 'audio']
    if len(streams) != 1:
        raise WorkspaceError('Managed transcription requires exactly one audio stream; select it explicitly first.')
    import math
    duration = float(properties.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise WorkspaceError('Source duration must be finite and positive.')
    directory = workspace / 'media'
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f'.transport-{identifier()}.flac'
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-map', '0:a:0',
                        '-c:a', 'flac', str(temporary)], check=True, capture_output=True, timeout=remaining())
        def decoded(media: Path) -> str:
            result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(media), '-map', '0:a:0',
                                     '-c:a', 'pcm_s32le', '-f', 'hash', '-hash', 'sha256', '-'],
                                    check=True, capture_output=True, text=True, timeout=remaining())
            return result.stdout.strip().split('=')[-1]
        original_pcm, submitted_pcm = decoded(path), decoded(temporary)
        if original_pcm != submitted_pcm or file_hash(path) != source.fingerprint:
            raise WorkspaceError('FLAC decoded-audio equivalence failed; no transcription submitted.')
        submitted = inspect_source(temporary, deadline_at=deadline_at)
        submitted_stream = (submitted.properties or {})['streams'][0]
        for key in ('sample_rate', 'channels'):
            if streams[0].get(key) != submitted_stream.get(key):
                raise WorkspaceError('FLAC stream properties changed; no transcription submitted.')
        fingerprint = file_hash(temporary)
        destination = directory / f'{fingerprint}.flac'
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        flush_directory(directory)
        return Transport(source_fingerprint=source.fingerprint, submitted_fingerprint=fingerprint,
                         path=str(destination.relative_to(workspace)), duration=duration, decoded_sha256=original_pcm)
    except (OSError, subprocess.SubprocessError) as error:
        raise WorkspaceError('Lossless transport preparation failed; no transcription submitted.') from error
    finally:
        temporary.unlink(missing_ok=True)
