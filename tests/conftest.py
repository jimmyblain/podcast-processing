"""Acceptance runs must never use real media services or credentials."""
import socket

import pytest

from podcast_processor.llm import ClaudeClient
from podcast_processor.transcriber import WhisperLocalTranscriber


@pytest.fixture(autouse=True)
def isolated_services(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('A test attempted an uncontrolled service call')

    monkeypatch.setattr(ClaudeClient, 'generate', forbidden)
    monkeypatch.setattr(WhisperLocalTranscriber, 'transcribe', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setenv('PODCAST_SHOW_SETUP', str(tmp_path / 'show-setup'))


@pytest.fixture
def approved_show_setup(tmp_path, isolated_services):
    from podcast_processor.cli import app
    from typer.testing import CliRunner
    from setup_audio import transitions
    directory, _ = transitions(tmp_path)
    result = CliRunner().invoke(app, ['setup', '--transitions', str(directory), '--no-play'], input='y\n')
    assert result.exit_code == 0, (result.output, result.exception)
