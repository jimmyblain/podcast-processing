# Podcast Processor

This CLI creates a timed transcript, a YouTube publishing package, an independent
section-planning outcome and a completion report in a resumable versioned workspace.
Read `CONTEXT.md` before exploring domain behavior. Work on `codex/podcast-pipeline-v2`.
Preserve existing media, local research and ignored evaluation bundles.

## Development and verification

Install with `uv venv && uv pip install -e '.[dev]'`; activate `.venv`. FFmpeg and
ffprobe are required. `.[local]` adds optional Whisper support for legacy commands.
Run `mypy src/podcast_processor` and focused pytest files while developing, then
`pytest tests/` for final verification. Tests use the public CLI/episode-operation
seam, real isolated workspaces and controlled services; subprocesses verify crashes
and concurrent ownership. Keep live paid trials out of deterministic tests.

## Workflow invariants

- `process RECORDING --solo` or `--guest NAME` uses approved show defaults and
  managed ASR. `process WORKSPACE` resumes all independent stages.
- `transcribe` makes no publishing requests. `generate WORKSPACE` and `import`
  never implicitly submit transcription. Explicit `--local` retains legacy behavior.
- One workspace writer spans the whole operation. Hash-verified immutable artifacts,
  receipts and atomic current snapshots protect recovery and exact direct-edit history.
- Preserve accepted/possibly accepted job slots, attempts, reservations and absolute
  deadlines across restart. Missing actual billing is unknown. `--fresh` records
  new possible spending and retains earlier ledgers.
- Invalidate only actual consumers. Shared chapter versions keep the standalone
  list and assembled description identical. A saved body alone is not a complete
  required description. Impossible section proposals do not block publishing.
- Use conservative supported attribution and text without mandatory per-episode
  review. Human release review and real source/runtime/cost gates remain issue #19.

## Context pointers

- For installation, CLI options, partial outcomes and recovery, read `README.md`.
- For publishing dependencies or validation, read `docs/publishing-package.md`.
- For source identity or schema imports, read `docs/workspace-import.md`.
- For managed ASR or accounting, read `docs/managed-transcription.md`.
- For participant mapping or corrections, read `docs/participant-corrections.md`.
- For section evidence or duration arithmetic, read `docs/section-planning.md`.
- For deterministic coverage and remaining release gates, read `docs/workflow-acceptance.md`.
- For GitHub issue operations, use `gh` as described in `docs/agents/issue-tracker.md`.
- For triage labels, read `docs/agents/triage-labels.md`.
- For domain documentation conventions, read `docs/agents/domain.md`.
