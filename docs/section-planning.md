# Three-section planning

A normal `podcast-process process RECORDING --solo` or `--guest NAME` run discovers
natural cut candidates automatically after reusable show setup. It uses the preserved
corrected timed transcript, original-source identity and timeline, and the saved
approved prepared transitions. No operator-authored timestamps, word IDs or evidence
file are needed. `podcast-process plan WORKSPACE` runs the same discovery/planning
stage on an existing episode with its saved setup, without ASR or publishing requests.
New semantic discovery requests use the configured Claude model and Anthropic key.

The result is a versioned `section-plan.json` outcome. A valid outcome also exposes
`section-boundaries.json`; an unavailable outcome explains the limiting evidence or
duration constraints and exposes no proposal. Independent outputs remain usable.
Missing or unprepared transitions yield `needs-setup`; a full `process` then exits 1
with a partial result. Run [show setup](show-setup.md) once to prepare, hear and approve
the supplied transitions. New full episode operations snapshot and reuse them automatically.

## Discovery and evidence strength

The local search considers sentence endings, speaker-turn changes and word gaps.
Those are search locations only. A semantic request examines the full conversation
and surrounding text to identify completed thoughts followed by natural topic changes,
with reasons and editorial strengths. It seeks alternatives throughout the recording,
including around unusable timing, rather than demanding equal parts. Returned IDs
must belong to the locally checked opportunities. The model cannot supply timestamps,
independent source-review status or safe-interval assertions.

Every candidate retains consecutive before/after word references, source-relative time,
surrounding word IDs/text, and the semantic reason. `section-candidates.json` is an
immutable internal artifact referenced under `inspect --json`'s `evidence`; it keeps
all generated candidates and rejected timing locations. The initial provider response
remains separate under `discovery-responses/`, with its request, model, token usage and
hash in `discovery_operations`. Reviewer annotations remain separate explicit evidence.

Generated candidates have `basis: transcript-supported`. They are suggestions based
on semantic judgment plus timed-transcript consistency, **not verified audio safety**.
Punctuation, waveform silence and model assertions alone do not prove safe cuts.
Independent listening may supply `source-reviewed` boundaries with safe intervals;
initial generated candidates are never relabeled as reviewed. No mandatory per-episode
review queue or media export is introduced. The [September 14 production trial](boundary-discovery-acceptance.md)
records a feasible generated proposal for later source review under #28.

## Recovery and outcome reasons

Discovery persists intent before dispatch, raw responses before validation, and derived
candidate evidence before proposals. A flushed response receipt survives a crash before
manifest commit. A request with no response remains a possibly billed attempt. Each
discovery operation has at most three attempts, including invalid outputs and provider
failures. Resume retains the same allowance. `plan WORKSPACE --fresh` explicitly grants
another operation; a full `process --fresh` includes fresh discovery, while selected
publishing regeneration does not. Missing credentials can resume the same operation
when credentials become available. No new whole-operation dollar cap is claimed.

Unchanged successful discovery/proposals are reused. Source or corrected transcript
changes invalidate their consumers. Model/template changes rerun semantic discovery;
prepared transition changes only recalculate the plan from reusable candidates. Saved
responses can rebuild damaged derived candidate artifacts without another request.
No discovery operation implicitly submits transcription.

`section-plan.json.reason_code` distinguishes:

| Reason | Discovery/result |
| --- | --- |
| `missing-setup` | Discovery not run; needs setup, full process partial |
| `source-unavailable` | Source identity/timing prerequisites prevent a supported search |
| `duration-impossible` | Source and prepared overhead cannot satisfy duration budgets; semantic request unnecessary |
| `discovery-failed` | Provider/local stage failed; no completed search result, full process and standalone plan exit 1 |
| `insufficient-boundaries` | Completed search/evidence evaluation cannot supply a feasible supported pair |
| `invalid-evidence` | Supplied evidence is inconsistent, such as duplicate boundary IDs |

A valid proposal has no failure reason. `discovery.status` and `summary` distinguish
completed semantic/local searches from failure and stages that were not run. A local
search with no timing-supported opportunities records that limitation without claiming
a semantic search occurred. All independent publishing outputs remain usable.

## Advanced explicit evidence

`podcast-process plan WORKSPACE --evidence planning.json` consumes explicit evidence
locally, with no API key or discovery request. This preserves historical fixture studies
and independently reviewed evidence; explicit inputs remain pinned across resume.

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
Missing/unprepared transitions yield `needs-setup`; missing source identity or supporting
boundary evidence yields `unavailable`. Real measurements must identify the verified
revision and evidence; preliminary silence-detector estimates are not prepared
durations. Saved approved setup provides measured transition defaults; there are no
hard-coded duration guesses.

Boundary `basis` values are `transcript-supported`, `source-reviewed`, or `fixture`.
The evidence producer supplies the complete-thought/topic judgment and reason.
For `source-reviewed`, also supply `safe_start` and `safe_end`; the candidate time
must lie within that interval. This planner validates consistency with the timed
transcript, not the truth of editorial assertions or independent audio annotations.
The explicit-evidence path does not request semantic discovery. Without supported
candidates it records unavailability immediately, with no mandatory manual review step.

The referenced words must be consecutive, with usable, uncertainty-free timing.
Cuts must lie between those words and avoid other overlapping speech. Unknown
timing elsewhere is acceptable only when source-timeline evidence bounds it away
from the cut. A containing turn or reliable same-turn neighboring words can supply
conservative outer bounds. A retained coarse word position bracketed by two reliable
neighbors can localize an isolated unbounded turn. Neither case makes the uncertain
word usable as a precise cut anchor; its neighboring complete words are included in
the uncertainty interval. Retained uncertain positions are never narrowed out when they conflict with neighboring
anchors. Unbounded uncertainty still prevents a proposal. All timestamps are original-source offsets, including initial music,
pauses between topics, and trailing source audio.

Among feasible pairs, the planner first prefers the stronger weakest boundary,
then combined editorial strength (1–3), then similar finished durations. There is
no equality tolerance. The example's source parts are 600, 700 and 800 seconds;
finished durations are 616.5, 711.5 and 805 seconds.

## Duration accounting and outcomes

Every prepared duration includes its saved ending silence **once**. The original
contract and historical evidence default to 2.5 seconds; the user-approved September 14
setup uses 2.0 seconds. `settings.transition_ending_silence` snapshots that setting.
Preparation evidence must attest that natural decay is preserved and excess dead
space replaced. This operation does not trim or append silence. The separate pause
before transition-out remains 1.5 seconds under the default contract.

- `D1 = E + P1 + pause + O`
- `D2 = I + P2 + pause + O`
- `D3 = I + P3`

Section 3 plays through the original episode ending. It has an opening transition,
but no added closing pause or transition-out, as clarified by the user during
issue #19 review. Only the first two sections have a closing transition.
New outcomes/proposals use schema version 2 and `section-planner-v4`; final-section
`pause` and `closing_duration` are zero. Version 1 proposals remain readable as
historical evidence of the earlier rule. Resuming planning replaces current plans
under the new rule while retaining history and independent publishing outputs.

Defaults are 600–1080 seconds inclusive. Explicit settings changes are preserved
as a new planning input revision and evaluated against their stated limits. The
report lists overhead and available source-part budgets before the selected cuts.
For Erica at 3369.842358 seconds, the source alone exceeds three default maximum
durations by 129.842358 seconds, before transition overhead.

Exit code 0 means the planning operation completed, including an explained
`unavailable` or `needs-setup` outcome; consumers must inspect `section-plan.json.status` to
distinguish feasibility. Discovery failures, invalid JSON/configuration or workspace failures exit 1.
An unavailable outcome never exposes `section-boundaries.json`.

Unchanged evidence and transcript inputs retain artifact IDs and make no paid
requests. Changes to transition revisions, prepared durations, pauses or limits
replace only planning outputs. Transcript corrections and source changes supersede
dependent plans. Previous outcomes and direct edits remain in immutable history.
Raw ASR and unrelated publishing outputs remain available when their inputs match.
