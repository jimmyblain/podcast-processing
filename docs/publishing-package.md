# Generate the approved publishing package

Issue #16 implements the versioned publishing workflow on `codex/podcast-pipeline-v2`.
It consumes saved timed-transcript evidence, participant attribution and correction lineage,
an approved show profile, and supplied episode metadata. Source media is unnecessary;
generation never transcribes or uploads anything. Legacy file-based generation retains its
older output contract. Import legacy evidence explicitly to use this workflow.

```sh
podcast-process generate output/episodes/episode-id
podcast-process generate output/episodes/episode-id --only titles --fresh
podcast-process generate output/episodes/episode-id --only description --fresh
podcast-process generate output/episodes/episode-id --only chapters --fresh
podcast-process inspect output/episodes/episode-id --json
```

An unchanged run reuses committed outputs and makes no paid requests. `--only` selects work;
`--fresh` explicitly starts a new allowance for selected generation, retaining history.
Without `--fresh`, an incomplete run resumes its existing allowance. Changing actual inputs,
model configuration (`CLAUDE_MODEL`) or a stage's rendered prompt creates new consuming work.
`--chapters 3` through `--chapters 10` sets a maximum, not an instruction to invent filler.

Successful current files:

- `description.md`: hook, overview naming Lish and confirmed guests, 3–5 takeaways, one
  comment question and subscribe/share invitation, shared chapters, approved/supplied extras.
- `titles.json`: exactly 15 concepts with `title`, `category`, `thumbnail_text`,
  `visual_direction` (`subject`, `expression`, `composition`) and `reasoning`.
- `chapters.txt`: timestamp/title-only lines. The description names the same committed
  chapter version in its dependencies. Chapter source positions and boundary evidence
  are retained separately in the `chapters.json` evidence checkpoint.
- `completion-report.md`: outcome, reused/completed stages, omissions/conflicts, uncertainty
  fallbacks, missing outputs, preserved edits, and publishing attempts/usage.

The description body is independently saved as `description-body.json` in the evidence store;
`inspect --json` exposes its immutable path. If chapters fail, this body survives, but
`description.md` is unavailable. Partial or failed packages exit with status 1. Valid
independent outputs survive; a missing required artifact never yields a completed package.

## Edit labels without another model request

Save a JSON array containing one new title per existing chapter, in the same order:

```json
["Start with honesty", "Listen before replying", "Prayer and practice"]
```

```sh
podcast-process generate output/episodes/episode-id --chapter-labels labels.json
```

This explicit operation validates the labels, versions the shared chapter data and locally
reassembles the description from its saved body. It cannot change timestamps. Direct edits
to exposed publishing files are instead preserved as exact bytes in distinct `human-edited`
history records before recovery/replacement. They never become source facts or transcript
corrections, and cannot keep the previous generated hash.

## Dependencies and recovery

Body and title requests consume approved voice/audience, participant names, angle/current
context and supported attributed text. Chapter requests consume supported text and source
positions, including reliable turn starts and aligned sentence starts within longer turns.
A candidate is evidence for a possible boundary; the model must choose natural topic breaks.
Unknown wording is excluded and unsupported timing never becomes a fabricated boundary.

Links, participant biographies/links, sponsor information and recurring promotion are
assembled locally from supplied values. Changes to these extras only invalidate final
assembly. Timing changes invalidate chapters and the embedded chapter version while keeping
an unchanged body and titles. A title-only run retains saved chapter settings. Profile/angle
changes invalidate their actual copy consumers; chapter labels only affect chapters/assembly.

Each publishing stage has a persisted maximum of three requests, counting invalid structured
responses and possibly billed interrupted requests. SDK retries are disabled and the existing
Claude client performs one attempt under this coordinator; retry layers cannot multiply.
Legacy generation retains its own bounded three-attempt client behavior.

Request intent is committed before dispatch. Successful provider text is flushed to a temporary receipt and atomically installed
before validation, rendering or output writes. A crash after receipt storage but before its
manifest update recovers that receipt by its precommitted path. A complete temporary receipt
is also recovered locally; an incomplete one records an unknown response/charge and uses
only the remaining bounded allowance. Successful responses survive
local output failures. An interruption before a receipt is durable leaves response/charge
unknown and consumes an attempt; ordinary resume never resets the allowance. A storage failure
that prevents writing the receipt cannot establish durable receipt of the remote response.

History records schema/stage versions, input/dependency and output hashes, immutable artifact
IDs, snapshots, exact rendered prompts, requested and returned models/IDs when available,
status and timestamps. Mutable model aliases are not immutable pins. Publishing token usage
is separate from transcription reservations; unavailable usage or billing cost stays unknown.
Credentials and authorization headers are not saved in these records.

## Validation and acceptance evidence

Automated validation enforces 15 distinct titles, required concept fields, 2–4-word overlays,
100-character titles without angle brackets, and 5,000 characters for the complete description
including chapters and supplied extras. This is the Studio-oriented contract; a future Data
API byte limit is outside this feature. Body length of 150–250 words remains an editorial
target, not a mechanical rejection rule. Category balance defaults to five per strategy but
can vary to maintain supported variety.

Chapter validation requires 3–10 entries, distinct nonempty labels, exact zero anchor, supported source positions,
strictly increasing times, and at least ten seconds per chapter, including the final interval.
Both precise and rendered positions are checked; rendering uses `MM:SS` below an hour and
`H:MM:SS` thereafter. No generated fallback uses evenly spaced boundaries.

The CLI tests use isolated real workspaces, controlled publishing responses, the actual SDK
with controlled HTTP, and process/storage interruptions. They cover limits, unavailable
chapters, recovery, usage, selective invalidation and preservation. They are structural and
workflow evidence, not a claim of source accuracy or actual v2 editorial acceptance.

The editorial reference is the user-approved communication prototype at commit
`05cc30b76389b5ec0e029baf51014f2b98519d9b`, especially its description, 15 title/overlay/visual
pairings and REVIEW.md. Its link candidates are not blanket approval, its text is not an exact
golden, and its timing is not verified source truth. Before release, the separate actual-output
human review must assess fidelity, voice, supported varied promises, complementary overlays,
actionable visual directions, natural chapters and honest reports, as required by gate A12.
