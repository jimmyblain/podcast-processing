"""One unattended episode workflow, preserving the independent stage checkpoints."""
from pathlib import Path

from .managed_models import TranscriptionPolicy
from .workspace import (PROCESS_FILES, Workspace, WorkspaceError, digest, file_hash,
                        identifier, now, ownership)
from .workspace_models import EpisodeMetadata, Run, ShowProfile, WorkspaceState


def episode_path(source: Path, target: Path | None = None) -> Path:
    if target is not None:
        return target.resolve()
    if source.is_dir():
        return source.resolve()
    identity = digest(('source:' + file_hash(source)).encode())[:32]
    return Path('output/episodes', f'episode-{identity}').resolve()


def process_episode(source: Path, *, workspace_path: Path | None = None,
                    show_profile: ShowProfile | None = None, metadata: EpisodeMetadata | None = None,
                    primary_key: str = '', backup_key: str = '', api_key: str = '', model: str,
                    policy: TranscriptionPolicy | None = None, fresh: bool = False,
                    only: str | None = None, chapters: int = 10, chapter_labels: Path | None = None,
                    evidence: Path | None = None) -> WorkspaceState:
    from .managed import transcribe_episode
    from .package import generate_package
    from .planning import plan_episode

    if only not in (None, 'titles', 'description', 'chapters') or not 3 <= chapters <= 10:
        raise WorkspaceError('Select titles, description or chapters; chapter limit must be 3–10.')
    if chapter_labels and (fresh or only not in (None, 'chapters')):
        raise WorkspaceError('Chapter labels require local reassembly without --fresh.')
    workspace = Workspace(episode_path(source, workspace_path))
    with ownership(workspace.path, 'complete episode workflow'):
        before = workspace.read() if (workspace.path / 'current').exists() else None
        previous = dict(before.artifacts) if before else {}
        prior_history = list(before.history) if before else []
        # Source-producing runs persist authority even when current files are damaged
        # or an import was interrupted before its transcript artifact was committed.
        using_import = bool(before and next((run.operation == 'import' for run in reversed(before.runs)
            if run.operation in ('import', 'transcribe')), bool(before.import_hash)))
        started = now()
        first_run = len(before.runs) if before else 0
        notes = []
        stage_failed = False
        if before:
            note_count = len(before.runs[-1].limitations)
            interrupted = before.runs[-1].status in ('running', 'interrupted')
            workspace.reconcile(before)
            notes.extend(before.runs[-1].limitations[note_count:])
            if interrupted:
                notes.append('Recovered abandoned operation; committed checkpoints and allowances retained.')
        try:
            if before and using_import and not (fresh and only is None) and source.is_dir():
                from .operations import input_revision
                from .package import prune_inputs
                from .participants import current_transcript, map_episode
                state = before
                workspace.reconcile(state)
                from .authority import approved_show_profile
                state.show_profile = show_profile or state.show_profile or approved_show_profile()
                state.episode_metadata = metadata or state.episode_metadata
                if state.show_profile is None or state.episode_metadata is None:
                    raise WorkspaceError('Supply an approved show profile and confirmed participants or solo status.')
                state.input_revision = input_revision(state)
                prune_inputs(state, current_transcript(workspace, state))
                workspace.commit(state)
                state = map_episode(workspace.path)
            else:
                state = transcribe_episode(source, workspace_path=workspace.path, show_profile=show_profile,
                    metadata=metadata, primary_key=primary_key, backup_key=backup_key, policy=policy,
                    fresh=fresh and only is None)
        except (WorkspaceError, OSError, ValueError) as error:
            if not (workspace.path / 'current').exists():
                raise
            state = workspace.read()
            notes.append(f'Transcription unavailable: {error}')
            stage_failed = True
        for stage in ('publishing', 'planning'):
            if 'transcript.json' not in state.artifacts:
                notes.append(f'{stage.capitalize()} unavailable: no current usable timed transcript.')
                continue
            try:
                if stage == 'publishing':
                    state = generate_package(workspace.path, api_key, model, chapters, only, fresh, chapter_labels)
                    stage_failed |= state.runs[-1].status != 'completed'
                else:
                    state = plan_episode(workspace.path, evidence)
            except (WorkspaceError, OSError, ValueError) as error:
                state = workspace.read()
                notes.append(f'{stage.capitalize()} unavailable: {error}')
                stage_failed = True
                if stage == 'planning':
                    from .planning import PLAN_FILES
                    for name in PLAN_FILES:
                        state.artifacts.pop(name, None)
                    workspace.commit(state)
        for run in state.runs[first_run:]:
            notes.extend(run.limitations)
        for name, artifact in state.artifacts.items():
            prior = previous.get(name)
            outcome = 'Fresh'
            if prior and prior.id == artifact.id:
                outcome = 'Reused'
            elif not fresh and any(old.name == name and old.sha256 == artifact.sha256
                                   and old.dependencies == artifact.dependencies for old in prior_history):
                outcome = 'Recovered'
            notes.append(f'{outcome} {name}: {artifact.id}.')
        for name, artifact in previous.items():
            if name not in state.artifacts or state.artifacts[name].id != artifact.id:
                notes.append(f'Superseded {name}: {artifact.id}; immutable history retained.')
        missing = [name for name in PROCESS_FILES if name not in state.artifacts]
        run = Run(id=identifier(), operation_id=identifier(), operation='process', started_at=started,
            finished_at=now(), status=('partial' if state.artifacts else 'failed') if missing or stage_failed else 'completed',
            inputs={'source_revision': state.source_revision, 'fresh': fresh, 'only': only,
                    'stage_runs': [r.id for r in state.runs[first_run:]]},
            missing=missing, limitations=list(dict.fromkeys(notes)))
        state.runs.append(run)
        workspace.commit(state)
        return state


def completion_report(workspace: Workspace, state: WorkspaceState) -> str:
    from .participants import current_transcript, uncertainty_report
    from .planning import planning_report

    run = state.runs[-1]
    lines = ['# Completion report', '', f'Episode: {state.episode_id}', 'Operation: process',
             f'Status: {run.status}', '', f'Usable outputs: {", ".join(state.artifacts) or "none"}',
             f'Missing required outputs: {", ".join(run.missing) or "none"}', '',
             planning_report(workspace, state), 'Transcription usage (separate from publishing):']
    for op in state.transcription_operations:
        lines.append(f'- Operation {op.id}: allowance ${op.policy.allowance_usd:.2f}; '
                     f'deadline {op.deadline_at}; elapsed {op.elapsed_seconds:.1f}s. {op.outcome or ""}')
        for attempt in op.attempts:
            actual = 'unknown' if attempt.actual_usd is None else f'${attempt.actual_usd:.4f}'
            role = 'primary' if attempt.provider == 'assemblyai' else 'backup'
            lines.append(f'  {role} {attempt.provider}: {attempt.status}; job {attempt.job_id or "unknown"}; '
                         f'estimated ${attempt.estimated_usd:.4f}, reserved ${attempt.reserved_usd:.4f}, actual {actual}. '
                         f'{attempt.error or ""}')
    lines.extend(['Reservations are admission estimates, not verified bills. A timeout does not cancel remote jobs or imply free usage.',
                  '', 'Publishing usage (billing cost unknown):'])
    for publishing in state.publishing_operations:
        lines.append(f'- {publishing.stage} operation {publishing.id}: {len(publishing.attempts)}/3 attempts; '
                     + ', '.join(f'{a.status} (usage {a.usage})' for a in publishing.attempts))
    lines.extend(['', *('- ' + note for note in run.limitations)])
    if 'transcript.json' in state.artifacts:
        transcript = current_transcript(workspace, state)
        if 'import' in state.artifacts['transcript.json'].dependencies:
            lines.append('Imported-with-limitations: original settings, identity and source timing may be unknown; import is not source verification.')
        lines.append(uncertainty_report(transcript))
    lines.append('Deterministic checks do not establish source quality, safe real cuts, human editorial approval, representative runtime or actual-cost acceptance (#19).')
    return '\n'.join(lines) + '\n'
