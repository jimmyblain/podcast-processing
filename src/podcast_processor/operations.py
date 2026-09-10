"""Public episode operations; the CLI handles presentation only."""
import json
from pathlib import Path

from .config import WhisperModel
from .generators import generate_all_content
from .llm import ClaudeClient
from .models import GeneratedContent, Transcript
from .outputs import save_outputs


def transcribe_legacy(source: Path, output: Path, model: WhisperModel) -> Transcript:
    from .transcriber import WhisperLocalTranscriber

    transcript = WhisperLocalTranscriber(model_name=model).transcribe(source)
    save_outputs(output, transcript)
    return transcript


def generate_legacy(transcript: Transcript, output: Path, api_key: str,
                    model: str, chapters: int) -> GeneratedContent:
    content = generate_all_content(ClaudeClient(api_key=api_key, model=model), transcript, chapters)
    save_outputs(output, transcript, content)
    return content


# Versioned operations share a single persisted episode boundary.
import re

from .importers import import_transcript
from .workspace import Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import EpisodeMetadata, Run, ShowProfile, SourceRevision, WorkspaceState
from .sources import copy_source, inspect_source, require_source


def import_episode(transcript_file: Path, root: Path, source_path: Path | None = None,
                   copy: bool = False, target: Path | None = None,
                   show_profile: ShowProfile | None = None,
                   episode_metadata: EpisodeMetadata | None = None) -> Path:
    transcript, original = import_transcript(transcript_file)
    original_hash = digest(original)
    if copy and source_path is None:
        raise WorkspaceError('--copy-source requires --source.')
    source = inspect_source(source_path) if source_path else None
    with ownership(root, 'find/import episode'):
        if target is None:
            for path in root.iterdir():
                if path.is_dir() and (path / 'current/state.json').exists():
                    candidate = Workspace(path).read()
                    matches = (any(s.fingerprint == source.fingerprint for s in candidate.sources)
                               if source else candidate.import_hash == original_hash
                               and all(s.fingerprint is None for s in candidate.sources))
                    if matches:
                        target = path
                        break
        identity = 'source:' + source.fingerprint if source and source.fingerprint else 'import:' + original_hash
        episode_id = digest(identity.encode())[:32]
        name = re.sub(r'[^a-zA-Z0-9_-]+', '-', (source_path.stem if source_path else transcript_file.parent.name)).strip('-') or 'episode'
        workspace = Workspace(target or root / f'{name}-{episode_id}')
        with ownership(workspace.path, 'import episode'):
            if (workspace.path / 'current').exists():
                state = workspace.read()
                workspace.reconcile(state)
                if source:
                    update_source(state, source, copy, workspace)
                profile = show_profile or state.show_profile
                metadata = episode_metadata or state.episode_metadata
                unchanged = (state.import_hash == original_hash and profile == state.show_profile
                             and metadata == state.episode_metadata
                             and all(name in state.artifacts for name in ('transcript.json', 'transcript.txt', 'import-original.json')))
                if unchanged:
                    workspace.commit(state)
                    return workspace.path
                preserve_transcript = state.import_hash == original_hash and 'transcript.json' in state.artifacts
                metadata_changed = profile != state.show_profile or metadata != state.episode_metadata
                state.show_profile, state.episode_metadata = profile, metadata
                state.import_hash = original_hash
                if preserve_transcript and metadata_changed:
                    state.artifacts = {name: artifact for name, artifact in state.artifacts.items()
                                       if name in ('transcript.json', 'transcript.txt', 'import-original.json')}
                elif not preserve_transcript:
                    state.artifacts.clear()
            else:
                source = source or SourceRevision(id=identifier(), created_at=now())
                if copy:
                    copy_source(source, workspace.path)
                state = WorkspaceState(episode_id=episode_id, name=name, source_revision=source.id,
                                       sources=[source], input_revision=original_hash, import_hash=original_hash,
                                       show_profile=show_profile, episode_metadata=episode_metadata)
            state.input_revision = input_revision(state)
            run = Run(id=identifier(), operation_id=identifier(), operation='import', status='running',
                      started_at=now(), inputs={**input_snapshot(state), 'import_source': str(transcript_file.resolve()),
                                               'import_schema': '2' if 'schema_version' in json.loads(original) else 'legacy-unversioned'},
                      limitations=['Import preserves evidence; source correspondence and timing accuracy are unverified.'])
            state.runs.append(run)
            # Expose changed input revisions together with supersession, before new artifacts.
            workspace.commit(state)
            dependencies = {'import': original_hash, 'source_revision': state.source_revision}
            if 'import-original.json' not in state.artifacts:
                workspace.add_artifact(state, 'import-original.json', original, dependencies, 'import-v1')
            if 'transcript.json' not in state.artifacts:
                workspace.add_artifact(state, 'transcript.json', json_bytes(transcript.model_dump()), dependencies, 'import-v1')
            if 'transcript.txt' not in state.artifacts:
                workspace.add_artifact(state, 'transcript.txt', transcript.readable().encode(), dependencies, 'render-v1')
            run.status, run.finished_at = 'completed', now()
            workspace.commit(state)
            return workspace.path


def input_snapshot(state: WorkspaceState) -> dict:
    return {'source_revision': state.source_revision, 'import_hash': state.import_hash,
            'show_profile': state.show_profile.model_dump() if state.show_profile else None,
            'episode_metadata': state.episode_metadata.model_dump() if state.episode_metadata else None}


def input_revision(state: WorkspaceState) -> str:
    return digest(json_bytes(input_snapshot(state)))


def update_source(state: WorkspaceState, source: SourceRevision, copy: bool, workspace: Workspace) -> None:
    existing = next((s for s in state.sources if s.fingerprint == source.fingerprint), None)
    if existing:
        existing.locator = source.locator
        source = existing
    else:
        state.sources.append(source)
    if copy:
        copy_source(source, workspace.path)
    if state.source_revision != source.id:
        # Attaching previously unknown media still changes consumed input evidence.
        state.artifacts.clear()
        state.source_revision = source.id
    state.input_revision = input_revision(state)


def attach_source(path: Path, source_path: Path, copy: bool = False) -> WorkspaceState:
    source = inspect_source(source_path)
    workspace = Workspace(path)
    with ownership(workspace.path, 'attach source'):
        state = workspace.read()
        workspace.reconcile(state)
        update_source(state, source, copy, workspace)
        state.runs.append(Run(id=identifier(), operation_id=identifier(), operation='attach-source',
                              status='completed', started_at=now(), finished_at=now(), inputs=input_snapshot(state),
                              limitations=['Changed source revisions require explicit import of matching transcript evidence.']
                              if 'transcript.json' not in state.artifacts else []))
        workspace.commit(state)
        return state


def check_source(path: Path) -> Path:
    workspace = Workspace(path)
    with ownership(workspace.path, 'check source'):
        state = workspace.read()
        return require_source(next(s for s in state.sources if s.id == state.source_revision), workspace.path)


def inspect_episode(path: Path) -> WorkspaceState:
    workspace = Workspace(path)
    with ownership(workspace.path, 'inspect/recover episode'):
        state = workspace.read()
        workspace.reconcile(state)
        return state


def generate_episode(path: Path, api_key: str, model: str, chapters: int = 10) -> WorkspaceState:
    """Generate solely from committed evidence; checkpoint each successful result."""
    from .generators import generate_chapters, generate_description, generate_titles
    from .transcript_content import publishing_transcript, transcript_inputs
    from .publishing import PreservedPublishingClient
    from .workspace import PUBLISHING_FILES
    from .workspace_models import PreservedTranscript

    workspace = Workspace(path)
    with ownership(workspace.path, 'generate publishing from preserved text'):
        state = workspace.read()
        workspace.reconcile(state)
        if state.show_profile is None or state.episode_metadata is None:
            raise WorkspaceError('Generation requires an approved show profile and confirmed guest names or explicit solo metadata. Reimport with --show-profile and --metadata.')
        artifact = state.artifacts.get('transcript.json')
        if artifact is None:
            raise WorkspaceError('No current usable timed transcript. Explicitly import evidence for this source revision.')
        preserved = PreservedTranscript.model_validate_json(workspace.artifact_bytes(artifact))
        chapter_timing_available = preserved.has_timing and bool(publishing_transcript(preserved, timed=True).segments)
        if not publishing_transcript(preserved).full_text.strip():
            raise WorkspaceError('No usable preserved text for publishing.')
        consumed = transcript_inputs(preserved)
        dependencies = {key: consumed[key] for key in ('transcript_text', 'transcript_attribution')}
        dependencies.update({'input_revision': state.input_revision, 'model': model, 'stage_version': 'speaker-publishing-v1'})
        expected = {name: {**dependencies, **({'chapter_count': str(chapters), 'transcript_timing': consumed['transcript_timing']}
                                             if name == 'chapters.txt' else {})}
                    for name in PUBLISHING_FILES}
        reusable = [name for name in PUBLISHING_FILES if name in state.artifacts
                    and state.artifacts[name].dependencies == expected[name]]
        if len(reusable) == 3:
            if state.runs[-1].operation == 'generate' and state.runs[-1].status != 'completed':
                state.runs[-1].status = 'completed'
                state.runs[-1].finished_at = now()
                state.runs[-1].missing = []
                workspace.commit(state)
            return state
        run = Run(id=identifier(), operation_id=identifier(), operation='generate', status='running',
                  started_at=now(), inputs={**input_snapshot(state), 'model': model, 'chapter_count': chapters,
                                           'stage_version': 'speaker-publishing-v1', 'transcript_artifact': artifact.id})
        state.runs.append(run)
        for name in PUBLISHING_FILES:
            if name not in reusable:
                state.artifacts.pop(name, None)
        if not chapter_timing_available:
            state.artifacts.pop('chapters.txt', None)
            run.limitations.append('Chapters unavailable: preserved timing is missing or unusable.')
        workspace.commit(state)
        transcript = publishing_transcript(preserved)
        client = PreservedPublishingClient(workspace, state, api_key, model)
        try:
            for name in PUBLISHING_FILES:
                if name in state.artifacts or (name == 'chapters.txt' and not chapter_timing_available):
                    continue
                if name == 'description.md':
                    description = generate_description(client, transcript)
                    if not description.strip():
                        raise WorkspaceError('Publishing returned an empty description.')
                    data = description.encode()
                elif name == 'titles.json':
                    titles = generate_titles(client, transcript)
                    if not titles or any(not t.title.strip() or not t.thumbnail_text.strip() for t in titles):
                        raise WorkspaceError('Publishing returned empty titles or thumbnail text.')
                    data = json_bytes([title.model_dump() for title in titles])
                else:
                    generated_chapters = generate_chapters(client, publishing_transcript(preserved, timed=True), chapters)
                    if not generated_chapters:
                        raise WorkspaceError('Publishing returned no chapters.')
                    data = ('\n'.join(chapter.to_youtube_format() for chapter in generated_chapters) + '\n').encode()
                workspace.add_artifact(state, name, data, expected[name], 'speaker-publishing-v1')
                workspace.commit(state)
        except Exception as error:
            run.status = 'partial'
            run.finished_at = now()
            run.missing = [name for name in PUBLISHING_FILES if name not in state.artifacts]
            run.limitations.append(f'Publishing stopped ({type(error).__name__}); preserved results remain usable.')
            workspace.commit(state)
            raise WorkspaceError('Publishing failed; successful checkpoints and the timed transcript are preserved. See completion-report.md.') from error
        run.missing = [name for name in PUBLISHING_FILES if name not in state.artifacts]
        run.status = 'partial' if run.missing else 'completed'
        run.finished_at = now()
        workspace.commit(state)
        return state


def load_legacy_transcript(path: Path) -> Transcript:
    preserved, raw = import_transcript(path)
    if preserved.provenance.original_schema != 'legacy-unversioned' or 'schema_version' in json.loads(raw):
        raise WorkspaceError('Versioned transcripts require explicit import; generate using the workspace directory.')
    return Transcript.model_validate_json(raw)
