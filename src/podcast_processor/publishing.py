"""Publishing requests: one durable allowance, response recovery, no nested retries."""
import json
import os
from collections.abc import Callable
from typing import TypeVar

from .llm import ClaudeClient
from .workspace import Workspace, WorkspaceError, digest, flush_directory, identifier, json_bytes, now, write_file
from .workspace_models import PublishingAttempt, PublishingOperation, WorkspaceState

T = TypeVar('T')


class PreservedPublishingClient:
    def __init__(self, workspace: Workspace, state: WorkspaceState, api_key: str, model: str):
        self.workspace, self.state, self.api_key, self.model = workspace, state, api_key, model

    def generate(self, operation: PublishingOperation, prompt: str, validate: Callable[[str], T]) -> T:
        """Persist request intent, then raw response before validation or artifact writes.

        The receipt has a deterministic path recorded before dispatch. A crash between
        receipt storage and manifest commit recovers it without another paid request.
        A requested attempt without a receipt counts as possibly billed on resume.
        """
        while True:
            pending = next((a for a in reversed(operation.attempts) if a.status in ('requested', 'responded', 'validated')), None)
            if pending is not None:
                committed_receipt = self.workspace.path / pending.response_path
                receipt = committed_receipt if committed_receipt.exists() else committed_receipt.with_suffix('.pending')
                if receipt.exists():
                    data = receipt.read_bytes()
                    if pending.response_hash and digest(data) != pending.response_hash:
                        raise WorkspaceError('Saved publishing response failed hash verification.')
                    try:
                        saved = json.loads(data)
                        if not isinstance(saved, dict) or not isinstance(saved.get('response'), str) or not isinstance(saved.get('metadata'), dict):
                            raise ValueError('Incomplete receipt structure.')
                    except ValueError:
                        pending.status, pending.finished_at = 'failed', now()
                        pending.error = 'Incomplete publishing response receipt; response and charge unknown.'
                        self.workspace.commit(self.state)
                        continue
                    if receipt != committed_receipt:
                        os.replace(receipt, committed_receipt)
                        flush_directory(committed_receipt.parent)
                    pending.response_hash = digest(data)
                    pending.status = 'responded'
                    for key in ('returned_model', 'request_id', 'response_id', 'usage'):
                        if key in saved['metadata']:
                            setattr(pending, key, saved['metadata'][key])
                    self.workspace.commit(self.state)
                    try:
                        result = validate(saved['response'])
                    except ValueError as error:
                        pending.status = 'invalid'
                        # Validation errors may embed untrusted provider text. Keep the
                        # diagnostic useful without copying arbitrary text into reports.
                        pending.error = str(error)[:2000]
                        self.workspace.commit(self.state)
                    else:
                        pending.status = 'validated'
                        pending.finished_at = now()
                        self.workspace.commit(self.state)
                        return result
                else:
                    if pending.status != 'requested':
                        raise WorkspaceError('Saved publishing response is missing; no automatic paid replacement.')
                    pending.status = 'failed'
                    pending.error = 'Interrupted request; response and charge unknown.'
                    pending.finished_at = now()
                    self.workspace.commit(self.state)
            if len(operation.attempts) >= 3:
                raise WorkspaceError(f'{operation.stage} unavailable: three publishing attempts exhausted; resume grants no new allowance.')
            repair = next((a.error for a in reversed(operation.attempts) if a.status == 'invalid'), None)
            rendered = prompt + ('\nRepair the previous invalid output. Validation feedback:\n' + repair if repair else '')
            if not self.api_key:
                raise WorkspaceError('Anthropic API key required for a new publishing request; saved responses remain reusable.')
            attempt_id = identifier()
            attempt = PublishingAttempt(id=attempt_id, started_at=now(),
                request={'model': self.model, 'prompt': rendered, 'max_tokens': 8192,
                         'endpoint': 'anthropic.messages.create', 'sdk_max_retries': 0,
                         'template_version': operation.dependencies['template'], 'schema_version': 2},
                response_path=f'publishing-responses/{attempt_id}.json')
            operation.attempts.append(attempt)
            self.workspace.commit(self.state)
            try:
                client = ClaudeClient(api_key=self.api_key, model=self.model, max_attempts=1)
                response = client.generate(rendered, max_tokens=8192)
            except Exception as error:
                attempt.status, attempt.finished_at = 'failed', now()
                attempt.error = f'Provider request failed ({type(error).__name__}); charge unknown.'
                self.workspace.commit(self.state)
                continue
            receipt_data = json_bytes({'response': response, 'metadata': client.response_metadata,
                                       'received_at': now()})
            receipt = self.workspace.path / attempt.response_path
            temporary = receipt.with_suffix('.pending')
            write_file(temporary, receipt_data)
            os.replace(temporary, receipt)
            flush_directory(receipt.parent)
            attempt.response_hash = digest(receipt_data)
            attempt.status, attempt.finished_at = 'responded', now()
            self.workspace.commit(self.state)
