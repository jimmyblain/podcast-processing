"""Small HTTP adapters. No SDK retries, implicit model fallback or idempotency."""
import json
from pathlib import Path
from typing import Any

import httpx

from .managed_models import ProviderName
from .workspace import WorkspaceError

BASELINES: dict[ProviderName, dict[str, Any]] = {
    'assemblyai': {
        'endpoint': 'https://api.eu.assemblyai.com', 'region': 'EU',
        'privacy': {'training': 'EU exclusion requested via endpoint', 'retention_verified': False,
                    'deletion_verified': False},
        'settings': {'speech_models': ['universal-3-5-pro'], 'language_code': 'en',
                     'speaker_labels': True, 'punctuate': True, 'format_text': False,
                     'disfluencies': True}},
    'deepgram': {
        'endpoint': 'https://api.deepgram.com', 'region': 'US',
        'privacy': {'mip_opt_out': True, 'retention_verified': False, 'deletion_verified': False},
        'settings': {'model': 'nova-3', 'diarize_model': 'v2', 'language': 'en',
                     'utterances': True, 'punctuate': True, 'filler_words': True,
                     'smart_format': False, 'multichannel': False, 'mip_opt_out': True}},
}


class ProviderError(WorkspaceError):
    def __init__(self, message: str, *, rejected: bool = False, fatal: bool = False):
        super().__init__(message)
        self.rejected = rejected
        self.fatal = fatal


def response_object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Provider response must be an object.')
    return value


class ManagedProvider:
    def __init__(self, name: ProviderName, api_key: str, request: dict[str, Any]):
        self.name, self.api_key, self.request = name, api_key, request

    def validate(self) -> None:
        if not self.api_key:
            raise ProviderError(f'{self.name}: API key is required.', rejected=True, fatal=True)

    def call(self, method: str, path: str, timeout: float, **kwargs: Any) -> bytes:
        self.validate()
        headers = {'Authorization': self.api_key if self.name == 'assemblyai' else f'Token {self.api_key}'}
        try:
            with httpx.Client(timeout=max(0.001, timeout), follow_redirects=False) as client:
                response = client.request(method, self.request['endpoint'] + path, headers=headers, **kwargs)
        except httpx.TransportError as error:
            # Even a transport failure may occur after the server accepts the body.
            raise ProviderError(f'{self.name}: transport failure; acceptance may be unknown.') from error
        if not response.is_success:
            code = response.status_code
            raise ProviderError(f'{self.name}: HTTP {code}.',
                                rejected=code in (400, 401, 403, 404, 413, 415, 422, 429),
                                fatal=code in (400, 401, 403, 404, 413, 415, 422))
        return response.content

    def upload(self, path: Path, timeout: float) -> bytes:
        with path.open('rb') as stream:
            return self.call('POST', '/v2/upload', timeout, content=stream)

    def submit(self, path: Path, upload_url: str | None, timeout: float) -> bytes:
        settings = self.request['settings']
        if self.name == 'assemblyai':
            return self.call('POST', '/v2/transcript', timeout, json={**settings, 'audio_url': upload_url})
        params = {k: str(v).lower() if isinstance(v, bool) else v for k, v in settings.items()}
        with path.open('rb') as stream:
            return self.call('POST', '/v1/listen', timeout, params=params, content=stream)

    def read(self, job_id: str, timeout: float) -> bytes:
        from urllib.parse import quote
        return self.call('GET', '/v2/transcript/' + quote(job_id, safe=''), timeout)

    def list_jobs(self, timeout: float, before_id: str | None = None) -> bytes:
        params: dict[str, Any] = {'limit': 200}
        if before_id:
            params['before_id'] = before_id
        return self.call('GET', '/v2/transcript', timeout, params=params)
