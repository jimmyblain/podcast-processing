# Import episodes into a versioned workspace

Import preserves existing text without transcription or paid calls. It creates a v2
workspace for resumable publishing and full processing. Generation from an
unversioned `transcript.json` retains the legacy format; import first to use v2.

## Demo

Install the project and development checks with `uv pip install -e '.[dev]'`. FFmpeg/`ffprobe` is needed only when attaching or inspecting media. This synthetic fixture contains no private recording:

```sh
podcast-process import tests/fixtures/legacy-transcript.json --root output/episodes
```

The command prints the episode directory. Use that path in the following commands:

```sh
podcast-process inspect output/episodes/fixtures-EPISODE_ID
podcast-process inspect output/episodes/fixtures-EPISODE_ID --json
cat output/episodes/fixtures-EPISODE_ID/current/transcript.txt
cat output/episodes/fixtures-EPISODE_ID/current/completion-report.md
```

Import can proceed without a source or authoritative publishing inputs. Missing source fingerprints, speaker identities, original model/settings, and timing confidence remain unknown. Legacy timestamps are preserved evidence, not verified speech alignment. Unknown timestamps render as `[unknown time]`; no participant is inferred from segment order. Missing or unusable timing prevents chapter generation while allowing description and title generation.

## Supply authoritative publishing inputs

Create your approved `show.json` (links and promotional text are optional):

```json
{
  "schema_version": 2,
  "approved": true,
  "name": "I'll Just Let Myself In",
  "host": "Lish Speaks",
  "audience": "People ready to take a chance on themselves—in creative work, careers, relationships, and personal growth—who welcome honest conversation, practical encouragement, and a Christian perspective.",
  "voice": "Warm and familiar, candid and challenging, practical, faith-grounded, playful and human."
}
```

Create `episode.json` with explicit solo status:

```json
{
  "schema_version": 2,
  "solo": true,
  "participants": [{"name": "Lish Speaks", "role": "host"}]
}
```

For an interview, set `solo` to `false` and add confirmed participants with `role: "guest"`. The collection supports multiple guests. Each participant may have `biography` and `links`. Episode `angle`, `links`, `sponsors` (strings), and `current_context` are optional. Approval is supplied by the operator; import does not infer it from the recording.

```sh
podcast-process import tests/fixtures/legacy-transcript.json \
  --root output/episodes --show-profile show.json --metadata episode.json
podcast-process generate output/episodes/fixtures-EPISODE_ID
```

Generation uses `ANTHROPIC_API_KEY` and the configured Claude model. It requires the approved profile and confirmed participants but can use preserved text with missing media. It does not transcribe. A missing required result yields a nonzero exit and an honest partial report. Successful description, titles, chapters, and raw publishing responses are checkpointed independently. An unchanged completed rerun retains artifact IDs and makes no service calls, even without an API key. A metadata-only reimport supersedes publishing outputs while preserving the timed transcript.

Versioned generation produces fifteen title concepts, actionable visual directions,
shared embedded/standalone chapters and a validated publishing package. Use `process
WORKSPACE` to add the independent planning outcome. Imported text never implicitly
submits transcription. Deterministic completion is separate from real source,
editorial, runtime and billing acceptance in issue #19.

## Source identity and copies

```sh
podcast-process import legacy/transcript.json --root output/episodes --source /recordings/episode.wav
podcast-process attach-source output/episodes/episode-EPISODE_ID /new/location/episode.wav
podcast-process check-source output/episodes/episode-EPISODE_ID
podcast-process attach-source output/episodes/episode-EPISODE_ID /new/location/episode.wav --copy-source
```

Media is referenced by default. Inspection records SHA-256 and audio stream properties. `--copy-source` explicitly makes a verified local copy, which can satisfy media access when the original locator disappears. Identical bytes retain source revision identity; changed bytes create a new source revision within the selected episode and supersede its current transcript and publishing outputs. Import matching evidence explicitly after changing source bytes:

```sh
podcast-process import new/transcript.json --root output/episodes \
  --workspace output/episodes/episode-EPISODE_ID --source /recordings/revised.wav
```

Within a collection, source fingerprints find an existing episode even after a move. Different recordings sharing a basename get different directories. Without known media, the exact imported-file hash identifies repeated imports. To associate a changed legacy file with an existing episode, select `--workspace`; names and paths cannot prove identity. Reattaching a source whose fingerprint was previously unknown changes the evidence revision and requires explicit reimport. No paid transcription repairs a locator.

Supported adapters are the original unversioned transcript shape and this slice's strict schema 2 transcript. Future versions and unknown fields fail explicitly, including through the old generation command. For schema 2 input, explicitly import it and generate using the workspace directory. Original import bytes and their hash are retained; existing provenance is not replaced by invented migration facts.

## Persistence and recovery

- `current/` is one atomic pointer to a fully validated snapshot containing `state.json`, `completion-report.md`, and usable output files. Read a single resolved snapshot when consuming several files programmatically. Separate path lookups across a concurrent commit may naturally observe different snapshots.
- `artifacts/` retains original artifact bytes; `state.json` lists artifact IDs, hashes, dependencies, stage/schema versions, input snapshots, run/operation IDs, statuses and timestamps. Publishing request/response evidence is stored separately from the current copy-paste outputs. Keys and authorization headers are excluded.
- `snapshots/` retains complete and partial committed views. Do not edit history or state. Direct edits to current output files are preserved as distinct historical artifacts before replacement; they do not silently become transcript corrections or authoritative metadata.
- On the next operation, current and original hashes are checked. Damaged outputs are removed from the usable set; an invalid timed transcript also supersedes its dependent publishing outputs. An explicit reimport repairs preserved transcript outputs.
- One process owns a workspace. A contender reports the active operation. OS ownership is released after a crash; the next operation marks its run interrupted and resumes from committed evidence. Temporary, uncommitted files never become current. Unreferenced interrupted snapshots/artifacts are retained; automatic garbage collection is not implemented.

This local store uses POSIX advisory locks, directory flushing, and atomic symlink replacement (macOS/Linux local filesystems). Network filesystem and Windows semantics are not supported by this slice. Imported raw data is retained exactly, so only import transcript files appropriate for local preservation. Do not supply credentials as episode content. All persistence stays local.

Publishing requests whose responses were saved can be replayed locally after an output-write failure. The later publishing/provider-ledger slices must handle uncertain remote acceptance and enforce persisted retry/spending bounds; this slice does not claim those recovery or cost guarantees.

## Verification

```sh
pytest tests/test_workspace.py
pytest tests/test_workspace_recovery.py
mypy src/podcast_processor
pytest tests/
```

The suite uses synthetic audio in temporary directories, controlled publishing responses, real subprocess crashes and ownership contention, and filesystem-visible committed outcomes. It verifies import preservation, source identity/copies, limited-evidence generation, strict adapters, changed metadata, checkpoint reuse, secret exclusion, and interruption/hash recovery. It does not establish real audio accuracy, editorial acceptance, production performance, or actual billed cost.
