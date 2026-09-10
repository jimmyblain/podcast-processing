# Participant mapping and optional corrections

Issue #15 adds the B3 workflow over a managed timed transcript. After the required
approved show profile and confirmed episode metadata, transcription maps supported
identities automatically and completes without an identity prompt. You can rerun
mapping over saved evidence without contacting a service:

```sh
podcast-process map-participants output/episodes/my-episode
podcast-process inspect output/episodes/my-episode
```

Explicit self-introductions identify confirmed participants. A supported host's
named guest introduction followed by acknowledgment of the invitation can identify
the guest, including up to four turns of brief greetings within fifteen source
seconds. Assignments then follow the same episode-local voice through subsequent
speech. Conflicting introductions retain uncertain identity. A name mention,
vendor label order, roster size, or recognition confidence alone proves no identity.
These conservative local rules cover explicit introductions; other identity evidence
can be supplied with an optional correction. No voice enrollment or model call is
required. Participant records support multiple guests.

`current/transcript.txt` uses source timestamps and supported names or anonymous
labels, with paragraphs at speaker changes and lines wrapped to 100 columns.
Wrapping does not split structured turns or rewrite speech. The structured file
retains word detail, source bounds, identity evidence, and overlapping-turn
references. Unclear wording such as `[inaudible]` remains explicit. An unclear
sentence is excluded from publishing inputs as a whole to avoid changing its meaning
by deleting a missing word. Clear sentences in the same turn remain available;
their source positions use retained word evidence when available. Anonymous
speech uses neutral topic-based attribution. Word confidence remains provider
evidence, separate from identity, wording uncertainty, and timing usability.

The separate completion report lists unresolved identity, unclear wording, timing
limitations and overlap with available source positions/references, affected
consumers, conservative fallbacks, and optional correction examples. It lists only
outputs that exist. Review and corrections are optional.

## Create and apply a corrections file

```sh
podcast-process corrections-template output/episodes/my-episode --output corrections.json
# Edit changes using exact references from current/transcript.json.
podcast-process correct output/episodes/my-episode corrections.json
```

The template refuses to overwrite an existing file. Omit `--output` to print it.
It contains this envelope with the current base values filled in:

```json
{
  "schema_version": 1,
  "source_revision": "exact-source-revision",
  "transcript_revision": "exact-current-transcript-revision",
  "transcript_sha256": "exact-current-artifact-hash",
  "changes": []
}
```

Leave the base fields unchanged. All three must match, including when `changes`
is empty. Unknown fields, incompatible bases, and invalid references fail clearly
before publishing any correction. Every successful nonempty file creates a new
revision; create a new template for subsequent edits. Operations execute in file
order, so a reference removed by an earlier operation is unavailable to later ones.

Use one or more of these objects in `changes`. The example reference names below
are placeholders, not vendor labels; copy actual IDs from the structured output.

| Operation | Example | Effect |
| --- | --- | --- |
| Relabel | `{"op":"relabel","speaker":"speaker-id","participant":"Lish Speaks"}` | Associate every turn of that voice with a confirmed participant. Use `null` to explicitly leave it anonymous. Wording and timing are unchanged. |
| Merge | `{"op":"merge","speaker":"duplicate-id","into":"retained-id"}` | Merge duplicate voices while retaining turn/word IDs and intervals. Conflicting named participants must first be explicitly relabeled. |
| Separate | `{"op":"separate","turn_ids":["turn-id","another-turn-id"]}` | Assign selected turns and their words to one new anonymous speaker. Read its new ID and relabel in a subsequent file if supported. |
| Replace | `{"op":"replace","turn_id":"turn-id","first_word":"word-id","last_word":"word-id","text":"my sisters."}` | Replace an inclusive contiguous word range within one turn. Use the same word ID at both ends for one word, or `[unclear]` for unresolved wording. |
| Split | `{"op":"split","turn_id":"turn-id","before_word":"word-id"}` | Create a second turn beginning at that word's supported source start. Requires two nonempty passages with usable word intervals and no word crossing the cut. |
| Retime | `{"op":"retime","word_id":"word-id","start":12.1,"end":12.4,"evidence":"Listened to this source interval."}` | Record source-checked word timing in seconds and recompute the containing turn's bounds. Requires positive, finite, in-source bounds and a nonempty evidence note. |

Replacement words get new IDs and **no inherited timestamps or recognition
confidence**. Unchanged words retain their IDs, detail and timing. The original turn
envelope remains surrounding evidence, while affected alignment is marked
unverified. Source-checked `retime` operations can subsequently establish the new
words' alignment. A supplied evidence note records the operator's assertion; it is
not independent audio verification. Overlap is legal and is never flattened to a
sequential timeline. Reliable word bounds must fit their containing turns.

Automatic identity evidence is reconsidered after wording, attribution or timing edits;
explicit operator relabels remain authoritative within the confirmed roster.
Publishing-copy edits do not become transcript corrections or episode metadata.
Missing legacy references/settings stay unknown; this workflow does not fabricate
word references or alignment for an unversioned text-only import.

## Preservation, reuse and affected results

Raw ASR, the normalized original, correction-file bytes, historical transcripts and
previous publishing outputs remain immutable evidence. Lineage records the exact
base/source, component version, input hashes and applied changes. Artifact records
retain their hashes and run/dependency references. Corrections need no media file,
API key, transcription request, or publishing request. Publication of the corrected
JSON, readable text and affected-output status uses one atomic snapshot switch.
Direct edits are preserved in history before replacement.

An unchanged reread/resume preserves corrected IDs. A fresh transcription uses new
speaker/turn/word references, even when the provider returns the same labels or
text. Ordinary metadata changes do not trigger ASR; changed actual ASR settings,
including any configured name hints, change the request fingerprint.

Publishing records declare consumed text, attribution and timing hashes. Corrections
supersede only changed consumers and recorded dependents; older artifacts that
consume the whole transcript are conservatively superseded. Timing changes remove
chapters while the current legacy description and titles remain reusable if their
text/attribution inputs are unchanged. A consumer embedding chapters must record
its chapter dependency and is then superseded transitively. The B4 shared-chapter
description and B5 section proposal remain later work; this change does not create
or claim those outputs. Saving a correction never claims publishing regeneration.
Run `generate <workspace>` explicitly to rebuild superseded publishing results.

## Verification

`pytest tests/test_participant_corrections.py` exercises the public CLI with isolated
workspaces and controlled service responses. It covers unknown/conflicting identity,
repeated identities, spoken name mentions, greeting exchanges, fillers, unclear
important wording, overlap, all correction operations, invalid bases/references,
preserved bytes/IDs, selective invalidation, local recovery and actual-request
fingerprints. The existing managed-provider suite also replays cached evidence
when available. No paid calls or private media are added by these tests.

Precise real-source timing, true simultaneous-overlap annotations, representative
speech accuracy, publishing editorial acceptance and measured cost/runtime remain
the evaluation ticket's work. The selected listening observations are limited
evidence; these deterministic workflow tests establish no full-episode accuracy
percentage or release approval.
