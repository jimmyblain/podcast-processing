"""Content identity and verified optional copies of episode media."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from .workspace import WorkspaceError, file_hash, flush_directory, identifier, now
from .workspace_models import SourceRevision


def inspect_source(path: Path) -> SourceRevision:
    if not path.is_file():
        raise WorkspaceError(f'Source media missing: {path}. Reattach the recording; preserved text can still be used.')
    before = file_hash(path)
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration:stream=index,codec_type,codec_name,sample_rate,channels,duration,time_base',
             '-of', 'json', str(path.resolve())], capture_output=True, text=True, check=True, timeout=60)
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
