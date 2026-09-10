# Source acceptance record — issue #19

Status on 2026-09-10: **ready for issue closure with an explicit user-authorized
billing exception. Actual-cost gate A14 remains incomplete.**

The user explicitly directed that missing Deepgram spend data must not hold up
closure. Delayed reporting is possible, but unverified. This decision changes the
closure requirement; it does not establish an actual charge or an all-gates-passed
release claim. The current gate ledger below and final closure decision supersede
earlier pending-status statements in this chronological evidence record.
Evaluated production baseline: `edbd5a3def7274f382ea5b1ab661d315917c3ec8`
on `codex/podcast-pipeline-v2`. Source preparation measurements below apply to that
baseline. The subsequent user listening feedback also corrects final-section
assembly; the current planner implements that correction. This record supplements the
[deterministic workflow evidence](workflow-acceptance.md). Provider selection and
the GitHub parent specification/Wayfinder map remain unchanged. The local
specification and section-planning documentation reflect the user's correction.

Codex performed byte, stream and lossless transport checks and ran the existing
tests. Codex did not supply human listening or editorial approval. The user later
supplied partial listening feedback, recorded separately below. The user subsequently approved a $6 total ASR allowance and a separate $5 total
publishing allowance. Live normal and controlled-fallback Communication trials
have completed. Both actual publishing packages completed after supported corrections,
and the user approved both review packets. The sampled source-timing and safe-cut checks pass. The user has supplied the
remaining overlap detail; the new Deepgram fallback charge remains unknown and
is nonblocking for closure by the user's explicit decision.
Missing results are incomplete, not passes or zero-dollar bills.

## Verified source catalog and local preparation

Locations came from the existing ignored `output/evaluation-corpus/manifest.json`.
Fresh streaming SHA-256 and ffprobe measurements matched both accepted sources:

| Source | Duration (seconds) | Source SHA-256 |
| --- | ---: | --- |
| Communication solo | 2306.182676 | `6169e359350d60b36f748b84b4d69f21183d94319a9b8812fcd5f91476b3d787` |
| Erica interview | 3369.842358 | `48889a5fe1e5aade91c433244aceb0da8ced86435f713db1bf533f20b2637e13` |

Both are stereo 44.1 kHz `pcm_s16le`. This establishes accepted file identity.
It does **not** establish that the communication content/timeline corresponds to
the historical transcript. The historical `output/0710/transcript.json` reports
2306.1826875 seconds; neither this near-match nor its plausible text is source truth.

The production `inspect_source` and `prepare_transport` functions were exercised
locally once per source, with a 900-second preparation deadline, in new ignored
directories. Full-episode FLAC preparation verified matching decoded PCM hashes,
sample rates and channel counts, with zero timeline offset and no trimming.
Decoded hash format was explicitly `pcm_s32le`; hashes in earlier comparison
records may use a different decoded sample format and must not be compared blindly.

| Source | Inspection | Transport preparation | Local total |
| --- | ---: | ---: | ---: |
| Communication | 0.489 s | 9.531 s | 10.020 s |
| Erica | 0.697 s | 13.849 s | 14.546 s |

Environment: macOS 26.6.2 ARM64, Python 3.12.9, FFmpeg 8.0.1. Timings use
`time.perf_counter`, include fingerprint/stream/equivalence checks, and are one-run
local observations. They exclude upload, processing/polling, normalization,
automatic recovery and publishing. They are **not A13 acceptance**, and must not
be added to the old comparison times to manufacture a new full-operation trial.
The FLAC copies were prepared locally and were not uploaded despite the transport
schema calling their hashes `submitted_fingerprint`.

[Machine-readable evidence](evidence/source-acceptance-2026-09-10.json) records
source revisions, transport hashes, measurements and hashes of private supporting
records. The full local packet is `output/acceptance-issue-19-2026-09-10/`.
Original recordings, transition assets, manifest, historical output and annotations
remain unchanged. Private media and credentials remain outside version control.

## Required gate ledger

Rows follow the acceptance criteria in [issue #19](https://github.com/jimmyblain/podcast-processing/issues/19).
Pass applies only to the stated scope; missing combined criteria remain incomplete.

| Criterion | Status | Evidence and remaining obligation |
| --- | --- | --- |
| 1. Accepted sources and correspondence | Pass (identified sources and sampled correspondence) | Accepted WAV hashes/durations verified. Three independent human Communication onsets match historical content/timeline within 0.064, 0.051 and 0.005 seconds; historical output remains separate from source truth. |
| 2. Targeted human source annotations | Pass (targeted sample) | Six word-start points, two preceding word ends, phrase/speaker judgments and the approximately 0.315-second Erica/Lish overlap are recorded with source identity and uncertainty. No full-window transcription or coverage is inferred. |
| 3. Preserve earlier listening truth | Pass | Original annotation hash recorded; five Erica identities and ambiguous both-speaker thanks preserved, with no new overlap label. |
| 4. Independent point anchors and safe intervals | Pass (sampled points and two cuts) | Independent human word onsets/ends define safe gaps [753.684,753.936] and [1506.209,1506.789]. Both selected cuts lie inside them; chapter zero remains only a format anchor. |
| 5. Real output timing and cuts (A6) | Pass (sampled timing/cuts) | All sampled point errors are <=1 s, including two word ends and the Erica handoff comparison; both Communication cuts pass human safe intervals. Maximum across consumer comparisons is 0.789 s after chapter rendering. No full-episode or complete overlap claim. |
| 6. Feasible communication / impossible Erica (A7) | Pass (explicit transition fixtures) | Production planner accepts both source-reviewed safe cuts with labeled E=55/I=50/O=50-second fixture assumptions, giving 860.184, 854.025 and 849.973676 seconds and exact full-source coverage. Erica returns explained impossibility while publishing completes; user accepted both outcomes. |
| 7. Speech/proper nouns/speakers (A12) | Pass (scoped diagnostics with stated limitations) | Nine earlier selected phrase/ownership diagnostics plus the confirmed five-word Lish phrase are recorded. The one annotated overlap is missed in the output; preceding mixed attribution remains conservatively anonymous. User approved corrected publishing outputs; no overall speech or overlap accuracy claim. |
| 8. Human production editorial review (A12) | Pass (pinned packages) | User approved both actual review packets after corrections and chapter repair. Exact packet/artifact hashes and approval provenance recorded; historical prototype approval remains separate. |
| 9. Bounded normal/fallback live operation | Pass (measured scope) | User approved $6 total ASR and $5 publishing before dispatch. One live primary-only Communication operation and one live primary-plus-Deepgram controlled recovery completed. Fallback publishing deliberately disabled. Durable cross-trial reservations retain all accepted jobs. |
| 10. Full-operation runtime (A13) | Pass (two observations) | Near-40-minute Communication normal ASR 147.211 seconds; controlled fallback 184.364 seconds, each including inspection, fresh transport preparation, upload, processing/polling, normalization and recovery. Publishing measured separately; no SLA or percentile claim. |
| 11. Account-specific actual cost (A14) | Incomplete; closure exception authorized | AssemblyAI current-day actual aggregate is $0.51009 including diarization, below the $3 normal-operation target. Deepgram sign-in works, but its new accepted fallback job has no visible billing record. No exact per-job allocation or zero fallback charge is inferred. |
| 12. Reservations/restarts and honest missing bills | Pass (mechanics only) | Existing CLI/operation and process-crash tests verify denied jobs, retained slots/reservations/deadlines and unknown actual charges. Actual-cost acceptance remains incomplete. |
| 13. Complete gate record / closure rule | Pass under explicit user exception | This ledger preserves scoped passes, limitations and incomplete actual cost. The user explicitly authorized #19 closure without the Deepgram charge; no complete A14 pass is claimed. |
| 14. First-release/material-change human review | Pass (current packages) | User approved both current packages. Material provider/model/prompt changes require affected human checks again. Actual-cost evidence remains incomplete with the explicit closure exception; routine episodes retain unattended completion. |

No full-episode WER, diarization error rate, proper-noun accuracy, overall speech
score is reported. Selected independent source points support the individual
errors and scoped maxima below; both reviewed Communication cuts pass their
human safe intervals. These samples do not establish full-episode accuracy. No failing point is hidden by an average.

## Human review packet and scoring method

The user's subsequent feedback is preserved verbatim in the ignored packet as
`user-feedback-01.json`, with source hashes/revisions and conversation provenance:

- Communication 1: Lish; preferred break after “implement them,” before the clarity
  discussion. Communication 2: Lish; preferred break after “proceed,” before the next
  point. This first feedback supplied editorial preferences; later numeric cut
  selections are recorded separately below.
- Communication 3: the user corrected the assembly rule, without supplying a
  listening annotation. This excerpt was a late timing sample, not a third cut.
  Section 3 now has no added closing pause or transition-out.
- Erica 1: user identifies Lish. Erica 2: Erica begins, with crosstalk from Lish.
  Subsequent phrase ownership is recorded below; exact point times and
  simultaneous overlap intervals remain unconfirmed.

Additional Erica feedback is preserved in `user-feedback-02.json`. The user
identifies “You have” near 39:59 as Lish; “offers coming in” in the 40:02 exchange
as Lish and the interrupting “they are” as Erica; brief “yeah” replies near 40:16
as Lish; and “it’s a God moment, so…” in the 40:39–40:46 passage as Erica before
Lish interrupts and continues. These are approximate navigation locations, not
exact word starts or simultaneous-overlap intervals. In particular, both cached
providers place their “They are” tokens near 40:06 within the broader exchange;
no retiming to 40:02 is inferred. The exact first words of Lish's final interruption
were not supplied. The phrase identity questions are answered and should not be
repeated.

Against these selected observations, historical AssemblyAI labels “You have,”
“They are” and its retained “Yeah” near 40:16 incorrectly. Its offers and God-moment
phrase labels agree with the supplied speakers. Deepgram labels “You have” and
“They are” consistently with the feedback, but assigns the God-moment phrase and
“So” to Lish; its cached words contain no “Yeah” near 40:16. Preserve these as
diagnostic findings and correction evidence, not an aggregate accuracy score.
The annotation record pins candidate token indices to hashed historical normalized
files. Raw/provider outputs remain unchanged; actual v2 corrections must reference
the corresponding versioned words and preserve timing uncertainty.

The user subsequently selected communication cuts at **12:33:684 (753.684 seconds)**
and **25:06:209 (1506.209 seconds)** on the original recording. The raw input and
exact decimal conversions are preserved in `user-feedback-03.json`. These are
human-selected points associated with the earlier phrase/break judgments, not
word-onset anchors or a claimed wider safe interval. No timing uncertainty bound
was supplied, and the selected points should not be requested again.

| Episode part | Source start (seconds) | Source end (seconds) | Source duration (seconds) |
| --- | ---: | ---: | ---: |
| 1 | 0 | 753.684 | 753.684 |
| 2 | 753.684 | 1506.209 | 752.525 |
| 3 | 1506.209 | 2306.182676 | 799.973676 |

These parts cover the source exactly once, with no gaps or overlap. Final duration
acceptance still requires prepared transition evidence or labeled assumptions:
section 1 can accommodate at most 326.316 seconds of `E + 1.5 + O`, section 2
327.475 seconds of `I + 1.5 + O`, and section 3 280.026324 seconds of `I` before
exceeding 1080 seconds. All source parts alone exceed 600 seconds.

The historical transcript ends “them” at 753.78, 96 ms after the user's first
selected cut, and places the second cut inside its “proceed”/“The” gap. Preserve
these differences rather than moving the human reference to fit ASR. Historical
model timing neither disproves the first cut nor verifies a safe interval for the
second. Neither comparison is a measured word-onset error or actual v2 acceptance.

No precise review date or actual listened interval was supplied; the record's
capture time is not represented as the listening time. User wording is preserved
as supplied, including possible typing errors, and is not silently cleaned into a
verbatim scoring reference. Historical AssemblyAI wording and provider timestamps
for Erica 2 are available in `erica-review-02-reference.md` solely as a comparison
aid; they are not a new v2 acceptance run or independently verified timing.

The ignored packet contains `REVIEW.md`, `pending-annotations.json`, and five PCM
WAV excerpts at communication 749–759, 1501.84–1511.84 and 2230.67–2240.67 seconds,
and Erica 70–90 and 2395–2455 seconds. These are review excerpts, not finished
section exports. Clip-relative time must be added to the recorded source start.
Empty annotation fields mean unreviewed, not silence, a safe cut or absent overlap.

Earlier user listening covers Erica 162–176, 1002–1017 and 3299–3308 seconds
(38 seconds). The original user-annotation record does not contain a precise
review timestamp; it must not be invented. Erica says “Hello,” “Six,” “Harmonica,”
“my sisters, my kids,” and “I don’t think it will.” AssemblyAI matched four of these
five selected disputed identities and Deepgram one; these are not overall accuracy
percentages. Both say “thank you,” but exact ownership, ordering and simultaneous
overlap are unknown. Do not request the established identities again.

For new annotations, record source hash/revision, exact listened interval, reviewer,
date/provenance, annotation type and uncertainty. Obtain independent listening
before comparing provider or historical timestamps. Preserve uncertain reference
spans. Extend coverage only for complete thoughts, a feasible split or verified
overlapping speech; full manual transcription and the offered MP3 are unnecessary.

For each reviewed production word/turn/chapter anchor, record artifact ID/hash,
anchor reference, output seconds and absolute error against the independent point.
Every reviewed point must be within 1.0 second; uncertain reference spans stay
explicitly unresolved rather than becoming invented exact anchors. Publish each
error, the maximum, counts and reviewed time coverage. For every proposed section
cut, verify inclusion in the independently annotated safe interval and preserve
words, complete thoughts and natural breaks. Sparse unusable word timing requires
a supported alternative or explicit unavailability.

Communication requires two source-reviewed cuts and contiguous full coverage.
Use `D1 = E + P1 + 1.5 + O`, `D2 = I + P2 + 1.5 + O`, and
`D3 = I + P3`, with each finished duration inclusively 600–1080 seconds. The third
formula follows the user's subsequent correction; section 3 plays through the
original ending with no added closing pause or transition-out.
Each prepared asset already includes its 2.5-second tail once. Actual prepared
durations need evidence; fixture assumptions must remain labeled. Preliminary
silence detection does not establish approved trims or complete thoughts.
Erica's source alone exceeds `3 × 1080` by 129.842358 seconds, so positive
transition overhead cannot make it feasible. Its independent publishing outputs
must nevertheless complete in the actual workflow.

Human editorial review must cover both actual v2 packages: grounded speech and
attribution, all fifteen meaningful titles, complementary overlays, actionable
subject/expression/composition briefs, warm/candid/practical and appropriately
faith-grounded voice, no forced slang or invented religious content/claims,
natural chapters and usable descriptions, safe feasible cuts and an honest report
understandable without episode knowledge. Use the approved prototype at
`05cc30b76389b5ec0e029baf51014f2b98519d9b` as a reference. All fifteen prototype
concepts were approved; T01/T06/T13 are examples, not required output strings.
Correct meaningful omissions, changed meaning and confident wrong attribution
before affected output is usable, preserving raw evidence and correction lineage.
Blanket unknown attribution is not a substitute for useful supported identity.

## Live observations after the approved allowance

The user approved **$6 total for new ASR trials** and **$5 total for publishing**,
with the original **$3 per-transcription-operation target**, before any new live
request. Local `live/authorization.json` records the approval. The trial runner
uses the production `process_episode` operation and real providers, and stores
atomic cross-trial reservations under an evaluation lock. ASR reservations remain
$1.50 per source hour for each potentially billed provider attempt. Publishing
admission reserves counted input plus maximum output at the recorded published
rates with 25% margin; after a complete response, retained allowance uses returned
token counts at those same rates plus 25%, while preserving the original maximum
reservation. Unknown/failed responses retain their full reservation. This is
conservative estimated accounting, **not actual billing or a verified hard cap**.

| Communication trial | Full transcription operation | Scope |
| --- | ---: | --- |
| Normal primary | 02:27:211 (147.211 s) | Fresh source inspection/FLAC preparation, EU AssemblyAI upload/job/polling, normalization, mapping and persistence |
| Controlled fallback | 03:04:364 (184.364 s) | Same preparation plus completed live AssemblyAI job; deliberate normalization rejection then live Deepgram backup and persistence |

The fallback injection is an evaluation control, not evidence of a spontaneous
AssemblyAI failure. Both real accepted jobs remain in its ledger. Fallback
publishing was disabled to keep the trial focused on transcription recovery.
One observation per path passes 900 seconds; this is not a latency distribution
or SLA. Original local-only preparation and historical Erica comparisons remain
separate observations.

The normal initial workflow finished partial in 245.142 seconds: description body
and titles validated, but three chapter responses used supported IDs with
incorrect numeric times. Strict validation rejected them. The validator now lists
each mismatched entry's exact expected source time; unknown IDs still fail. A
public-CLI regression failed before the fix and passed after it. An explicit
chapter-only fresh operation, bounded by the same total allowance, completed in
30.687 seconds with a rejected first attempt and a repaired second attempt. It
reused ASR/body/titles and produced identical chapters in the standalone file and
description. The interruption between those runs is not hidden as continuous
workflow runtime, and the first three invalid attempts remain retained/billed-unknown.

Actual Communication output is in `live/normal/episode/current/`; the frozen review
packet and artifact hashes are in `live/normal/REVIEW.md` and
`live/normal/review-artifact-hashes.json`. The user approved this pinned packet
in the subsequent feedback recorded below. The planner's valid proposal uses the exact user points, checks them
against current provider word gaps, and **labels boundary basis transcript-supported**
because independently annotated safe interval endpoints are still missing.
Transition durations remain explicitly hypothetical fixtures; no trims were made.

Erica's fresh full transcription operation took **03:23:558 (203.558 seconds)**,
including 13.992 seconds of FLAC preparation and 122.591 seconds of upload. It was
run first with publishing disabled so existing human corrections could be applied
before generating copy. Fifteen public correction operations mapped the supported
guest voice, reassigned “Hello,” “You have,” “They are” and “Yeah,” and left the
short unresolved interruption passage anonymous. Original/raw and intermediate
revisions remain intact; no source word times were altered. The five earlier
selected lexical targets all appear in this fresh output. This selected diagnostic
set is not overall accuracy, WER, or a complete overlap annotation.

Erica publishing subsequently completed in 63.949 seconds with three live requests
and no invalid responses. Its current plan cleanly explains that source duration
alone exceeds the three-section maximum by 129.842358 seconds. Its description,
chapters, fifteen title concepts and report are preserved in `live/erica/REVIEW.md`
with `review-artifact-hashes.json`; the user subsequently approved the pinned packet
and accepted its explained section impossibility.

## Remaining live billing obligations

The approved total allowances above apply across all trials and resumes. Per-operation `--allowance` does not enforce
a cross-workspace evaluation budget. Preserve every accepted/possibly accepted
request and reservation across restarts; do not renew spending with `--fresh` or
retry billing access by submitting more transcription jobs.

Retain the completed normal and controlled-fallback records, injected failure
point, accepted primary job and live backup operation. A cached
or simulated provider result proves mechanics only. Record source and transport
hashes, code/model/prompt/artifact versions, endpoint/privacy/request settings,
environment, trial count, absolute deadlines and every phase from initial local
preparation through normalization/recovery. Evaluate transcription against 900
seconds and measure publishing time/token usage separately. A warm-cache run must
be labeled and cannot replace required preparation coverage.

Verify account rates for the exact endpoint/model/privacy settings and obtain
request-linked billed usage or account deductions with unrelated activity excluded.
Credits/deductions and gross charges need an explicit reconciliation method; keep
actual, estimated and reserved usage separate. Compare each normal and controlled-
fallback operation, including automatic recovery, against the **$3 transcription/
diarization target**, excluding publishing-text generation. The separate total
evaluation allowance does not replace this per-operation acceptance target.
The prior approximately $0.457
comparison estimate is not observed billing. A fresh Deepgram balance request again returned HTTP 403; dashboard sign-in was
requested. An earlier AssemblyAI dashboard snapshot showed the two Communication EU jobs
completed (before the new Erica job);
the current-day Cost view reported no activity with all active keys selected.
A final reload returned “An error occurred while fetching data.” These displays
are incomplete billing evidence, not proof of zero cost.
Missing exact bills leave A14 incomplete, never zero or a verified hard dollar cap.
Old Erica observations of 184.36 and 24.05 seconds excluded prior preparation and
remain single-run comparison evidence, not current integrated acceptance.

Human review is required before first release and after material provider/model/
prompt changes. Rerun affected checks and retain versioned evidence; do not repeat
unrelated paid work or add mandatory per-episode review.

## Deterministic verification

Initial `mypy src/podcast_processor`: passed all 31 source files.
Initial focused managed transcription/recovery, episode workflow and section-planning
tests: **136 passed in 34.91 seconds**. These use the already agreed public
CLI/episode-operation seam. The initial evidence-only work added no tests.
The subsequent final-section correction adds regression coverage for retaining
the original ending without an added pause/transition-out and reading historical
version 1 proposals while enforcing version 2 assembly. Updated focused planning
and integrated workflow tests: **100 passed in 21.35 seconds**.
After this correction, mypy again passed all 31 source files and the full suite
passed **255 tests in 72.76 seconds**, with no skips. Logs are retained as
`ending-rule-mypy.txt` and `ending-rule-full-suite.txt` in the ignored packet.
Standards and specification reviews of the final-section work found no remaining issues after updating
the verification text; the incomplete release gates above remain open.

Initial full suite before the final-section correction: **253 passed in 70.99 seconds**,
with no skips. The run log is retained
in the ignored packet as `full-suite.txt`. Test-suite time is not production
runtime or billing evidence. Reservation coverage includes insufficient
allowance without refill, ambiguous primary preventing backup, two ambiguous slots
surviving resumes, unchanged deadlines and real subprocess restart checkpoints.

The live chapter failure led to one further public-CLI regression. The complete
publishing test file passes **50 tests**, mypy passes all **31 source files**, and
the final full suite passes **256 tests in 79.81 seconds**, with no skips. The final
log is `live/final-full-suite.txt`. Standards review found no actionable issues in
the diagnostic change. Strict rejection, accepted response reuse and the existing
three-attempt limit remain unchanged; the diagnostic does not silently retime output.

Final specification review found no blocking issues; the dashboard provenance wording
was clarified to identify its earlier two-Communication-job snapshot. No required
human or actual-cost gate was waived, and issue #19 remains open.

## Subsequent human publishing approval

The user approved both actual production review packets and explicitly accepted
Erica's current duration-limit outcome. The approval and exact artifact hashes are
preserved in `user-feedback-04.json`. The approved publishing and transcript files
still match those hashes; the later source-reviewed planning evidence update is
recorded below with new plan/report versions.
Longer-episode section handling is recorded as future work, with no expansion of
this implementation's three-section contract. This approval does not supply new
word-start timestamps, safe interval endpoints, precise overlapping-speech bounds
or billed-dollar observations. Those remaining source-timing and cost gates stay
incomplete; no repeat editorial approval is needed for these unchanged packages.

## Billing update after publishing approval

AssemblyAI's signed-in dashboard now reports **$0.51009** actual current-day
aggregate spend: **$0.46573** for Universal-3.5 Pro in the EU and **$0.04436** for
EU speaker diarization. The aggregate is consistent with the three completed
AssemblyAI evaluation jobs. It is below $3 even before separating the normal job,
but the dashboard did not provide an individual-request allocation. Earlier
empty/error displays remain preserved as historical observations, not zero bills.

Deepgram sign-in now works. Its earlier Erica comparison request is visible with
an actual charge of **$0.24339**. The new fallback request lookup currently finds
no record, and the September 10 spend view shows no activity. The earlier charge
cannot substitute for the new fallback charge. Thus fallback actual-cost acceptance
remains incomplete; no further login is currently needed. Exact observations are
preserved in `live/billing-after-editorial-approval.json`.

## Six independent source timing anchors

The user supplied six Audition word-start timestamps in `user-feedback-05.json`.
They are retained as source-reviewed best estimates with no invented uncertainty
bound. All approved output hashes remain unchanged: no timestamps were retimed
to fit these references. Navigation windows do not imply that the user annotated
every second within them.

| Reference | Human source time | Primary output time | Absolute error |
| --- | --- | --- | --- |
| 1. Communication: You know… | 12:33:936 | 12:34:013 | 00:00:077 |
| 2. Communication: The next one is relevance | 25:06:789 | 25:06:843 | 00:00:054 |
| 3. Communication: I hope that this helps | 37:15:675 | 37:15:742 | 00:00:067 |
| 4. Erica intro: What's up everybody | 01:12:559 | 01:12:535 | 00:00:024 |
| 5. Lish: You have? | 39:59:671 | 39:59:721 | 00:00:050 |
| 6. Erica: I don't think it will | 55:02:344 | 55:02:370 | 00:00:026 |

All six primary word starts pass the <=1.0-second requirement; maximum **0.077 s**.
The same three Communication source points also score the saved live fallback
output, with errors **0.019 s**, **0.0889 s**, and **0.010 s**; all pass. Those
are three additional output comparisons, not three new source annotations.

The matching Communication chapter boundaries have precise errors 0.077/0.054 s;
the whole-second YouTube displays have errors 0.064/0.789 s. The matching corrected
Erica turn starts have errors 0.050/0.026 s. These consumer checks all pass, with
**0.789 s maximum including chapter rendering**. No other chapter start has been
independently timed. IDs, hashes, exact decimal arithmetic and coverage are in
`live/timing-comparison-v1.json` and `live/timing-consumers-v1.json`.

The two next-word onsets are now known. Completing source-reviewed Communication
safe intervals still requires the ends of “them” and “proceed”; do not ask for the
six supplied starts or the chosen cuts again. Erica's precise interruption words,
start and simultaneous-overlap bounds remain unresolved.

## Source-reviewed safe gaps and Erica handoff

In `user-feedback-06.json`, the user confirms the preceding words end exactly at
the two selected cut times, and supplies Lish's interruption start **40:46:521**.
Combined with the already supplied next-word onsets, the Communication safe gaps
are **12:33:684–12:33:936** (0.252 seconds) and
**25:06:209–25:06:789** (0.580 seconds). Both selected cuts lie at their safe
interval's lower endpoint. The production planner was rerun locally with
`basis=source-reviewed`; both cuts pass with unchanged source parts and finished
durations. Original planning evidence and reviewed artifact versions remain in
history. The approved transcript, description, titles and chapters are unchanged;
only planning/report evidence was refreshed. No new paid request was made.

The primary word-end errors are **0.024 s** for “them” and **0.281 s** for
“proceed”; fallback errors at those same source references are **0.271 s** and
**0.0909 s**. The supplied Lish handoff is compared to the saved next Lish turn
at 40:46:840, giving **0.319 s** error. All are within one second. “Amen” is the
provider's candidate word at that turn; the user has not supplied the first words
or the end of simultaneous speech, so no word-identity or overlap interval is
inferred from this comparison. Detailed references and hashes are retained in
`live/boundary-and-handoff-checks-v1.json`.

Three historical Communication onsets were also compared with the independent
human source anchors: differences are 0.064, 0.051 and 0.005 seconds. This establishes
sampled historical content/timeline correspondence alongside the accepted WAV
hashes; it does not make the historical transcript authoritative or certify every
word. See `live/historical-source-correspondence.json`.

## Confirmed Lish phrase and approximate overlap

In `user-feedback-07.json`, the user confirms Lish says “amen, amen, let me just”
and Erica's voice stops around **40:46:836**. Combined with Lish's previously
supplied onset **40:46:521**, this establishes an approximately **00:00:315**
simultaneous-speech interval. The stop remains an approximate human estimate;
no numerical uncertainty bound is invented. No further targeted listening
annotation is needed from the user.

The five retained Lish words and their attribution match. The saved onset error
is **00:00:319**. The preceding retained God-moment passage ends at 40:46:580,
**00:00:256** before the approximate Erica voice stop. The **00:00:256** difference
is an unscored diagnostic, not a matched endpoint error: the last audible word
is not established, since earlier human feedback also mentioned “so.” Only the
confirmed Lish onset receives a timing pass here. Maximum scored consumer error
remains **00:00:789**.

The output does **not** represent this overlap: it has a 00:00:260 gap instead.
This is a recorded limitation on one annotated interval, not a passing overlap
detection score. The already approved corrected output keeps the preceding
mixed-speaker passage locally anonymous; the new phrase confirmation does not
justify assigning that whole passage to Erica. Publishing and transcript artifacts
are unchanged, and no paid regeneration was needed. Details are pinned in
`live/overlap-checks-v1.json`. The sole remaining acceptance obligation is the
new Deepgram fallback's actual billed charge.

## Billing access diagnosis

The existing configured Deepgram key successfully lists the same project as the
signed-in dashboard (HTTP 200). The documented Management API lookup for the
exact fallback request returns **HTTP 403**. This confirms a read-access blocker
and rules out a different listed project; it does not establish the specific
authorization cause or any actual charge. Obtaining an authorized request-cost
record or provider confirmation is the next step. No further transcription job
is needed. Sanitized results are in `live/deepgram-management-diagnostic.json`.

The user's signed-in browser was then checked directly: the exact request is
absent, unfiltered history extended through September 11 still contains only the
older September 8 trial, and September 10–11 Spend shows $0.00000 with no data.
The prior September 8 charge is visible. These observations do not establish a
zero fallback bill. A local support draft includes the preserved request ID,
response timestamp, settings and duration; it has not been sent. See
`live/deepgram-signed-in-dashboard-recheck.json`.

## Final closure decision

The user explicitly states: “its possible the spend data is just delayed. I don't
want this to hold up closure of the ticket.” The exact message and scope are
preserved in `user-feedback-08.json`. This later instruction supersedes the
original issue requirement to keep #19 open for the missing Deepgram charge.

The accepted source checks, scoped timing/speech diagnostics, safe Communication
cuts, corrected final-section rule, both human publishing approvals and measured
normal/fallback runtimes are complete within the coverage stated above. The
approximately 315 ms missed overlap remains a disclosed output limitation.
Erica's long-episode impossibility is accepted; broader long-episode handling is
future work. Prepared transition durations remain explicit fixtures.

AssemblyAI actual aggregate remains **$0.51009**; the new Deepgram fallback charge
remains **unknown**. A14 is incomplete, with an explicit exception for ticket
closure. Delayed billing is a possible explanation, not a verified finding.
Historical estimates, reservations and the older Deepgram charge remain separate.
No further paid trial, monitoring task, support message, parent-issue closure or
release deployment is part of this decision.
