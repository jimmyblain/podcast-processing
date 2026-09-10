"""Generate and assemble a coherent publishing package from saved episode evidence."""
import json
import re
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from .publishing import PreservedPublishingClient
from .publishing_models import DescriptionBody, PublishingChapter, TitleConcept, timestamp
from .publishing_prompts import VERSIONS, request_prompt
from .speech import clear_sentence_spans, supported_passages
from .transcript_content import publishing_transcript, transcript_inputs
from .workspace import PUBLISHING_FILES, Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import Artifact, PreservedTranscript, PublishingOperation, Run, WorkspaceState

STAGE_FILES = {'body': 'description-body.json', 'titles': 'titles.json', 'chapters': 'chapters.json'}


def supplied_appendix(state: WorkspaceState) -> str:
    assert state.show_profile and state.episode_metadata
    profile, episode = state.show_profile, state.episode_metadata
    parts = list(dict.fromkeys([*profile.links, *episode.links]))
    for person in episode.participants:
        if person.biography or person.links:
            parts.append('\n'.join([person.name, *([person.biography] if person.biography else []), *person.links]))
    parts.extend(episode.sponsors)
    if profile.promotional_text:
        parts.append(profile.promotional_text)
    return '\n\n'.join(parts)


def chapter_context(transcript: PreservedTranscript) -> dict:
    words = {w.id: w for w in transcript.words if w.id is not None}
    turns = []
    for index, segment in enumerate(transcript.segments):
        for passage_index, passage in enumerate(supported_passages(segment, words)):
            # Explicitly unknown or unverified v2 timing cannot become a boundary.
            # Legacy imported positive intervals are usable with import limitations.
            known = segment.timing_usable or (transcript.revision is None and transcript.provenance.original_schema == 'legacy-unversioned')
            if known and passage.start is not None and passage.end is not None and passage.start < passage.end:
                turns.append({'boundary_id': f'turn-{index}' + (f'-{passage_index}' if passage_index else ''),
                              'start_time': passage.start, 'end_time': passage.end, 'text': passage.text})
        members = [words[ref] for ref in segment.word_ids if ref in words]
        if ' '.join(word.word for word in members) == segment.text:
            offsets = {}
            cursor = 0
            for word in members:
                offsets[cursor] = word
                cursor += len(word.word) + 1
            clear = clear_sentence_spans(segment)
            for sentence in re.finditer(r'\S.*?(?:[.!?](?=\s|$)|$)', segment.text):
                boundary_word = offsets.get(sentence.start())
                if (sentence.start() > 0 and boundary_word and boundary_word.id and boundary_word.timing_usable
                        and any(start <= sentence.start() and sentence.end() <= end for start, end in clear)):
                    turns.append({'boundary_id': f'word-{boundary_word.id}', 'start_time': boundary_word.start,
                                  'end_time': boundary_word.end, 'text': sentence.group()})
    return {'duration': transcript.duration, 'turns': turns,
            'conversation': publishing_transcript(transcript).full_text}


def stage_inputs(state: WorkspaceState, transcript: PreservedTranscript, model: str, chapters: int) -> dict[str, tuple[dict, str]]:
    assert state.show_profile and state.episode_metadata
    profile, metadata = state.show_profile, state.episode_metadata
    # Links, biographies, sponsors and recurring promotion are assembled from exact
    # supplied bytes locally, so they never enter title/body/chapter requests.
    editorial = {'show': {'name': profile.name, 'host': profile.host, 'audience': profile.audience, 'voice': profile.voice},
                 'episode': {'solo': metadata.solo, 'participants': [{'name': p.name, 'role': p.role} for p in metadata.participants],
                             'angle': metadata.angle, 'current_context': metadata.current_context},
                 'conversation': publishing_transcript(transcript).full_text}
    consumed = transcript_inputs(transcript)
    result = {}
    for stage in STAGE_FILES:
        context = {**chapter_context(transcript), 'chapter_limit': chapters} if stage == 'chapters' else editorial
        prompt = request_prompt(stage, context)
        dependencies = {'transcript_text': consumed['transcript_text'], 'transcript_attribution': consumed['transcript_attribution'],
                        'request': digest(prompt.encode()), 'model': model, 'template': VERSIONS[stage]}
        if stage == 'chapters':
            dependencies['transcript_timing'] = consumed['transcript_timing']
            dependencies['source_revision'] = state.source_revision
            dependencies['chapter_count'] = str(chapters)
        result[stage] = dependencies, prompt
    return result


def validate_chapters(raw: str, transcript: PreservedTranscript, limit: int) -> list[dict]:
    chapters = TypeAdapter(list[PublishingChapter]).validate_json(raw)
    if not 3 <= len(chapters) <= limit:
        raise ValueError('Chapters require 3–10 supported natural boundaries within the requested limit.')
    labels = [re.sub(r'[^\w]', '', c.title.casefold()) for c in chapters]
    if len(set(labels)) != len(labels):
        raise ValueError('Chapter labels must be distinct, including case/punctuation variants.')
    if chapters[0].start_time != 0 or chapters[0].boundary_id != 'anchor':
        raise ValueError('Chapters must begin exactly at 00:00 with the format anchor.')
    if transcript.duration is None:
        raise ValueError('Chapters unavailable: source duration is unknown.')
    candidates = {t['boundary_id']: t['start_time'] for t in chapter_context(transcript)['turns']}
    mismatches = []
    for index, chapter in enumerate(chapters[1:], start=2):
        if chapter.boundary_id not in candidates:
            mismatches.append(f'Entry {index}: unknown boundary_id; select an ID from the supplied turns.')
        elif chapter.start_time != candidates[chapter.boundary_id]:
            mismatches.append(f'Entry {index}: boundary_id {chapter.boundary_id} requires '
                              f'start_time {candidates[chapter.boundary_id]}, received {chapter.start_time}.')
    if mismatches:
        raise ValueError('Chapter time must match its supported natural boundary evidence. ' + ' '.join(mismatches))
    for chapter, end in zip(chapters, [c.start_time for c in chapters[1:]] + [transcript.duration]):
        if end - chapter.start_time < 10 or end - int(chapter.start_time) < 10:
            raise ValueError('Every chapter including the last must last at least ten seconds.')
    rendered = [int(c.start_time) for c in chapters]
    if any(b - a < 10 for a, b in zip(rendered, rendered[1:])):
        raise ValueError('Rendered chapter times must be distinct, ascending and at least ten seconds apart.')
    return [c.model_dump() for c in chapters]


def validate_copy(stage: str, raw: str, state: WorkspaceState, transcript: PreservedTranscript, limit: int) -> Any:
    if stage == 'chapters':
        return validate_chapters(raw, transcript, limit)
    if stage == 'titles':
        titles = TypeAdapter(list[TitleConcept]).validate_json(raw)
        if len(titles) != 15:
            raise ValueError('Exactly fifteen title concepts are required.')
        normalized = [re.sub(r'[^\w]', '', t.title.casefold()) for t in titles]
        if len(set(normalized)) != 15:
            raise ValueError('Title concepts must be distinct, including case/punctuation variants.')
        return [t.model_dump() for t in titles]
    body = DescriptionBody.model_validate_json(raw)
    rendered = body.render()
    assert state.episode_metadata
    if any(p.name not in body.overview for p in state.episode_metadata.participants):
        raise ValueError('Overview must name Lish Speaks and each confirmed guest with official spelling.')
    if body.question.count('?') != 1:
        raise ValueError('Supply one episode-specific comment question.')
    if re.search(r'https?://|www\.|#\w|\b\d+:\d{2}\b', rendered):
        raise ValueError('Body cannot include links, hashtags or chapter timestamps; assembly supplies extras.')
    if len(rendered) > 5000:
        raise ValueError('Description body exceeds the 5,000-character complete-description limit.')
    return body.model_dump()


def dependencies_match(artifact: Artifact | None, expected: dict[str, str]) -> bool:
    return artifact is not None and all(artifact.dependencies.get(key) == value for key, value in expected.items())


def supersede_stage(state: WorkspaceState, stage: str) -> None:
    target = state.artifacts if stage == 'titles' else state.evidence
    target.pop(STAGE_FILES[stage], None)
    if stage == 'chapters':
        state.artifacts.pop('chapters.txt', None)
    if stage in ('body', 'chapters'):
        state.artifacts.pop('description.md', None)


def supersede_assembly(state: WorkspaceState) -> None:
    description = state.artifacts.get('description.md')
    if description and (description.dependencies.get('appendix') != digest(supplied_appendix(state).encode())
                        or 'chapters.txt' not in state.artifacts):
        state.artifacts.pop('description.md', None)


def prune_inputs(state: WorkspaceState, transcript: PreservedTranscript) -> None:
    """Remove obsolete consumers before exposing changed authority inputs."""
    for stage, file in STAGE_FILES.items():
        target = state.artifacts if stage == 'titles' else state.evidence
        artifact = target.get(file)
        if artifact:
            # Keep saved request configuration until generation explicitly changes it.
            model = artifact.dependencies.get('model', '')
            count = int(artifact.dependencies.get('chapter_count', '10'))
            expected = stage_inputs(state, transcript, model, count)[stage][0]
            if not dependencies_match(artifact, expected):
                supersede_stage(state, stage)
    supersede_assembly(state)


def generate_package(path: Path, api_key: str, model: str, chapters: int = 10,
                     only: str | None = None, fresh: bool = False,
                     chapter_labels: Path | None = None) -> WorkspaceState:
    if only not in (None, 'titles', 'description', 'chapters') or not 3 <= chapters <= 10:
        raise WorkspaceError('Select titles, description or chapters; chapter limit must be 3–10.')
    if chapter_labels and (fresh or only not in (None, 'chapters')):
        raise WorkspaceError('Chapter labels are a local change; use without --fresh or with --only chapters.')
    workspace = Workspace(path)
    with ownership(workspace.path, 'generate publishing package'):
        state = workspace.read()
        workspace.reconcile(state)
        preserved_edits = [item for item in state.runs[-1].limitations if item.startswith('Preserved direct edit')]
        if state.show_profile is None or state.episode_metadata is None:
            raise WorkspaceError('Generation requires an approved show profile and confirmed guest names or explicit solo metadata.')
        artifact = state.artifacts.get('transcript.json')
        if artifact is None:
            raise WorkspaceError('No current usable timed transcript. Explicitly import matching evidence.')
        transcript = PreservedTranscript.model_validate_json(workspace.artifact_bytes(artifact))
        if not publishing_transcript(transcript).full_text.strip():
            raise WorkspaceError('No usable preserved text for publishing.')
        selected = {'titles'} if only == 'titles' else {'chapters'} if only == 'chapters' else {'body', 'chapters'} if only == 'description' else set(STAGE_FILES)
        if chapter_labels:
            if 'chapters.json' not in state.evidence:
                raise WorkspaceError('Chapter labels require saved valid chapter data; generate chapters first.')
            selected = set()
        fresh_stages = selected if only is None else { {'description': 'body'}.get(only, only) }
        inputs = stage_inputs(state, transcript, model, chapters)
        for stage in set(STAGE_FILES) - selected:
            prior = next((op for op in reversed(state.publishing_operations) if op.stage == stage), None)
            if prior:
                inputs[stage] = stage_inputs(state, transcript, prior.dependencies['model'],
                                            int(prior.dependencies.get('chapter_count', '10')))[stage]
        run = Run(id=identifier(), operation_id=identifier(), operation='generate', status='running', started_at=now(),
                  inputs={'show_profile': state.show_profile.model_dump(), 'episode_metadata': state.episode_metadata.model_dump(),
                          'transcript_artifact': artifact.model_dump(), 'source_revision': state.source_revision,
                          'corrections': [c.model_dump() for c in transcript.lineage], 'model': model, 'chapter_count': chapters,
                          'selected': sorted(selected), 'fresh': fresh, 'stage_version': 'publishing-package-v2'},
                  limitations=preserved_edits)
        state.runs.append(run)
        # Supersede only actual changed consumers. Independent current outputs survive.
        for stage, (dependencies, _) in inputs.items():
            file = STAGE_FILES[stage]
            target = state.artifacts if stage == 'titles' else state.evidence
            saved = target.get(file)
            if saved:
                try:
                    workspace.artifact_bytes(saved)
                except WorkspaceError:
                    saved = None
            if not dependencies_match(saved, dependencies) or (fresh and stage in fresh_stages):
                supersede_stage(state, stage)
        supersede_assembly(state)
        workspace.commit(state)
        client = PreservedPublishingClient(workspace, state, api_key, model)
        for stage in ('body', 'titles', 'chapters'):
            if stage not in selected:
                continue
            file = STAGE_FILES[stage]
            target = state.artifacts if stage == 'titles' else state.evidence
            if file in target:
                run.limitations.append(f'Reused {stage}: {target[file].id}.')
                continue
            if stage == 'chapters' and (transcript.duration is None or transcript.duration < 30
                                       or len(chapter_context(transcript)['turns']) < 2):
                run.limitations.append('Chapters unavailable: preserved timing cannot support three natural chapters; body preserved separately.')
                continue
            dependencies, prompt = inputs[stage]
            operation = next((op for op in reversed(state.publishing_operations)
                              if op.stage == stage and op.dependencies == dependencies), None)
            if operation is None or (fresh and stage in fresh_stages):
                operation = PublishingOperation(id=identifier(), stage=stage, dependencies=dependencies, created_at=now())
                state.publishing_operations.append(operation)
            try:
                data = client.generate(operation, prompt, lambda raw: validate_copy(stage, raw, state, transcript, chapters))
                workspace.add_artifact(state, file, json_bytes(data), dependencies, VERSIONS[stage], exposed=stage == 'titles')
                run.limitations.append(f'Completed {stage}: {target[file].id}.')
                if stage == 'body':
                    run.limitations.extend(data.get('notes', []))
                workspace.commit(state)
            except (WorkspaceError, OSError) as error:
                run.limitations.append(f'{stage} unavailable ({type(error).__name__}): {error}')
                # A failed artifact write must not discard independently successful stages.
                continue
        assembly_failed = False
        try:
            chapter_artifact = state.evidence.get('chapters.json')
            if chapter_artifact:
                data = json.loads(workspace.artifact_bytes(chapter_artifact))
                if chapter_labels:
                    label_bytes = chapter_labels.read_bytes()
                    labels = json.loads(label_bytes)
                    run.inputs['chapter_labels'] = {'path': str(chapter_labels.resolve()),
                                                    'sha256': digest(label_bytes), 'labels': labels}
                    if not isinstance(labels, list) or len(labels) != len(data) or any(not isinstance(label, str) for label in labels):
                        raise ValueError('Chapter labels must be a JSON array with one title per saved chapter.')
                    for chapter, label in zip(data, labels):
                        chapter['title'] = label
                    data = validate_chapters(json.dumps(data), transcript, chapters)
                    if json_bytes(data) != workspace.artifact_bytes(chapter_artifact):
                        chapter_artifact = workspace.add_artifact(state, 'chapters.json', json_bytes(data),
                            {**chapter_artifact.dependencies, 'labels': digest(label_bytes),
                             'base_chapters': chapter_artifact.id}, 'chapter-labels-v2', exposed=False)
                        state.artifacts.pop('chapters.txt', None)
                        state.artifacts.pop('description.md', None)
                chapter_bytes = ('\n'.join(f'{timestamp(c["start_time"])} {c["title"]}' for c in data) + '\n').encode()
                rendered = state.artifacts.get('chapters.txt')
                if rendered is None or rendered.dependencies.get('chapter_data') != chapter_artifact.sha256:
                    state.artifacts.pop('description.md', None)
                    workspace.add_artifact(state, 'chapters.txt', chapter_bytes,
                        {**chapter_artifact.dependencies, 'chapter_data': chapter_artifact.sha256}, 'chapter-render-v2')
                # Chapters and final description always refer to a committed common version.
                workspace.commit(state)
            body_artifact = state.evidence.get('description-body.json')
            rendered = state.artifacts.get('chapters.txt')
            if body_artifact and rendered:
                appendix = supplied_appendix(state)
                dependencies = {'body': body_artifact.sha256, 'chapters': rendered.sha256,
                                'chapters_version': rendered.id, 'appendix': digest(appendix.encode()), 'template': 'assembly-v2'}
                description = state.artifacts.get('description.md')
                if description is None or description.dependencies != dependencies:
                    state.artifacts.pop('description.md', None)
                    workspace.commit(state)
                    body = DescriptionBody.model_validate_json(workspace.artifact_bytes(body_artifact))
                    complete = body.render() + '\n\nChapters\n' + workspace.artifact_bytes(rendered).decode().rstrip()
                    if appendix:
                        complete += '\n\n' + appendix
                    complete += '\n'
                    if len(complete) > 5000:
                        raise ValueError('Assembled description exceeds 5,000 characters including chapters, links and promotion; body preserved.')
                    workspace.add_artifact(state, 'description.md', complete.encode(), dependencies, 'assembly-v2')
                    workspace.commit(state)
        except (ValueError, WorkspaceError, OSError) as error:
            assembly_failed = True
            run.limitations.append(f'Local publishing assembly unavailable: {error}')
        body_checkpoint = state.evidence.get('description-body.json')
        if body_checkpoint:
            try:
                notes = DescriptionBody.model_validate_json(workspace.artifact_bytes(body_checkpoint)).notes
                run.limitations.extend(note for note in notes if note not in run.limitations)
            except (ValueError, WorkspaceError):
                pass  # An unavailable checkpoint was already reported by its stage.
        run.missing = [file for file in PUBLISHING_FILES if file not in state.artifacts]
        run.status = ('partial' if any(file in state.artifacts for file in PUBLISHING_FILES) or 'description-body.json' in state.evidence
                      else 'failed') if run.missing else 'completed'
        if assembly_failed and run.status == 'completed':
            run.status = 'partial'
        run.finished_at = now()
        workspace.commit(state)
        return state
