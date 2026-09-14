# Approved show setup

Run `podcast-process setup` once from the project. It locates these existing files
in `audio-files/` in the current directory or a parent:

- `transition-episode-start.WAV` — episode opening
- `transition-in.WAV` — section opening
- `transition-out.WAV` — section closing

Use `--transitions DIRECTORY` for another location. The supplied files are 16-bit
stereo PCM WAV; the preparer also supports 24/32-bit integer PCM WAV. It preserves
sample rate, channels, all content through the last nonzero frame, and interior
silence. Only exact digital silence at the end is replaced. Quiet decay is never
discarded using a detector threshold. Files with a noisy tail retain that noise;
listening establishes whether a prepared version is suitable.

The initial contract uses exactly 2.5 seconds of total ending silence. An explicit
`--ending-silence SECONDS` changes that setting and requires new listening approval.
On September 14, 2026, the user requested half a second removed from all three
initial prepared results, then listened and approved the versions with **2.0 seconds**
of ending silence. That setting is saved locally. A fresh installation can reproduce
it with `podcast-process setup --ending-silence 2`.

Durations are measured from the prepared WAV's frame count and sample rate, including
the ending silence once. The separate section-closing pause remains 1.5 seconds.
No episode media is cut, stitched or exported by setup.

## Listening and reuse

Setup plays the three results sequentially using `afplay` or `ffplay`, then asks
whether all three have been heard and approved. If no player is available, open
the printed WAV paths in an audio player before approving.

```sh
# Prepare files for listening elsewhere, leaving approval pending.
podcast-process setup --prepare-only

# After listening to the saved files, answer the approval prompt.
podcast-process setup --no-play

# Read status, paths and measured durations; --json includes full provenance.
podcast-process inspect-setup

# Explicitly replace recordings or change the preparation setting.
podcast-process setup --transitions path/to/updated-recordings
podcast-process setup --ending-silence 2
podcast-process setup --reprepare
```

An unchanged setup reuses its approved files immediately without preparation or
another approval prompt, even if originals have moved. Explicitly supplied identical
recordings also reuse the same version. A changed recording or setting creates a new
unapproved version; the prior files and approval remain in history. `--reprepare`
uses the originals and saved setting, including when prepared audio needs recovery.

The setup stores the approved identity/audience/voice and these exact recurring links:

- https://www.lishspeaks.com/
- https://www.instagram.com/lishspeaks/
- https://www.illjustletmyselfin.com/

There is no additional recurring promotional paragraph, schedule or sponsor claim.
An episode's explicit `--show-profile` continues to override its editorial inputs.

## Storage and episode snapshots

Defaults live in `output/show-setup/`. Set `PODCAST_SHOW_SETUP` to an absolute path
in the environment or `.env` to reuse one setup from different working directories.
Setup uses one writer, immutable version directories and hash-verified manifests/audio,
with an atomic `current.json` pointer. Prepared files and manifests remain local;
they are not committed to Git.

A full `process` snapshots the approved setup revision, profile revision, settings,
source/prepared fingerprints, sample measurements and listening approval. Copies of
the prepared recordings and setup manifest are retained as immutable episode evidence
before paid work. Resuming uses those copies even if the global setup changes or
disappears. A new episode consumes the current approved setup. Historical episode
profiles remain authoritative unless explicitly overridden.

With missing, unapproved or damaged global setup, independent publishing still runs
using the approved editorial defaults. Planning records **needs-setup** and the full
operation is **partial** (exit 1), with `podcast-process setup` as the next action.
After setup, resume the episode to add the missing evidence without retranscription
or repeated publishing requests. A missing setup never establishes an impossible split.

Automatic natural-cut discovery is separate work in issue #24. Explicit planning
evidence remains available for historical studies; fixture assumptions retain their
fixture labels and never become verified prepared measurements.

## September 14 listening acceptance

The user approved all three shorter versions after hearing them. Original bytes
were preserved. All files are 44,100 Hz, stereo, 16-bit PCM; each prepared file has
88,200 frames (2.0 seconds) of ending silence.

| Transition | Retained source frames | Prepared frames | Measured duration (rounded) |
| --- | ---: | ---: | ---: |
| Episode opening | 473,339 | 561,539 | 12.733311 s |
| Section opening | 191,100 | 279,300 | 6.333333 s |
| Section closing | 279,299 | 367,499 | 8.333311 s |

The saved manifest retains exact frame counts, decimal durations and source/prepared
SHA-256 fingerprints. These replace neither historical fixture evidence nor episode
cut/source acceptance. Controlled CLI tests separately demonstrate preparation,
approval, two isolated new episodes reusing the same defaults, and unchanged resume.
