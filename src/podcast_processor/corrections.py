"""Exact-base, local corrections. Immutable evidence is never rewritten."""
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import Field

from .participants import MAPPING_VERSION, current_transcript, map_supported
from .transcript_content import supersede_consumers
from .workspace import Workspace, WorkspaceError, digest, identifier, json_bytes, now, ownership
from .workspace_models import DetectedSpeaker, PreservedTranscript, PreservedWord, Record, Run, TranscriptChange, WorkspaceState, unclear_wording

CORRECTIONS_VERSION = 'transcript-corrections-v1'


class Relabel(Record):
    op: Literal['relabel']
    speaker: str
    participant: str | None


class Merge(Record):
    op: Literal['merge']
    speaker: str
    into: str


class Separate(Record):
    op: Literal['separate']
    turn_ids: list[str] = Field(min_length=1)


class Replace(Record):
    op: Literal['replace']
    turn_id: str
    first_word: str
    last_word: str
    text: str = Field(min_length=1, pattern=r'\S')


class Split(Record):
    op: Literal['split']
    turn_id: str
    before_word: str


class Retime(Record):
    op: Literal['retime']
    word_id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    evidence: str = Field(min_length=1, pattern=r'\S')


class Corrections(Record):
    schema_version: Literal[1] = 1
    source_revision: str
    transcript_revision: str | None
    transcript_sha256: str
    changes: list[Annotated[Relabel | Merge | Separate | Replace | Split | Retime, Field(discriminator='op')]]


def corrections_template(path: Path) -> bytes:
    workspace = Workspace(path)
    with ownership(workspace.path, 'prepare optional corrections'):
        state = workspace.read()
        workspace.reconcile(state)
        transcript = current_transcript(workspace, state)
        return json_bytes(Corrections(source_revision=state.source_revision, transcript_revision=transcript.revision,
            transcript_sha256=state.artifacts['transcript.json'].sha256, changes=[]).model_dump())


def correct_episode(path: Path, corrections_path: Path) -> WorkspaceState:
    raw = corrections_path.read_bytes()
    corrections = Corrections.model_validate_json(raw)
    workspace = Workspace(path)
    with ownership(workspace.path, 'correct timed transcript'):
        state = workspace.read()
        workspace.reconcile(state)
        original = current_transcript(workspace, state)
        base = state.artifacts['transcript.json']
        if (corrections.source_revision != state.source_revision or corrections.transcript_revision != original.revision
                or corrections.transcript_sha256 != base.sha256):
            raise WorkspaceError('Incompatible correction base: source revision, timed-transcript revision and hash must match current output. Create a new corrections template.')
        if not corrections.changes:
            return state
        result = original.model_copy(deep=True)
        revision = digest(json_bytes([base.sha256, digest(raw), CORRECTIONS_VERSION, MAPPING_VERSION]))
        speakers = {s.id: s for s in result.speakers}
        participants = {p.name for p in state.episode_metadata.participants} if state.episode_metadata else set()
        for index, change in enumerate(corrections.changes):
            if isinstance(change, Retime):
                word = next((w for w in result.words if w.id == change.word_id), None)
                if word is None:
                    raise WorkspaceError(f'Unknown word reference: {change.word_id}')
                if result.duration is None or not 0 <= change.start < change.end <= result.duration:
                    raise WorkspaceError('Timing corrections require positive intervals within the known source duration.')
                turn = next((t for t in result.segments if t.id == word.turn_id), None)
                if turn is None:
                    raise WorkspaceError('Word lacks a containing turn reference; cannot establish source timing.')
                word.start, word.end, word.timing_usable, word.timing_uncertainty = change.start, change.end, True, []
                members = [w for w in result.words if w.turn_id == turn.id]
                turn.timing_usable = all(w.timing_usable for w in members)
                starts = [w.start for w in members if w.start is not None]
                ends = [w.end for w in members if w.end is not None]
                if not turn.timing_usable:
                    starts += [turn.start] if turn.start is not None else []
                    ends += [turn.end] if turn.end is not None else []
                turn.start, turn.end = min(starts), max(ends)
                if turn.timing_usable:
                    turn.uncertainty = []
                continue
            if isinstance(change, Split):
                turn = next((t for t in result.segments if t.id == change.turn_id), None)
                if turn is None or change.before_word not in turn.word_ids:
                    raise WorkspaceError('Split requires an existing word in the selected turn.')
                offset = turn.word_ids.index(change.before_word)
                lookup = {w.id: w for w in result.words}
                words = [lookup[ref] for ref in turn.word_ids]
                if offset == 0 or any(not w.timing_usable or w.start is None or w.end is None for w in words):
                    raise WorkspaceError('Split requires two nonempty passages with supported word timing.')
                cut = words[offset].start
                assert cut is not None
                if any(w.end is None or w.end > cut for w in words[:offset]) or any(w.start is None or w.start < cut for w in words[offset:]):
                    raise WorkspaceError('Split position crosses overlapping or out-of-order word evidence.')
                right = turn.model_copy(deep=True)
                right.id = f'{revision}:t{index}'
                for part, part_words in [(turn, words[:offset]), (right, words[offset:])]:
                    part.word_ids = [w.id or '' for w in part_words]
                    part.text = ' '.join(w.word for w in part_words)
                    part.start = min(w.start for w in part_words if w.start is not None)
                    part.end = max(w.end for w in part_words if w.end is not None)
                    part.timing_usable = True
                    for word in part_words:
                        word.turn_id = part.id
                result.segments.insert(result.segments.index(turn) + 1, right)
                continue
            if isinstance(change, Replace):
                turn = next((t for t in result.segments if t.id == change.turn_id), None)
                if turn is None or change.first_word not in turn.word_ids or change.last_word not in turn.word_ids:
                    raise WorkspaceError('Passage correction requires existing word references within the selected turn.')
                first, last = turn.word_ids.index(change.first_word), turn.word_ids.index(change.last_word)
                if first > last:
                    raise WorkspaceError('Passage word references are reversed.')
                old_ids = turn.word_ids[first:last + 1]
                replacements = [PreservedWord(id=f'{revision}:c{index}:w{i}', word=token, turn_id=turn.id,
                    speaker=turn.speaker, timing_uncertainty=['Wording corrected; alignment unverified until checked.'])
                    for i, token in enumerate(re.findall(r'\[[^]]*\]|<[^>]*>|\S+', change.text))]
                offset = next(i for i, w in enumerate(result.words) if w.id == change.first_word)
                result.words = [w for w in result.words if w.id not in old_ids]
                result.words[offset:offset] = replacements
                turn.word_ids[first:last + 1] = [w.id or '' for w in replacements]
                lookup = {w.id: w for w in result.words}
                turn.text = ' '.join(lookup[ref].word for ref in turn.word_ids)
                turn.quotation_usable = not unclear_wording(turn.text)
                turn.timing_usable = False
                turn.uncertainty = ['Wording corrected; affected word alignment unverified until checked.']
                continue
            if isinstance(change, Separate):
                turns = {t.id: t for t in result.segments}
                if len(set(change.turn_ids)) != len(change.turn_ids) or any(ref not in turns for ref in change.turn_ids):
                    raise WorkspaceError('Separate requires distinct existing turn references.')
                separated = DetectedSpeaker(id=f'{revision}:s{index}', label=f'Separated speaker {len(speakers) + 1}', identity_status='corrected',
                                             identity_evidence=[f'operator separation {revision}'])
                result.speakers.append(separated)
                speakers[separated.id] = separated
                for ref in change.turn_ids:
                    turns[ref].speaker = separated.id
                for word in result.words:
                    if word.turn_id in change.turn_ids:
                        word.speaker = separated.id
                continue
            if change.speaker not in speakers:
                raise WorkspaceError(f'Unknown speaker reference: {change.speaker}')
            if isinstance(change, Merge):
                if change.into not in speakers or change.into == change.speaker:
                    raise WorkspaceError('Merge requires two distinct existing speaker references.')
                source, target = speakers[change.speaker], speakers[change.into]
                if source.participant and target.participant and source.participant != target.participant:
                    raise WorkspaceError('Conflicting participant mappings; explicitly relabel before merging.')
                if source.participant and target.participant is None:
                    target.participant = source.participant
                target.identity_status = 'corrected'
                target.identity_evidence += source.identity_evidence + [f'operator merge {revision}']
                for turn in result.segments:
                    if turn.speaker == source.id:
                        turn.speaker = target.id
                for word in result.words:
                    if word.speaker == source.id:
                        word.speaker = target.id
                result.speakers.remove(source)
                del speakers[source.id]
                continue
            if change.participant is not None and change.participant not in participants:
                raise WorkspaceError(f'Participant is not in confirmed metadata: {change.participant}')
            speaker = speakers[change.speaker]
            speaker.participant = change.participant
            speaker.identity_status = 'corrected'
            speaker.identity_evidence = [f'operator correction {revision}']
        result.refresh_overlaps()
        result = PreservedTranscript.model_validate(result.model_dump())
        result.revision = revision
        if state.episode_metadata is not None:
            remapped = map_supported(result, state.episode_metadata, state.source_revision)
            result.speakers, result.mapping_inputs = remapped.speakers, remapped.mapping_inputs
        result.lineage.append(TranscriptChange(base_revision=original.revision, base_sha256=base.sha256,
            source_revision=state.source_revision, revision=revision, component=CORRECTIONS_VERSION,
            input_hash=digest(raw), changes=[c.model_dump() for c in corrections.changes] + [
                {'mapping_component': MAPPING_VERSION, 'mapping_inputs': result.mapping_inputs,
                 'speakers': [s.model_dump() for s in result.speakers]}]))
        superseded = supersede_consumers(state, original, result)
        state.runs.append(Run(id=identifier(), operation_id=identifier(), operation='correct', status='completed',
            started_at=now(), finished_at=now(), inputs={'base_revision': original.revision, 'base_sha256': base.sha256,
                'source_revision': state.source_revision, 'corrections_hash': digest(raw), 'component': CORRECTIONS_VERSION},
            limitations=[f'Superseded: {", ".join(superseded) or "none"}. Publishing artifacts were not regenerated.']))
        workspace.add_artifact(state, f'corrections-{revision}.json', raw,
            {'base': base.sha256, 'source_revision': state.source_revision}, CORRECTIONS_VERSION, exposed=False)
        dependencies = {**base.dependencies, 'correction': digest(raw), 'base': base.sha256}
        for name, data in [('transcript.json', json_bytes(result.model_dump())), ('transcript.txt', result.readable().encode())]:
            workspace.add_artifact(state, name, data, dependencies, CORRECTIONS_VERSION)
        workspace.commit(state)
        return state
