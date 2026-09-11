# Integrated workflow acceptance evidence — issue #18

## Post-merge new-episode audit

The [user-approved experience audit](specs/podcast-pipeline-v2-experience-audit.md)
qualifies the initial completion claim: automatic candidate discovery and reusable
transition setup are missing, and a fresh interview exposed participant-mapping
and publishing-attribution concerns. The passing tests below prove their stated
mechanics; manually supplied boundary candidates and corrected participant inputs
did not prove the intended normal new-episode workflow. Corrective acceptance must
exercise those production stages before the workflow is declared complete.

## Parent specification reconciliation — issue #12

On 2026-09-10, the completed #13–#19 tickets were reconciled against the
[specification outcome](specs/podcast-pipeline-v2.md#implementation-and-acceptance-outcome).
Fresh verification of implementation `d6b5339` passed mypy for all 31 source files
and **256 tests in 71.71 seconds**, with no skips. This reconciliation changes
documentation and tracker status only; it makes no new provider requests or
human-approval claims. The A14 actual-cost exception remains explicit, with
[nonblocking follow-up #20](https://github.com/jimmyblain/podcast-processing/issues/20).

## Deterministic evidence scope

Deterministic evidence is collected at the public CLI/episode-operation seam using
real isolated workspaces, controlled HTTP/publishing responses and clock, generated
media and actual subprocess crashes. Fixtures establish structural/recovery behavior;
silent media and supplied synthetic natural-cut assertions do not establish audio
quality. No live paid trials are required or authorized by these tests.

## Gate coverage

| Gate | Deterministic evidence |
| --- | --- |
| A1 inputs/unattended workflow | `test_episode_workflow.py`: confirmed solo/interview participants, approved defaults with optional context absent, full independent outputs, conservative mapping; `test_participant_corrections.py` and `test_publishing_package.py`: supported identity, uncertain names/wording, neutral fallbacks and separate reports |
| A2 normalization | `test_managed_transcription.py`: provider units, mixed word labels, zero-duration/unknown timing, overlap, source bounds, non-speech annotations and faithful wording; optional cached local provider replays supplement always-present fixtures |
| A3 corrections/provenance | `test_participant_corrections.py`: relabel/merge/separate/split/text/timing, incompatible bases and immutable lineage; `test_episode_workflow.py`: corrected full reruns preserve edits and avoid ASR, timing-only changes retain text copy |
| A4 publishing structure | `test_publishing_package.py`: fifteen distinct concepts, length/overlay/visual/rationale validation, description structure, supplied facts and complete-description bounds; `test_episode_workflow.py`: completed full package |
| A5 chapters/assembly | `test_publishing_package.py`: supported boundaries, timestamp rendering and durations, labels, regeneration/reassembly and independent body recovery; integrated tests: failed chapters preserve body, selected recovery, exact standalone/embedded match, invalid local labels remain partial |
| A6 deterministic timing mechanics | `test_managed_transcription.py`, `test_participant_corrections.py`, `test_section_planning.py`: lossless original offsets, corrected bounds, overlapping/unknown timing rejected at cuts. Real sampled anchors and two source-safe cuts are recorded separately in [source acceptance](source-acceptance.md). |
| A7 section arithmetic | `test_section_planning.py`: inclusive limits, adjacent complete coverage, unequal sections, just-outside/overhead/overlap failures and 3369.842358-second impossibility; integrated tests: valid synthetic 616.5/711.5/805-second finished sections under the user-corrected final-section rule, transition-only changes, missing/invalid evidence without blocking usable publishing |
| A8 reuse/invalidation | `test_episode_workflow.py`: unchanged completed rerun has zero paid calls and identical IDs, full/selected fresh ledgers, profile/links, metadata/facts, publishing model/template, raw-response normalization reuse, actual ASR hints, corrections and transitions; publishing/correction suites cover other model/template/metadata/label changes |
| A9 current/history/ownership | `test_episode_recovery.py`: real CLI process death at inspection, preparation, submission, accepted identity, raw response, normalization, mapping, publishing response/body/titles/chapters, assembly and planning; interrupted output writes; two simultaneous full CLI processes; `test_workspace_recovery.py` and integrated edit tests: exact edit preservation even with a damaged original artifact |
| A10 bounded recovery | Integrated recovery/accounting tests: primary failure/ambiguous acceptance, backup allowed/denied, exhausted reservations, unchanged deadline, pending/completed remote jobs after expiry, saved response reuse; managed/publishing suites: rejection/auth/transient/SDK/invalid-output retry bounds, unknown billing and no new allowance on resume |
| A11 identity/import | `test_workspace.py` and recovery tests: same-basename separation, moved/missing media, identical reattachment, changed bytes, verified copy, preserved legacy source bytes, unknown provenance and future-schema rejection; integrated tests: full source identity/move/reattachment/copy/replacement and future-schema rejection; explicit imports remain authoritative even after damage/repeated resume; legacy generation preserves existing files |

The full-operation tests observe output bytes, schema, current artifact references,
history, reservations/deadlines and provider requests. The subprocess recovery tests
assert exactly one primary submission and one successful request per publishing
stage after recovery at every saved-response/output boundary. An interrupted
publishing request without a saved response remains an attempt with unknown charge;
a replacement consumes another slot within its three-attempt operation.

## Verification record

Verified 2026-09-10 after implementation and independent standards/specification
reviews: `mypy src/podcast_processor` passed for all 31 source files;
`pytest tests/ -q` passed **253 tests in 68.72 seconds**, with no skips in this local
run. Both review axes have zero remaining findings after regression fixes. Focused
integrated workflow and subprocess recovery files were also run during development.
The optional cached provider replays can skip elsewhere when private bundles are absent.
This suite duration is test runtime, not production episode-performance evidence.

## Source acceptance and cost exception — issue #19

The dated [source acceptance record](source-acceptance.md) contains the actual
source/transport correspondence, independent timing anchors, two natural safe-cut
intervals, scoped speaker/overlap diagnostics and human approval of both production
publishing packages. Communication has a feasible proposal under explicit
transition-duration fixtures. Erica's explained duration-limit outcome is accepted.

The representative Communication transcription operations measured **147.211 s**
for normal primary and **184.364 s** for controlled fallback, including preparation,
upload, provider processing, normalization and recovery. Publishing is accounted
for separately. These are single observations, not service guarantees.

AssemblyAI's observed actual aggregate is **$0.51009**. The accepted Deepgram
fallback request's actual charge remains unavailable. On September 10, the user
explicitly authorized issue closure without waiting for that charge. **A14 remains
incomplete, with an authorized closure exception**; unknown charges are not zero,
and reservations or advertised estimates are not actual bills or a verified cap.

After the issue #19 code corrections, mypy passed all 31 source files and the full
suite passed **256 tests in 79.81 seconds**. The later source annotations and closure
exception change evidence only. The detailed record retains the test logs and
independent standards/specification review outcomes.

Issue closure does not close the parent specification/map, certify unreviewed
full-episode speech or overlap accuracy, export media, or create a mandatory
per-episode review queue. First-release/material-change human review remains
recorded independently of the missing actual-cost evidence.
