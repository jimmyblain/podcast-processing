# Three-section planning

`podcast-process plan WORKSPACE --evidence planning.json` is a local planning
operation. It consumes the current corrected timed transcript, source evidence,
prepared transition durations, and supported natural-boundary candidates. It does
not require a publishing package or an API key and does not prepare or export media.

The result is a versioned `section-plan.json` outcome. A valid outcome also exposes
`section-boundaries.json`; an unavailable outcome explains the limiting evidence or
duration constraints and exposes no proposal. Independent outputs remain usable.

Candidate evidence must identify complete thoughts and natural topic breaks on the
original source timeline. Supplying evidence is not a review queue: the operation
finishes immediately with the evidence available. Sentence punctuation and silence
alone cannot establish a natural cut. Real source timing and safe-cut accuracy
remain evaluation work; synthetic fixtures establish arithmetic only.

## Evidence file

Obtain `source_revision` and the current `artifacts["transcript.json"].sha256` from
`podcast-process inspect WORKSPACE --json`. Word IDs come from the current
`transcript.json`. All candidate evidence is pinned to that transcript hash;
corrections require evidence against the new hash. Candidate IDs must be unique.

This example uses **synthetic assumptions**, including the source identity, asset
durations and natural-cut judgments. Replace all of them with the corresponding
episode evidence before using it for a real episode. Decimal seconds may be JSON
strings or numbers; persisted calculations use decimal strings to preserve exact
arithmetic.

```json
{
  "schema_version": 1,
  "source": {
    "revision": "CURRENT_SOURCE_REVISION",
    "fingerprint": "synthetic-source-identity",
    "duration": "2100",
    "basis": "fixture",
    "evidence": "Synthetic duration assumption, not measured audio"
  },
  "transcript_sha256": "CURRENT_TRANSCRIPT_SHA256",
  "episode_start": {
    "asset_revision": "synthetic-E-v1",
    "prepared_revision": "synthetic-E-prepared-v1",
    "duration": "10",
    "ending_silence": "2.5",
    "preserves_decay": true,
    "replaces_excess_tail": true,
    "basis": "fixture",
    "evidence": "Synthetic prepared duration including the total ending silence"
  },
  "transition_in": {
    "asset_revision": "synthetic-I-v1",
    "prepared_revision": "synthetic-I-prepared-v1",
    "duration": "5",
    "ending_silence": "2.5",
    "preserves_decay": true,
    "replaces_excess_tail": true,
    "basis": "fixture",
    "evidence": "Synthetic prepared duration including the total ending silence"
  },
  "transition_out": {
    "asset_revision": "synthetic-O-v1",
    "prepared_revision": "synthetic-O-prepared-v1",
    "duration": "5",
    "ending_silence": "2.5",
    "preserves_decay": true,
    "replaces_excess_tail": true,
    "basis": "fixture",
    "evidence": "Synthetic prepared duration including the total ending silence"
  },
  "settings": {"pause": "1.5", "minimum": "600", "maximum": "1080"},
  "boundaries": [
    {
      "id": "topic-2", "time": "600",
      "before_word": "last-word-of-topic-1", "after_word": "first-word-of-topic-2",
      "complete_thought": true, "natural_topic_boundary": true,
      "reason": "Synthetic complete thought followed by a new topic",
      "basis": "fixture", "strength": 3
    },
    {
      "id": "topic-3", "time": "1300",
      "before_word": "last-word-of-topic-2", "after_word": "first-word-of-topic-3",
      "complete_thought": true, "natural_topic_boundary": true,
      "reason": "Synthetic complete thought followed by a new topic",
      "basis": "fixture", "strength": 3
    }
  ]
}
```

Source and asset `basis` values are `verified`, `fixture`, or `unknown`.
Missing transitions, prepared revisions, durations, source identity or supporting
evidence yield an unavailable outcome. Real measurements must identify the verified
revision and evidence; preliminary silence-detector estimates are not prepared
durations. No default transition durations are supplied.

Boundary `basis` values are `transcript-supported`, `source-reviewed`, or `fixture`.
The evidence producer supplies the complete-thought/topic judgment and reason.
For `source-reviewed`, also supply `safe_start` and `safe_end`; the candidate time
must lie within that interval. This planner validates consistency with the timed
transcript, not the truth of editorial assertions or independent audio annotations.
It does not automatically generate semantic candidates. Without supported candidates
it records unavailability immediately, with no mandatory manual review step.

The referenced words must be consecutive, with usable, uncertainty-free timing.
Cuts must lie between those words and avoid other overlapping speech. Unknown
timing elsewhere is acceptable only when containing turn evidence bounds it away
from the cut. All timestamps are original-source offsets, including initial music,
pauses between topics, and trailing source audio.

Among feasible pairs, the planner first prefers the stronger weakest boundary,
then combined editorial strength (1–3), then similar finished durations. There is
no equality tolerance. The example's source parts are 600, 700 and 800 seconds;
finished durations are 616.5, 711.5 and 811.5 seconds.

## Duration accounting and outcomes

Every prepared duration includes its total 2.5-second ending silence **once**.
Preparation evidence must attest that natural decay is preserved and excess dead
space replaced. This operation does not trim or append silence. The separate pause
before transition-out remains 1.5 seconds under the default contract.

- `D1 = E + P1 + pause + O`
- `D2 = I + P2 + pause + O`
- `D3 = I + P3 + pause + O`

Defaults are 600–1080 seconds inclusive. Explicit settings changes are preserved
as a new planning input revision and evaluated against their stated limits. The
report lists overhead and available source-part budgets before the selected cuts.
For Erica at 3369.842358 seconds, the source alone exceeds three default maximum
durations by 129.842358 seconds, before transition overhead.

Exit code 0 means the planning operation completed, including an explained
`unavailable` outcome; consumers must inspect `section-plan.json.status` to
distinguish feasibility. Invalid JSON/configuration or workspace failures exit 1.
An unavailable outcome never exposes `section-boundaries.json`.

Unchanged evidence and transcript inputs retain artifact IDs and make no paid
requests. Changes to transition revisions, prepared durations, pauses or limits
replace only planning outputs. Transcript corrections and source changes supersede
dependent plans. Previous outcomes and direct edits remain in immutable history.
Raw ASR and unrelated publishing outputs remain available when their inputs match.
