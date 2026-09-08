# Publishing-package prototype

**THROWAWAY — editorial sample approved on 2026-09-07.** This is the concrete sample for [Prototype the copy-paste-ready publishing package](https://github.com/jimmyblain/podcast-processing/issues/6). It is an approved editorial reference, not a production generator or a verified transcription/timing golden.

## Question

Does the agreed publishing contract produce a useful, copy-paste-ready package for a real episode, and can an operator unfamiliar with the episode use the result without resolving transcript uncertainty?

## Open it

Double-click `index.html`. It is a self-contained HTML file; no server, packages, or account are needed. The other files are directly usable even without the preview.

The floating bottom bar switches three structurally different views of the same content:

- **A · Read:** a full description reading view, preceded by the selected title/thumbnail brief.
- **B · Copy desk:** a file navigator, plain-text copy area, and selected-concept panel.
- **C · Compare:** all 15 title concepts in three strategy tables with visual directions and rationales.

The `variant` URL parameter accepts `A`, `B`, or `C`; arrows cycle between views. Keyboard left/right also cycles, except while a text control has focus. A title selected in Compare carries into the other views while the page remains open. Selection is intentionally not persisted. All 15 concepts remain in the exported package regardless of selection.

Use the copy buttons for the chosen title, overlay, or file. The description includes the exact standalone chapter text. Downloads point to adjacent files; keep this directory together to retain those downloads. The preview itself contains all sample data inline.

## Files

- `description.md`: 217-word main copy plus nine chapters and sample official links.
- `chapters.txt`: exact timestamp-plus-title lines on the local recording timeline.
- `titles.json`: exactly 15 title/overlay/visual-direction/rationale concepts, five per strategy, with source ranges for editorial traceability.
- `completion-report.md`: real source limitations and the conservative decisions used to finish the sample.
- `chapter-evidence.json`: short local-transcript excerpts supporting the selected topic starts.
- `package.json`: the complete sample, source fingerprint, and counts.
- `index.html`: self-contained generated review preview.
- `preview-template.html` and `build.py`: the throwaway authoring source.

To regenerate the included sample:

```sh
python3 src/podcast_processor/publishing_package_prototype/build.py
```

If `output/0710/transcript.json` is available, chapter evidence and its fingerprint are refreshed from it. Otherwise the included evidence and fingerprint are retained. An optional first argument supplies that same episode transcript from another location; this script is a fixed sample builder, not a general episode generator.

## Source and assumptions

Selected episode: the local communication episode in `output/0710/transcript.json`, duration 2306.1826875 seconds (38:26). This representative solo sample was chosen because its five explicit topic pillars make the output easy to judge. Lish Speaks and the show name come from the approved show profile. Solo status is supported by the text; it was not newly diarized. Sample link choices are verified official website/Instagram candidates and remain configurable.

The historical transcript is source material, **not a quality benchmark**. No existing description or title set was reused. All sample publishing copy was newly authored for this prototype. The full private transcript and source audio are not committed. Short chapter excerpts and a source fingerprint provide provenance.

The published podcast player previously showed a different duration, so its timestamps were not reused. No claim of audio-verified ±1-second alignment is made. The name discrepancy at the opening, unverified friend name, and old schedule/channel plug are documented with fallbacks in the completion report. This illustrates nonblocking completion; it does not implement automatic detection of those conditions.

## Verification and verdict

Passed one-off structural checks: 15 distinct titles, 5/5/5 strategy mix, title length limits, 2–4 overlay words, populated visual directions/rationales, 9 chronological chapter starts at least 10 seconds apart, final-chapter duration, and identical embedded/standalone chapter text. Main-description word count and total character length are within the agreed bounds.

The browser tool blocked local-file navigation. The preview has not received an interactive browser smoke check in this session. JavaScript syntax was checked separately. No prototype test suite was introduced.

**Verdict: approved by the user on 2026-09-07.** The user confirmed the voice across the package, liked all 15 titles, found the thumbnail briefs sufficient, and accepted the operator experience and completion report. Favorite titles are T01, T06, and T13, one from each strategy. See [the recorded review](REVIEW.md). This approves the editorial sample and output shapes; audio timing and production automation remain unverified. No single preview layout was selected as a production UI requirement. The original CLI is unchanged.
