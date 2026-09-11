# Podcast pipeline v2 — specification and operator-experience audit

Status: **September 10, 2026. The user confirmed the consolidated contract: “Yes we are in agreement.” Corrective implementation and its acceptance remain open.**

The first new-episode run exposed a gap between the completed specification's
intended operator workflow and the evidence used to close it. This audit compares
the original decisions, implementation, tests and actual saved outcomes. It is not
a new release approval, an implementation change or a blanket certification of
the code. No new paid requests or source-audio listening were performed for it.

Baseline: local `04b2417`, merged into main by PR #21 as `0382404`. The earlier
mypy/256-test verification remains valid for its tested behavior; those passes do
not prove capabilities that the tests supplied as fixtures. This audit qualifies
the earlier broad completion claim in the [specification](podcast-pipeline-v2.md).

## Confirmed scope and user feedback

- A normal episode should use the recording and confirmed guest names or solo
  status, plus approved reusable show configuration. Normal uncertainty must not
  require the operator to know the episode or adjudicate corrections.
- The intended section proposal includes discovering two suitable natural cuts.
  Supplied candidate validation alone does not deliver that operator workflow.
- Exactly three source parts, full ordered coverage, and 10–18-minute finished
  sections remain the accepted constraints. Section 3 retains its opening
  transition and original episode ending, with no added closing pause/outro.
- Actual transition preparation, cutting, stitching and media export were
  explicitly deferred in the original specification. In interview round 1 the
  user approved adding one-time preparation and saved reuse of transition audio
  alongside reusable show configuration. Cutting/stitching/export of episode
  sections remains a separate phase.
- The terminal should acknowledge startup, report meaningful progress, and finish
  with concise outcomes and actions. Detailed diagnostics belong in the saved
  report. This feedback is already approved in issue #22.
- The missing historical Deepgram fallback charge remains the accepted
  nonblocking exception in #20. It is not a verified zero charge or a new reason
  to reopen billing acceptance during this interview.

## Evidence and gaps

| Area | What was promised or decided | Observed behavior | Classification |
| --- | --- | --- | --- |
| Automatic section proposals | I7 produces two natural source boundaries; ordinary episode inputs do not include operator-authored candidate lists. | New-workspace planning creates source/transcript references but leaves transitions absent and candidate boundaries empty. No candidate search is attempted. | Missing part of the intended workflow. |
| Transition setup | I7 consumes explicit prepared-duration evidence; media preparation/export was deferred. | No reusable transition registration/default loading exists. Current planning needs episode-specific evidence with asset revisions, durations, transcript hash and word references. | Deferred prerequisite with an unfinished setup experience. |
| Participant mapping | I4 uses introductions, subsequent dialogue and consistent voice assignments; blanket unknown identity is not acceptance for clear passages. | The new interview has two detected speakers, both unresolved. Exact-name self-introductions and narrow welcome patterns do not cover its opening dialogue and spelling variation. | Demonstrated limitation and likely implementation shortfall; no source-listening claim about the correct assignments. |
| Conservative publishing attribution | I5 requires neutral topic-based attribution when identity is unresolved. | The same saved description attributes personal experiences to the named guest despite both speakers remaining unresolved. The prompt states the guardrail; structural validation does not enforce it. | Observed inconsistency requiring investigation/fix; not proof the named claims are factually false. |
| Terminal feedback | Concise useful outcomes and the user's new progress-feedback requirement. | Silence during work, then a full diagnostic dump including recovered retries, raw usage, IDs and repeated timing notes. | Tracked in #22, including concise completion requirements. |
| Direct publishing edits | Preserve exact edited bytes before replacement; edits do not become source facts. | Reconciliation, including inspect, archives direct edits and removes those files from the usable current set. Later processing can restore generated outputs. No dedicated history browsing/restoration command. | Narrow preservation contract implemented; desired editing experience needs clarification. |
| Reusable editorial configuration | Approved identity/audience/voice; links and promotional copy only when approved/configured. | Built-in identity/audience/voice exist. Links/promotional text default empty; a custom profile must be supplied for each new workspace. | Configuration/onboarding question, not proof approved links were omitted. |
| Completion semantics | Preserve independent publishing and explain impossible/unsupported planning outcomes. | Missing planning prerequisites and genuinely impossible constraints both permit a completed process outcome. | Documented behavior; missing capability was obscured by the same fallback used for legitimate impossibility. #22 addresses presentation, not all status semantics. |
| Costs and deadlines | $3/15-minute transcription target; publishing separately accounted with bounded attempts; unknown bills stay unknown. | Transcription admission/deadline and publishing attempt limits exist. No equivalent whole-operation dollar allowance or automatic per-episode bill reconciliation. | Consistent with the stated contract; any broader budget control is an explicit new decision. |

Code/evidence pointers: [planner](../../src/podcast_processor/planning.py),
[planning input contract](../section-planning.md),
[participant mapping](../../src/podcast_processor/participants.py),
[publishing prompts](../../src/podcast_processor/publishing_prompts.py),
[publishing validation](../../src/podcast_processor/package.py),
[workspace reconciliation](../../src/podcast_processor/workspace.py),
[CLI](../../src/podcast_processor/cli.py), and
[completion reporting](../../src/podcast_processor/workflow.py).

The saved new-episode run completed transcription and publishing in approximately
3m58s. Chapter generation recovered on its second attempt. Its 130 words with
unusable precise timing were retained. Section planning did not establish
impossibility: the approximately 39m49s source was never given candidate cuts or
transition durations. Private episode text, IDs and raw evidence stay in the
ignored workspace; they are not copied into this audit.

## What acceptance demonstrated, and what it did not

- The default integrated test explicitly expects unavailable sections. The valid
  integration supplies synthetic candidate evidence. This proves validation and
  arithmetic, not candidate discovery.
- Real Communication acceptance used user-supplied cuts and explicitly hypothetical
  E=55/I=50/O=50-second transitions. Independent listening later established the
  cuts' safe intervals. It did not establish automatic new-episode discovery or
  preparation of the supplied transition recordings.
- The approved Erica publishing package followed fifteen supported correction
  operations, including participant mapping. It establishes corrected-input
  publishing quality, not robust automatic mapping for an unseen interview.
- There is substantial implementation/test evidence for preserved transcription,
  fifteen title concepts, shared chapters, authoritative spelling, optional
  corrections, selective reuse, explicit import, source identity/reattachment,
  exact edit archives, ownership, real crash recovery, accepted/ambiguous provider
  slots and persisted deadlines. This audit did not uncover another missing
  production stage in those areas; it did not rerun a full correctness review.

See [workflow acceptance](../workflow-acceptance.md),
[source acceptance](../source-acceptance.md),
[integrated tests](../../tests/test_episode_workflow.py), and
[planning fixtures](../../tests/test_section_planning.py).

## Existing tickets

- [#22 — Show live terminal progress during episode processing](https://github.com/jimmyblain/podcast-processing/issues/22): open; includes concise final summary, preserved detailed diagnostics, and honest unavailable-section explanations. It does not implement candidate discovery or reusable transition setup.
- [#20 — Reconcile the outstanding Deepgram fallback charge](https://github.com/jimmyblain/podcast-processing/issues/20): open, nonblocking, scoped to the historical accepted fallback request. It does not supply a new whole-job spending control or routine billing integration.
- #12 and #17 remain closed as of this audit. Their closure must not be treated as
  proof of automatic candidate discovery. No tracker status was changed by this
  interview's initial evidence pass.

## Design tree and interview record

Already settled: unattended normal processing; conservative uncertainty;
automatic proposed boundaries as intended output; fixed section arithmetic and
final ending; source-relative times; preserved independent work; #22 feedback;
nonblocking #20. These are not new approval questions.

### Round 1 — accepted decisions

The user accepted recommendations 1–4 and deferred additional cost control:

1. **Reusable show setup:** prepare and remember transition audio, approved links
   and recurring promotional copy once. Ordinary episodes require recording and
   guest names or solo status. The user emphasized that these defaults, especially
   the transition recordings, rarely change.
2. **Readable handoff:** readable documents accompany structured title/thumbnail
   concepts and section proposals. Show all fifteen pairings; for each proposed
   section show source start/end, expected finished duration, and cut rationale.
   Actual section-audio export remains a separate phase.
3. **Edits remain current:** ordinary inspection and unchanged reruns retain the
   user's publishing edits. Explicit regeneration may replace them while keeping
   earlier versions. Publishing edits still do not become timed-transcript facts.
4. **Missing setup is partial:** successful publishing with unattempted sections
   due to missing setup is a needs-setup/partial result. A genuinely impossible
   split may complete with an explanation under the previously agreed behavior.
5. **Cost controls deferred:** prioritize getting the workflow working, then assess
   reasonable costs. Retain existing admission/deadline/attempt limits and usage
   distinctions. Do not add a new publishing/planning budget-control requirement;
   #20 remains nonblocking. This preference is not unlimited authorization for
   live paid experiments.

### Round 2 — accepted decisions and workflow emphasis

6. **One-time transition approval:** prepare the existing three recordings using
   the agreed rules, let the user hear the results once, and save those approved
   versions for routine reuse. Revisit only when the recordings/settings change.
7. **Respect completed edits:** the user almost never reprocesses the same content;
   a new processing run would usually start from a new recording. Preserve the
   user's edited output as they left it. Do not build a competing-draft workflow
   or make rare rerun cases the center of the product. Explicit replacement can
   retain prior history, but inspection/resume must not discard or rewrite edits.
   This answer supersedes the proposed automatic separate-draft behavior in Q7.
8. **No automatic rewriting of user edits:** keep the operator's exact wording.
   Format problems may be identified without changing the file or blocking
   independent work. Existing generated chapter consistency remains required;
   detecting conflicting manual edits is not authorization to choose a winner or
   rewrite the operator's files. Stale/invalid evidence must not be labeled valid,
   but protecting that distinction must not erase the edited deliverable.
9. **Initial recurring links:** include Lish's website, Instagram, and the podcast
   website. Start without an additional recurring promotional paragraph. The user
   approved starting with these recommended obvious items, not every candidate
   link or researched schedule. Initial approved URLs:
   - https://www.lishspeaks.com/
   - https://www.instagram.com/lishspeaks/
   - https://www.illjustletmyselfin.com/

The interview's decision frontier is now empty for this corrective scope. The
normal journey is one new recording in and useful outputs out. Recovery remains
background protection; advanced editing, competing drafts, history browsing UI
and expanded cost controls are not added workstreams by inference.

Setup facts have been checked: all three original transition recordings are
present and match their earlier saved fingerprints. No verified prepared versions
or approved trim points were found. The agreed preparation behavior remains
preserving audible transition/natural decay and replacing excess tail with
exactly 2.5 seconds total ending silence; the user need not supply durations.
Existing saved show profiles have empty links/promotional text. The approved
identity/audience/voice remain reusable; round 2 now selects the initial links
listed above for future setup. Existing episode outputs have not been changed.
The host homepage was checked again on September 10 and still links the podcast
library, YouTube, Instagram, Apple Podcasts and Spotify:
[official host site](https://www.lishspeaks.com/).

Source-attribution guardrails and missing candidate discovery remain implementation
obligations. The final acceptance plan must exercise a normal new-episode run
without hand-authored speaker mappings or cut candidates replacing those stages.

## Consolidated operator contract

Set up the show once: approved identity/voice, the three selected recurring links,
and prepared transitions whose audio the user approves once. For each new episode,
supply its recording and guest names or solo status. The tool performs the complete
workflow with visible terminal progress and no requirement to author evidence JSON,
map ordinary clear speaker introductions by hand, or choose the section cuts.

The result includes a useful speaker-aware timed transcript, a ready-to-use
description with the same chapters as the standalone list, fifteen readable
title/thumbnail pairings, and a readable three-section proposal with source ranges,
finished durations and reasons. Structured artifacts remain available. When the
source supports no valid split, explain the limiting condition and preserve all
independent outputs. Missing setup is reported as incomplete/needs setup, not as
proof that no valid split exists. Actual episode cutting/stitching/export remains
a separate phase.

Make supported speaker identity useful; retain uncertainty when the evidence is
insufficient and keep named publishing claims consistent with that uncertainty.
Optional corrections remain available without becoming routine prerequisites.
At completion, show outcomes, output location and useful next actions. Preserve
detailed diagnostics separately. Respect edits after delivery and retain existing
recovery and cost safeguards without expanding those product surfaces now.

## Corrective work and proof of completion

1. Deliver reusable show setup and real prepared-transition measurements, using
   the existing recordings and the selected recurring links. Demonstrate reuse on
   a second episode without repeating preparation or link configuration.
2. Generate and evaluate natural boundary candidates from an episode's preserved
   evidence, then feed the existing duration/coverage checks. The new-episode
   workflow must attempt this stage without operator-authored candidate lists.
3. Broaden supported participant identification beyond the narrow current string
   patterns and enforce conservative named attribution in publishing. Demonstrate
   useful automatic identification on a fresh interview and honest fallback where
   evidence is insufficient; do not replace that test with pre-mapped fixtures.
4. Produce readable title/thumbnail and section handoffs from the same underlying
   data as the structured outputs. Demonstrate the operator can use them without
   reading JSON or interpreting raw second-based formulas.
5. Complete #22's live progress and concise final summary, and distinguish missing
   setup from a genuinely unavailable split in operation outcomes. Test that
   absent capability/configuration cannot appear as successful section generation.
6. Preserve direct user edits during ordinary inspection/resume. Demonstrate this
   with exact bytes and no automatic replacement or forced editing workflow;
   invalid/stale evidence retains honest status without destroying the copy.
7. Verify the complete journey after one-time setup on a new episode, including
   proposed cuts produced by the tool, supported participant mapping, approved
   recurring links, readable handoff and concise feedback. Human evaluation may
   assess the resulting source fidelity and cut quality for release acceptance;
   it must not silently provide missing production-stage inputs beforehand.

Retain focused deterministic recovery/validation tests, but pair them with this
ordinary operator journey. Reconcile #12/#17 and their acceptance records with
these observed gaps and completed fixes. #22 already owns terminal presentation;
avoid duplicate tickets for it. #20 remains the existing nonblocking billing task.
The current interview does not authorize unlimited paid trials; use bounded live
evaluation only when specifically authorized.

The user confirmed shared understanding after both interview rounds. The
consolidated contract is approved for corrective ticketing and implementation;
its approval is not evidence that the missing behavior has been delivered.
No product code or episode artifacts were changed during this audit. The original
source/editorial approvals and nonblocking billing exception remain recorded with
their original scope.
