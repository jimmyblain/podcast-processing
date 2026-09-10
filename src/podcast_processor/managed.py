"""Full-episode managed transcription under one durable allowance and writer lock."""
import base64
import copy
import json
import os
from pathlib import Path
import time

from . import normalization
from .participants import current_transcript, ensure_readable, map_supported, save_mapped
from .managed_models import ProviderName, TranscriptionAttempt, TranscriptionOperation, TranscriptionPolicy
from .managed_providers import BASELINES, ManagedProvider, ProviderError, response_object
from .operations import input_revision, input_snapshot, update_source
from .sources import inspect_source, prepare_transport
from .workspace import (Workspace, WorkspaceError, digest, file_hash, identifier, json_bytes,
                        now, ownership, write_file, flush_directory)
from .workspace_models import EpisodeMetadata, Run, ShowProfile, WorkspaceState


def transcribe_episode(source_or_workspace: Path, *, workspace_path: Path | None = None,
                       show_profile: ShowProfile | None = None, metadata: EpisodeMetadata | None = None,
                       primary_key: str = '', backup_key: str = '',
                       policy: TranscriptionPolicy | None = None, fresh: bool = False) -> WorkspaceState:
    invoked_at = time.time()
    source = inspect_source(source_or_workspace) if source_or_workspace.is_file() else None
    if source:
        identity = digest(('source:' + (source.fingerprint or '')).encode())[:32]
        workspace = Workspace(workspace_path or Path('output/episodes') / f'episode-{identity}')
    else:
        workspace = Workspace(workspace_path or source_or_workspace)
    with ownership(workspace.path, 'managed transcription'):
        if (workspace.path / 'current').exists():
            state = workspace.read()
            workspace.reconcile(state)
            if source:
                update_source(state, source, False, workspace)
            old_inputs = state.input_revision
            state.show_profile = show_profile or state.show_profile
            state.episode_metadata = metadata or state.episode_metadata
            state.input_revision = input_revision(state)
            if old_inputs != state.input_revision:
                state.artifacts = {n: a for n, a in state.artifacts.items() if n in ('transcript.json', 'transcript.txt')}
        else:
            if source is None:
                raise WorkspaceError('Supply a recording or an existing episode workspace.')
            state = WorkspaceState(episode_id=identity, name=source_or_workspace.stem,
                source_revision=source.id, sources=[source], import_hash='', input_revision='',
                show_profile=show_profile, episode_metadata=metadata)
            state.input_revision = input_revision(state)
        if state.show_profile is None or state.episode_metadata is None:
            raise WorkspaceError('Managed transcription requires an approved --show-profile and confirmed --metadata (guests or solo).')
        dependencies = {'source_revision': state.source_revision, 'requests': digest(json_bytes(BASELINES)),
                        'transport_version': 'lossless-flac-v1'}
        operation = next((op for op in reversed(state.transcription_operations) if op.dependencies == dependencies), None)
        if operation is None or fresh:
            started = invoked_at
            policy = policy or TranscriptionPolicy()
            operation = TranscriptionOperation(id=identifier(), dependencies=dependencies, policy=policy,
                                              started_at=started, deadline_at=started + policy.deadline_seconds)
            state.transcription_operations.append(operation)
        expected = {**dependencies, 'operation': operation.id, 'normalization': normalization.NORMALIZATION_VERSION}
        reusable = ('transcript.json' in state.artifacts and all(
            state.artifacts['transcript.json'].dependencies.get(k) == v for k, v in expected.items()))
        if reusable and operation.status == 'completed':
            state.runs.append(Run(id=identifier(), operation_id=operation.id, operation='transcribe',
                status='completed', started_at=now(), finished_at=now(),
                inputs={**input_snapshot(state), 'requests': copy.deepcopy(BASELINES)},
                limitations=[operation.outcome or 'Reused completed timed transcript.',
                             'Source-audited quality, representative runtime and billed cost remain unevaluated.']))
            original = current_transcript(workspace, state)
            mapped = map_supported(original, state.episode_metadata, state.source_revision)
            if mapped != original:
                save_mapped(workspace, state, mapped)
            ensure_readable(workspace, state)
            workspace.commit(state)
            return state
        operation.status = 'running'
        run = Run(id=identifier(), operation_id=operation.id, operation='transcribe', status='running',
                  started_at=now(), inputs={**input_snapshot(state), 'requests': copy.deepcopy(BASELINES)})
        state.runs.append(run)
        if 'transcript.json' in state.artifacts and state.artifacts['transcript.json'].dependencies != expected:
            state.artifacts.clear()
        workspace.commit(state)
        session = ManagedSession(workspace, state, operation, primary_key, backup_key, expected)
        try:
            session.execute()
        except ProviderError as error:
            operation.outcome = str(error)
        except (WorkspaceError, OSError, ValueError) as error:
            operation.outcome = f'Local processing stopped ({type(error).__name__}); retained evidence is reusable.'
            session.finish()
            raise WorkspaceError(operation.outcome) from error
        session.finish()
        return state


class ManagedSession:
    def __init__(self, workspace: Workspace, state: WorkspaceState, operation: TranscriptionOperation,
                 primary_key: str, backup_key: str, expected: dict[str, str]):
        self.workspace, self.state, self.operation = workspace, state, operation
        self.keys = {'assemblyai': primary_key, 'deepgram': backup_key}
        self.expected = expected

    def checkpoint(self) -> None:
        self.operation.elapsed_seconds = max(self.operation.elapsed_seconds, time.time() - self.operation.started_at)
        self.workspace.commit(self.state)

    def remaining(self) -> float:
        return max(0, self.operation.deadline_at - time.time())

    def receipt(self, attempt: TranscriptionAttempt, phase: str) -> Path:
        return self.workspace.path / 'receipts' / self.operation.id / attempt.id / f'{phase}.json'

    def save_receipt(self, attempt: TranscriptionAttempt, phase: str, raw: bytes) -> None:
        destination = self.receipt(attempt, phase)
        temporary = destination.with_name(f'.receipt-{identifier()}')
        envelope = json_bytes({'sha256': digest(raw), 'body': base64.b64encode(raw).decode('ascii')})
        write_file(temporary, envelope)
        os.replace(temporary, destination)
        parent = destination.parent
        while parent != self.workspace.path:
            flush_directory(parent)
            parent = parent.parent
        flush_directory(self.workspace.path)

    def read_receipt(self, path: Path) -> bytes:
        try:
            envelope = response_object(path.read_bytes())
            if not isinstance(envelope.get('body'), str) or not isinstance(envelope.get('sha256'), str):
                raise ValueError('Missing receipt body/hash.')
            raw = base64.b64decode(envelope['body'], validate=True)
            if digest(raw) != envelope['sha256']:
                raise ValueError('Receipt hash mismatch.')
            return raw
        except (ValueError, TypeError) as error:
            raise WorkspaceError('Recovery receipt is corrupt; possible job and charge retained.') from error

    def save_raw(self, attempt: TranscriptionAttempt, raw: bytes) -> None:
        name = f'raw-{attempt.id}.json'
        artifact = self.state.evidence.get(name)
        if artifact is None:
            artifact = self.workspace.add_artifact(self.state, name, raw, self.operation.dependencies,
                                                   'managed-response-v1', exposed=False)
        attempt.raw_artifact = artifact.name
        attempt.status = 'failed' if response_object(raw).get('status') == 'error' else 'completed'
        if attempt.status == 'failed':
            attempt.error = 'Provider processing failed; raw error retained.'
        self.checkpoint()

    def consume_submission(self, attempt: TranscriptionAttempt, raw: bytes) -> None:
        result = response_object(raw)
        if attempt.provider == 'assemblyai':
            job_id = result.get('id')
        else:
            job_id = result.get('metadata', {}).get('request_id')
        if not isinstance(job_id, str) or not job_id:
            attempt.status = 'ambiguous'
            attempt.error = 'Submission response has no job identity; possible charge retained.'
            self.checkpoint()
            return
        attempt.job_id, attempt.status = job_id, 'accepted'
        self.checkpoint()
        if attempt.provider == 'deepgram' or result.get('status') == 'completed':
            self.save_raw(attempt, raw)

    def submit(self, provider: ManagedProvider, attempt: TranscriptionAttempt) -> None:
        transport = self.operation.transport
        assert transport is not None
        path = self.workspace.path / transport.path
        if file_hash(path) != transport.submitted_fingerprint:
            raise WorkspaceError('Submitted transport fingerprint no longer matches.')
        while attempt.submissions < self.operation.policy.submission_attempts and self.remaining() > 0:
            # A committed intent reserves a possibly accepted job BEFORE the network call.
            attempt.status = 'intent'
            attempt.submissions += 1
            attempt.updated_at = time.time()
            self.checkpoint()
            try:
                raw = provider.submit(path, self.operation.upload_url, self.remaining())
            except ProviderError as error:
                attempt.status = 'rejected' if error.rejected else 'ambiguous'
                attempt.error = str(error)
                if error.fatal:
                    attempt.status = 'blocked'
                if error.rejected:
                    attempt.reserved_usd = 0
                self.checkpoint()
                if error.fatal:
                    raise
                if not error.rejected:
                    return
                if attempt.submissions < self.operation.policy.submission_attempts and self.remaining() > 0:
                    time.sleep(min(2 ** attempt.submissions, self.remaining()))
                    attempt.reserved_usd = attempt.estimated_usd
                continue
            # The synchronous result/accepted ID survives a later manifest/output failure.
            self.save_receipt(attempt, 'submission', raw)
            try:
                self.consume_submission(attempt, raw)
            except (ValueError, TypeError):
                attempt.status = 'ambiguous'
                attempt.error = 'Invalid submission response; possible charge retained.'
                self.checkpoint()
            return

    def reconcile_submission(self, provider: ManagedProvider, attempt: TranscriptionAttempt) -> None:
        if attempt.provider != 'assemblyai' or attempt.status != 'ambiguous':
            return
        # Listing is supported, but an absent match NEVER demonstrates nonacceptance.
        before_id = None
        while attempt.reconciliations < self.operation.policy.read_attempts:
            attempt.reconciliations += 1
            self.checkpoint()
            try:
                raw = provider.list_jobs(min(30, self.remaining()) if self.remaining() else 5, before_id)
                result = response_object(raw)
            except (ProviderError, ValueError) as error:
                attempt.error = f'Reconciliation unavailable ({type(error).__name__}); possible charge retained.'
                self.checkpoint()
                if isinstance(error, ProviderError) and error.fatal:
                    raise
                if self.remaining() <= 0:
                    return
                time.sleep(min(2 ** attempt.reconciliations, self.remaining()))
                continue
            jobs = result.get('transcripts', [])
            matches = [job for job in jobs if job.get('audio_url') == self.operation.upload_url]
            if len(matches) == 1 and isinstance(matches[0].get('id'), str):
                attempt.job_id, attempt.status = matches[0]['id'], 'accepted'
                self.checkpoint()
                return
            if matches or len(jobs) < 200 or self.remaining() <= 0:
                return
            before_id = jobs[-1].get('id')
            if not before_id:
                return

    def read_result(self, provider: ManagedProvider, attempt: TranscriptionAttempt) -> None:
        if attempt.provider != 'assemblyai' or not attempt.job_id:
            return
        # One bounded non-waiting recovery read remains available after expiry per invocation.
        expired_read = self.remaining() <= 0
        first_read = True
        while attempt.transient_reads < self.operation.policy.read_attempts or (expired_read and first_read):
            first_read = False
            attempt.reads += 1
            self.checkpoint()
            try:
                raw = provider.read(attempt.job_id, min(30, self.remaining()) if self.remaining() else 5)
                result = response_object(raw)
            except (ProviderError, ValueError) as error:
                attempt.transient_reads += 1
                attempt.error = str(error)
                self.checkpoint()
                if isinstance(error, ProviderError) and error.fatal:
                    raise
                if expired_read or self.remaining() <= 0:
                    return
                time.sleep(min(2 ** attempt.transient_reads, self.remaining()))
                continue
            if result.get('status') in ('completed', 'error'):
                self.save_receipt(attempt, 'result', raw)
                self.save_raw(attempt, raw)
                if result.get('status') == 'error':
                    attempt.status = 'failed'
                    attempt.error = 'Provider processing failed; raw error retained.'
                    self.checkpoint()
                return
            if result.get('status') not in ('queued', 'processing'):
                attempt.error = 'Unknown provider status; accepted job retained.'
                self.checkpoint()
                return
            if expired_read or self.remaining() <= 0:
                return
            time.sleep(min(3, self.remaining()))
            if self.remaining() <= 0:
                return

    def normalize_result(self, attempt: TranscriptionAttempt) -> bool:
        if attempt.raw_artifact is None or attempt.status == 'failed':
            return False
        artifact = self.state.evidence[attempt.raw_artifact]
        raw = self.workspace.artifact_bytes(artifact)
        assert self.operation.transport is not None
        try:
            transcript = normalization.normalize(response_object(raw), attempt.provider, self.operation.transport,
                self.state.source_revision, artifact.sha256, attempt.request, self.operation.id)
        except (ValueError, TypeError):
            attempt.status = 'unusable'
            attempt.error = 'Provider result has an unsupported speech schema; raw evidence retained.'
            self.checkpoint()
            return False
        if not transcript.words:
            attempt.status = 'unusable'
            attempt.error = 'No recoverable episode speech in provider result.'
            self.checkpoint()
            return False
        normalized_name = f'normalized-{transcript.revision}.json'
        if normalized_name not in self.state.evidence:
            self.workspace.add_artifact(self.state, normalized_name, json_bytes(transcript.model_dump()),
                                        self.expected, normalization.NORMALIZATION_VERSION, exposed=False)
            self.checkpoint()
        assert self.state.episode_metadata is not None
        transcript = map_supported(transcript, self.state.episode_metadata, self.state.source_revision)
        for name, data in [('transcript.json', json_bytes(transcript.model_dump())),
                           ('transcript.txt', transcript.readable().encode())]:
            if name not in self.state.artifacts:
                self.workspace.add_artifact(self.state, name, data, self.expected, normalization.NORMALIZATION_VERSION)
                self.checkpoint()
        uncertain = sum(not w.timing_usable for w in transcript.words)
        self.operation.status = 'completed'
        self.operation.outcome = f'Timed transcript preserved; {uncertain} words unusable for precise cuts. Supported participants mapped; unresolved identities retain anonymous labels.'
        return True

    def start_attempt(self, provider: ManagedProvider) -> TranscriptionAttempt | None:
        op = self.operation
        if self.remaining() <= 0:
            op.outcome = 'Transcription deadline exhausted; no new job submitted. Remote jobs and possible charges remain.'
            return None
        source = next(s for s in self.state.sources if s.id == self.state.source_revision)
        if op.transport is None:
            op.transport = prepare_transport(source, self.workspace.path, op.deadline_at)
            self.checkpoint()
        rate = (op.policy.primary_reservation_per_hour if provider.name == 'assemblyai'
                else op.policy.backup_reservation_per_hour)
        reservation = op.transport.duration / 3600 * rate
        used = sum(max(a.reserved_usd, a.actual_usd or 0) for a in op.attempts)
        if used + reservation > op.policy.allowance_usd or self.remaining() <= 0:
            op.outcome = 'Conservative spending reservation or deadline denies another transcription job.'
            return None
        provider.validate()
        if provider.name == 'assemblyai' and op.upload_url is None:
            upload = provider.upload(self.workspace.path / op.transport.path, self.remaining())
            op.upload_url = response_object(upload)['upload_url']
            self.checkpoint()
        if self.remaining() <= 0:
            op.outcome = 'Deadline expired during upload; no paid transcription job submitted.'
            return None
        attempt = TranscriptionAttempt(id=identifier(), provider=provider.name, request=provider.request,
            submitted_at=time.time(), updated_at=time.time(), estimated_usd=reservation, reserved_usd=reservation)
        op.attempts.append(attempt)
        self.submit(provider, attempt)
        return attempt

    def execute(self) -> None:
        op = self.operation
        providers: tuple[ProviderName, ...] = ('assemblyai', 'deepgram')
        for name in providers:
            attempt = next((a for a in op.attempts if a.provider == name), None)
            provider = ManagedProvider(name, self.keys[name], attempt.request if attempt else copy.deepcopy(BASELINES[name]))
            if attempt is None:
                attempt = self.start_attempt(provider)
                if attempt is None:
                    return
            else:
                if attempt.status == 'blocked':
                    op.outcome = (attempt.error or 'Provider configuration failed.') + ' Correct configuration and use --fresh to authorize a new operation.'
                    return
                result_receipt = self.receipt(attempt, 'result')
                submission_receipt = self.receipt(attempt, 'submission')
                if attempt.raw_artifact is None:
                    if result_receipt.exists():
                        self.save_raw(attempt, self.read_receipt(result_receipt))
                    elif submission_receipt.exists():
                        self.consume_submission(attempt, self.read_receipt(submission_receipt))
                if attempt.status == 'intent':
                    attempt.status = 'ambiguous'
                    attempt.error = 'Invocation interrupted during submission; possible charge retained.'
                    self.checkpoint()
                if attempt.status == 'rejected' and attempt.submissions < op.policy.submission_attempts:
                    used = sum(max(a.reserved_usd, a.actual_usd or 0) for a in op.attempts if a.id != attempt.id)
                    if used + attempt.estimated_usd > op.policy.allowance_usd:
                        op.outcome = 'Remaining reservations deny a rejected-submission retry.'
                        return
                    attempt.reserved_usd = attempt.estimated_usd
                    self.submit(provider, attempt)
            if attempt.raw_artifact is None:
                self.reconcile_submission(provider, attempt)
                if attempt.status == 'accepted':
                    self.read_result(provider, attempt)
            if attempt.raw_artifact and self.normalize_result(attempt):
                return
            if attempt.status == 'accepted':
                op.outcome = 'Accepted job remains pending; resume uses the same ID. A deadline does not cancel it or remove possible charges.'
                return
        op.outcome = 'Transcription unavailable after bounded primary and backup processing; evidence and possible charges retained.'

    def finish(self) -> None:
        op = self.operation
        run = self.state.runs[-1]
        if op.status != 'completed' or any(n not in self.state.artifacts for n in ('transcript.json', 'transcript.txt')):
            op.status = 'unavailable'
        run.status = 'completed' if op.status == 'completed' else 'partial'
        run.finished_at = now()
        run.missing = [n for n in ('transcript.json', 'transcript.txt') if n not in self.state.artifacts]
        run.limitations = [op.outcome or 'Transcription unavailable.',
                           'Native confidence is not timing accuracy; source-audited quality, representative runtime and actual billed cost remain unevaluated.']
        self.checkpoint()
