import json
from pathlib import Path

from typer.testing import CliRunner

from podcast_processor.cli import app

FIXTURE = Path(__file__).parent / 'fixtures/legacy-transcript.json'
runner = CliRunner()


def imported(tmp_path, *options):
    result = runner.invoke(app, ['import', str(FIXTURE), '--root', str(tmp_path / 'episodes'), *options])
    assert result.exit_code == 0, result.output
    return next(path for path in (tmp_path / 'episodes').iterdir() if path.is_dir())


def inspect(workspace):
    result = runner.invoke(app, ['inspect', str(workspace), '--json'])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_import_is_readable_honest_and_non_destructive(tmp_path):
    original = FIXTURE.read_bytes()
    workspace = imported(tmp_path)
    state = inspect(workspace)
    assert state['schema_version'] == 2
    assert state['episode_id'] in workspace.name
    transcript = json.loads((workspace / 'current/transcript.json').read_text())
    assert transcript['segments'][0]['text'] == 'Well, well, taking a chance is hard.'
    assert transcript['segments'][0]['speaker'] is None
    assert transcript['provenance']['settings'] is None
    assert transcript['provenance']['timing_confidence'] is None
    assert '[00:00] Unknown speaker:' in (workspace / 'current/transcript.txt').read_text()
    report = (workspace / 'current/completion-report.md').read_text()
    assert 'unknown' in report
    assert 'description.md' in report
    assert FIXTURE.read_bytes() == original


def make_media(path, value=0):
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(value.to_bytes(2, 'little') * 8000)
    return path


def test_source_identity_moves_revisions_and_explicit_copy(tmp_path):
    source = make_media(tmp_path / 'one/episode.wav')
    workspace = imported(tmp_path, '--source', str(source))
    first = inspect(workspace)
    same = imported(tmp_path, '--source', str(source))
    assert same == workspace
    assert inspect(same)['artifacts'] == first['artifacts']
    moved = tmp_path / 'moved.wav'
    source.rename(moved)
    result = runner.invoke(app, ['attach-source', str(workspace), str(moved), '--copy-source'])
    assert result.exit_code == 0, result.output
    attached = inspect(workspace)
    assert attached['episode_id'] == first['episode_id']
    assert attached['source_revision'] == first['source_revision']
    assert attached['artifacts'] == first['artifacts']
    assert (workspace / attached['sources'][-1]['copied_path']).read_bytes() == moved.read_bytes()
    other = make_media(tmp_path / 'two/episode.wav', 1)
    result = runner.invoke(app, ['import', str(FIXTURE), '--root', str(tmp_path / 'episodes'), '--source', str(other)])
    assert result.exit_code == 0, result.output
    assert len([p for p in (tmp_path / 'episodes').iterdir() if p.is_dir()]) == 2
    result = runner.invoke(app, ['attach-source', str(workspace), str(other)])
    assert result.exit_code == 0, result.output
    changed = inspect(workspace)
    assert changed['episode_id'] == first['episode_id']
    assert changed['source_revision'] != first['source_revision']
    assert len(changed['sources']) == 2
    assert 'transcript.json' not in changed['artifacts']
    assert any(a['id'] == first['artifacts']['transcript.json']['id'] for a in changed['history'])


def authority(tmp_path):
    profile = tmp_path / 'show.json'
    profile.write_text(json.dumps({'approved': True, 'name': "I'll Just Let Myself In", 'host': 'Lish Speaks',
                                   'audience': 'People ready to take a chance on themselves.', 'voice': 'Warm and candid.'}))
    metadata = tmp_path / 'episode.json'
    metadata.write_text(json.dumps({'solo': True, 'participants': [{'name': 'Lish Speaks', 'role': 'host'}]}))
    return ['--show-profile', str(profile), '--metadata', str(metadata)]


def test_generation_from_missing_source_preserves_checkpoints_and_reuses_calls(tmp_path, monkeypatch):
    from podcast_processor.llm import ClaudeClient, LLMError
    source = make_media(tmp_path / 'episode.wav')
    workspace = imported(tmp_path, '--source', str(source), *authority(tmp_path))
    source.unlink()
    missing = runner.invoke(app, ['check-source', str(workspace)])
    assert missing.exit_code == 1
    assert 'missing' in missing.output.lower()
    transcript_id = inspect(workspace)['artifacts']['transcript.json']['id']
    calls = []

    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        if len(calls) == 1:
            return 'One honest conversation can be a beginning.'
        if len(calls) == 2:
            raise LLMError('injected late failure')
        if 'thumbnail_text' in prompt:
            return '[{"title":"Start With One Honest Conversation","thumbnail_text":"Start Here"}]'
        return '[{"start_time":0,"title":"A beginning"}]'

    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    args = ['generate', str(workspace), '--api-key', 'secret-test-token']
    failed = runner.invoke(app, args)
    assert failed.exit_code == 1, failed.output
    partial = inspect(workspace)
    assert partial['artifacts']['transcript.json']['id'] == transcript_id
    assert (workspace / 'current/description.md').exists()
    assert partial['runs'][-1]['status'] == 'partial'
    done = runner.invoke(app, args)
    assert done.exit_code == 0, done.output
    assert len(calls) == 4
    complete = inspect(workspace)
    rerun = runner.invoke(app, args)
    assert rerun.exit_code == 0, rerun.output
    assert len(calls) == 4
    assert inspect(workspace)['artifacts'] == complete['artifacts']
    assert all('secret-test-token' not in path.read_text() for path in workspace.rglob('*.json'))
    assert all('Lish Speaks' in prompt and 'Warm and candid' in prompt for prompt in calls)


def test_metadata_change_keeps_transcript_identity_but_supersedes_publishing(tmp_path, monkeypatch):
    from podcast_processor.llm import ClaudeClient
    options = authority(tmp_path)
    workspace = imported(tmp_path, *options)

    def publish(self, prompt, max_tokens=4096):
        if 'thumbnail_text' in prompt:
            return '[{"title":"A beginning","thumbnail_text":"Start Here"}]'
        if 'start_time' in prompt:
            return '[{"start_time":0,"title":"A beginning"}]'
        return 'A beginning.'

    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    assert runner.invoke(app, ['generate', str(workspace), '--api-key', 'test']).exit_code == 0
    before = inspect(workspace)
    metadata = json.loads((tmp_path / 'episode.json').read_text())
    metadata['links'] = ['https://example.com/approved']
    (tmp_path / 'episode.json').write_text(json.dumps(metadata))
    imported(tmp_path, *options)
    after = inspect(workspace)
    assert after['artifacts']['transcript.json']['id'] == before['artifacts']['transcript.json']['id']
    assert 'description.md' not in after['artifacts']
    assert not (workspace / 'current/description.md').exists()
    assert any(a['id'] == before['artifacts']['description.md']['id'] for a in after['history'])


def test_future_and_unknown_schemas_are_rejected_in_import_and_legacy_generate(tmp_path):
    for payload in ({'schema_version': 99, 'segments': []},
                    {**json.loads(FIXTURE.read_text()), 'new_provenance': {'source': 'unknown'}},
                    {**json.loads(FIXTURE.read_text()), 'segments': [{'text': 'hello', 'start': 0, 'end': 1, 'vendor_label': 'A'}]}):
        path = tmp_path / 'future.json'
        path.write_text(json.dumps(payload))
        for args in (['import', str(path), '--root', str(tmp_path / 'episodes')],
                     ['generate', str(path), '--api-key', 'test']):
            result = runner.invoke(app, args)
            assert result.exit_code == 1, result.output
            assert 'Unsupported' in result.output or 'Extra inputs' in result.output, result.output
    assert not (tmp_path / 'episodes').exists()


def test_supported_v2_reimport_preserves_original_provenance(tmp_path):
    workspace = imported(tmp_path)
    versioned = workspace / 'current/transcript.json'
    original = versioned.read_bytes()
    result = runner.invoke(app, ['import', str(versioned), '--root', str(tmp_path / 'migrated')])
    assert result.exit_code == 0, result.output
    target = next(p for p in (tmp_path / 'migrated').iterdir() if p.is_dir())
    assert (target / 'current/import-original.json').read_bytes() == original
    assert json.loads((target / 'current/transcript.json').read_bytes())['provenance'] == json.loads(original)['provenance']


def test_missing_timing_allows_text_outputs_but_reports_partial(tmp_path, monkeypatch):
    from podcast_processor.llm import ClaudeClient
    path = tmp_path / 'untimed.json'
    path.write_text(json.dumps({'segments': [{'text': 'Well, well, we can start again.'}]}))
    result = runner.invoke(app, ['import', str(path), '--root', str(tmp_path / 'episodes'), *authority(tmp_path)])
    assert result.exit_code == 0, result.output
    workspace = next(p for p in (tmp_path / 'episodes').iterdir() if p.is_dir())
    calls = []

    def publish(self, prompt, max_tokens=4096):
        calls.append(prompt)
        if 'thumbnail_text' in prompt:
            return '[{"title":"Begin Again","thumbnail_text":"One Step"}]'
        return 'We can start again.'

    monkeypatch.setattr(ClaudeClient, 'generate', publish)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'test'])
    assert result.exit_code == 1, result.output
    assert len(calls) == 2
    state = inspect(workspace)
    assert state['runs'][-1]['missing'] == ['chapters.txt']
    assert (workspace / 'current/description.md').exists()
    assert not (workspace / 'current/chapters.txt').exists()
    assert 'unknown time' in (workspace / 'current/transcript.txt').read_text()
    assert 'Chapters unavailable' in (workspace / 'current/completion-report.md').read_text()


def test_required_authority_is_validated_before_service_calls(tmp_path, monkeypatch):
    from podcast_processor.llm import ClaudeClient

    def forbidden(*args, **kwargs):
        raise AssertionError('No publishing call expected')

    monkeypatch.setattr(ClaudeClient, 'generate', forbidden)
    workspace = imported(tmp_path)
    result = runner.invoke(app, ['generate', str(workspace), '--api-key', 'test'])
    assert result.exit_code == 1
    assert 'approved show profile' in result.output
    options = authority(tmp_path)
    profile = json.loads((tmp_path / 'show.json').read_text())
    profile['host'] = 'Speaker 1'
    (tmp_path / 'show.json').write_text(json.dumps(profile))
    result = runner.invoke(app, ['import', str(FIXTURE), '--root', str(tmp_path / 'episodes'), *options])
    assert result.exit_code == 1
    assert 'Lish Speaks' in result.output
    assert inspect(workspace)['show_profile'] is None
