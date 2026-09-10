"""Explicit adapters; absent legacy provenance stays absent."""
import json
from pathlib import Path

from .workspace import WorkspaceError, digest
from .workspace_models import ImportProvenance, PreservedTranscript


def import_transcript(path: Path) -> tuple[PreservedTranscript, bytes]:
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise WorkspaceError('A transcript must be a JSON object.')
    version = data.get('schema_version')
    if version == 2:
        return PreservedTranscript.model_validate(data), raw
    if version is not None:
        raise WorkspaceError(f'Unsupported transcript schema: {version}; supported: legacy (unversioned), 2.')
    allowed = {'segments', 'words', 'language', 'duration'}
    if set(data) - allowed:
        raise WorkspaceError('Unsupported legacy fields; import requires an explicit schema adapter.')
    if not data.get('segments'):
        raise WorkspaceError('The legacy transcript has no usable text segments.')
    return PreservedTranscript.model_validate({
        **data,
        'provenance': ImportProvenance(source_path=str(path.resolve()), original_hash=digest(raw),
                                       original_schema='legacy-unversioned').model_dump(),
    }), raw
