# Speaker-aware podcast pipeline v2 — implementation specification

Status: **Specification for review. Production implementation and release acceptance are not complete.**

Consolidated on 2026-09-08 from [Wayfinder map #2](https://github.com/jimmyblain/podcast-processing/issues/2), all nine closed decision tickets and their comments, referenced research, the approved publishing prototype, and the current planning checkout. Repository work belongs on `codex/podcast-pipeline-v2`.

The accepted resolutions are authoritative. Later unattended-completion, provider, recovery, and quality resolutions supersede earlier proposals in the research and ticket history. No in-scope product question is reopened here. The proposed testing seam and build sequence are presented for specification review; pending evidence is work to perform during implementation, not a new requirements interview.

## Problem Statement

An operator needs to turn an English episode of I'll Just Let Myself In into a useful, speaker-aware timed transcript and a complete YouTube publishing package in one run. The operator may know nothing about the conversation beyond the required supplied inputs. They need trustworthy source references, faithful wording, grounded publishing copy in Lish Speaks' voice, and clear outcomes without having to adjudicate normal speech-recognition uncertainty.

The current CLI performs local transcription without speaker identity, emits ten title concepts without visual direction, permits chapter descriptions, and does not assemble the required shared chapters into the description. Saving the timed transcript before publishing generation already protects valuable work, but publishing stages lack independent durable recovery, selective reuse, version history, and budget accounting. Repeating work can overwrite useful artifacts or require unnecessary calls.

The same timed transcript must support source-relative section-boundary proposals for a later three-section media workflow. Plausible timestamps, provider agreement, or a well-formed document cannot establish safe natural cuts. The specification must retain the accepted design while making outstanding audio, timing, production, editorial, runtime, and cost evidence explicit.

## Solution

Provide a resumable CLI workflow using managed full-episode transcription and speaker detection: AssemblyAI Universal-3.5 Pro as primary and Deepgram Nova-3 with diarization v2 as bounded automatic backup. Normalize preserved provider evidence into faithful source-relative words and speaker turns, keeping anonymous speakers distinct from confirmed participants. Identify participants from introductions and consistent dialogue when supported; otherwise retain uncertainty and finish conservatively.

An approved reusable show profile and authoritative episode metadata guide one publishing package: a concise description with embedded chapters, exactly fifteen title/thumbnail concepts, and the identical standalone YouTube chapter list. Keep diagnostics in a separate completion report. Preserve valid completed stages, original results, optional corrections, direct human edits, prior versions, and the evidence behind every version. Repeating an unchanged completed operation makes no paid calls.

Produce a valid three-part source-boundary proposal when supported by natural boundaries and transition budgets. Report an unavailable proposal when the constraints cannot be met, while completing independent artifacts. Media preparation, splitting, stitching, and export belong to the later media effort. Routine episodes complete without mandatory human review; implementation and material changes require the evaluation evidence specified below.

## User Stories

1. As an operator, I want one full episode run to create the timed transcript and publishing package, so that I do not coordinate separate manual generation steps.
2. As an operator, I want to supply the recording and confirmed guest names or explicit solo status, so that the workflow starts from authoritative participant information.
3. As an operator, I want an approved reusable show profile, so that audience, voice, identity, links, and promotional defaults remain consistent.
4. As an operator, I want to supply optional episode angles, biographies, links, sponsors, and current context, so that relevant details can guide the package without becoming mandatory homework.
5. As an operator, I want unverified optional details omitted and conflicts reported, so that the package does not invent facts or require me to research the episode.
6. As an operator, I want managed transcription and speaker detection, so that I do not maintain a required local machine-learning stack.
7. As an operator, I want a second provider used automatically for failed or unusable processing within limits, so that recoverable provider failure does not require intervention.
8. As an operator, I want sparse uncertainty handled without an automatic full-episode rerun, so that normal imperfections do not create unnecessary delay and cost.
9. As an operator, I want timestamped readable paragraphs with supported participant labels, so that I can locate and understand speech when needed.
10. As an editor, I want repetitions, false starts, and fillers preserved, so that the timed transcript faithfully represents what was spoken.
11. As an editor, I want source-relative word and speaker-turn evidence, so that publishing and future cuts refer to the correct recording positions.
12. As an editor, I want recoverable overlapping speech and uncertainty retained, so that simultaneous dialogue is not flattened or invented.
13. As an operator, I want anonymous speakers kept separate from participant names, so that a vendor label or spoken name does not become false attribution.
14. As an operator, I want uncertain identity and wording handled with neutral publishing copy, so that a useful package completes without episode knowledge.
15. As an editor, I want optional speaker relabeling, merging, separation, and supported turn splits, so that I can fix attribution without retranscribing the episode.
16. As an editor, I want wording and timing corrections to retain their base version and invalidate affected evidence, so that corrections do not fabricate alignment or silently alter another revision.
17. As an operator, I want a warm, candid, practical description that reflects the episode's actual Christian themes, so that the package fits the approved audience and voice.
18. As a publisher, I want an episode hook, overview, specific takeaways, comment question, and brief subscribe/share invitation, so that listeners understand the conversation and can respond.
19. As a publisher, I want only approved or supplied links and promotional information, so that stale schedules, guest details, and sponsor claims do not enter the package.
20. As a publisher, I want exactly fifteen distinct grounded title concepts using varied strategies, so that I have meaningful editorial choices.
21. As a thumbnail designer, I want complementary two-to-four-word overlays and concrete subject, expression, and composition directions, so that each concept is actionable.
22. As a publisher, I want a short pairing rationale for every title and thumbnail concept, so that I can understand the intended promise.
23. As a publisher, I want at most ten chapters at natural conversation breaks, so that navigation follows the episode instead of an arbitrary count.
24. As a publisher, I want timestamp-and-title-only chapter lines, so that I can paste them without removing generated subtitles or explanations.
25. As a publisher, I want identical standalone and embedded chapter lists, so that editing or regenerating chapters cannot leave contradictory timestamps in the description.
26. As a publisher, I want title, chapter, and full-description validation, so that invalid artifacts are repaired within limits or clearly reported unavailable.
27. As an operator, I want an honest separate completion report with source examples and fallbacks, so that I understand the outcome without polluting copy-paste text.
28. As an operator, I want valid partial outputs preserved after a failure, so that completed work remains useful and unavailable artifacts are never reported as successful.
29. As an operator, I want rerunning an unchanged episode to resume or reuse saved work, so that I avoid unnecessary transcription and generation charges.
30. As an operator, I want input changes to invalidate only their actual dependents, so that a link edit or title-only request does not retranscribe the episode.
31. As an operator, I want individual publishing artifacts regenerated from a preserved timed transcript, so that I can improve the package independently.
32. As an operator, I want prior versions retained during fresh generation, so that I can inspect and recover earlier work.
33. As an operator, I want direct publishing-file edits preserved before replacement, so that regeneration cannot silently destroy my changes.
34. As an operator, I want only current-input-valid artifacts exposed together, so that I never mistake stale copy for a newly completed package.
35. As an operator, I want stable episode identity independent of recording names and locations, so that equal basenames do not collide and moving identical media does not create a new episode.
36. As an operator, I want original media referenced by default with optional verified copying, so that workspaces avoid unnecessary large duplicates while supporting self-contained use.
37. As an operator, I want preserved timed transcripts usable when source media is unavailable, so that text-only work can continue and media-dependent work fails honestly.
38. As an operator, I want explicit non-destructive legacy import, so that existing outputs remain intact and missing provenance stays unknown.
39. As an operator, I want crash-safe writes and one writer per episode workspace, so that concurrent or interrupted runs cannot expose truncated artifacts or duplicate paid jobs.
40. As an operator, I want known and possibly accepted provider submissions recorded across restarts, so that network uncertainty does not silently reset retries or spending.
41. As an operator, I want bounded transcription and publishing recovery with separate usage ledgers, so that the workflow stops honestly when its allowance is exhausted.
42. As an operator, I want actual, estimated, and reserved cost distinguished, so that advertised rates and missing billing access are not presented as verified charges.
43. As a future media editor, I want exactly three consecutive episode parts covering the whole source once, so that no content is omitted or repeated.
44. As a future media editor, I want each finished section to last ten to eighteen minutes including transitions and pauses, so that duration checks reflect the eventual assembly.
45. As a future media editor, I want complete thoughts and natural boundaries prioritized over equal durations, so that the conversation survives the cuts.
46. As an operator, I want impossible section proposals explained without waiting for review, so that independent publishing outputs still complete.
47. As a maintainer, I want small source-reviewed excerpts tied to recording fingerprints, so that timing and speaker claims have bounded, reproducible evidence.
48. As a maintainer, I want deterministic production regression tests using cached responses and simulated failures, so that recovery behavior can be verified without repeated paid requests.
49. As a maintainer, I want actual v2 outputs reviewed before release and after material changes, so that automated structure checks are supported by semantic and editorial evidence.
50. As an operator, I want routine episodes to retain unattended completion after that release review, so that evaluation work does not become a recurring approval queue.

## Implementation Decisions

### I1. Public workflow and module responsibilities

Retain the existing CLI entry-point concepts: full processing, transcription only, and publishing generation from preserved timed transcript data. Extend the public workflow to support explicit legacy import, optional versioned corrections, selected-artifact regeneration, explicit fresh operations, source reattachment, and optional media copying. Exact option spellings are implementation details; these behaviors must be documented and acceptance-tested. Transcription-only in v2 uses managed services but makes no publishing-text calls. Generation/import must not implicitly submit transcription.

Keep the CLI thin over one episode-operation coordinator. That coordinator owns dependencies, checkpoints, outcomes, and bounded recovery. Evolve the existing typed models, configuration, transcriber interface, publishing generators, prompt templates, and Claude client; add small managed-provider adapters, a versioned workspace store, participant/correction handling, deterministic package rendering/validation, and section-boundary planning. These are responsibility boundaries, not a mandate for one module per stage or a framework of generic workflow abstractions. Continue using the existing publishing client boundary; this decision does not choose a new publishing provider or guarantee an immutable Claude alias.

Expose enough external outcome/state information to distinguish a completed requested workflow, partial results, failures, and unavailable section planning. Missing required publishing artifacts must not yield a full-success claim. Normal uncertainty and an explained impossible section split must not prompt or block independent work. Validate genuine required inputs and configuration explicitly; they are not license to invent missing information.

### I2. Authoritative inputs and editorial defaults

The host is always Lish Speaks. Current episodes are solo or host plus one guest; participant/speaker representations must allow additional guests later without a two-speaker schema limit. Required episode inputs are the recording and confirmed guest names or explicit solo status, alongside the approved reusable show profile. Legacy generation follows the limited-evidence import contract instead of pretending to have a recording.

The show profile carries approved host/show identity, audience, voice, official links, and recurring promotional text. Episode metadata carries confirmed participants and optional angle, biographies, links, sponsors, and current context. Use official supplied spellings; record conflicts with speech evidence, omit unverified optional details, and use neutral attribution where needed. Current context is user-supplied. There is no default live web enrichment.

Approved audience: **People ready to take a chance on themselves—in creative work, careers, relationships, and personal growth—who welcome honest conversation, practical encouragement, and a Christian perspective.** This is an editorial default, not a demographic measurement.

Approved voice is warm and familiar, candid and challenging, practical, faith-grounded, playful and human. Address listeners directly while referring to Lish in third person in the overview. Preserve Christian themes present in the episode; do not add religious claims absent from supported content, force slang, invent controversy, or promise unsupported results. Exact recurring promotional copy and selected links remain profile configuration. Research candidates and prototype sample links are not automatic approval to include every value.

### I3. Managed transcription and provider normalization

Use full-episode AssemblyAI Universal-3.5 Pro primary and Deepgram Nova-3 with diarization v2 backup. Run backup only for failed/unusable processing within I10's limits: service failure or a result that cannot supply usable episode speech under the normalized contract after local validation. Preserve salvageable evidence and identify the failure reason. Individual uncertain words, sparse timing problems, or uncertain participant mapping are handled conservatively and do not independently trigger a second full-episode job. Do not invent an aggregate confidence threshold as a backup trigger.

Use minimal preprocessing that preserves original-source time. The verified lossless FLAC transport is supported. Record original-source and submitted-transport fingerprints and transformation provenance; verify decoded-audio equivalence for lossless transport conversion. Do not remove pauses, shift intros, apply unvalidated denoising, or require local models, separate forced alignment, voice enrollment, or chunk stitching. Any later chunking/preprocessing change requires timeline reconciliation, speaker reconciliation where applicable, and affected quality evaluation.

Carry forward the comparison's fidelity-oriented request baseline: English, punctuation, fillers/disfluencies retained, text/smart formatting disabled, word speaker labels, no forced speaker count, no default keyterms or paid identification features. AssemblyAI used the EU endpoint; Deepgram used Nova-3, diarization v2, utterances, mixed-audio processing, and per-request model-improvement opt-out. Record endpoint/region and explicit privacy/request settings; do not infer verified deletion, retention, or privacy-adjusted billing from these settings. Changed settings become new dependency inputs and require affected evaluation.

Adapters retain raw responses before normalization, translate units explicitly, and rebuild speaker turns from word-level speaker labels and usable word bounds. Never propagate a vendor utterance's speaker over differently labeled words or assume its start/end is precise. Deepgram's cached case contains 153 mixed-speaker utterances and 939 words differing from parent labels; AssemblyAI has three utterance starts over one second before their first word. These are required normalization fixtures.

Keep original word order and overlapping evidence; presentation sorting must not fabricate sequential speech. Preserve AssemblyAI's 103 zero-duration words as recoverable text with unusable/uncertain timing. Keep music and other provider annotations separate from spoken prose and participant identity evidence. Native confidence is supporting evidence, not a standalone accuracy gate.

### I4. Timed-transcript and participant contract

Use explicit schema versions and these minimal typed records; exact field names may follow existing conventions:

| Record | Required meaning |
| --- | --- |
| Episode/source revision | Stable episode identity, exact recording revision/fingerprint, duration, language, source locator and relevant stream properties. |
| Speaker | Anonymous detected voice identity scoped to the timed-transcript revision, with a separate optional participant association and explicit unresolved/uncertain state. |
| Participant | Confirmed host or guest identity from authoritative metadata; never inferred solely from vendor label order. |
| Speaker turn | Stable revision-scoped reference, speaker or explicit unknown attribution, source-relative bounds when usable, faithful speech, and uncertainty/overlap annotations. |
| Word | Spoken text, containing turn reference, source-relative start/end when available, timing usability, and optional native confidence with source/meaning. |
| Correction/provenance | Exact base/source revision and referenced records, applied changes/lineage, and the components/settings that produced the result. |

Retain spoken repetitions, false starts, and fillers. Punctuation and capitalization may improve readability; grammar rewriting and paraphrase may not alter the timed transcript. Render timestamped paragraphs with confirmed participant names or anonymous labels. Start a new paragraph at speaker changes and wrap long turns for readability without changing the underlying speaker-turn semantics. Structured output retains word detail.

Known times must be finite, ordered within each interval, source-relative, and within recording duration. Usable precise intervals have positive duration, and reliable word bounds must fit their containing turns. Missing, zero-length, or inconsistent evidence remains explicitly unknown/unusable and is excluded from precise-cut uses while recoverable text and raw evidence survive. Preserve legal cross-speaker overlap rather than enforcing one global non-overlapping timeline. Recognition confidence, timing uncertainty, and speaker uncertainty remain separate; never fabricate one accuracy percentage.

Use Lish's self-introduction, guest introductions, subsequent speech, and consistent episode-local voice assignments to map participants. Lish saying a guest's name is still Lish speaking. Neither A/0 nor B/1 is a participant identity convention. Confirmed metadata may name who appears in an episode without claiming which unresolved voice said a particular sentence. Clear source-supported identity should remain useful and consistent; labeling every clear passage unknown is not acceptance.

### I5. Optional corrections and conservative completion

Provide a lightweight readable corrections file targeting the exact source/timed-transcript version and stable speaker/turn/word references. Support episode-wide relabeling, merging duplicate voices, separating incorrectly combined speakers by selected turns, correcting passages, and splitting a combined turn at a supported source position without full retranscription. Preserve original versions and change lineage; reject incompatible correction bases clearly rather than silently applying them elsewhere.

Relabeling cannot change wording or timing. Text correction invalidates affected word alignment until checked and must not transfer old timing to new words as verified evidence. Supported timing corrections retain source-relative meaning. Apply corrections as new versions for subsequent generation; report which prior publishing artifacts became superseded instead of claiming they were regenerated automatically by an edit alone.

Unknown mapping retains anonymous labels and neutral topic-based publishing attribution. Unclear words carry an explicit marker and cannot become exact quotations or unsupported factual promises. Retain recoverable overlap without inventing missing dialogue or ownership. Unknown word timing may use reliable surrounding turn evidence where appropriate, never invented precision. Prefer another supported natural boundary when one is uncertain; report unavailable chapters/section planning if valid alternatives do not exist.

The separate completion report identifies the issue, source time or affected passage where known, affected artifact, fallback, and any unavailable result. Short examples support optional correction. It also distinguishes fresh, reused, unavailable, superseded, imported-with-limitations, and recovered results, preservation of human edits, and usage. Normal uncertainty must not introduce questions, required review, or review instructions inside copy-paste publishing text.

### I6. Publishing package and shared chapters

The final description contains, in order: an episode-grounded short hook; an overview naming Lish Speaks and confirmed guests; three to five specific takeaways; one episode-specific comment question and brief subscribe/share invitation; the shared chapter breakdown; and approved links plus supplied guest/sponsor information and approved recurring promotional text. Aim for 150–250 words before chapters/links as an editorial target. Do not pad or mechanically reject strong copy solely for missing that target. Use natural relevant topic language and no default hashtags.

Create exactly fifteen distinct, nonempty, grounded title concepts. Default to five topic/benefit, five curiosity/story, and five bold-perspective concepts. Adapt distribution when a formula would be forced, retaining meaningful variety and fifteen total. Every concept has a two-to-four-word complementary overlay, concrete visual direction covering subject/expression/composition, and a short pairing rationale. The approved prototype's concept/category identifiers and source ranges illustrate useful editorial traceability; its fixed text and exact JSON layout are not required golden outputs.

Each title is at most 100 characters; exclude angle brackets as recommended by the publishing-constraints research for title portability. The entire copy-paste description, including chapters, links, and promotion, is at most 5,000 characters. These are the accepted Studio-oriented constraints. The separate Data API byte limit belongs to a future uploader, not this CLI package.

Generate chapter data once. Render the identical ordered timestamp/title sequence into both the standalone list and final description; chapter changes must reassemble the description from that same version. A valid manual chapter list has 3–10 natural topic entries, begins exactly at `00:00`, uses strictly increasing distinct in-source timestamps, and leaves at least ten seconds in every chapter, including the last through source end. Fewer than ten is acceptable. Each standalone line is only timestamp, space, and a nonempty title: no heading, bullets, code fence, description, or subtitle. Use `MM:SS` below an hour and `H:MM:SS` when hours are needed. Preserve precise source times internally and validate actual rendered timestamps as well as structured bounds.

Chapter zero is a required format anchor. Other chapters follow supported natural conversation breaks; evenly spaced replacements to hit a count are invalid. Chapter validity does not guarantee platform feature availability for every channel/video. All chapter timestamps address the original episode, not future transition-augmented clips.

Checkpoint the description body, titles, and chapter data independently; final description assembly is local. If chapters fail, keep the successful body but do not present it as the required complete description. A label-only chapter edit reassembles the description without another model request. A known-invalid artifact is repaired within bounded attempts or unavailable; successful unrelated artifacts remain usable.

### I7. Source-relative three-section planning

Produce two internal section boundaries defining exactly three consecutive episode parts covering the source from zero through its duration once, with identical adjacent endpoints and no gaps or repetition. Preserve complete thoughts and natural topic boundaries before preferring similar durations. Unequal finished sections are acceptable; there is no added equality tolerance.

Let P1, P2, P3 be source-part durations and E, I, O the prepared episode-start, transition-in, and transition-out durations. Every prepared transition includes its total 2.5-second ending silence exactly once, preserving audible transition and natural decay. Excess trailing dead space is replaced to reach that total; 2.5 seconds is not appended to an already long silent tail.

| Finished section | Agreed assembly | Duration constraint |
| --- | --- | --- |
| 1 | Episode-start → part 1 → separate 1.5-second pause → transition-out | D1 = E + P1 + 1.5 + O; 600 ≤ D1 ≤ 1080 seconds |
| 2 | Transition-in → part 2 → separate 1.5-second pause → transition-out | D2 = I + P2 + 1.5 + O; 600 ≤ D2 ≤ 1080 seconds |
| 3 | Transition-in → part 3 → separate 1.5-second pause → transition-out | D3 = I + P3 + 1.5 + O; 600 ≤ D3 ≤ 1080 seconds |

Budget transition durations and pauses before choosing source boundaries. The separate 1.5-second pause does not replace or shorten any prepared asset's 2.5-second tail, including the final transition-out tail. Transition additions never shift stored source timestamps.

The planner consumes explicit transition asset revisions/prepared-duration evidence and settings. It does not prepare or export media. Real-episode acceptance must use verified prepared durations or clearly labeled fixture assumptions; absent duration evidence must be reported rather than replaced with fabricated precision. Preliminary estimates of E≈12.93, I≈6.59, O≈8.78 seconds are planning observations only, never approved trim points or hard-coded defaults.

When no valid natural split can satisfy all constraints, save an explained unavailable outcome with source duration, transition/pause budget, and limiting constraints. Do not force cuts, omit/repeat speech, label out-of-range sections valid, or wait for manual review. The 3369.842358-second Erica episode is already 129.842358 seconds longer than three 18-minute finished sections before transitions and must take this outcome. A valid proposal includes source revision, boundaries, transition/settings revisions, duration calculations, and boundary evidence/limitations. No valid proposal artifact is exposed for an impossible case.

### I8. Episode workspace, history, source references, and schemas

Use a canonical workspace per stable episode ID, with a readable name plus ID so equal basenames cannot collide. Paths are locators, not identities. Renaming/relocating identical bytes preserves recording identity; changed bytes create a new source revision. Keep episode/source metadata, current usable outputs, immutable history, durable state/provider evidence/input snapshots, and optional copied media distinct.

The user-visible current artifact contract comprises structured and readable timed transcript (`transcript.json`, `transcript.txt`), description (`description.md`), title concepts (`titles.json`), standalone chapters (`chapters.txt`), a valid section proposal when available (`section-boundaries.json`), and the completion report (`completion-report.md`). Current output presence is conditional on success and applicability. Missing required artifacts are named; older complete and partial versions remain addressable through history. Source media and raw provider responses remain outside copy-paste publishing files.

Reference original media by default with content fingerprint and stream properties. Copy only on explicit selection, verifying copied bytes. Missing/moved sources do not prevent operations using saved evidence alone; media-dependent operations report the missing source. Reattaching identical bytes preserves identity. Do not assume same-name media is identical or retranscribe to solve a locator problem.

Import legacy data explicitly into a new versioned workspace, preserving the original folder and files unchanged. Record import source/hash/schema and keep absent source fingerprint, speakers, settings, and timing confidence unknown. Import alone never makes a paid transcription call. Legacy text may support conservative publishing, while precise boundaries or valid chapters can be unavailable when evidence is missing.

Use explicit adapters for known legacy and v2 schemas; migrations create new versions and preserve original data. An unsupported future schema fails clearly instead of being loaded through an older model that silently drops fields. This supersedes permissive legacy loading where it would discard v2 information.

### I9. Durable checkpoints, coherent publication, and provenance

Checkpoint independently: source inspection/preparation; provider submission intent/job identity; completed raw response; normalized timed transcript; participant mapping/corrections; description body; title concepts; chapters; final description assembly; and section proposal. Later failures retain successful earlier work. Local assembly, formatting, and write recovery reuse saved successful responses.

Before exposing changed inputs, coherently mark/remove superseded current artifacts while retaining history. Write new artifacts temporarily, validate, then atomically publish files and committed version references through a recoverable manifest protocol. A reusable completed stage requires agreement between committed files and recorded hashes. Recover interruptions without presenting truncated, mixed-revision, or stale artifacts as usable.

Allow one writer per episode workspace. A second invocation reports the active run instead of launching duplicate work. Recover abandoned ownership after crashes without leaving a permanent lock or permitting overlapping paid submissions.

Persist stable episode, source-revision, artifact, operation, and run identifiers. Unchanged reuse retains artifact IDs. Speaker/turn/word references belong to their timed-transcript revision; corrections carry explicit lineage. Fresh transcription must not equate a new vendor A/0 label to an old voice automatically.

Each stage records schema/stage versions, consumed input and dependency hashes, requested provider/model/settings and endpoint, returned model versions/UUIDs when supplied, prompt/template version and exact rendered request content needed for provenance, response/request IDs, timestamps/status, output hashes, and separate actual/estimated/reserved usage. Snapshot consumed show profile, episode metadata, corrections, and transition settings. Preserve unknown model versions; generic AssemblyAI metadata and mutable publishing aliases are not immutable pins. Never retain API keys or authorization headers in provenance.

Detect direct publishing-file edits against the last generated hash. Before replacement, preserve the exact edited bytes as a distinct historical version and report it. Regeneration proceeds without requiring adjudication. Publishing-copy edits never become authoritative episode facts or timed-transcript corrections implicitly. Human-edited bytes cannot silently pass as the unchanged generated artifact under its old hash.

### I10. Persisted bounded recovery and usage accounting

For one transcription operation, allow at most one primary job plus one backup job under a shared configured deadline and spending allowance. Count accepted and possibly accepted submissions. Persist intent before sending a paid request and job identity immediately when returned; resume/poll known jobs instead of resubmitting. Retry transient status/download operations with bounded backoff. Retry submission only when demonstrably unaccepted or protected by documented provider idempotency; do not invent such a guarantee.

Ambiguous submission reserves both its possible charge and attempt slot. Reconcile through supported provider facilities when possible. If unresolved, backup can proceed only when remaining deadline, job count, and conservative spending reservation permit it; otherwise record the unresolved submission and retain work. Authentication/configuration errors are explicit failures, not infinite retries.

Persist attempts, IDs, elapsed/deadline information, actual/estimated/reserved usage, and unresolved charges across restarts. Ordinary resume grants no fresh allowance. Explicit fresh generation creates a separately recorded operation with possible new cost while retaining the previous ledger. A local deadline stops automatic waiting/new submissions; it does not prove remote cancellation or zero billing. Retain remote IDs/uncertainty for reconciliation, and recover an already completed response without silently submitting a new job.

The evaluation targets remain at most 15 minutes and $3 for typical 40-minute transcription/diarization including automatic recovery, excluding publishing-text generation. Admission uses conservative configured rates/reservations, not an advertised-price assertion of a verified hard cap. Actual costs remain unknown until observed. Missing billing access must not become zero usage or trigger unbounded retries.

Publishing generation permits at most three attempts per failed artifact/stage, including SDK retries and invalid structured-output retries, persisted across resumes. Ensure retry layers share that allowance instead of multiplying it. Retry only unsuccessful work. A saved successful provider response survives local formatting/write failures and does not require another paid request. Track publishing usage separately from the transcription allowance. Exhausted recovery preserves usable results and explicit failures.

### I11. Selective invalidation and regeneration

Dependency fingerprints use the inputs a stage actually consumes, including versioned configuration and rendered requests where relevant. Ordinary unchanged runs reuse saved profile/prompt/model snapshots; wall-clock time or a mutable alias alone does not silently invalidate existing work. Explicit source/configuration changes and requested regeneration create new work with retained history.

| Change | Invalidate/regenerate | Reuse when otherwise valid |
| --- | --- | --- |
| Source bytes or ASR/diarization request model/settings | Transcription and actual dependents | Independent configuration/history |
| Normalization logic with raw response saved | Normalization and downstream consumers | Raw provider response; no automatic paid retranscription |
| Confirmed participant names or speaker correction | Mapping and attribution consumers | Raw ASR and unchanged timing |
| Timed-transcript text correction | Text-dependent outputs and affected word alignment | Unaffected source/raw evidence |
| Timing correction | Chapters, embedded chapters, section boundaries | Text-only outputs with unchanged consumed inputs |
| Audience, voice, angle, supplied facts, publishing prompt/model | Publishing stages consuming changes and their dependents | Transcription and unrelated publishing stages |
| Chapter selection, label, or timing | Shared chapters and final description assembly | Saved description body when unchanged; label-only reassembly is local |
| Approved links/promotional text | Description content/assembly consuming them | Titles, ASR, and unrelated outputs |
| Title/thumbnail-only regeneration | Title concepts | Description, chapters, timed transcript |
| Transition assets, prepared durations, pauses, section limits | Section proposal | ASR and unrelated publishing copy |

If a normally publishing-only name/profile field is sent to ASR as a hint in a later configuration, it becomes part of transcription's actual fingerprint. Do not reuse a request under changed hints by relying on a static field-category assumption.

## Testing Decisions

### Test seam and prior art

**Proposed primary seam for review: the public episode-operation workflow, exercised through the CLI with an isolated real workspace and controlled external services.** Assert outcomes, output bytes/schema, committed artifact references/history, persisted attempts/reservations, and externally observable provider calls. Use deterministic provider/publishing fakes or cached responses, a controlled clock, and targeted I/O interruption at service/storage boundaries. Tests should survive internal refactoring; do not assert helper call order or exact generated prose. Restart/crash/concurrency cases must cross a real persistence/process boundary where needed to establish their behavior.

This one primary seam covers the coordinator, workspace/state store, models/normalization, participant corrections, generators/renderers, validation, and section planning together. Add narrow adapter contract tests only for provider unit/label/schema differences difficult to diagnose through the public operation. Source-audio and human editorial evaluations inspect the resulting artifacts from the same workflow; they are additional evidence, not new production entry points.

Prior art is the existing full-process/transcribe/generate interface, the early timed-transcript save that survives publishing failure, the approved prototype's one-off structure checks, and the managed-provider comparison's cached responses and analysis scripts. There is no configured reusable production acceptance suite. Prototype checks and one-off benchmark scripts are examples to adapt, not tests already passed by v2. Introduce a proportionate test harness during implementation; this specification adds no production tests or provider requests.

### Mandatory implementation acceptance requirements

All requirements below are open implementation acceptance work unless an existing evidence status is explicitly stated. Structural/recovery checks pass exactly. Editorial targets remain targets; human checks and measured timing cannot be replaced by schema validation.

| Gate | Required evidence and pass/failure behavior |
| --- | --- |
| A1 — Inputs and unattended workflow | Run solo and interview cases with confirmed metadata; validate real missing inputs. Ambiguous voice/name/wording, an unverified friend name, stale promotional context, and uncertain timing complete independent outputs with neutral supported copy and a separate useful report. No input/review prompt after required inputs. Clear supported identities remain consistently useful. |
| A2 — Timed-transcript structure/normalization | Validate schema, revision references, unit conversion, finite in-source intervals, positive usable durations, containment, faithful wording, unknown timing/confidence, and overlap/order preservation. Replay Deepgram mixed-speaker utterances and AssemblyAI early utterance bounds/zero-duration words. No parent-label propagation, blanket host-label convention, invented durations, or annotation markup in publishing prose. Preserve raw evidence. |
| A3 — Corrections/provenance | Exercise relabel, merge, separate selected turns, supported split, text correction, timing correction, and incompatible base. Relabel preserves timing/text; wording changes invalidate affected alignment; old versions survive; only real downstream consumers become stale. Check consumed revisions/settings/prompts/request evidence and secret exclusion. Unknown legacy/model information stays unknown. |
| A4 — Publishing structure | Exactly 15 distinct nonempty titles, each ≤100 characters, no title angle brackets, each with a 2–4-word overlay, subject/expression/composition direction and rationale. Check obvious duplicates and required fields mechanically. Description follows approved section order, 3–5 takeaways, one episode question and brief subscribe/share invitation, approved/supplied links/promotion only, no default hashtags, and ≤5,000 characters in full. The 5/5/5 mix and 150–250-word body are editorial targets, not inflexible rejection gates. |
| A5 — Chapters and assembly | A valid list contains 3–10 natural entries, initial `00:00`, strictly ascending distinct rendered in-source timestamps, nonempty title-only lines, and every duration ≥10 seconds including the last. Check under/over-hour rendering, rounding effects, empty/duplicate labels/times, too-short final chapter, and invalid count. Embedded and standalone lists use the same committed chapter data and match exactly. Invalid/unavailable chapters do not leave a falsely complete description; preserve its body and other work. |
| A6 — Source timing | Complete the targeted source annotations below. Every reviewed point anchor has absolute error ≤1.0 second; each reviewed cut lands inside its independently annotated safe interval and preserves words/complete thoughts. Report every sampled error, maximum, and coverage. Test original offsets through music, pauses, transport/preprocessing, and corrections. A good mean/median or provider agreement cannot conceal a failed hard boundary check. |
| A7 — Section proposals | Test exact full coverage/order/adjacency, explicit transition durations, all inclusive 600/1080-second endpoints, just-outside failures, transition-overhead failures, gaps/repetition, and unequal valid sections. Include each transition's 2.5-second tail once and the distinct 1.5-second pause. Erica yields explained impossibility while publishing completes. A synthetic positive proves arithmetic only; a source-reviewed feasible communication case supplies natural-cut evidence with verified durations or labeled assumptions. |
| A8 — Reuse and invalidation | An unchanged completed rerun makes zero new paid calls and retains artifact IDs. Resume known jobs and successful checkpoints. Exercise every I11 change, including chapter-label-only local assembly and ASR hints when configured. Only actual consumers/dependents rerun. Preserve previous complete/partial versions and direct edits as exact bytes before replacement. Publishing edits do not become source facts. |
| A9 — Durable current/history behavior | Inject late-stage failures, temporary-write/commit interruption, corrupt/mismatched hashes, input revision changes, and concurrent invocations. No truncated, stale, or mixed-revision artifact is exposed as valid; successful work survives; one writer owns the workspace; abandoned ownership recovers; no duplicate paid jobs result. Missing required artifacts yield honest partial/failed outcomes. |
| A10 — Bounded recovery | Simulate failed primary, accepted-job recovery, ambiguous accepted status, demonstrably unaccepted submission, backup, expired deadline, unavailable billing, exhausted allowance, and restart in each state. At most one primary plus one backup job including possibly accepted jobs; reserve possible charges, reconcile known IDs, retain ledgers/deadlines, and deny unaffordable submissions. A timeout never proves cancellation/free usage. Publishing uses at most three failed-stage attempts including SDK and invalid-output retries; local failures reuse saved successful responses. |
| A11 — Source identity and imports | Exercise equal-basename different recordings, moved/missing source, identical reattachment, changed bytes, explicit verified copying, and explicit legacy import with zero transcription calls. Preserve original legacy files/folders, unknown speakers/settings/timing, and useful text-only operation. Unsupported future schema fails clearly; migrations preserve originals. Missing evidence honestly limits chapters/precise boundaries. |
| A12 — Speech and editorial acceptance | Review affected actual v2 corpus outputs before first release and after material provider/model/prompt changes using the rubric below. No meaningful omission, changed meaning, invented claim, or incorrect confident attribution may remain unhandled in affected usable content. Use conservative fallback or supported correction while preserving raw/original evidence. No exact generated-text snapshot equality; model critics alone cannot approve truth/voice. |
| A13 — Full-operation time | Measure near-40-minute communication transcription/diarization for normal primary and a controlled fallback path against the 15-minute target, including required local preparation, upload, processing/polling, normalization, and recovery. Record source duration, environment, phase times, settings, trial count, accepted/uncertain requests, and limitations. Exclude publishing generation from this target and measure it separately. |
| A14 — Actual-cost verification | Establish account-specific rates for the configured endpoints/settings, including relevant opt-out adjustments, and available billed deductions/usage for primary and controlled fallback against the $3 transcription/diarization target. Keep actual/estimated/reserved usage distinct. Use an explicit bounded evaluation allowance. Missing billed amounts leave cost acceptance incomplete, not zero or a verified hard cap; retain conservative admission tests and explain access limits. Simulated usage cannot stand in for observed billing. |

### Reference corpus and pending annotations

Use the accepted two-episode corpus plus cached responses and small synthetic recovery/state fixtures. Keep media outside version control and identify fixtures by content fingerprint and original-source time rather than basename alone. Annotations record source revision, exact reviewed interval, annotation type, reviewer/provenance, and uncertainty. Keep provider output and historical timed transcripts distinct from source-reviewed truth.

| Reference | Identity and coverage | Required remaining evidence |
| --- | --- | --- |
| Communication solo | 2306.182676-second WAV; SHA-256 `6169e359350d60b36f748b84b4d69f21183d94319a9b8812fcd5f91476b3d787` | Verify content/timeline correspondence to the historical communication source; annotate early/middle/late timing and a feasible natural split; obtain representative complete-operation performance/cost evidence. Existing duration match alone is insufficient. |
| Erica Campbell interview | 3369.842358-second WAV; SHA-256 `48889a5fe1e5aade91c433244aceb0da8ced86435f713db1bf533f20b2637e13` | Annotate precise word/turn/chapter anchors and safe intervals; verify real simultaneous overlap if present. Cover cold open/music, short answers, introductions, later identity consistency, closing speech, and impossible split. |
| Approved communication publishing prototype | User-approved description, all 15 concepts, visual briefs, and operator presentation | Use as an editorial reference, not source/timing truth, exact text snapshots, or evidence that production automation passed. |
| Cached/synthetic inputs | Two preserved provider responses and focused constructed cases | Implement deterministic structure, uncertainty, arithmetic, import, persistence, and recovery tests; synthetic success does not prove real audio quality. |

Candidate original-source review windows are communication 749–759, 1501.84–1511.84, and 2230.67–2240.67 seconds; Erica introductions 70–90 and later conversation 2395–2455 seconds. Existing Erica speaker checks cover 162–176, 1002–1017, and 3299–3308 seconds. Together these are about 2.5 minutes including the already reviewed 38 seconds. Extend/adjust only to capture complete thoughts, a feasible positive section case, or independently verified overlapping speech. Full manual transcription of both episodes is not required. The offered communication MP3 is unnecessary for this initial set.

For point anchors, record actual word/turn/chapter starts independently from source audio. For section cuts, annotate safe gap intervals and complete-thought suitability. Neither waveform silence alone nor a plausible historical/provider sentence establishes editorial safety. Chapter zero is formatting, not evidence of a natural transition. Preserve uncertainty in reference spans rather than manufacture precise truth. Choose reliable alternative boundaries or explicitly report unavailability.

Existing listening truth is limited: Erica says “Hello,” “Six,” “Harmonica,” “my sisters, my kids,” and “I don’t think it will.” AssemblyAI matches four of those five selected disputes and Deepgram one; this is not representative accuracy. Both participants say “thank you” in the close, but exact ownership, order, and simultaneity remain unknown. Exclude the thanks observation from single-speaker scoring and do not manufacture a timed-overlap annotation. The earlier requested listening answers are complete; the new source-timing annotations are pending acceptance work.

Compute word/proper-noun/speaker error diagnostics only over adequately annotated material, with sample counts, duration/coverage, and method. Establish baselines without an arbitrary aggregate WER/diarization cutoff for this small corpus. Provider agreement and the five deliberately selected disputes are not full-episode error rates. Preserve and explain each material omission, changed meaning, or wrong confident attribution and its conservative downstream handling; blanket uncertainty is not a substitute for useful speaker-aware output.

### Editorial review and performance evidence

Before first release and after material provider, model, or publishing-prompt changes, a human reviews the affected actual v2 corpus outputs for source/metadata fidelity; warm, candid, practical, appropriately faith-grounded voice; fifteen meaningfully varied grounded promises; complementary overlays and actionable visual directions; natural chapters and safe feasible cuts; and an honest completion report usable without episode knowledge. Correct or conservatively handle material errors before affected output is considered usable. Rerun affected checks after changes. Routine episodes use automated gates and conservative completion with optional review afterward.

The approved prototype favorites are T01, “5 Communication Skills for More Honest Relationships”; T06, “You Said Everything. Why Do You Still Feel Unheard?”; and T13, “Keeping Quiet Isn’t Always Keeping the Peace.” All fifteen concepts were approved. Favorites are examples, not performance rankings, required formulas, or the only acceptable strings. No production preview variant was selected; the blocked agent browser smoke check does not undo the user's editorial approval or establish browser verification.

Existing Erica observations are one run per provider: AssemblyAI result observed within 3:04 and Deepgram in about 24 seconds, including uploads and excluding previously performed FLAC preparation. These do not establish complete-operation runtime for typical episodes or SLAs. The comparison's approximately $0.457 combined advertised baseline estimate was not a billed deduction. Deepgram billing scopes returned HTTP 403; AssemblyAI timed-transcript responses did not supply billed dollars. Do not mark A13/A14 passed from those observations. Record inaccessible exact costs as incomplete evidence and preserve the $3 target without asserting a verified hard cap.

## Out of Scope

- Production code, provider calls, new audio annotation, and release approval in this specification-only task.
- Cutting, trimming/preparing transition media, stitching, rendering, exporting, or uploading the three finished sections. Final export format, loudness targets, and trimming/rendering technology belong to the later media effort; the agreed asset order, source boundaries, pauses, and arithmetic remain binding interfaces.
- Finished thumbnail-image generation, show/playlist artwork production, YouTube upload automation, automatic publishing, and analytics-driven title ranking or A/B testing.
- Non-English support, default live web research, voice enrollment, mandatory local ML/forced alignment, or unvalidated chunk stitching.
- A separate transcript-editing product, mandatory corrections, or a human approval queue for routine episodes.
- Treating historical speech recognition as a quality golden, promising every word has verified timing, treating provider confidence/agreement as accuracy, or claiming measured view/ranking improvements from packaging.
- Adopting the throwaway prototype's web interface, any one preview layout, fixed sample content, or all researched links as production requirements.
- Reopening resolved Wayfinder choices or using missing implementation evidence as a new product-discovery phase.

## Further Notes

### Authority and traceability

The following source resolutions and all their available comments were reviewed. These links are the canonical decision history; the consolidated behavior above resolves earlier proposals in favor of the accepted outcomes.

| Decision | Contract carried forward | Implementation/gates |
| --- | --- | --- |
| [#3 — Compare transcription and diarization architectures](https://github.com/jimmyblain/podcast-processing/issues/3) | Provider-neutral evidence and limits of vendor claims; candidate research superseded by final provider choice | I3–I4; A2, A6, A12–A14 |
| [#4 — Choose pipeline state, recovery, and provenance behavior](https://github.com/jimmyblain/podcast-processing/issues/4) | Workspace identity, history, imports, committed checkpoints, reuse, direct edits, bounded recovery | I8–I11; A3, A8–A11, A14 |
| [#5 — Verify YouTube publishing-package constraints](https://github.com/jimmyblain/podcast-processing/issues/5) | Exact chapter syntax/durations, title/description constraints, grounded discoverability | I6; A4–A5 |
| [#6 — Prototype the copy-paste-ready publishing package](https://github.com/jimmyblain/podcast-processing/issues/6) | Approved voice, 15 concepts, visual briefs, and completion presentation; approval limits | I2, I5–I6; A1, A4, A12 |
| [#7 — Define the timed transcript and speaker-correction contract](https://github.com/jimmyblain/podcast-processing/issues/7) | Speech fidelity, source-relative timing, identity separation, overlap, optional corrections, unattended completion | I4–I5; A1–A3, A6, A12 |
| [#8 — Define authoritative episode metadata and publishing requirements](https://github.com/jimmyblain/podcast-processing/issues/8) | Inputs, approved audience/voice, description order, 15 concepts, natural shared chapters | I2, I6; A1, A4–A5, A12 |
| [#9 — Define the three-section boundary contract](https://github.com/jimmyblain/podcast-processing/issues/9) | Complete coverage/thoughts, 600–1080 seconds including transitions, separate pauses, impossibility | I7; A6–A7 |
| [#10 — Define quality gates and the evaluation corpus](https://github.com/jimmyblain/podcast-processing/issues/10) | Two-episode corpus, exact hard checks, sampled timing, diagnostic speech metrics, review cadence, outstanding evidence | All A1–A14 |
| [#11 — Choose the transcription and diarization architecture](https://github.com/jimmyblain/podcast-processing/issues/11) | AssemblyAI primary/Deepgram backup, full-episode word-based normalization, conservative identity, measured evidence limits | I3–I5, I10; A2, A6, A10, A12–A14 |

Research read: [YouTube publishing constraints at 7269d82](https://github.com/jimmyblain/podcast-processing/blob/7269d82/docs/research/youtube-publishing-constraints.md), [architecture options at 08e49f8](https://github.com/jimmyblain/podcast-processing/blob/08e49f8/docs/research/transcription-diarization-options.md), and [accepted managed-provider comparison at 1938edb](https://github.com/jimmyblain/podcast-processing/blob/1938edb/docs/research/managed-transcription-comparison.md). The local audience/voice research was also read; its approved subset is recorded in #8. Earlier pricing, optional exclusive-overlap representations, mandatory review proposals, and unapproved profile candidates do not override the later resolutions.

Prototype read: [approved sample at 05cc30b76389b5ec0e029baf51014f2b98519d9b](https://github.com/jimmyblain/podcast-processing/tree/05cc30b76389b5ec0e029baf51014f2b98519d9b/src/podcast_processor/publishing_package_prototype), including source/instructions, description, all titles, chapters/evidence, package, completion report, and [recorded approval](https://github.com/jimmyblain/podcast-processing/blob/05cc30b76389b5ec0e029baf51014f2b98519d9b/src/podcast_processor/publishing_package_prototype/REVIEW.md).

The domain glossary's distinctions remain controlling: a speaker is an anonymous voice, a participant is a known person, a YouTube chapter is a timestamp/title, a section boundary is a proposed source cut, an episode part covers source content, and a finished section includes transitions/pauses. The accepted v2 decisions intentionally replace the legacy local-only/ten-title/chapter-description behavior; old implementation documentation describes the current baseline rather than overruling v2.

### Evidence ledger at specification handoff

| Evidence | Status now | Completion requirement |
| --- | --- | --- |
| Description voice, 15 title concepts, actionable briefs, operator reference | User approved in prototype | Review actual v2 outputs under A12; do not require reapproval of the same product preferences |
| Five Erica phrase identities and both-speaker thanks | User supplied; selected limited sample | Preserve annotations and limits; additional time/overlap truth remains open |
| Erica provider outputs, settings, hashes, structural analysis, observed elapsed times | Available, one run each | Reuse cached evidence for A2; obtain complete representative A13/A14 evidence |
| Communication source correspondence, precise anchors, safe cuts | Pending source review | Complete targeted annotation and A6/A7 real feasible case |
| Erica precise anchors/safe intervals and verified simultaneous overlap | Pending targeted annotation | Complete source-relative references; do not infer from the thanks observation |
| Production structural, correction, state, import, and recovery suite | Specified, not implemented or run | Implement and pass A1–A11 |
| Account-adjusted rates, actual billed deductions, representative normal/fallback performance | Pending; previous billing access limited | Complete A13/A14 or explicitly retain incomplete cost evidence without claiming a verified cap |
| First-release actual-output editorial review | Required during implementation | Complete A12 before release; prototype approval alone is insufficient |

The ignored local evaluation-corpus manifest records exact source locations/fingerprints and candidate windows. The ignored Erica provider-comparison bundle contains raw responses, requests/timings, fingerprints, one-off analyses, and the listening-check annotations. Preserve those bundles, existing untracked media, the local domain glossary, and audience research. Do not commit private recordings, credentials, or raw local benchmark bundles as part of this specification.

### Sequenced implementation handoff for review

This is a proposed breakdown for subsequent build tickets, not tickets dispatched or production work started by this specification. Each build ticket must link the relevant I/A identifiers, preserve evidence status, and include observable acceptance outcomes. The sequence delivers through the common public operation seam instead of independently shipping internal scaffolding with no user-visible proof.

| Step | Deliverable and dependency | Acceptance attached |
| --- | --- | --- |
| B1 | Establish versioned episode inputs/workspace, explicit legacy import, public generation-from-preserved-data path, and isolated workflow harness; preserve existing media/output folders | I1–I2, I8–I9; A1, A9, A11, initial A3/A8 |
| B2 | Integrate full-episode provider adapters, raw-result checkpoints, word-based normalization, persisted submission/recovery ledger, and transcription-only operation; depends on B1 | I3–I4, I9–I10; A2, A9–A10; no paid evaluation needed for deterministic mechanics |
| B3 | Add supported participant mapping, faithful readable timed transcript, optional corrections, lineage, selective invalidation, and nonblocking uncertainty outcomes; depends on B2 | I4–I5, I11; A1–A3, A8, A12 speech cases |
| B4 | Deliver approved publishing generation, independent artifact checkpoints, shared chapter rendering, validation, selective regeneration, and honest partial reports; depends on B1/B3 | I2, I5–I6, I9–I11; A1, A4–A5, A8–A10, A12 editorial rubric |
| B5 | Deliver source-boundary proposal/explicit impossibility using transition budgets, with no media export; depends on B3 and workspace outcomes | I7; A6–A7, transition-change portion of A8 |
| B6 | Consolidate complete process/resume/fresh-operation flows, history/manual-edit preservation, concurrency/crash recovery, migrations, and documentation; depends on B2–B5 | All deterministic A1–A11, particularly cross-stage failure/restart cases |
| B7 | Complete targeted audio annotations and source correspondence, evaluate actual v2 timing/speech/editorial output, and measure bounded normal/fallback complete-operation runtime plus account-adjusted billed usage; source annotation may begin alongside B1–B6 | A6–A7 and A12–A14; publish per-gate evidence and coverage, retain unmet/inaccessible evidence as incomplete |

Specification completeness means the decisions, interfaces, scenarios, and pending acceptance obligations are ready to implement. It does not mean production gates passed, real cut timing is verified, costs were observed, or implementation/release has been approved by this review.
