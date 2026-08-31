# Transcription and diarization architecture options

Research date: 2026-08-30  
Decision ticket: [Compare transcription and diarization architectures](https://github.com/jimmyblain/podcast-processing/issues/3)

## Question and constraints

What credible local or inexpensive managed architecture can transcribe English podcast episodes that are usually either Lish Speaks alone or Lish plus one guest, while preserving:

- automatically detected, episode-stable speaker labels;
- source-relative speaker-turn and word start/end times useful to a roughly ±1 second boundary target;
- room for more than two speakers later;
- correction of participant names, spellings, words, and speaker assignments without retranscribing;
- an honest representation of overlap and short interjections;
- low cost for the 40.4-minute median episode;
- enough provenance to reproduce and compare a run.

This report surfaces trade-offs; it does **not** choose the architecture. Prices are public list prices captured on the research date and exclude tax, network transfer, electricity, hardware, and any existing subscription commitment.

## Evidence labels

- **Documented fact** means an official product document, source repository, model card, or API schema states the behavior.
- **Research evidence** means a published evaluation or benchmark measured the behavior. Vendor-run benchmarks are identified as such.
- **Inference** means a design implication drawn from the documented behavior. It must be validated against this podcast's audio before becoming an acceptance claim.

## Current baseline

The application currently uses `faster-whisper` with `word_timestamps=True` and Silero VAD, then stores source-relative segment and word start/end values. It has no diarization or participant layer and performs no timing-invariant validation ([current transcriber](../../src/podcast_processor/transcriber.py), [current transcript models](../../src/podcast_processor/models.py)).

That is a useful starting point, but its word timings are Whisper-derived estimates. The WhisperX paper reports that original Whisper utterance timestamps can be inaccurate by several seconds and shows better word segmentation from a separate phoneme forced-alignment pass ([WhisperX paper](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.pdf)). This is evidence for evaluating forced alignment; it is not evidence that every current `faster-whisper` timestamp misses the requested tolerance.

## Findings that apply to every option

### Speaker and participant are different records

Diarization answers “which episode-local voice spoke when,” not “which real person is this.” Most systems return anonymous labels such as `SPEAKER_00`, `A`, or `0`. OpenAI can accept 2–10 second reference clips for up to four known speakers, while pyannoteAI Precision-2 supports separately enrolled voiceprints; AssemblyAI's optional Speaker Identification derives a name or role from conversation content ([OpenAI transcription API](https://platform.openai.com/docs/api-reference/audio), [pyannoteAI identification API](https://docs.pyannote.ai/api-reference/identify), [AssemblyAI speaker identification](https://www.assemblyai.com/docs/speech-understanding/speaker-identification)).

**Inference:** preserve immutable, episode-local `speaker_id` values in the timed transcript and keep the editable `Participant` mapping (`Lish Speaks`, guest name, or unknown) in a separate layer. Lish's self-introduction and supplied metadata can assist that mapping, but the transcript should not silently convert uncertain diarization into claimed identity.

### Overlap has two representations

pyannote's regular diarization may return simultaneous regions for more than one speaker; its exclusive view assigns exactly one speaker to each instant to simplify reconciliation with one ASR word stream ([pyannote speaker configuration](https://docs.pyannote.ai/tutorials/speaker-configuration), [Community-1 model card](https://huggingface.co/pyannote/speaker-diarization-community-1)). WhisperX explicitly says overlapping speech is not handled particularly well and diarization is imperfect ([WhisperX README](https://github.com/m-bain/whisperX#limitations-%EF%B8%8F)). AssemblyAI says cross-talk reduces accuracy and speakers who only contribute short phrases such as “yeah” or “right” may not form reliable clusters ([AssemblyAI diarization guidance](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers)). Deepgram assigns one speaker to each recognized word and documents using word intervals to find some cross-talk, but does not promise two independently transcribed word streams during simultaneous speech ([Deepgram diarization](https://developers.deepgram.com/docs/diarization/), [Deepgram multichannel vs. diarization](https://developers.deepgram.com/docs/multichannel-vs-diarization)). OpenAI documents segment-level speaker labels but no overlap contract ([OpenAI transcription API](https://platform.openai.com/docs/api-reference/audio)).

**Inference:** retain both the raw overlap-aware diarization regions (when available) and a normalized, exclusive turn stream. Mark overlap regions explicitly. No option reviewed documents reliable transcription of both simultaneous voices from a mixed mono recording; benchmark backchannels and interruptions rather than assuming they will be captured.

### “Has timestamps” does not establish ±1 second accuracy

All options except OpenAI's diarizing model expose documented word start/end fields. None of the managed providers publishes a podcast-specific guarantee that its word or speaker boundaries fall within ±1 second. The WhisperX paper evaluates exact recognized words with a 200 ms collar and finds forced alignment substantially improves word segmentation, but its test corpora and hardware are not this podcast ([WhisperX paper](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.pdf)).

**Inference:** the ±1 second target must be an application-level acceptance test. Validate source-relative, monotonic, in-bounds times and manually score boundary error on representative excerpts. Keep model timestamps at their returned precision; round only when rendering.

## Architecture options

### Option A — Minimal local extension

**Shape:** retain `faster-whisper` for English ASR and its word timestamps; run pyannote Community-1 locally over the same source audio; reconcile each word with speaker regions; derive readable turns from adjacent words with the same speaker.

**Documented facts**

- `faster-whisper` supports CPU and NVIDIA CUDA inference, VAD, hotwords/initial prompts, word timestamps, and per-word probabilities ([faster-whisper repository](https://github.com/SYSTRAN/faster-whisper)). Its CTranslate2 runtime's prebuilt binaries support x86-64 and ARM64 CPUs; documented GPU support is NVIDIA CUDA, not Apple Metal ([CTranslate2 hardware support](https://opennmt.net/CTranslate2/hardware_support.html)).
- Community-1 runs locally and offline after download, automatically estimates speaker count, accepts exact or min/max speaker bounds, returns regular and exclusive diarization, and is CC-BY-4.0 ([Community-1 model card](https://huggingface.co/pyannote/speaker-diarization-community-1)).
- Community-1's vendor model card reports improved counting/assignment versus its 3.1 predecessor. Its fully automatic benchmark includes overlap and uses no forgiveness collar; reported DER varies widely by domain, from 8.9% on REPERE to 46.8% on Ego4D. Those figures are not podcast-specific ([Community-1 model card](https://huggingface.co/pyannote/speaker-diarization-community-1)).

**Correction affordances**

- ASR can receive episode metadata as `hotwords` or `initial_prompt` for participant, artist, and brand spellings.
- Because ASR words and diarization regions are separate artifacts, a correction UI or file can change text, a word's speaker assignment, a turn boundary, or participant mapping without rerunning both models.
- The reconciliation algorithm and invariants are application code and therefore inspectable.

**Privacy, runtime, and maintenance**

- Audio and derived artifacts can remain on the workstation after the initial model downloads.
- Marginal provider cost is $0.00. Electricity and operator time remain.
- On an Apple Silicon Mac, ASR uses ARM64 CPU through the documented CTranslate2 path; the stack's advertised GPU speed figures are CUDA-specific. Community-1 also runs on CPU and can use CUDA. Runtime on the actual machine is unknown until benchmarked.
- This option owns the most glue: model downloads, Hugging Face access terms/token, Python/PyTorch/CTranslate2 compatibility, word-to-speaker reconciliation, overlap policy, dependency pinning, and regression testing.

**Decision-relevant inference:** this is the smallest change from the current app and exposes the raw evidence needed for correction, but it leaves the timestamp-quality question dependent on Whisper-derived word timing and home-grown reconciliation.

### Option B — Local WhisperX pipeline

**Shape:** use WhisperX's pipeline: VAD cut/merge → batched `faster-whisper` ASR → English wav2vec2 phoneme forced alignment → local pyannote Community-1 diarization → word/speaker reconciliation.

**Documented facts and research evidence**

- WhisperX is built on `faster-whisper`, adds forced word alignment and pyannote speaker labeling, and accepts exact or min/max speaker counts ([WhisperX README](https://github.com/m-bain/whisperX)).
- Its Interspeech 2023 paper reports that VAD cut/merge reduces boundary effects and that forced alignment outperforms Whisper-derived word timing on AMI and Switchboard word-segmentation evaluations. Alignment added less than 10% inference overhead in the reported setup ([WhisperX paper](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.pdf)).
- The paper's speed tests used an NVIDIA A40. The current README's high-throughput claims also describe NVIDIA GPU operation; it documents CPU mode for macOS but provides no equivalent Apple CPU runtime claim ([WhisperX README](https://github.com/m-bain/whisperX)).
- WhisperX documents that words outside the alignment model dictionary may lack timing, overlap is not handled particularly well, and diarization is “far from perfect” ([WhisperX README](https://github.com/m-bain/whisperX#limitations-%EF%B8%8F)).

**Correction affordances**

- It preserves separable ASR, alignment, and diarization artifacts, supporting the same non-destructive correction layer as Option A.
- Forced alignment can be rerun after transcript text correction without necessarily rerunning diarization; the exact behavior needs a prototype because a corrected word absent from the audio/alignment vocabulary can remain unaligned.

**Privacy, runtime, and maintenance**

- It can remain local and has $0.00 marginal provider cost.
- It adds an English alignment model and WhisperX's integration/dependency surface to Option A. CPU operation is documented, but acceptable median-episode runtime on the target Mac is unproven.

**Decision-relevant inference:** this is the strongest locally documented path to higher-confidence word timing, but it increases installation and maintenance risk and still cannot promise clean attribution of overlapping interjections.

### Option C — AssemblyAI pre-recorded API

**Shape:** send the source audio to Universal-3.5 Pro or Universal-2 with speaker diarization enabled; normalize returned utterances and words into the local transcript schema.

**Documented facts**

- Speaker diarization returns utterances with source-relative millisecond start/end values and words containing start, end, confidence, and speaker fields ([AssemblyAI diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers)).
- Speaker count is automatic by default. An exact `speakers_expected` or a min/max range is supported; the docs warn that a wrong exact count can split or merge speakers and that an overly high maximum can over-split one speaker ([AssemblyAI diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers)).
- The docs explicitly warn about short interjections, cross-talk, noise, and similar-sounding speakers. Each speaker should ideally have at least 30 seconds of uninterrupted speech ([AssemblyAI diarization](https://www.assemblyai.com/docs/pre-recorded-audio/label-speakers)).
- Universal-3.5 Pro supports paid keyterm prompting and natural-language prompting. Universal-2 includes keyterm prompting but not natural-language prompting ([AssemblyAI pricing](https://www.assemblyai.com/pricing/)).
- Generic speaker labels can optionally be mapped to names or roles by a separate, content-based Speaker Identification service ([AssemblyAI speaker identification](https://www.assemblyai.com/docs/speech-understanding/speaker-identification)).

**Correction affordances**

- The response already groups words inside speaker utterances, reducing reconciliation code.
- The application still needs its own immutable raw response plus an editable correction overlay. Provider-side jobs should not be the only source of record: without a configured TTL, async final transcripts may be retained indefinitely; transcript deletion and TTL controls are documented ([AssemblyAI retention](https://www.assemblyai.com/docs/data-retention-and-model-training)).

**Privacy, runtime, and maintenance**

- Audio leaves the workstation. AssemblyAI documents training opt-out, EU processing, encryption, deletion, and configurable async TTL as low as one hour; defaults and eligibility depend on account configuration ([AssemblyAI retention](https://www.assemblyai.com/docs/data-retention-and-model-training)).
- No local ML hardware is needed. Maintenance is API integration, job polling/webhooks, retention configuration, schema/version pinning, and regression tests.

**Decision-relevant inference:** AssemblyAI exposes the most explicit speaker-count controls and failure guidance among the all-in-one APIs reviewed. Its documented 30-second-per-speaker guidance makes brief guest interjections a mandatory evaluation case.

### Option D — Deepgram Nova-3 pre-recorded API + diarizer v2

**Shape:** send the source audio to Nova-3 Monolingual with `diarize_model=v2` (or deliberately tracked `latest`), punctuation/utterances, and optional keyterm prompting; normalize word-level output into turns.

**Documented facts**

- The batch diarizer v2 assigns speaker and `speaker_confidence` to each recognized word, alongside word start/end and ASR confidence ([Deepgram diarization](https://developers.deepgram.com/docs/diarization/)).
- `diarize=true` is deprecated and routes to v1; new integrations should select a version through `diarize_model`. Pinning `v2` favors reproducibility, while `latest` favors automatic upgrades ([Deepgram diarization](https://developers.deepgram.com/docs/diarization/)).
- The published API parameters reviewed do not expose exact or min/max speaker-count controls. Speaker labels are zero-based anonymous indexes ([Deepgram pre-recorded API](https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded), [Deepgram diarization](https://developers.deepgram.com/docs/diarization/)).
- Keyterm prompting is a paid add-on. Smart formatting is included ([Deepgram pricing](https://deepgram.com/pricing)).
- Words have a single speaker label. Deepgram documents that word intervals can help inspect cross-talk, but it does not document dual word streams for overlap ([Deepgram multichannel vs. diarization](https://developers.deepgram.com/docs/multichannel-vs-diarization)).

**Correction affordances**

- Per-word speaker and speaker-confidence values support targeted human review and turn rebuilding.
- There is no documented known-speaker reference mechanism in the reviewed batch API. Participant mapping remains application-side.

**Privacy, runtime, and maintenance**

- Audio leaves the workstation. Deepgram's Model Improvement Program can be disabled per request with `mip_opt_out=true`; opted-out data is retained only as necessary to process the request. Public pricing is unchanged when opting out ([Deepgram model-improvement policy](https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program), [March 2026 change](https://developers.deepgram.com/changelog/2026/3/5)).
- No local ML hardware is needed. Deepgram bills actual duration by the second and documents no rounding ([Deepgram pricing](https://deepgram.com/pricing)).
- Maintenance is smaller than local ML, but a diarizer version and returned model metadata should be recorded because v1/v2 behavior differs.

**Decision-relevant inference:** word-level speaker confidence is useful for a correction queue, while the lack of speaker-count bounds removes a control that fits the known one-or-two-person prior.

### Option E — OpenAI GPT-4o Transcribe Diarize

**Shape:** send audio to `gpt-4o-transcribe-diarize` with `diarized_json`, English language, automatic VAD chunking, and optionally a clean Lish reference clip.

**Documented facts**

- The model returns speaker-labeled segments with start/end seconds and can map up to four 2–10 second known-speaker reference clips to supplied labels. Otherwise it returns anonymous `A`, `B`, and subsequent labels ([OpenAI transcription API](https://platform.openai.com/docs/api-reference/audio)).
- Inputs over 30 seconds require VAD chunking. The API lets callers tune VAD threshold, prefix padding, and silence duration ([OpenAI transcription API](https://platform.openai.com/docs/api-reference/audio)).
- The diarizing model does **not** support `timestamp_granularities=word`, transcription prompts, or log probabilities. Its documented output has segment timestamps only ([OpenAI transcription API](https://platform.openai.com/docs/api-reference/audio)).
- API audio transcription data is not used for training by default; the audio transcription endpoint is documented with no abuse-monitoring or application-state retention and is eligible for Zero Data Retention ([OpenAI data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)).

**Correction affordances**

- A reusable, clean Lish reference could remove one participant-mapping step, subject to consent and secure handling as biometric-like data.
- Missing word timestamps, confidence, and prompt/custom-vocabulary support limit targeted correction. A separate local forced-alignment pass could add word timing, turning this into a hybrid rather than an all-in-one solution.

**Privacy, runtime, and maintenance**

- Audio leaves the workstation, but the documented endpoint retention posture is comparatively simple.
- No local ML hardware is required. The model alias has no dated snapshot listed on its model page, so raw response, model name, request parameters, and run date should be retained ([model page](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize)).

**Decision-relevant inference:** segment timestamps may be enough for a readable transcript, but this API alone does not meet the accepted word-timestamp contract or support metadata-guided proper-noun correction.

### Option F — pyannoteAI hybrid or managed orchestration

Two related shapes are credible:

1. Keep local `faster-whisper`/WhisperX ASR and outsource only diarization to hosted Community-1 or Precision-2.
2. Use pyannoteAI STT Orchestration, which runs Precision-2 plus Parakeet v3 or Whisper Large v3 Turbo and returns reconciled word- and turn-level transcription.

**Documented facts and vendor evidence**

- Precision-2 supports automatic/exact/min/max speaker counts, overlap-aware and exclusive output, optional turn confidence, and optional voiceprint identification. Hosted Community-1 lacks confidence and voiceprints but exposes flexible speaker-count controls ([pyannoteAI models](https://www.pyannote.ai/md/models), [speaker configuration](https://docs.pyannote.ai/tutorials/speaker-configuration)).
- pyannoteAI's vendor benchmark says Precision-2 is 28% more accurate than Community-1 across 259 recordings, roughly 67 hours and ten domains containing 9.3% overlapping speech. This is vendor-run evidence and not a podcast guarantee ([pyannoteAI model comparison](https://www.pyannote.ai/md/models), [benchmark methodology](https://www.pyannote.ai/benchmark)).
- Managed STT Orchestration returns source-relative word-level and turn-level text with speaker labels and retains jobs for 24 hours ([STT Orchestration docs](https://docs.pyannote.ai/tutorials/speech-to-text-diarization)).
- Precision-2 is a cloud service on standard plans. Community-1 is available offline and local; on-prem Precision-2 is enterprise-only ([pyannoteAI models](https://www.pyannote.ai/md/models)).

**Correction affordances**

- The diarization-only hybrid preserves the ability to swap ASR/alignment independently while gaining better diarization controls, confidence, and optional Lish voiceprint matching.
- Orchestration returns both word and turn views, reducing reconciliation code. It cannot currently combine transcription with speaker identification in the same job, so named-participant mapping remains a separate step ([STT Orchestration docs](https://docs.pyannote.ai/tutorials/speech-to-text-diarization)).

**Privacy, runtime, and maintenance**

- Hybrid mode uploads audio for diarization while retaining ASR locally; orchestration uploads it for both. pyannoteAI documents 24-hour job-result deletion and EU data-residency availability, with plan-dependent details ([STT Orchestration docs](https://docs.pyannote.ai/tutorials/speech-to-text-diarization), [pricing](https://www.pyannote.ai/pricing)).
- Hybrid mode carries both local and API operational surfaces. Orchestration removes local ML hardware but has a monthly plan minimum.

**Decision-relevant inference:** this option makes the transcription and diarization layers independently replaceable and offers the richest overlap/count/confidence controls, but the subscription minimum matters much more than per-episode usage at low volume.

## Cost for a 40.4-minute median episode

`40.4 minutes = 0.6733 hours`. Values below are arithmetic from the cited public rates.

| Option | Public rate used | Median-episode usage cost | Important qualification |
| --- | ---: | ---: | --- |
| Minimal local extension | No provider meter | **$0.00** | Excludes electricity, workstation depreciation, and operator/maintenance time. |
| Local WhisperX | No provider meter | **$0.00** | Same exclusion; extra alignment compute. |
| AssemblyAI Universal-2 + diarization | ($0.15 + $0.02)/hour | **$0.114** | Keyterms included; pay-as-you-go has no minimum. |
| AssemblyAI Universal-3.5 Pro + diarization | ($0.21 + $0.02)/hour | **$0.155** | Add $0.034 per episode for keyterms and another $0.034 for natural-language prompting if both are enabled. |
| Deepgram Nova-3 Monolingual pre-recorded + diarization | ($0.0077 + $0.0020)/minute | **$0.392** | Add $0.053 for keyterm prompting. Deepgram bills per second. |
| OpenAI GPT-4o Transcribe Diarize | Estimated $0.006/minute | **about $0.242** | OpenAI publishes token rates for this model; the per-minute figure is an estimate inferred from its identical token rates to GPT-4o Transcribe in the official pricing table, not a flat guaranteed meter ([model](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize), [pricing](https://developers.openai.com/api/docs/pricing)). |
| pyannoteAI Community-1 diarization only | €0.035/hour | **€0.024** | Requires the €19/month Developer plan; usage consumes included credit. ASR remains separate. |
| pyannoteAI Precision-2 diarization only | €0.112/hour | **€0.075** | Same €19/month minimum; ASR remains separate. |
| pyannoteAI Precision-2 + STT Orchestration | (€0.112 + €0.168)/hour | **€0.189** | Docs say orchestration is charged in addition to diarization; €19/month minimum still applies ([pricing](https://www.pyannote.ai/pricing), [orchestration billing](https://docs.pyannote.ai/tutorials/speech-to-text-diarization#pricing)). |

At one or a few episodes per month, pay-as-you-go all-in-one APIs have the lowest effective cash commitment even if a pyannoteAI unit rate is lower. At higher volume, the pyannoteAI included credit can absorb usage. Local provider cost remains zero, but engineering and review time can dominate all of these sub-dollar API charges.

## Compact capability comparison

| Capability | Local minimal | Local WhisperX | AssemblyAI | Deepgram | OpenAI diarize | pyannoteAI orchestration |
| --- | --- | --- | --- | --- | --- | --- |
| Word start/end | Yes, Whisper-derived | Yes, forced-aligned | Yes | Yes | **No** | Yes |
| Turn start/end | Derived | Derived | Native utterances | Native/derived utterances | Native segments | Native |
| Word confidence | ASR probability | ASR/alignment fields vary | Yes | Yes | **No** | Not documented in reviewed output |
| Speaker confidence | Not from Community-1 | Not from Community-1 | Not documented per word | Yes | No | Precision-2 optional turn confidence |
| Automatic speaker count | Yes | Yes | Yes | Yes, no count controls documented | Yes, no count controls documented | Yes |
| Exact/min/max count control | Yes | Yes | Yes | Not documented | Not documented | Yes |
| Raw overlap-aware regions | Yes | Yes | Not documented | Single label per word | Not documented | Yes |
| Known-speaker audio reference | Custom work | Custom work | Content-based naming add-on | Not documented | Up to four references | Precision-2 voiceprints; not same orchestration job |
| Proper-noun guidance | Hotwords/prompt | Hotwords/prompt | Keyterms/prompt | Keyterms | **Prompt unsupported** | Transcription options are narrower; validate |
| Audio can stay local | Yes | Yes | No | No | No | No (unless Community-1 local instead) |
| ML maintenance | Highest | Highest | Low | Low | Low | Low managed / medium hybrid |

## What the evidence does and does not settle

The sources establish feature availability, price, and important failure modes. They do **not** establish which service produces the best transcript or diarization on this show's microphones, accents, music beds, remote-call compression, names, or conversational style. Public DER/WER values are not directly comparable when corpora, scoring collars, overlap treatment, and speaker-count hints differ.

Before selecting an architecture, run a small bake-off against newly annotated audio rather than treating historical transcripts or descriptions as gold. A useful private evaluation set would contain short, manually corrected excerpts from actual source audio:

1. solo Lish audio with intro/outro music;
2. a clean Lish-plus-guest exchange;
3. backchannels and short interjections;
4. overlap/cross-talk and remote-call artifacts;
5. artist, participant, and brand proper nouns;
6. silence and a plausible future section boundary.

Score each candidate on:

- word error rate and proper-noun error count;
- speaker-count correctness;
- diarization error or, more practically, speaker-attributed word error and manual speaker-flip count;
- percentage and worst-case error of selected word/turn boundaries versus manual source-audio marks, including the ±1 second target;
- whether overlap is detected and whether both voices' words survive;
- median wall-clock runtime, peak memory, upload time, retries, and actual billed usage;
- correction effort in minutes, not only raw model accuracy.

Pin model/version and request parameters for the bake-off. Preserve raw provider/model output and normalize it into one provider-neutral timed-transcript schema. This makes a later architecture decision reversible and allows transcript/content regeneration without retranscribing.

## Decision dimensions left for the architecture ticket

The later decision should explicitly trade:

- local privacy and inspectability against local CPU runtime and ML dependency maintenance;
- forced alignment's additional machinery against the required confidence in future cut points;
- an all-in-one API's simplicity against the ability to swap ASR and diarization independently;
- generic episode-local speakers against a consented Lish reference/voiceprint workflow;
- low per-episode cost against monthly minimums;
- “best average diarization” against correction effort on the show's actual backchannels and overlap.

None of these trade-offs needs to change the durable output contract: source-relative words and turns, anonymous stable speaker IDs, separate participant mapping, preserved raw evidence, explicit overlap, confidence/quality flags where available, and non-destructive corrections.
