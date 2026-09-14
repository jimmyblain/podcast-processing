"""One-time measured transition preparation and immutable, approved show defaults."""
import io
import os
import wave
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from pydantic import Field, model_validator

from .authority import approved_show_profile
from .workspace import (Workspace, WorkspaceError, digest, file_hash, flush_directory, identifier,
                        now, ownership, write_file)
from .workspace_models import Record, Run, ShowProfile, WorkspaceState

TRANSITIONS = {'episode_start': 'transition-episode-start.WAV',
               'transition_in': 'transition-in.WAV', 'transition_out': 'transition-out.WAV'}
LABELS = {'episode_start': 'Episode opening', 'transition_in': 'Section opening',
          'transition_out': 'Section closing'}
PREPARATION = 'pcm-digital-silence-v1'
NEEDS_SETUP = 'Needs setup: run podcast-process setup and approve the three prepared transitions after listening.'


class TransitionRecording(Record):
    source_path: str
    source_sha256: str
    path: str
    sha256: str
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    sample_width: Literal[2, 3, 4]
    source_frames: int = Field(gt=0)
    retained_frames: int = Field(gt=0)
    ending_silence_frames: int = Field(gt=0)
    prepared_frames: int = Field(gt=0)
    duration: Decimal = Field(gt=0)

    @model_validator(mode='after')
    def measured_duration(self) -> 'TransitionRecording':
        if (self.prepared_frames != self.retained_frames + self.ending_silence_frames
                or self.duration != Decimal(self.prepared_frames) / self.sample_rate
                or self.retained_frames > self.source_frames):
            raise ValueError('Prepared duration must match measured PCM frames including its ending silence.')
        return self


class ShowSetup(Record):
    schema_version: Literal[1] = 1
    revision: str
    profile_revision: str
    profile: ShowProfile
    preparation: str = PREPARATION
    ending_silence: Decimal = Field(default=Decimal('2.5'), gt=0)
    transitions: dict[str, TransitionRecording]
    approved_at: str | None = None

    @model_validator(mode='after')
    def complete_setup(self) -> 'ShowSetup':
        if set(self.transitions) != set(TRANSITIONS):
            raise ValueError('Show setup requires all three prepared transitions.')
        if self.profile_revision != digest(self.profile.model_dump_json().encode()):
            raise ValueError('Show profile revision does not match its saved content.')
        if any(asset.ending_silence_frames != asset.sample_rate * self.ending_silence
               for asset in self.transitions.values()):
            raise ValueError('Prepared ending silence must match the saved preparation setting.')
        return self


def setup_directory() -> Path:
    from .config import get_settings
    return get_settings().show_setup_dir.resolve()


def prepared_bytes(root: Path, transition: TransitionRecording) -> bytes:
    path = (root / transition.path).resolve()
    if not path.is_relative_to(root.resolve() / 'versions'):
        raise WorkspaceError('Prepared transition path escapes the show setup.')
    data = path.read_bytes()
    if digest(data) != transition.sha256:
        raise WorkspaceError('Prepared transition changed; run podcast-process setup --reprepare and listen again.')
    return data


def read_setup(root: Path, *, verify_audio: bool = True) -> ShowSetup | None:
    pointer = root / 'current.json'
    if not pointer.exists() and not pointer.is_symlink():
        return None
    path = pointer.resolve()
    if not path.is_relative_to(root.resolve() / 'versions'):
        raise WorkspaceError('Invalid saved show setup path.')
    data = path.read_bytes()
    if digest(data) != path.stem:
        raise WorkspaceError('Show setup manifest failed hash verification; restore its preserved version.')
    setup = ShowSetup.model_validate_json(data)
    if verify_audio:
        for transition in setup.transitions.values():
            prepared_bytes(root, transition)
    return setup


def point_to(root: Path, path: Path) -> None:
    pointer = root / f'.current-{identifier()}'
    pointer.symlink_to(path.relative_to(root))
    os.replace(pointer, root / 'current.json')
    flush_directory(root)


def save_setup(root: Path, setup: ShowSetup) -> None:
    data = setup.model_dump_json(indent=2).encode()
    version = root / 'versions' / setup.revision
    path = version / f'{digest(data)}.json'
    write_file(path, data)
    flush_directory(version.parent)
    point_to(root, path)


def prepare_recording(source: Path, destination: Path, root: Path, ending_silence: Decimal) -> TransitionRecording:
    original = source.read_bytes()
    try:
        with wave.open(io.BytesIO(original), 'rb') as audio:
            rate, channels, width = audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
            frames = audio.getnframes()
            pcm = audio.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise WorkspaceError(f'Use an uncompressed 16/24/32-bit PCM WAV transition: {source}') from error
    if width not in (2, 3, 4) or rate % 2 or len(pcm) != frames * channels * width:
        raise WorkspaceError(f'Transition requires complete 16/24/32-bit PCM frames and an even sample rate: {source}')
    # Only remove exact digital silence. No threshold can discard quiet decay,
    # and interior pauses or a quiet channel never cause an early cut.
    frame_size = channels * width
    retained = (len(pcm.rstrip(b'\0')) + frame_size - 1) // frame_size
    if not retained:
        raise WorkspaceError(f'Transition contains only silence: {source}')
    silence_frames = rate * ending_silence
    if not silence_frames.is_finite() or silence_frames <= 0 or silence_frames != int(silence_frames):
        raise WorkspaceError('Ending silence must be positive and exactly representable in audio frames.')
    tail = int(silence_frames)
    prepared = io.BytesIO()
    with wave.open(prepared, 'wb') as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        audio.writeframes(pcm[:retained * frame_size] + b'\0' * tail * frame_size)
    data = prepared.getvalue()
    write_file(destination, data)
    # Measure the written output, never a detector estimate or source duration.
    with wave.open(str(destination), 'rb') as audio:
        measured_frames = audio.getnframes()
        measured_rate = audio.getframerate()
    if file_hash(source) != digest(original):
        raise WorkspaceError('Transition source changed during preparation; retry with stable bytes.')
    return TransitionRecording(source_path=str(source.resolve()), source_sha256=digest(original),
        path=str(destination.relative_to(root)), sha256=digest(data), sample_rate=measured_rate,
        channels=channels, sample_width=cast(Literal[2, 3, 4], width), source_frames=frames, retained_frames=retained,
        ending_silence_frames=tail, prepared_frames=measured_frames,
        duration=Decimal(measured_frames) / measured_rate)


def prepare_setup(root: Path, directory: Path | None = None, *, reprepare: bool = False,
                  ending_silence: Decimal | None = None) -> ShowSetup:
    root = root.resolve()
    with ownership(root, 'prepare show setup'):
        # Repreparation can recover damaged audio while retaining historical files.
        previous = read_setup(root, verify_audio=not reprepare)
        silence = ending_silence if ending_silence is not None else previous.ending_silence if previous else Decimal('2.5')
        if previous and directory is None and not reprepare and silence == previous.ending_silence:
            return previous
        if directory is None and previous:
            sources = {name: Path(asset.source_path) for name, asset in previous.transitions.items()}
        else:
            if directory is None:
                directory = next((parent / 'audio-files' for parent in [Path.cwd(), *Path.cwd().parents]
                                  if all((parent / 'audio-files' / name).is_file() for name in TRANSITIONS.values())), None)
            if directory is None:
                raise WorkspaceError('Cannot locate the three supplied recordings. Run podcast-process setup --transitions AUDIO_DIRECTORY.')
            sources = {name: directory / filename for name, filename in TRANSITIONS.items()}
        if any(not path.is_file() for path in sources.values()):
            raise WorkspaceError('Supply transition-episode-start.WAV, transition-in.WAV and transition-out.WAV with --transitions DIRECTORY.')
        if (previous and not reprepare and previous.preparation == PREPARATION and silence == previous.ending_silence
                and all(file_hash(sources[name]) == asset.source_sha256 for name, asset in previous.transitions.items())):
            return previous
        revision = identifier()
        version = root / 'versions' / revision
        profile = previous.profile if previous else approved_show_profile()
        setup = ShowSetup(revision=revision, profile=profile, ending_silence=silence,
            profile_revision=digest(profile.model_dump_json().encode()),
            transitions={name: prepare_recording(source, version / TRANSITIONS[name], root, silence)
                         for name, source in sources.items()})
        save_setup(root, setup)
        return setup


def approve_setup(root: Path, revision: str) -> ShowSetup:
    with ownership(root, 'approve show setup'):
        setup = read_setup(root)
        if setup is None or setup.revision != revision:
            raise WorkspaceError('Show setup changed during listening. Run podcast-process setup to hear the current results.')
        if setup.approved_at:
            return setup
        setup.approved_at = now()
        save_setup(root, setup)
        return setup


def snapshot_setup(workspace: Workspace, state: WorkspaceState, setup: ShowSetup) -> None:
    """Persist approved inputs before paid work; later resumes need no global store."""
    from .operations import input_revision

    if not setup.approved_at:
        raise WorkspaceError(NEEDS_SETUP)
    if 'show-setup.json' in state.evidence:
        return
    recordings = {name: prepared_bytes(setup_directory(), asset) for name, asset in setup.transitions.items()}
    state.show_setup_revision = setup.revision
    state.input_revision = input_revision(state)
    dependencies = {'show_setup': setup.revision, 'profile': setup.profile_revision}
    state.runs.append(Run(id=identifier(), operation_id=identifier(), operation='show-setup',
        status='completed', started_at=now(), finished_at=now(), inputs=dependencies))
    for name, data in recordings.items():
        workspace.add_artifact(state, f'prepared-{name}.wav', data,
            {'prepared_revision': setup.transitions[name].sha256}, PREPARATION, exposed=False)
    workspace.add_artifact(state, 'show-setup.json', setup.model_dump_json(indent=2).encode(),
                           dependencies, 'show-setup-v1', exposed=False)
    workspace.commit(state)


def episode_setup(workspace: Workspace, state: WorkspaceState) -> ShowSetup | None:
    artifact = state.evidence.get('show-setup.json')
    if artifact is None:
        return None
    setup = ShowSetup.model_validate_json(workspace.artifact_bytes(artifact))
    if not setup.approved_at or setup.revision != state.show_setup_revision:
        raise WorkspaceError('Consumed show setup is unapproved or mismatched; restore its preserved evidence.')
    for name, asset in setup.transitions.items():
        recording = state.evidence.get(f'prepared-{name}.wav')
        if recording is None or digest(workspace.artifact_bytes(recording)) != asset.sha256:
            raise WorkspaceError('Consumed prepared transition is missing or changed; restore its preserved evidence.')
    return setup


def planning_transitions(setup: ShowSetup) -> dict:
    from .planning_models import PreparedTransition
    return {name: PreparedTransition(asset_revision=asset.source_sha256, prepared_revision=asset.sha256,
        duration=asset.duration, ending_silence=setup.ending_silence, preserves_decay=True,
        replaces_excess_tail=True, basis='verified',
        evidence=f'Measured {asset.prepared_frames} PCM frames at {asset.sample_rate} Hz; '
                 f'{asset.retained_frames} source frames retained, {asset.ending_silence_frames} ending silence frames. '
                 f'Listening approved {setup.approved_at}; preparation {setup.preparation}.')
        for name, asset in setup.transitions.items()}
