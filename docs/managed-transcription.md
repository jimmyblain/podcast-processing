# Managed transcription with bounded recovery

Implements issue #14 (B2 of #12). This slice produces a versioned timed transcript
and completion report. Participant mapping/corrections, the new publishing package,
and source-quality/runtime/billed-cost acceptance belong to later slices.

## Run and resume

Set `ASSEMBLYAI_API_KEY` and `DEEPGRAM_API_KEY` in the environment or `.env`.
FFmpeg and ffprobe are required; local ML is not installed or used by this workflow.
Install `pip install -e ".[local]"` only when using the legacy local pipeline.

```sh
podcast-process transcribe episode.wav --workspace output/episodes/my-episode \
  --show-profile show-profile.json --metadata episode.json
podcast-process transcribe output/episodes/my-episode
podcast-process inspect output/episodes/my-episode
```

Use the approved show profile and confirmed episode metadata described in
[workspace import](workspace-import.md). Supply explicit solo status or confirmed
guest names. Their presence never assigns vendor A/0 to Lish Speaks.
Without `--workspace`, recordings use `output/episodes/episode-<content-identity>`;
the command prints the location. Moving unchanged bytes preserves that identity.
Pass a changed recording with the same `--workspace` to record a new source revision.

Outputs are `current/transcript.json`, `current/transcript.txt`, and
`current/completion-report.md`. The structured state, history, raw response evidence,
and recovery receipts stay in the workspace. Exit 0 means the transcription request
completed; exit 1 means a partial/unavailable outcome or explicit input/configuration
failure. Transcription never invokes publishing text generation. Anonymous speakers
are valid completed output. Timing is provider evidence, not source-audited truth.

The existing `process` command remains the legacy full pipeline in this slice.
For explicit legacy local transcription, use `transcribe episode.wav --local`.
Existing `transcribe episode.wav -o old-output` also retains legacy behavior when
neither authority files nor `--workspace` are given. For managed runs, use
`--workspace` to avoid this compatibility routing.

## Admission and recovery

The default operation deadline is 900 seconds and the transcription allowance is
$3. `--deadline` and `--allowance` can lower those limits. Default conservative
reservations are $1.50 per source hour for **each** provider: a typical 40-minute
source reserves $1 for primary and, if needed, another $1 for backup. These are
admission policy values, not advertised rates, measured charges or a billing cap.
Account-adjusted conservative rates can be configured with
`TRANSCRIPTION_PRIMARY_RESERVATION_PER_HOUR` and
`TRANSCRIPTION_BACKUP_RESERVATION_PER_HOUR`. Publishing usage is separate.

Every operation saves its policy, absolute deadline, elapsed information, request
settings, attempts, job IDs, and separate estimated/reserved/actual USD fields.
Actual cost remains `null` until there is billing evidence; neither provider adapter
claims to observe billing. Reservations for accepted/ambiguous jobs are not released
on failure, expiry or missing billing access. A request that cannot fit is denied.

An ordinary resume **does not** renew limits, even if different allowance/rate/deadline
options are supplied. `--fresh` explicitly starts a new operation and possible
spending, retaining prior ledgers and artifacts. It never cancels old remote jobs.
Source or provider request changes also create new dependency-specific operations.
A normalization-version change uses existing raw evidence without retranscription.

There is at most one primary and one backup accepted or possibly accepted job in an
operation. A submission intent is committed under exclusive workspace ownership
before sending; the returned ID and raw bytes are checkpointed before normalization.
Receipts are atomically written with hashes and allow recovery after a later snapshot
failure. A second process reports the active writer; process death releases ownership.

Transient reads have four persisted automatic failure attempts with bounded backoff.
A provider HTTP 429 demonstrably rejecting the submission permits one retry within
the original slot (two submission calls maximum). Transport errors and server 5xx do
**not** prove rejection and never authorize repeating a paid submission. Authentication
and configuration errors stop explicitly. A blocked submission requires corrected
configuration plus `--fresh`; missing credentials before submission can be corrected
and resumed without a new ledger.

AssemblyAI reconciliation searches up to four pages/requests of its supported job
list for the unique upload URL; missing/nonunique matches stay ambiguous. Known IDs
are polled, never resubmitted. After expiry, a resume may make one bounded read for
an already completed known job, without waiting or starting another job. Deepgram
synchronous transcripts cannot be downloaded again: a retained receipt can be
recovered, but a lost response without that evidence stays unresolved.

The deadline stops waiting/new submissions, not remote work already accepted.
Network calls have bounded timeouts; an in-flight operation or local persistence
may finish after the deadline. No timeout implies cancellation, deletion, or free usage.

## Evidence and fidelity

Both providers receive full-episode lossless FLAC with no trimming, resampling,
channel changes, intro/music removal, denoising or stitching. The original and
submitted fingerprints, decoded PCM hash, source duration and transformation are
recorded. Decoded PCM, sample rate and channel count must agree before submission.
An unsupported/lossy transformation fails locally. Multiple audio streams require
explicit selection outside this workflow.

- AssemblyAI: EU endpoint, `universal-3-5-pro` only, English, word speaker labels,
  punctuation and disfluencies on, text formatting off.
- Deepgram backup: US endpoint, `nova-3`, `diarize_model=v2`, English, utterances,
  punctuation and fillers on, smart formatting and multichannel off, `mip_opt_out=true`.
- No forced speaker counts, keyterms, paid identity features or automatic provider
  model fallback. Request/endpoint privacy settings are recorded; retention/deletion
  and privacy-adjusted pricing are not verified by those settings.

Words retain source order and native speaker labels. Turns derive from consecutive
word labels and usable word bounds, never from parent utterance labels/bounds.
Cross-speaker overlaps and backwards starts remain evidence. Missing, nonfinite,
reversed, out-of-source and zero-duration word timing cannot become precise cuts;
recoverable wording survives. Invalid bounds remain in raw evidence. Provider
annotation markup is stored separately. Recognition and speaker confidence are
separate, nullable native evidence, not inferred timing confidence or identity.

## Verification and remaining acceptance

Run `pytest tests/test_managed_transcription.py tests/test_managed_recovery.py` and
`mypy src/podcast_processor`. Tests use a real workspace, generated silent media,
controlled HTTP responses/failures, a controlled clock, and subprocess crash/lock
checks. They verify observed calls, committed IDs, reservations, faithful wording,
label/unit conversion, overlap, salvage, and honest outcomes without paid calls.

Two optional tests replay the full local comparison files from
`output/provider-comparison-erica-campbell/{assemblyai,deepgram}-response.json`.
They verify the 103 zero-duration-word case, three early AssemblyAI utterances,
and 153 mixed Deepgram utterances with 939 differing word labels. These private
bundles remain untracked; the suite skips their replay when absent. Synthetic cases
remain in the ordinary suite. Silent test media supplies transport scaffolding only;
it does not establish correspondence to the original episode or source accuracy.

Representative paid runtime, source-audited timing/word/speaker quality, account
billing, retention/deletion verification and release approval remain unevaluated.
No A12–A14 acceptance is claimed by these mechanics tests.

Provider contracts checked against the official references:
[AssemblyAI submit](https://www.assemblyai.com/docs/pre-recorded-audio/api-reference/transcripts/submit),
[AssemblyAI list/reconciliation](https://www.assemblyai.com/docs/pre-recorded-audio/api-reference/transcripts/list),
[Deepgram request controls](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded),
[Deepgram synchronous response retention](https://developers.deepgram.com/docs/pre-recorded-audio).
