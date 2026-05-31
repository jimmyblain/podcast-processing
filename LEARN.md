# LEARN.md — The Podcast Processor, Explained

Welcome! This document is the "story" of this project, written so that you — someone
who knows the basics of coding but isn't a career software engineer — can understand
not just *what* the code does, but *why* it's built the way it is, and what lessons
hide inside it. Think of it as a guided tour with a chatty tour guide rather than a
dry instruction manual.

---

## 1. What does this thing actually do?

Imagine you've just recorded a podcast episode. You have a single audio file (an
`.mp3`, say) that's an hour long. To publish it nicely on YouTube, you need four
things:

1. A **transcript** (the words that were spoken, with timestamps).
2. A **description** (the blurb under the video).
3. **Titles** — ideally several catchy options, plus short text for the thumbnail.
4. **Chapters** — those clickable "00:00 Intro / 04:32 Main topic" markers.

Doing all of that by hand is tedious. This tool automates it. You point it at an audio
file, and it hands you all four, ready to paste into YouTube.

The flow, in one sentence: **audio goes in → words come out (transcription) → an AI
reads those words and writes the description, titles, and chapters.**

---

## 2. The two "brains" behind it

This project leans on two very different kinds of AI, and understanding the split is
the key to understanding the whole architecture.

### Brain #1: Whisper (the "ears") — runs on YOUR computer

**Whisper** is a speech-to-text model originally made by OpenAI. We use a fast version
called `faster-whisper`. Its only job: listen to audio and write down the words, with
precise timing for each word.

The important detail: **it runs locally, on your own machine.** Nothing gets uploaded.

*Why local?* Two reasons:
- **Privacy** — your audio never leaves your laptop.
- **Cost** — transcription is the slow, heavy part. Doing it locally means you don't
  pay a cloud service per minute of audio. The trade-off is that it uses your
  computer's CPU/GPU and takes time (often several minutes for an hour of audio).

Think of Whisper as a diligent stenographer sitting in the room with you — slow, but
free and discreet.

### Brain #2: Claude (the "wordsmith") — runs in the cloud

**Claude** is Anthropic's large language model (the same family that powers Claude
Code). It's brilliant at *understanding* and *writing* text. Its job here: read the
transcript Whisper produced and write the human-facing content — the punchy titles,
the SEO-friendly description, the sensible chapter breaks.

This one runs in the cloud via an API, so it needs an **API key** (a password that
proves you're allowed to use it) and it costs a small amount of money per request.

Think of Claude as the creative editor who takes the stenographer's raw notes and
turns them into polished marketing copy.

**The big architectural idea:** use the cheap, private, local tool for the mechanical
work (transcription) and the powerful, paid, cloud tool only for the creative work
(writing). That's a deliberate cost/quality trade-off, not an accident.

---

## 3. The codebase, room by room

The code lives in `src/podcast_processor/`. Here's what each file is responsible for.
A good mental model: each file is a specialist employee who does one job well.

| File | Plain-English role |
|------|--------------------|
| `__main__.py` | The "front door." Lets you run the tool with `python -m podcast_processor`. |
| `cli.py` | The **receptionist / manager.** Reads your command, decides what happens, in what order, and prints messages back to you. This is the orchestrator. |
| `config.py` | The **settings binder.** Knows your API key, default output folder, which models to use. Reads them from a `.env` file or environment variables. |
| `models.py` | The **shape definitions.** Defines what a "Transcript," a "Chapter," a "Title" *look like* as data. Uses Pydantic (more on that below). |
| `transcriber.py` | The **stenographer.** Wraps Whisper. Takes audio, returns a `Transcript`. |
| `llm.py` | The **phone line to Claude.** A thin wrapper that sends a prompt and returns Claude's text, with automatic retries if the call hiccups. |
| `generators.py` | The **content factory.** Contains the three functions that turn a transcript into a description, titles, and chapters. |
| `prompts.py` | The **scripts we read to Claude.** Big template strings telling Claude exactly what to write and in what format. |

### How they connect (the data's journey)

```
  You type a command
        │
        ▼
   cli.py  ──asks──►  transcriber.py  ──uses──►  Whisper (local)
        │                   │
        │              returns a Transcript  (defined in models.py)
        │
        ├──► [SAVE transcript to disk immediately]   ← the safety net (see §5)
        │
        ▼
   cli.py  ──asks──►  generators.py  ──uses──►  llm.py  ──calls──►  Claude (cloud)
                            │                      ▲
                            └── reads templates from prompts.py
        │
   returns GeneratedContent (description, titles, chapters)
        │
        ▼
   cli.py  ──► saves everything to the output/ folder & prints a summary
```

---

## 4. The technologies, and why we chose them

These are the notable libraries. Knowing *why* each was picked is more useful than
knowing *that* it was picked.

- **Typer** — builds the command-line interface. Why: it turns plain Python functions
  into CLI commands almost automatically, using the function's type hints. Less
  boilerplate than the older `argparse`.

- **Pydantic** (and **pydantic-settings**) — the unsung hero. Pydantic lets you declare
  the *shape* of your data ("a Chapter has a `start_time` that's a number and a `title`
  that's text") and then it **enforces** that shape at runtime. If Claude returns
  garbage, Pydantic complains immediately instead of letting a weird value silently
  poison things three steps later. `pydantic-settings` does the same trick for config,
  pulling values out of your `.env` file and validating them.

  *Metaphor:* Pydantic is the bouncer at the club door checking IDs. Bad data doesn't
  get in.

- **faster-whisper** — the local transcription engine. A re-implementation of Whisper
  that's much faster and lighter on memory than the original.

- **anthropic** — the official Python SDK for talking to Claude.

- **tenacity** — a "try again" library. Network calls fail randomly sometimes.
  Tenacity automatically retries failed Claude calls with **exponential backoff**
  (wait 2s, then 4s, then 8s…) so a momentary blip doesn't kill the whole run. See it
  in action as the `@retry(...)` decorator above `generate()` in `llm.py`.

- **rich** — makes the terminal output pretty: spinners while you wait, colored text,
  neat tables summarizing the results. Pure polish, but it makes the tool feel good to
  use.

---

## 5. War stories: the bugs we hit and what they taught us

This is the most valuable section. Real bugs teach more than any tutorial.

### Bug #1 — "`temperature` is deprecated for this model"

**What happened.** We upgraded the Claude model from an older version to **Opus 4.8**.
The very next run crashed with:

> `API error: Error code: 400 - 'temperature' is deprecated for this model.`

**The "why."** Older Claude models accepted a `temperature` setting — a dial from 0 to
1 controlling how "creative" vs. "predictable" the output is. The newer Claude 4 models
(like Opus 4.8) **removed** that dial; they manage that internally now. So sending
`temperature` is no longer "an option it ignores" — it's an outright error that the API
*rejects*.

**The trap we nearly fell into.** The obvious fix is to delete `temperature` from
`llm.py`, where the API call lives. We did — but that **wasn't enough**. The
`temperature` value was actually being passed in from *three other places* in
`generators.py` (`client.generate(prompt, temperature=0.7)` and friends). If we'd only
fixed `llm.py`, those three calls would have crashed in a *new* way:
`TypeError: generate() got an unexpected keyword argument 'temperature'`. We'd have
swapped one bug for another.

**The lesson — fix the whole call chain, not just the error line.** When you remove or
rename something (a function argument, in this case), you must hunt down *every place
that uses it*. A quick `grep -rn "temperature" src/` confirmed we'd caught them all.
**Search is your friend; "it compiles" is not the same as "it's correct."**

### Bug #2 — the lost transcript (the expensive-work-thrown-away bug)

**What happened.** While Bug #1 was still live, a run transcribed an entire episode
(several minutes of Whisper churning away)… and then crashed during content generation.
The transcript was **gone** — never written to disk. All that work, lost.

**The "why."** Look at how the old `cli.py` was structured. Roughly:

```python
try:
    transcript = transcriber.transcribe(audio_file)   # slow & expensive
    content    = generate_all_content(...)            # crashed HERE
    save_outputs(transcript, content)                 # never reached
except LLMError:
    ...
```

Everything — transcribe, generate, **and save** — sat inside *one* `try` block. When
generation threw an error, Python leapt straight to the `except` and exited, **skipping
the save entirely.** The transcript existed only in memory (RAM), and memory vanishes
the instant the program stops.

**The fix.** Save the expensive result *the moment you have it*, before attempting
anything that might fail:

```python
transcript = transcriber.transcribe(audio_file)   # step 1
save_outputs(transcript, content=None)             # step 2: SAVE NOW
content    = generate_all_content(...)             # step 3 (may fail — that's OK now)
save_outputs(transcript, content)                  # step 4: save the rest
```

If step 3 fails, the transcript is already safe on disk, and the error message now
tells you how to resume: `podcast-process generate "output/<episode>/transcript.json"`.

**The lesson — persist expensive, hard-to-reproduce work as early as possible.** Don't
let a cheap, retryable step (a 2-second API call) act as a gatekeeper for saving an
expensive, slow step (10 minutes of transcription). This is the same instinct behind a
video game's autosave: save *after* the hard boss fight, not only when you reach the
final screen.

A related sub-lesson: **structure your `try/except` blocks around failure boundaries.**
One giant try block treats unrelated steps as all-or-nothing. Splitting them lets each
failure be handled — and recovered from — independently.

---

## 6. How good engineers think (patterns visible in this code)

A few habits worth internalizing, all of which show up here:

- **Separation of concerns.** Notice no single file does everything. `transcriber.py`
  doesn't know about Claude; `llm.py` doesn't know about audio. Each piece can be
  understood, tested, and replaced on its own. If you wanted to swap Claude for a
  different AI tomorrow, you'd touch `llm.py` and almost nothing else.

- **Fail loudly and early.** Pydantic rejects bad data at the door. The CLI checks for
  a missing API key *before* doing any slow work, not after.

- **Design for resumability.** Because the transcript is saved separately and there's a
  standalone `generate` command, a failure halfway through isn't fatal — you can pick
  up where you left off. This is *why* the three commands (`process`, `transcribe`,
  `generate`) exist as separate entry points rather than one monolithic button.

- **Make waiting pleasant.** The `rich` spinners and tables aren't strictly necessary,
  but a tool that communicates "I'm working, here's progress" is far less stressful to
  use than one that sits silent. Good engineers think about the human on the other end.

- **Lazy loading.** The Whisper model is large and slow to load, so `transcriber.py`
  only loads it on the *first* transcription (`_load_model`), not when the program
  starts. You don't pay that cost if you're just running `--help`.

---

## 7. Pitfalls to watch for in the future

- **Hard-coded limits hide silently.** `generators.py` truncates the transcript before
  sending it to Claude, to stay within the model's token limit. This cap lives in one
  named constant — `MAX_TRANSCRIPT_CHARS` — precisely so it's easy to find and reason
  about rather than buried as a "magic number." It was originally `50,000` characters
  (a value sized for an older, smaller model), which meant Claude only "saw" the first
  ~30 minutes of a long episode. We raised it to `500,000` (~125k tokens) to match Opus
  4.8's 200k-token context window with safe headroom, so full multi-hour episodes are
  now read end to end. *The lesson:* limits sized for an old model don't update
  themselves when you upgrade — revisit them. For truly enormous transcripts that still
  exceed the cap, a future improvement would be to summarize in chunks, then combine.

- **JSON from an AI is not guaranteed to be valid JSON.** `generators.py` has an
  `_extract_json` helper and `try/except json.JSONDecodeError` precisely because an LLM
  *usually* returns clean JSON but occasionally wraps it in chatter. Never trust that
  model output is perfectly formatted; always parse defensively.

- **Model upgrades can change the rules.** Bug #1 is the cautionary tale: moving to a
  newer model isn't always a drop-in swap. Parameters get deprecated, defaults change.
  When you bump a model version, read its release notes and test a real run.

---

## 8. The quickest way to use it

```bash
# One-time setup
uv venv && uv pip install -e .      # create environment, install the tool
brew install ffmpeg                 # Whisper needs this to read audio files
export ANTHROPIC_API_KEY=your-key   # or put it in a .env file

# The main event: transcribe + generate everything
podcast-process process episode.mp3

# Just the transcript, no AI/cost
podcast-process transcribe episode.mp3

# Already have a transcript and want to (re)generate content from it
podcast-process generate "output/episode/transcript.json"
```

Everything lands in `output/<episode-name>/`: `transcript.json`, `transcript.txt`,
`description.md`, `titles.json`, and `chapters.txt`.

---

*Happy processing — and remember the two big lessons: **fix the whole call chain, not
just the error line**, and **save expensive work the moment you have it.***
