# Erica Campbell managed transcription comparison

Run date: 2026-09-08 UTC. Architecture decision: [issue #11](https://github.com/jimmyblain/podcast-processing/issues/11).

## Recommendation and evidence limit

Recommend AssemblyAI Universal-3.5 Pro as the initial primary candidate, with Deepgram Nova-3 / diarization v2 as the automatic backup. Both processed this full episode comfortably within the 15-minute target. AssemblyAI's word-level speaker assignments were more plausible in several short guest answers and closing exchanges when assessed against conversational context; Deepgram was substantially faster and has useful separate speaker-confidence fields.

This recommendation is supported by one recording, structural checks, contextual review, and the user’s listening annotations for selected phrases. It is **not** a representative full-episode accuracy ranking. This session could not directly listen to audio through the available tool interface. The user subsequently supplied five single-speaker phrase annotations and one both-speaker thanks annotation from the prepared source excerpts (see below). WER, full-episode diarization error rate, overlap accuracy, and the source-audited approximately ±1-second boundary target remain unmeasured. Historical transcripts and agreement between providers are not ground truth. The selected listening check is complete and favors AssemblyAI. Source-audited cut timing remains outstanding; do not describe the complete quality contract as validated.

## Input, authorization, and requests

The user supplied the full episode folder, configured both credentials locally, and explicitly authorized uploading to both providers with up to $3 total for this comparison, using existing credits. Exactly one transcription was submitted to each provider; no automatic retry or additional paid feature was used.

Source: `IJLMI - Erica Campbell 4K.WAV`, 3369.842358 seconds (56:09.842), stereo 44.1 kHz 16-bit PCM, 594,440,236 bytes. The 4K video audio stream and historical transcript have matching durations. The radio edit is shorter and was not used.

The prepared FLAC is 184,214,501 bytes. Its decoded PCM SHA-256 matches the source. No trimming, resampling, channel changes, or timeline shifts were applied locally. Deepgram's returned upload fingerprint also matches the FLAC SHA-256. Both received the same bytes with multichannel transcription disabled; Deepgram reports one processed channel. This tests diarization on mixed audio, not isolated microphone channels.

- AssemblyAI: EU `/v2/upload` and `/v2/transcript`; `speech_models=["universal-3-5-pro"]`, `speaker_labels=true`, `language_code=en`, `punctuate=true`, `format_text=false`, `disfluencies=true`. No forced speaker count, name hints, prompts, or provider-internal alternate model. Returned model: `universal-3-5-pro`; acoustic/language model fields are generic `assemblyai_default`, not immutable version pins. Request ID: `7162e103-82b4-4e34-9f13-2a158caf2a05`.
- Deepgram: US `/v1/listen`; `model=nova-3`, `diarize_model=v2`, `language=en`, `utterances=true`, `punctuate=true`, `filler_words=true`, `smart_format=false`, `multichannel=false`, `mip_opt_out=true`. No keyterms. Returned ASR version `2025-07-31.0`, model UUID `2187e11a-3532-4498-b076-81fa530bdd49`; diarization v2 UUID `6946b038-8264-4505-acf7-9822c009fecb`. Request ID: `01a07f41-ec6b-7f53-8338-d9c736a72308`.

AssemblyAI documents exclusion from training for EU processing; Deepgram documents per-request model-improvement opt-out. These are the settings used, not a claim of immediate deletion or account-specific retention verification. See [AssemblyAI data handling](https://www.assemblyai.com/docs/data-retention-and-model-training) and [Deepgram request controls](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded).

## Measured operational results

| Measure | AssemblyAI | Deepgram |
| --- | ---: | ---: |
| Input duration | 56:09.842 | 56:09.842 |
| Time from upload start until result available/observed | ≤184.36 s (3:04) | 24.05 s |
| Upload stage | 114.71 s to upload response | 20.39 s to request-body send completion |
| Word records | 11,738 | 11,431 |
| Anonymous speakers | 2 | 2 |
| Missing word speaker labels | 0 | 0 |
| Missing/nonfinite/reversed/out-of-source word intervals | 0 | 0 |
| Zero-duration word intervals | 103 | 0 |
| Speaker turns rebuilt from consecutive word labels | 489 | 423 |
| Words with separate speaker confidence | 0 | 11,431 |

AssemblyAI was already complete at the first status poll, so 184.36 seconds is an observed upper bound, not an exact service runtime. Its upload plus submission took 115.34 seconds. Deepgram's synchronous response provides a directly measured total. Uploads did not overlap; AssemblyAI's cloud processing could overlap Deepgram's upload. Endpoints are in different regions. These are single-run observations including local upload, excluding FLAC preparation performed previously. Do not generalize them as vendor SLAs or linearly extrapolate a guaranteed 40-minute runtime.

Both passed basic interval-range checks, but zero-length intervals are separately flagged rather than treated as usable word spans. Deepgram has five start-time reversals in returned word order and 70 adjacent overlapping word intervals; AssemblyAI has seven adjacent overlaps. These counts do not prove simultaneous speech or model error; normalization must preserve original order and evidence without flattening overlaps.

## Text and speaker review

The self-introductions and subsequent dialogue support episode-local mappings A/0 → Lish and B/1 → Erica. These mappings come from textual identity evidence and episode context, not from assuming the first vendor label is the host or from independent voice recognition.

Review used the opening/introductions, a rapid exchange around 16:40, a later exchange around 40 minutes, and the close around 54–56 minutes. The following examples use **word-level** labels:

| Passage | AssemblyAI | Deepgram | Interpretation |
| --- | --- | --- | --- |
| Self-introduction near 01:12 and guest introduction near 02:40 | Lish Speaks and Erica Campbell spelled correctly | Same | Both support introduction-based participant mapping without supplied hints |
| Greeting near 02:43 | “Welcome” assigned B; “Hello” assigned A | “Welcome” assigned 0; “Hello” assigned 1 | Deepgram is more plausible in context |
| Award-count answer near 02:48 | “Six” assigned B | “Six” assigned 0, speaker confidence about 0.89 | AssemblyAI is more plausible for the guest answering the host; confidence alone cannot guarantee attribution |
| Award question near 02:47 | “five Gummies” | “five Grammys” | Deepgram preserves the intended award term more plausibly in context |
| Album exchange near 16:46–16:52 | “Harmonica” and “my sisters, my kids” assigned B | Those words assigned 0 | AssemblyAI is more plausible given the guest's album discussion |
| “We do” near 17:40 | Assigned A | Assigned 0 | Both preserve this host interjection at word level |
| Closing reply and thanks near 55:02–55:05 | Guest reply and thanks assigned B | Assigned 0 | AssemblyAI is more plausible in context |

Both have suspect assignments and wording. These observations are inference from conversation structure, not a scored listening test. Raw outputs were preserved, not silently corrected to match these judgments. The source's historical promotional details also differ from current show-profile details; downstream publishing should continue to use approved current metadata for official links/schedules rather than infer updates from a provider transcript.

Across sequence-aligned equal tokens, there are 10,805 matched word pairs: 92.05% of AssemblyAI records and 94.52% of Deepgram records. This excludes punctuation/case and is **agreement, not WER or correctness**. Median absolute start-time difference is 0.053 seconds; the 95th percentile is 0.225 seconds. About 0.56% exceed one second. Among 10,800 equal word pairs within two seconds, 500 disagree on the mapped speaker (4.63%). No provider is declared correct by that calculation. Repeated words can affect alignment.

## Integration findings

1. Build speaker turns from word-level labels. Deepgram returned 561 vendor utterances; 153 contain multiple word-level speakers, and 939 words differ from their containing utterance's top-level label. Treating an utterance label as authoritative for all its words would introduce avoidable attribution errors. Reconstructing from words yields 423 consecutive-speaker runs.
2. Use the first and last usable word timing for conversational bounds. Three AssemblyAI utterance starts precede their first word by over one second. Paragraph wrapping and breaks at pauses are presentation concerns, separate from stable speaker identities. Intro music and long pauses must not shift source time.
3. Preserve questionable timing explicitly. Keep the text of AssemblyAI's 103 zero-duration words, retain the original response, flag those word intervals as unsuitable for precise cuts, and use reliable nearby turn/boundary evidence. Do not fabricate durations or fail the entire episode for sparse uncertainty.
4. Preserve provider annotations separately from prose. AssemblyAI returned music/lyric markers in the intro; their markup should not leak into publishing copy or be mistaken for participant identity evidence.
5. Keep ASR and speaker confidence separate. Deepgram's speaker confidence is useful evidence but is uncalibrated for this show. High scores on plausible misattributions rule out treating a single confidence threshold as sufficient validation.

## Cost and usage

Public prices rechecked on 2026-09-08 give these baseline estimates, with no keyterms or other optional add-ons:

| Provider | Usage returned | Advertised rate | Estimated credits consumed |
| --- | ---: | ---: | ---: |
| AssemblyAI | 3,370 seconds | $0.21/hour + $0.02/hour diarization | $0.2153 |
| Deepgram | 3,369.8423 seconds | $0.0043/minute, batch diarization included | $0.2415 before any opt-out pricing adjustment |
| Total | Two full-episode requests | | $0.4568 baseline estimate |

Sources: [AssemblyAI pricing](https://www.assemblyai.com/pricing), [Deepgram pricing](https://deepgram.com/pricing). For a typical 40-minute episode, the same advertised rates imply about $0.1533 primary-only or $0.3253 primary plus one backup, before account-specific adjustments. These are estimates, not observed deductions or permission to exceed the agreed budget.

Exact billed deductions could not be verified: Deepgram project discovery succeeded, but balance, request-details, and billing-breakdown reads returned HTTP 403 with this key. AssemblyAI's transcript response supplies duration, not billed dollars; billing is exposed in its account dashboard. No purchases or account billing settings were changed. Actual usage dollars remain unavailable; retain an estimate/actual distinction and reconcile account-specific rates before implementing a strict dollar cap. No further paid calls were made.

## Proposed architecture to carry forward

- Managed full-episode ASR plus diarization behind small provider adapters; AssemblyAI primary candidate, Deepgram backup candidate. Preserve raw responses and normalize to the agreed provider-neutral timed-transcript contract before downstream work.
- No mandatory local models, separate forced-alignment stage, or chunk stitching in the initial default. This full episode fits both services. Chunking would require explicit offset mapping and cross-chunk speaker reconciliation, and was not validated here.
- Preserve source timing through minimal preprocessing. A lossless FLAC transport copy worked. Optimize upload size only after a separate quality check; don't remove pauses or run untested denoising by default.
- Record selected model names, all request settings, returned versions/UUIDs, source fingerprint, endpoint/region, request IDs, and artifact versions. Pin immutable versions where supported; do not pretend AssemblyAI's generic metadata is a reproducible model pin. Provider/model changes require evaluation under #10.
- Use introductions, confirmed participant metadata, and consistent later dialogue to map anonymous voices. Keep ambiguous attribution anonymous and finish. No enrollment or mandatory operator identity review.
- Automatic backup for service failure or an unusable transcript, subject to the shared time/cost budget. Do not invoke a second provider merely for individual low-confidence words. Preserve usable results and report limited/unsupported outputs after bounded recovery. Exact checkpoints, uncertain POST handling, caching, and retry accounting remain #4; measured quality thresholds and reference fixtures remain #10.

These are recommendations, not production changes or a completed acceptance test. The existing CLI still uses its existing local transcriber.

## Local evidence

Under ignored `output/provider-comparison-erica-campbell/`:

- `manifest.json`: source/copy hashes, stream properties, lossless PCM match, provisional listening windows.
- `assemblyai-run.json`, `deepgram-run.json`: timestamps, request settings, IDs, attempts.
- `assemblyai-response.json`, `deepgram-response.json`: returned raw results (AssemblyAI's uploaded-file URL omitted).
- `assemblyai-normalized.json`, `deepgram-normalized.json`, corresponding `*-transcript.txt`: word-level labels and derived speaker runs for review.
- `selected-passages.md`, `metrics.json`: comparative evidence and descriptive checks.
- `deepgram-balance-before.json`, `deepgram-usage.json`: access status for attempted billing verification.
- `run_comparison.py`, `analyze_results.py`: one-off evaluation scripts, not integrated production code.

The full audio and credentials must not be committed. The source file was not modified. Remaining source-verified timing and broader accuracy evaluation needs an annotated reference or an audio-capable review environment; it does not introduce a human gate into normal episode processing.

## Completed user listening check

The user listened to all three prepared source clips. Erica says the five single-speaker phrases below. For the final thanks, the user clarified that both speakers said “thank you”; exact word ownership, ordering, and simultaneous overlap were not specified.

| Source phrase | User-confirmed speaker | AssemblyAI word label | Deepgram word label |
| --- | --- | --- | --- |
| “Hello” near 02:44 | Erica | Lish — mismatch | Erica — match |
| “Six” near 02:48 | Erica | Erica — match | Lish — mismatch |
| “Harmonica” near 16:46 | Erica | Erica — match | Lish — mismatch |
| “my sisters, my kids” near 16:51 | Erica | Erica — match | Lish — mismatch |
| “I don’t think it will” near 55:02 | Erica | Erica — match | Lish — mismatch |
| Closing “thank you” | Both Lish and Erica | Erica only | Lish only |

AssemblyAI matches **4 of 5 single-speaker phrase checks**; Deepgram matches **1 of 5**. These deliberately selected disputed phrases provide direct listening evidence favoring AssemblyAI for these cases, not representative accuracy percentages. Exclude the both-speaker thanks from that score: neither single-label rendering fully captures the user’s description. Do not infer that both said the entire “Thank you so much” phrase or that their speech was simultaneous without finer annotation.

The user's listening answers are complete. The provider recommendation remains AssemblyAI primary and Deepgram backup. These annotations do not validate precise timestamps or cut boundaries. Preserve the both-speaker observation as uncertainty to handle conservatively, rather than force a single-person attribution or claim verified overlap timing. Machine-readable annotations are saved locally in `output/provider-comparison-erica-campbell/listening-check/user-annotations.json`.
