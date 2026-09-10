"""Local, single-writer workspace with an atomic current-snapshot pointer.

Artifacts are immutable originals. Snapshots contain separate user-editable copies;
only a fully flushed snapshot becomes current. flock ownership dies with its process.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

from .workspace_models import Artifact, WorkspaceState

PUBLISHING_FILES = ('description.md', 'titles.json', 'chapters.txt')


class WorkspaceError(Exception):
    """An actionable episode workspace error."""


def identifier() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
        return result.hexdigest()


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()


def flush_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if file_hash(path) != digest(data):
        raise WorkspaceError(f'Write verification failed: {path}')
    flush_directory(path.parent)


@contextmanager
def ownership(path: Path, operation: str) -> Iterator[None]:
    path.mkdir(parents=True, exist_ok=True)
    with (path / '.writer.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.seek(0)
            raise WorkspaceError(f'Active operation: {lock.read() or "workspace writer"}') from None
        try:
            lock.seek(0)
            lock.truncate()
            lock.write(json.dumps({'pid': os.getpid(), 'operation': operation, 'started_at': now()}))
            lock.flush()
            os.fsync(lock.fileno())
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Workspace:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def read(self) -> WorkspaceState:
        try:
            data = json.loads((self.path / 'current/state.json').read_bytes())
            if data.get('schema_version') != 2:
                raise WorkspaceError(f'Unsupported workspace schema: {data.get("schema_version")}')
            return WorkspaceState.model_validate(data)
        except FileNotFoundError:
            raise WorkspaceError(f'No committed workspace at {self.path}; rerun the import.') from None

    def artifact_bytes(self, artifact: Artifact) -> bytes:
        path = (self.path / artifact.path).resolve()
        if not path.is_relative_to(self.path / 'artifacts'):
            raise WorkspaceError('Artifact path escapes the artifact store.')
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise WorkspaceError(f'Missing committed artifact: {artifact.name}') from None
        if digest(data) != artifact.sha256:
            raise WorkspaceError(f'Hash mismatch for committed artifact: {artifact.name}')
        return data

    def add_artifact(self, state: WorkspaceState, name: str, data: bytes,
                     dependencies: dict[str, str], stage: str, *, exposed: bool = True) -> Artifact:
        artifact_id = identifier()
        relative = f'artifacts/{artifact_id}/{name}'
        write_file(self.path / relative, data)
        flush_directory(self.path / 'artifacts')
        artifact = Artifact(id=artifact_id, name=name, path=relative, sha256=digest(data),
                            stage_version=stage, dependencies=dependencies,
                            run_id=state.runs[-1].id, created_at=now())
        state.history.append(artifact)
        if exposed:
            state.artifacts[name] = artifact
        else:
            state.evidence[name] = artifact
        return artifact

    def commit(self, state: WorkspaceState) -> None:
        """Validate files and state before one atomic namespace switch."""
        state = WorkspaceState.model_validate(state.model_dump())
        snapshot = self.path / 'snapshots' / identifier()
        snapshot.mkdir(parents=True)
        for name, artifact in state.artifacts.items():
            if Path(name).name != name:
                raise WorkspaceError('Invalid artifact filename.')
            write_file(snapshot / name, self.artifact_bytes(artifact))
        write_file(snapshot / 'state.json', json_bytes(state.model_dump()))
        write_file(snapshot / 'completion-report.md', self.report(state).encode())
        flush_directory(snapshot)
        flush_directory(snapshot.parent)
        pointer = self.path / f'.current-{identifier()}'
        pointer.symlink_to(snapshot.relative_to(self.path), target_is_directory=True)
        os.replace(pointer, self.path / 'current')
        flush_directory(self.path)

    def report(self, state: WorkspaceState) -> str:
        from .participants import current_transcript, uncertainty_report

        uncertainty = ''
        if 'transcript.json' in state.artifacts:
            uncertainty = uncertainty_report(current_transcript(self, state))
        run = state.runs[-1]
        if run.operation == 'transcribe':
            operation = next(op for op in state.transcription_operations if op.id == run.operation_id)
            attempts = []
            for attempt in operation.attempts:
                role = 'primary' if attempt.provider == 'assemblyai' else 'backup'
                actual = 'unknown' if attempt.actual_usd is None else f'${attempt.actual_usd:.4f}'
                attempts.append(f'- {role} {attempt.provider}: {attempt.status}; job {attempt.job_id or "unknown"}; '
                                f'submissions {attempt.submissions}, reads {attempt.reads}; '
                                f'estimated ${attempt.estimated_usd:.4f}, reserved ${attempt.reserved_usd:.4f}, actual {actual}. '
                                f'{attempt.error or ""}')
            return ('# Completion report\n\n'
                    f'Episode: {state.episode_id}\nOperation: transcribe\nStatus: {run.status}\n'
                    f'Operation ledger: {operation.id}\n\n'
                    f'Usable outputs: {", ".join(state.artifacts) or "none"}\n'
                    'Publishing text was not requested.\n\n'
                    f'Allowance: ${operation.policy.allowance_usd:.2f}; elapsed {operation.elapsed_seconds:.1f}s; '
                    f'deadline (Unix seconds): {operation.deadline_at:.3f}.\n'
                    'Reservations are conservative admission estimates, not verified bills. '
                    'A local timeout does not cancel remote processing or imply zero charge.\n\n'
                    + '\n'.join(attempts) + '\n\n'
                    + '\n'.join(f'- {item}' for item in run.limitations) + '\n' + uncertainty + '\n')
        usage = '\n'.join(f'- {op.stage} operation {op.id}: {len(op.attempts)}/3 attempts; '
                          + ', '.join(f'{a.status} (usage {a.usage})' for a in op.attempts)
                          for op in state.publishing_operations)
        missing = [name for name in PUBLISHING_FILES if name not in state.artifacts]
        return ('# Completion report\n\n'
                f'Episode: {state.episode_id}\nOperation: {run.operation}\nStatus: {run.status}\n\n'
                f'Usable outputs: {", ".join(state.artifacts) or "none"}\n\n'
                f'Missing publishing results: {", ".join(missing) or "none"}\n\n'
                'Publishing uses the v2 package contract. Automated checks do not establish human editorial or source-timing acceptance.\n'
                'Imported speaker identity, original settings and timing confidence may be unknown.\n'
                'Precise section boundaries are unavailable in this slice.\n\n'
                + 'Publishing usage (separate from transcription; billing cost unknown):\n' + (usage or 'No requests.') + '\n\n'
                + '\n'.join(f'- {item}' for item in run.limitations) + '\n' + uncertainty + '\n')

    def reconcile(self, state: WorkspaceState) -> bool:
        """Preserve edits and stop exposing damaged outputs before any new work."""
        changed = False
        for name, artifact in list(state.artifacts.items()):
            visible = self.path / 'current' / name
            try:
                data = visible.read_bytes()
                original = self.artifact_bytes(artifact)
            except (OSError, WorkspaceError):
                data, original = None, None
            if data is None or digest(data) != artifact.sha256 or original is None:
                if data is not None and digest(data) != artifact.sha256:
                    edited = self.add_artifact(state, name, data, artifact.dependencies, 'manual-edit-v1')
                    edited.status = 'human-edited'
                    state.runs[-1].limitations.append(f'Preserved direct edit of {name} in history.')
                state.artifacts.pop(name, None)
                state.runs[-1].limitations.append(f'{name} failed committed hash verification; unavailable.')
                changed = True
        description = state.artifacts.get('description.md')
        chapters = state.artifacts.get('chapters.txt')
        if description and 'chapters_version' in description.dependencies and (
                chapters is None or description.dependencies['chapters_version'] != chapters.id):
            state.artifacts.pop('description.md')
            state.runs[-1].limitations.append('Description unavailable because its shared chapter version is unavailable.')
            changed = True
        if 'transcript.json' not in state.artifacts:
            state.artifacts.clear()
        if state.runs[-1].status == 'running':
            state.runs[-1].status = 'interrupted'
            state.runs[-1].finished_at = now()
            changed = True
        if changed:
            if state.runs[-1].status == 'completed':
                state.runs[-1].status = 'partial'
            required: tuple[str, ...] = ('transcript.json', 'transcript.txt')
            if state.runs[-1].operation == 'generate':
                required += PUBLISHING_FILES
            state.runs[-1].missing = [name for name in required if name not in state.artifacts]
            self.commit(state)
        return changed
