"""Validate operator copy without rewriting it or promoting it to episode evidence."""
import re

from .publishing_models import PublishingChapter, validate_title_concepts
from .workspace import EDITABLE_PUBLISHING_FILES, Workspace, WorkspaceError, digest
from .workspace_models import Artifact, PreservedTranscript, WorkspaceState


def validate_edited_chapters(text: str, duration: float | None) -> None:
    chapters = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'(?:(\d+):([0-5]\d):([0-5]\d)|(\d{2}):([0-5]\d)) (\S.*)', line.strip())
        if not match:
            raise ValueError('Invalid chapter timestamp/title line; use MM:SS or H:MM:SS followed by a title.')
        hours, minutes, seconds, short_minutes, short_seconds, label = match.groups()
        start = int(hours) * 3600 + int(minutes) * 60 + int(seconds) if hours else int(short_minutes) * 60 + int(short_seconds)
        chapters.append(PublishingChapter(start_time=float(start), title=label, boundary_id='operator', reason='Operator edit'))
    if not 3 <= len(chapters) <= 10:
        raise ValueError('Chapters require 3–10 entries.')
    if chapters[0].start_time != 0:
        raise ValueError('Chapters must begin at 00:00.')
    labels = [re.sub(r'[^\w]', '', c.title.casefold()) for c in chapters]
    if len(set(labels)) != len(labels):
        raise ValueError('Chapter labels must be distinct.')
    ends = [c.start_time for c in chapters[1:]]
    if duration is not None:
        ends.append(duration)
    if any(end - chapter.start_time < 10 for chapter, end in zip(chapters, ends)):
        raise ValueError('Chapters must ascend and each last at least ten seconds, including the final chapter.')


def stale_edit(workspace: Workspace, state: WorkspaceState, artifact: Artifact) -> bool:
    from .package import dependencies_match, stage_inputs, supplied_appendix

    ancestry = {a.id: a for a in state.history}
    ancestor = artifact
    visited = set()
    while ancestor.edited_from:
        if ancestor.edited_from in visited or ancestor.edited_from not in ancestry:
            raise WorkspaceError('Missing or cyclic operator edit history.')
        visited.add(ancestor.edited_from)
        ancestor = ancestry[ancestor.edited_from]
        workspace.artifact_bytes(ancestor)
    if artifact.edit_source_revision != state.source_revision:
        return True
    transcript_artifact = state.artifacts.get('transcript.json')
    if transcript_artifact is None or state.show_profile is None or state.episode_metadata is None:
        return True
    transcript = PreservedTranscript.model_validate_json(workspace.artifact_bytes(transcript_artifact))
    consumers = []
    if artifact.name == 'description.md':
        if artifact.dependencies.get('appendix') != digest(supplied_appendix(state).encode()):
            return True
        body = next((a for a in state.history if a.name == 'description-body.json'
                     and a.sha256 == artifact.dependencies.get('body')), None)
        chapters = next((a for a in state.history if a.id == artifact.dependencies.get('chapters_version')), None)
        if body is None or chapters is None:
            return True
        consumers = [('body', body), ('chapters', chapters)]
    else:
        consumers = [('titles' if artifact.name == 'titles.json' else 'chapters', artifact)]
    for stage, consumer in consumers:
        # The dependency claim is usable only while its immutable evidence verifies.
        workspace.artifact_bytes(consumer)
        if stage == 'chapters':
            chapter_data = next((a for a in state.history if a.name == 'chapters.json'
                                 and a.sha256 == consumer.dependencies.get('chapter_data')), None)
            if chapter_data is None:
                raise WorkspaceError('Missing structured chapter dependency evidence.')
            workspace.artifact_bytes(chapter_data)
        expected = stage_inputs(state, transcript, consumer.dependencies.get('model', ''),
                                int(consumer.dependencies.get('chapter_count', '10')))[stage][0]
        if not dependencies_match(consumer, expected):
            return True
    return False


def publishing_issues(workspace: Workspace, state: WorkspaceState) -> dict[str, list[str]]:
    if not any(artifact.status == 'human-edited' for artifact in state.artifacts.values()):
        return {}
    issues: dict[str, list[str]] = {}
    copies = {}
    transcript_artifact = state.artifacts.get('transcript.json')
    try:
        duration = (PreservedTranscript.model_validate_json(workspace.artifact_bytes(transcript_artifact)).duration
                    if transcript_artifact else None)
    except (OSError, ValueError, WorkspaceError):
        duration = None  # Each edit's dependency check reports unusable episode evidence.
    for name, artifact in state.artifacts.items():
        if name not in EDITABLE_PUBLISHING_FILES:
            continue
        problems = []
        try:
            text = workspace.artifact_bytes(artifact).decode('utf-8')
            copies[name] = text
            if artifact.status != 'human-edited':
                continue
            if not text.strip() or any(ord(c) < 32 and c not in '\r\n\t' for c in text):
                problems.append('Publishing copy must be nonempty text without control characters.')
            if name == 'description.md' and len(text) > 5000:
                problems.append('Description exceeds the 5,000-character limit.')
            if name == 'titles.json':
                validate_title_concepts(text)
            if name == 'chapters.txt':
                validate_edited_chapters(text, duration)
        except UnicodeDecodeError:
            problems.append('Publishing copy is not valid UTF-8 text.')
        except ValueError as error:
            problems.append(str(error))
        if artifact.status == 'human-edited' and name == 'titles.md':
            problems.append('Operator-edited readable titles: agreement with titles.json is unverified; exact bytes retained.')
        elif artifact.status == 'human-edited':
            try:
                if stale_edit(workspace, state, artifact):
                    problems.append('Operator edit is stale: its episode evidence or publishing inputs changed or are unavailable.')
            except (OSError, ValueError, WorkspaceError):
                problems.append('Operator edit is stale: its saved dependency evidence failed verification.')
        if problems:
            issues[name] = problems
    if state.is_edited('titles.md'):
        source = state.artifacts.get('titles.json')
        if (source is None or state.artifacts['titles.md'].dependencies.get('titles_version') != source.id
                or 'titles.json' in issues):
            issues.setdefault('titles.md', []).append('Readable title edit is stale: its structured title data changed or is unavailable.')
    if state.is_edited('description.md') or state.is_edited('chapters.txt'):
        description = copies.get('description.md')
        chapters = copies.get('chapters.txt')
        if description is not None:
            embedded = [line.strip() for line in description.splitlines() if re.match(r'^\d+:\d{2}(?::\d{2})?\s', line)]
            try:
                validate_edited_chapters('\n'.join(embedded), duration)
            except ValueError as error:
                issues.setdefault('description.md', []).append(f'Embedded chapters: {error}')
            standalone = [line.strip() for line in chapters.splitlines() if line.strip()] if chapters is not None else []
            if not embedded or embedded != standalone:
                problem = 'Chapter conflict: description.md and chapters.txt must contain the same timestamp/title lines.'
                for name in ('description.md', 'chapters.txt'):
                    if name in state.artifacts:
                        issues.setdefault(name, []).append(problem)
    return issues
