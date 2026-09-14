# Natural-boundary discovery evidence — issue #24

## Production trial, September 14, 2026

An isolated copy of the saved Ashlee episode from the experience audit exercised the
new production discovery stage. The user explicitly approved sending the preserved
transcript/context to Anthropic for one bounded operation with at most three requests.
No operator-authored cuts or word IDs were supplied. The original episode workspace,
recording and earlier evaluation bundles were preserved.

The operation reused the corrected timed transcript and publishing package, consumed
the real approved show setup, generated **12 candidates**, and selected this feasible
proposal under the 600–1080-second inclusive limits:

| Section | Original source range | Expected finished duration |
| --- | --- | --- |
| 1 | 0–831.090 seconds | 853.656621 seconds (14:13.66) |
| 2 | 831.090–1683.667 seconds | 868.743644 seconds (14:28.74) |
| 3 | 1683.667–2389.008254 seconds | 711.674587 seconds (11:51.67) |

The source is covered once with exact adjacency. Each approved prepared duration
includes its 2.0-second ending silence once. Sections 1 and 2 include the separate
1.5-second closing pause and transition-out. Section 3 retains only its opening
transition and plays through the source ending. Persisted decimal durations retain
full precision; the table rounds for readability.

The completed operation took **56.477 seconds** and used one Claude Opus 4.8 request:
218,322 input tokens and 3,351 output tokens. Actual dollar billing is **unknown**;
token usage is not a reconciled bill or a new verified budget cap. No transcription
or publishing requests were made. A subsequent full resume with no API key preserved
identical current artifacts and all three usage ledgers.

## Evidence and limits

The [machine-readable record](evidence/boundary-discovery-2026-09-14.json) pins the
source fingerprint, transcript and proposal hashes, approved setup revision, initial
candidate artifact, raw response identity, usage and reuse checks. Private transcript,
request/response text, complete proposal and all history remain in the ignored local
`output/acceptance-issue-24-2026-09-14/episode` workspace.

Initial generated candidates remain **transcript-supported suggestions**. Neither the
model's judgment nor the timed-transcript checks establish independent audio safety.
No listening annotations, source-reviewed safe intervals or human approval of the
cuts were supplied or claimed. Issue #28 must evaluate these preserved generated cuts;
reviewer-selected replacements must not substitute for the initial discovery result.
This is acceptance of the newly implemented discovery stage on the previously
unplanned episode, not the complete ordinary-new-episode acceptance for #22–#28.

The source transcript retains 130 words unusable for precise cuts. Local checks
rejected 53 potential locations and offered 1,300 timing-consistent search locations
to semantic discovery. One zero-length word in its own unbounded speaker turn was
localized by its preserved coarse position and reliable neighboring words; it never
became a precise cut anchor. Real accuracy of such localization remains part of
source review.

## Deterministic coverage

`test_boundary_discovery.py` exercises production discovery through the public full
operation, with controlled external services and generated source/setup audio. It
covers unequal feasible parts, unknown/uncertain/overlapping timing and supported
alternatives, an isolated uncertain turn, contradictory retained timing, correction invalidation, prepared-duration
recalculation, completed-but-insufficient searches, missing setup, impossible duration
constraints, failed/invalid requests, missing credentials, persistent attempt limits,
explicit fresh recovery, saved response recovery and unchanged reuse.

`test_discovery_recovery.py` kills real CLI subprocesses at request intent, flushed
response receipt, candidate artifact and proposal checkpoints. Resume preserves
allowances and recovers saved responses without duplicate successful requests. A
request interrupted before its response remains possibly billed and consumes a slot.
These fixtures prove workflow/timing mechanics, not editorial quality or real safe cuts.

## Final verification

After the independent reviews and uncertainty-localization correction,
`mypy src/podcast_processor` passed all **33 source files** and
`pytest -q tests/` passed **290 tests in 114.55 seconds**. Standards and specification
reviews have **zero remaining findings**. The specification review caught conflicting
retained timing being narrowed away; production regressions now cover zero-length,
start-only and end-only contradictions on both sides of a proposed cut.

Both saved real cuts also pass the final timing validator. Their supporting text
matches their preserved word references, source parts cover the exact source duration,
and all finished durations meet the inclusive limits. A separate local check verified
the moved original recording against its preserved fingerprint. These checks do not
replace the independent source listening still required by #28.
