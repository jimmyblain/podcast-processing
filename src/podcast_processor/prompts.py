"""Prompt templates for content generation."""

DESCRIPTION_PROMPT = """You are an expert YouTube content strategist. Create an engaging YouTube description for this podcast episode.

TRANSCRIPT:
{transcript}

Create a YouTube description with these sections:
1. **Hook** (2-3 compelling sentences that grab attention and create curiosity)
2. **Summary** (3-5 bullet points covering the main topics/takeaways)
3. **Call to Action** (subscribe, like, comment prompt)

Guidelines:
- Write in an engaging, conversational tone
- Include relevant keywords naturally for SEO
- Keep the total description under 500 words
- Use line breaks for readability
- Don't use hashtags (those go separately)

Output ONLY the description text, no additional commentary."""

TITLES_PROMPT = """You are a viral YouTube title expert. Generate 10 compelling title variations for this podcast episode.

TRANSCRIPT:
{transcript}

For each title, provide:
1. The title (under 60 characters for full display)
2. Thumbnail text (2-4 words that would overlay on a thumbnail)
3. Brief reasoning for why this title works

Use these proven title formulas:
- Curiosity gap ("I Tried X for 30 Days...")
- Contrarian take ("Why X is Actually Wrong")
- How-to with benefit ("How to X (Without Y)")
- List format ("5 Things...")
- Story hook ("The Day I Realized...")
- Question format ("Is X Really Worth It?")
- Urgency/Warning ("Stop Doing X Before...")

Output as valid JSON array with this structure:
[
  {{
    "title": "The video title here",
    "thumbnail_text": "SHORT TEXT",
    "reasoning": "Why this works"
  }}
]

Generate exactly 10 unique titles with different approaches. Output ONLY the JSON array."""

CHAPTERS_PROMPT = """You are a podcast editor creating YouTube chapters. Analyze this transcript and identify the major topic transitions.

TRANSCRIPT WITH TIMESTAMPS:
{transcript_with_timestamps}

REQUIREMENTS:
- Create {chapter_count} chapters that cover the full episode
- First chapter must start at 00:00
- Each chapter should represent a distinct topic or segment
- Titles should be concise (2-6 words) and descriptive
- Align chapter starts to natural topic transitions in the transcript

Output as valid JSON array with this structure:
[
  {{
    "start_time": 0.0,
    "title": "Introduction",
    "description": "Welcome and episode overview"
  }},
  {{
    "start_time": 154.5,
    "title": "Main Topic",
    "description": "Discussion of the core subject"
  }}
]

Use the actual timestamps from the transcript. Output ONLY the JSON array."""
