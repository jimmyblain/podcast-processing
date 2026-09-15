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
- `titles.md`: all 15 committed concepts in a copyable document, with separate title,
  overlay, visual-direction and pairing-rationale fields. Its source version and hash
  identify the exact `titles.json` used; rendering adds no new editorial claims.
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
reassembles a generated description from its saved body. It cannot change timestamps.
An edited description stays intact; any chapter mismatch is reported.

## Direct publishing edits

Edit `current/description.md`, `current/titles.json` or `current/chapters.txt` in place.
Inspection and ordinary `generate`/`process` resume preserve the exact bytes, including
whitespace and line endings. Each observed edit becomes a current `human-edited`
artifact with its own SHA-256, `edited_from` reference and original source revision.
Generated and previously captured edited artifacts remain immutable in history.
Publishing edits never enter model prompts, timed-transcript facts or episode metadata.

The current artifact index records delivered files, including edits that need attention.
`publishing_issues` in `inspect --json` and the completion report identify invalid UTF-8,
title/concept limits, description length, chapter format/durations, conflicts between
the description and standalone chapters, and stale or corrupt dependency evidence.
Validation checks structure and preserved dependencies; it does not certify the truth
of operator-authored claims or establish source support for manual chapter positions.
Issues make publishing partial and remove affected files from the terminal's ready list,
while preserving their exact bytes. Matching chapter edits can resolve a conflict;
neither file is automatically chosen as authoritative or rewritten.

Changed source, transcript or editorial inputs leave affected edits in place with a stale
status. Ordinary reruns do not generate competing replacements for edited outputs.
Different new recordings use separate workspaces by default. Explicit replacement via
`--fresh` releases only the selected edited output (`--only titles`, `description` or
`chapters`); without `--only`, it replaces the whole publishing package. A selected
chapter replacement retains an edited description and reports any resulting conflict.
Prior edits are committed to history before replacement begins, even if regeneration
fails. A missing current edited copy is restored from its verified edited artifact.
Damaged historical evidence is reported and is never trusted as a generated checkpoint.

### Readable title documents — issue #26

Readable titles are created locally in the same atomic current snapshot as the
structured titles. Unchanged data reuses the document version. Inspection and
`render WORKSPACE` add missing documents to older workspaces or restore missing
generated copies without a model request. Invalid structured title edits produce
an unavailable readable document without invented concepts; structurally valid
stale edits retain their concepts with a visible needs-attention status.

Direct edits to `titles.md` also retain their exact bytes through inspection and
ordinary resume. They do not change `titles.json` or become episode evidence.
Because arbitrary Markdown edits cannot establish agreement with structured titles,
the report and `publishing_issues` mark that agreement as unverified, exclude titles
from the ready list, and leave publishing partial. Changed or unavailable structured
data also marks the preserved readable edit stale. No competing readable draft is
generated. To restore agreement locally, run:

```sh
podcast-process render WORKSPACE --replace-title-edits
```

This explicit operation saves the edit in history before replacing `titles.md` from
current, structurally valid `titles.json`; it makes no service requests. Selected
`generate WORKSPACE --only titles --fresh` replaces both title deliverables under
the existing paid-generation contract. Chapter and description versions remain
independent of local title rendering.

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

### Conservative attribution — issue #25

Publishing validation now enforces a conservative attribution policy independently
of the prompt. The overview begins with a supplied presence sentence naming the
approved participants. That sentence establishes episode membership only.
The remaining generated copy uses neutral topics addressed to the listener.
Participant names and recognition variants, first/third-person personal pronouns,
host/guest references and quotation marks trigger validation unless the entire
field is an exact named quotation of a clear complete sentence from that participant's
supported or explicitly corrected voice. An approved name can also identify a
portrait subject, optionally followed by “in close-up.”

For example, `Erica Campbell: "I learned to ask for help."` is allowed only if that
complete clear sentence belongs to her supported voice. Naming Erica in the overview,
mapping her in an unrelated passage, or finding the sentence in an anonymous or
different participant's speech cannot authorize it. Named personal paraphrases are
conservatively excluded even when they might be true: these checks do not establish
semantic equivalence. Useful neutral themes and listener-directed takeaways remain
available. This rule applies to generated description fields, title/thumbnail
concepts, visual directions and chapter labels/reasons. Supplied biographies and
operator-authored edits retain their separate authority contracts.

Invalid attribution is repaired within the existing three-attempt stage allowance;
exhaustion leaves that stage unavailable while successful independent outputs survive.
Raw responses, repair feedback, immutable source-transcript references and the policy version
are checkpointed. Unchanged resume grants no new attempts. Corrections reconsider
ownership and invalidate its actual consumers; timing-only changes continue to
preserve copy when its wording and attribution evidence are unchanged.

This is a deliberately restrictive reference/quotation validator, not a general
semantic fact checker. New aliases and unusual indirect references may require
further coverage. Final source fidelity and editorial usefulness must be evaluated
on automatic outputs under #28, separately from earlier corrected-input approvals.

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

`test_publishing_edits.py` additionally exercises exact current bytes through inspection,
resume, selective explicit replacement, crashes around atomic edit commits and saved
regeneration receipts, validation/conflicts, stale inputs, historical recovery and paid
request counts. Integrated tests cover corrections and changed recordings while preserving
edits. Final ordinary-episode acceptance with the readable handoff belongs to issue #28.

The editorial reference is the user-approved communication prototype at commit
`05cc30b76389b5ec0e029baf51014f2b98519d9b`, especially its description, 15 title/overlay/visual
pairings and REVIEW.md. Its link candidates are not blanket approval, its text is not an exact
golden, and its timing is not verified source truth. Before release, the separate actual-output
human review must assess fidelity, voice, supported varied promises, complementary overlays,
actionable visual directions, natural chapters and honest reports, as required by gate A12.
