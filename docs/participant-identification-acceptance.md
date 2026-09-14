# Participant identification evidence — issue #25

## Automatic saved-interview evaluation, September 14, 2026

The production `map-participants` operation ran on an isolated copy of the saved
interview from the experience audit, before any optional participant corrections.
Both previously unresolved voices acquired supported associations. Evidence includes
the host-role opening, a named introduction with recognition-spelling variation,
the guest's acknowledgment after brief greetings and a later first-person
introduction on the same voice. Earlier and subsequent turns follow their preserved
episode-local voice IDs. The authoritative participant spellings come from the
existing confirmed episode metadata.

All source segments, words, timestamps and anonymous voice IDs remained identical.
The original workspace was preserved. Repeating the operation reused the exact
mapped transcript bytes. No transcription, publishing or other service request was
made, and no correction or manual mapping supplied the result.

The [machine-readable record](evidence/participant-identification-2026-09-14.json)
pins transcript hashes, evidence kinds and the scope of these checks. Private text,
names, exact turn references, immutable history and detailed local results remain in
`output/acceptance-issue-25-2026-09-14/` (ignored). The original episode workspace and
the earlier evaluation bundles remain intact.

## Limits and final acceptance

These associations have supporting transcript context; they are not independently
verified real-world voice identities. No source listening or new human publishing
approval occurred. The old description's attribution inconsistency does not prove
any particular private claim false. Previously approved corrected-input packages
retain their original scope and were not reclassified as automatic-output acceptance.

Issue #28 must evaluate the initial automatic transcript and publishing package
against the source before optional corrections, alongside the remaining ordinary
episode workflow. The new conservative publishing policy still needs that real
editorial evaluation. This implementation record does not close that release gate
or create a mandatory per-episode identity review.

## Deterministic coverage

`test_participant_identification.py` exercises fresh managed recognition and full
`process` through the public CLI. It covers a host-role opening, recognition spelling
variation in both names, greeting/acknowledgment exchanges, earlier and subsequent
voice continuity, conflicting introductions, name mentions, multiple responding
voices and unchanged checkpoint reuse. No fixture preassigns the new interview's
participants. Existing correction tests retain exact evidence and recovery coverage.

`test_publishing_attribution.py` verifies repaired and exhausted attribution attempts,
approved presence spelling, useful neutral copy, aliases/possessives, first/third-person
references, host/guest descriptions, title/overlay/visual/chapter fields, quotations
owned by another voice, supported exact quotations and later anonymizing corrections.
It checks independent outputs and persistent allowances through resume. Controlled
services establish mechanics; they make no paid calls and prove no real editorial
quality or source-accuracy percentage.

## Final verification

On September 14, `mypy src/podcast_processor` passed all **34 source files**, and
`pytest -q tests/` passed **315 tests in 119.97 seconds**. The final full run includes
the existing crash, concurrency, recovery, accounting and selective-reuse coverage.

Independent code-review axes have **zero remaining findings**. Standards review
identified punctuated-name validation, fuzzy short names and a dependent guest
association surviving host conflict. Spec review identified possessive name mentions
being interpreted as identity evidence. Public CLI regressions reproduced all four
before the fixes and pass afterward. The reviewed mapper was then reevaluated on
the isolated original interview evidence, with no corrections or service calls.
