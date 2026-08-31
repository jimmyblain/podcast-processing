# YouTube publishing-package constraints

Research date: 2026-08-30

## Question and evidence standard

What do current primary YouTube and Google sources require or recommend for copy-paste-ready video chapters, titles, descriptions, and thumbnail presentation?

This report separates platform requirements from editorial or implementation inferences. It deliberately excludes third-party SEO advice and undocumented claims about “the algorithm.”

## Executive conclusion

The publishing package can be made deterministic at the platform boundary: emit chapter lines in a single timestamp-and-label form, validate YouTube's three published chapter rules, keep titles within 100 characters, and keep descriptions within 5,000 characters for Studio or 5,000 UTF-8 bytes for a future Data API uploader. Discoverability is not a metadata-only optimization problem. YouTube officially describes Search in terms of relevance, engagement, and quality, and recommends accurate audience-facing packaging rather than keyword density.

## Copy-paste chapter contract

### Official requirements

YouTube says manual chapters belong in the video description as a list of timestamps and titles. The first timestamp must start with `00:00`, the list must contain at least three timestamps in ascending order, and every chapter must be at least 10 seconds long. Manual chapters override automatic chapters. Access to Advanced features is required; chapters may be unavailable when a channel has an active strike or the content may be inappropriate to some viewers. See [Video Chapters](https://support.google.com/youtube/answer/9884579?hl=en).

Google's first-party guidance for timestamps in YouTube descriptions supplies the remaining syntax details: use `[hour]:[minute]:[second]` and omit the hour when unnecessary; put the label on the same line as its timestamp; put each timestamp on a new line; give every label at least one word; and keep the lines chronological. See [Best practices for marking timestamps on YouTube](https://developers.google.com/search/docs/appearance/structured-data/video#youtube-timestamps).

Together, those sources support this copy-paste form:

```text
00:00 Opening Topic
08:14 Core Discussion
21:07 Closing Takeaways
```

For an episode beyond one hour, the documented timestamp grammar includes the hour, for example `1:03:15 Topic Name`. The current YouTube chapter page specifically says the first timestamp starts with `00:00`, so the generator should not rely on the looser `0:00` form even though older first-party examples have used it.

YouTube documents one timestamp plus one title/label per line. It does not define a second chapter subtitle field. Any trailing “subtitle” would simply become part of the visible chapter title. A parser-safe `chapters.txt` should therefore contain only timestamp-and-title lines: no heading, Markdown fence, bullets, separator punctuation, or trailing subtitle text.

### Validation derived from the official rules

Before writing `chapters.txt`, validate all of the following:

- The first line begins exactly with `00:00`.
- There are at least three timestamp-and-title lines.
- Timestamps are strictly increasing and within the source video's duration.
- Each boundary is at least 10 seconds after the preceding boundary.
- The final chapter lasts at least 10 seconds, measured from its timestamp to the video end.
- Each timestamp has one nonempty title on the same line.
- Times under one hour use `MM:SS`; times at or beyond one hour use `H:MM:SS` consistently.

The in-bounds, strict-order, and final-chapter checks are implementation consequences of the published ordering and minimum-duration rules. YouTube does not publish a chapter-validation API or a more detailed punctuation grammar. A Studio smoke test with a representative over-one-hour episode should remain an acceptance check.

## Documented field and image limits

| Artifact | Current official constraint | Practical consequence |
| --- | --- | --- |
| Episode video title | YouTube Studio allows at most 100 characters. The Data API also disallows `<` and `>`. | Validate every suggested title at 100 characters or fewer; exclude `<` and `>` for API portability. |
| Episode video description | Studio documents 5,000 characters. The Data API documents 5,000 UTF-8 bytes and disallows `<` and `>`. | Copy-paste output may use the Studio limit; a future API uploader should enforce the stricter byte limit and character exclusions. |
| Episode video thumbnail | Current recommendation: 3840×2160, minimum width 640, JPG or PNG, 16:9. Custom upload requires a verified account. Current size limits are 2 MB on mobile and 50 MB on desktop. | A future image generator should target 16:9 at the current recommended resolution and record the intended upload path when validating file size. |
| Podcast show/playlist artwork | Separate from an episode thumbnail: 1:1, with 1280×1280 recommended. Current size limits are 10 MB on mobile and 50 MB on desktop. | Do not apply square podcast-show artwork requirements to episode thumbnail briefs. |

Sources: [Edit video settings](https://support.google.com/youtube/answer/57404?hl=en), [YouTube Data API video resource](https://developers.google.com/youtube/v3/docs/videos), [Add custom thumbnails](https://support.google.com/youtube/answer/72431?hl=en), and [Create a podcast in YouTube Studio](https://support.google.com/youtube/answer/12751636?hl=en).

The current thumbnail page supersedes the widely repeated older 1280×720 / 2 MB desktop advice: as of the research date it recommends 3840×2160 and allows 50 MB on desktop. “Two to four overlay words” is not an official YouTube limit; it is an editorial constraint the application may adopt for readability.

All thumbnail concepts and eventual images must accurately represent the episode. YouTube prohibits thumbnails that mislead viewers about what the video contains and restricts sexual, violent, shocking, or otherwise violative imagery. See the [Thumbnails policy](https://support.google.com/youtube/answer/9229980?hl=en).

## Official discoverability guidance

### What YouTube says influences discovery

YouTube Search prioritizes relevance, engagement, and quality. Relevance includes how well the title, tags, description, and video content match a query; engagement includes signals such as watch time for the query; quality includes signals of expertise, authoritativeness, and trustworthiness. Metadata alone therefore cannot guarantee ranking. See [How YouTube Search works](https://support.google.com/youtube/answer/16090438?hl=en) and the [YouTube performance FAQ](https://support.google.com/youtube/answer/141805?hl=en).

For titles, YouTube recommends accuracy and brevity, important words near the beginning, and episode numbers or branding at the end. It recognizes both searchable titles, which make the expected content explicit, and intriguing titles, which create honest curiosity. It warns against misleading, sensational, shocking, and visually “loud” packaging. See [Thumbnail & title tips](https://support.google.com/youtube/answer/12340300?hl=en).

For descriptions, YouTube recommends a unique description for each video, an explanation of the video in the first few lines, and one or two main topic words featured prominently in both the title and description. It points creators to the Research tab in YouTube Analytics and Google Ads Keyword Planner for actual audience language. See [Tips for video descriptions](https://support.google.com/youtube/answer/12948449?hl=en).

For thumbnails, YouTube recommends a clear target audience, readable text when text is used, simple composition, high resolution, and evaluation through channel Analytics. The thumbnail and title should set an expectation the episode fulfills. See [Thumbnail & title tips](https://support.google.com/youtube/answer/12340300?hl=en).

Tags are not essential for discovery and are primarily useful for common misspellings. See [Add tags to your YouTube videos](https://support.google.com/youtube/answer/146402?hl=en). Hashtags are clickable discovery aids, but YouTube does not say that using exactly three improves ranking. Up to three description hashtags may appear by the title; more than 60 causes all hashtags to be ignored and may create policy risk. See [Find playlists & videos using hashtags](https://support.google.com/youtube/answer/6390658?hl=en).

Native YouTube A/B testing accepts up to three title/thumbnail variants at once and selects by watch-time share rather than click-through rate alone. Generating 15 concepts can be useful ideation, but 15 is not a platform requirement; the package could separately identify the strongest three for a native test. See [A/B test titles & thumbnails](https://support.google.com/youtube/answer/16391400?hl=en).

### Podcast-specific guidance

On YouTube, a podcast is a playlist of full-length episode videos. YouTube recommends keeping all seasons in that one podcast, excluding clips and unrelated uploads, using the show's actual name as the podcast title without adding “podcast” unless it is part of the name, and providing a detailed show description. Within the podcast, each video should use the episode name and may optionally include the show name. See [Podcast discovery tips](https://support.google.com/youtube/answer/12950577?hl=en).

## Implications for the future publishing-package decision

The following are reasoned product implications, not new YouTube rules:

- Define “SEO-focused” as accurate audience and query fit, not keyword stuffing or a promised ranking outcome.
- Put the episode subject, participant context, and viewer value in the opening lines of a unique, natural description; place reusable channel copy later.
- Produce both searchable and curiosity-led title concepts, but require every concept to make a promise supported by the transcript and supplied metadata.
- Keep the proposed two-to-four-word thumbnail overlay and one-sentence visual brief as house style, not platform compliance.
- Treat “up to three hashtags” as a configurable presentation choice, not an optimization guarantee.
- Keep chapter output as an exact standalone text artifact and reject generated subtitles or explanatory suffixes before writing it.
- If upload automation is later added, use the Data API's stricter UTF-8 byte and character rules rather than assuming Studio's UI counters are identical.

These findings constrain a later publishing contract; they do not decide its voice, content rubric, or evaluation examples.
