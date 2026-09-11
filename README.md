# Podcast Processor

A resumable CLI for a speaker-aware timed transcript, a YouTube publishing package,
and a three-section proposal when the available evidence supports one. It prepares
copy and planning data; it does not upload to YouTube, generate thumbnail images,
or cut, stitch, or export media.

## Install and configure

Python 3.10+, FFmpeg and ffprobe are required. On macOS, install FFmpeg with
`brew install ffmpeg`, then:

```sh
uv venv
uv pip install -e '.[dev]'
source .venv/bin/activate
cp .env.example .env
```

Alternatively use `python -m venv .venv` and `pip install -e '.[dev]'`.
Set `ASSEMBLYAI_API_KEY` (primary), `DEEPGRAM_API_KEY` (automatic bounded backup),
and `ANTHROPIC_API_KEY` (publishing) in `.env` or the environment. `CLAUDE_MODEL`
selects the publishing model; the configured requested alias and returned model
are recorded. Saved completed work is reusable without credentials or the media.
Install `.[local]` only for the explicit legacy Whisper commands.

## Run once, then resume

```sh
# Required inputs: recording and confirmed solo/guest status.
podcast-process process episode.wav --solo --workspace output/episodes/my-episode
podcast-process process interview.wav --guest 'Erica Campbell' --workspace output/episodes/interview

# Rerun the same command, or pass its printed workspace location.
podcast-process process output/episodes/my-episode
podcast-process inspect output/episodes/my-episode
podcast-process inspect output/episodes/my-episode --json
```

Without `--workspace`, the command prints a content-addressed location under
`output/episodes/episode-<identity>`. Different recordings with the same basename
remain separate. `--output`/`-o` is an alternative explicit workspace for `process`.
For changed recording bytes within an existing episode, pass the new recording
with the same `--workspace`; dependent current outputs are superseded coherently.

The approved reusable show identity, audience and voice are included. Selected links
and recurring promotional copy remain optional configuration, with no guessed
links. To supply them or change editorial inputs, use `--show-profile show.json`.
Use `--metadata episode.json` instead of `--solo`/`--guest` for optional angle,
participant biographies, links, sponsors or current context. See the
[authority JSON examples](docs/workspace-import.md#supply-authoritative-publishing-inputs).
Repeat `--guest` for multiple confirmed guests. A roster never assigns a detected
voice to a person by itself. Confirmed metadata and profile snapshots are saved;
normal uncertainty produces conservative output and a report, without a review prompt.

## Current outputs and partial completion

Open files under the workspace's `current/` directory:

| File | Meaning |
| --- | --- |
| `transcript.json` | Timed speaker turns/words, uncertainty, participant evidence and correction lineage |
| `transcript.txt` | Faithful readable timed transcript with supported names or anonymous labels |
| `description.md` | Complete description, embedded chapters and approved supplied extras; ≤5,000 characters |
| `titles.json` | Exactly 15 title concepts with 2–4-word overlays, visual directions and rationale |
| `chapters.txt` | 3–10 timestamp/title lines, identical to the embedded chapter list |
| `section-plan.json` | Valid or explained unavailable planning outcome |
| `section-boundaries.json` | Three contiguous source parts with transition-inclusive duration calculations, when feasible |
| `completion-report.md` | Full-operation status, reuse/supersession, failures/fallbacks, edits and separate usage ledgers |

Exit **0** means required timed-transcript/publishing outputs and a planning outcome
completed. An explained impossible/unavailable section proposal does not block publishing.
Exit **1** means required outputs are partial/missing or an input, service or local
stage failed. Successful independent work remains usable. If chapters fail, the
saved description body remains a checkpoint in `state.json`'s `evidence` and the
immutable artifact store; it is not exposed as a complete `description.md`.

Section planning consumes optional `--evidence planning.json`, or the last saved
planning evidence. See [planning evidence and arithmetic](docs/section-planning.md).
With missing transitions, unsupported natural cuts or incompatible evidence, the
operation records an unavailable result immediately. There is no default semantic
candidate generator or transition-duration guess. Evidence referencing an older
corrected transcript must be replaced with matching evidence. A synthetic feasible
proposal proves arithmetic, not real audio quality or safe natural cuts.

## Separate operations and selected regeneration

```sh
# Managed transcription only; no publishing requests.
podcast-process transcribe episode.wav --solo --workspace output/episodes/my-episode

# Publishing from preserved data; never transcribes.
podcast-process generate output/episodes/my-episode

# New title allowance only; preserve other usable artifacts.
podcast-process process output/episodes/my-episode --only titles --fresh
podcast-process generate output/episodes/my-episode --only chapters --fresh

# Change chapter labels locally, with one label per saved chapter.
podcast-process process output/episodes/my-episode --chapter-labels labels.json

# New full operation and possible spending, preserving previous versions/ledgers.
podcast-process process output/episodes/my-episode --fresh
```

`--only` selects `titles`, `description`, or `chapters`. `description --fresh`
regenerates its body and reuses valid shared chapters. A normal rerun resumes or
reuses committed work and does not reset attempts, reservations or deadlines.
`--fresh` without `--only` starts new transcription and publishing allowances; it
never cancels an earlier remote job. Selected fresh regeneration replaces only the
selected allowance. Direct edits to current publishing files are preserved as exact
historical bytes before regeneration, without becoming episode facts or corrections.

Inputs invalidate only actual consumers: links/promotional copy reassemble locally;
audience/voice/angle change editorial requests; timing changes chapters/plans while
preserving unchanged text outputs; transitions change only planning; configured ASR
hints/model/settings join transcription fingerprints. Calendar time alone does not
refresh snapshots. History and raw evidence remain in the workspace.

## Import, corrections and source reattachment

```sh
# Explicit non-destructive import; no transcription or publishing calls.
podcast-process import legacy/transcript.json --root output/episodes \
  --show-profile show.json --metadata episode.json
# Use the workspace printed by import for process/generate.
podcast-process process output/episodes/PRINTED_WORKSPACE

# Optional exact-base corrections, followed by normal resume.
podcast-process corrections-template output/episodes/my-episode --output corrections.json
# Edit corrections.json using supported changes.
podcast-process correct output/episodes/my-episode corrections.json
podcast-process process output/episodes/my-episode

# Reattach moved identical bytes; optionally make a verified local copy.
podcast-process attach-source output/episodes/my-episode /new/location/episode.wav --copy-source
podcast-process check-source output/episodes/my-episode
```

Imports preserve the original folder and unknown provenance. Full processing of an
imported workspace uses its preserved text without implicit transcription; missing
timing honestly limits precise outputs. Unsupported future schemas fail explicitly.
Incompatible timed-transcript corrections fail rather than applying to another
revision. See [imports](docs/workspace-import.md) and [corrections](docs/participant-corrections.md).
Missing media does not prevent work from saved text/raw responses. A verified copy
or identical reattachment restores media-dependent work without changing identity.

## Recovery and usage

One process owns a workspace across the full run. A concurrent command reports the
active owner. Process death releases ownership; immutable artifacts and atomically
switched snapshots prevent partial writes from becoming reusable current output.
Restart recovers accepted job IDs and saved successful responses before buying work.

Managed transcription permits at most one primary plus one backup accepted or
possibly accepted job per operation, within the persisted default 900-second deadline
and $3 admission allowance. `--deadline` and `--allowance` can lower those limits.
Conservative per-source-hour reservations are configurable in `.env`. A local timeout
is not cancellation or free usage; later resume can read an already completed remote
job. Publishing has up to three attempts per failed stage, including invalid-output
and SDK attempts, and a separate usage ledger. Missing billing remains unknown;
reservations do not prove an actual dollar cap. See [managed recovery](docs/managed-transcription.md).

## Legacy compatibility

```sh
podcast-process transcribe old-episode.wav --local -o legacy-output
podcast-process process old-episode.wav --local -o legacy-output
podcast-process generate legacy-output/transcript.json
```

Legacy generation writes a new `generated/<id>/` directory beside its input. An
explicit `--output` must be empty, preserving original transcript and publishing files.
These explicit local/legacy flows retain the old unversioned format and do not offer
the v2 guarantees or 15-concept contract. For managed transcription, use `--workspace`
or confirmed metadata; historical `transcribe file -o directory` with no authority
options still routes to local Whisper. Import preserved data for versioned generation.

## Verification and release evidence

```sh
mypy src/podcast_processor
pytest tests/
```

Tests use isolated workspaces, generated media, controlled services/clock and actual
process interruptions; no paid API trials are needed. The
[deterministic acceptance record](docs/workflow-acceptance.md) maps evidence to A1–A11.
The [post-merge experience audit](docs/specs/podcast-pipeline-v2-experience-audit.md)
records gaps in the intended new-episode workflow and the user-approved corrective
contract, including automatic cut discovery and reusable transition setup. The
[initial v2 specification outcome](docs/specs/podcast-pipeline-v2.md#implementation-and-acceptance-outcome)
retains the earlier build and scoped acceptance record. The
[source acceptance record](docs/source-acceptance.md) documents passing sampled
timing/safe-cut checks, human approval of both production publishing packages and
measured normal/fallback runtime, with coverage and overlap limitations.
Actual-cost gate A14 remains incomplete under the accepted closure exception;
the missing Deepgram fallback charge is tracked as
[nonblocking issue #20](https://github.com/jimmyblain/podcast-processing/issues/20).
Material provider/model/prompt changes still require affected evaluation.

MIT licensed.
