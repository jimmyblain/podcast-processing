"""Acceptance runs must never use real media services or credentials."""
import socket

import pytest

from podcast_processor.llm import ClaudeClient
from podcast_processor.transcriber import WhisperLocalTranscriber


@pytest.fixture(autouse=True)
def isolated_services(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('A test attempted an uncontrolled service call')

    monkeypatch.setattr(ClaudeClient, 'generate', forbidden)
    monkeypatch.setattr(WhisperLocalTranscriber, 'transcribe', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
