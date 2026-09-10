"""Legacy publishing adapter with durable request/response evidence.

This is intentionally the existing publishing format. The v2 package validator,
provider usage ledger, and bounded publishing retry policy are later slices.
"""
import json

from .llm import ClaudeClient
from .workspace import Workspace, digest, json_bytes
from .workspace_models import WorkspaceState


class PreservedPublishingClient:
    def __init__(self, workspace: Workspace, state: WorkspaceState, api_key: str, model: str):
        self.workspace = workspace
        self.state = state
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 4096) -> str:
        context = {'show_profile': self.state.show_profile.model_dump() if self.state.show_profile else None,
                   'episode_metadata': self.state.episode_metadata.model_dump() if self.state.episode_metadata else None}
        prompt += ('\n\nAuthoritative supplied context (use only confirmed facts; anonymous speakers are not '
                   'identified participants; use neutral topic-based attribution for anonymous speech. '
                   'Unclear passages have been excluded: do not reconstruct missing speech, quote it, or make factual '
                   'promises from it. Do not invent missing details):\n' + json.dumps(context, ensure_ascii=False))
        request = {'model': self.model, 'prompt': prompt, 'max_tokens': max_tokens,
                   'stage_version': 'legacy-publishing-v1', 'returned_model_version': None,
                   'request_id': None, 'usage': {'actual': None, 'estimated': None, 'reserved': None}}
        request_hash = digest(json_bytes(request))
        name = f'publishing-response-{request_hash}.json'
        cached = self.state.evidence.get(name)
        if cached:
            return json.loads(self.workspace.artifact_bytes(cached))['response']
        response = ClaudeClient(api_key=self.api_key, model=self.model).generate(prompt, max_tokens)
        self.workspace.add_artifact(self.state, name, json_bytes({'request': request, 'response': response}),
                                    {'request': request_hash}, 'legacy-publishing-v1', exposed=False)
        self.workspace.commit(self.state)
        return response
