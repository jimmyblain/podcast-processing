# Podcast Processing

This context describes the language used to turn a podcast episode into a timed transcript and a YouTube publishing package.

## Language

**Episode**:
The source recording and authoritative metadata for one publishable podcast installment.
_Avoid_: Audio file, job

**Speaker**:
An anonymous voice identity detected within one episode. A speaker label is stable within the episode but does not assert a real-world identity.
_Avoid_: Person, participant

**Participant**:
A known person appearing in an episode who may be mapped to a detected speaker.
_Avoid_: Speaker

**Host**:
Lish Speaks, the recurring primary participant in every episode.
_Avoid_: Speaker 1

**Guest**:
A participant other than the host. An episode may have zero or more guests.
_Avoid_: Secondary speaker

**Timed transcript**:
The episode's spoken text arranged into speaker-attributed turns with positions on the source-audio timeline, serving the publishing package and future section-boundary workflow.
_Avoid_: Transcript

**Speaker turn**:
A span of episode speech attributed to one detected speaker, which may overlap another speaker's turn.
_Avoid_: Paragraph, chapter

**Publishing package**:
The description, title and thumbnail concepts, and YouTube chapters prepared for one episode.
_Avoid_: Generated content

**Completion report**:
A concise account of the run's outcomes, unresolved uncertainties, and fallbacks used, separate from the publishing package. Any suggested review is optional and does not hold up completion.
_Avoid_: Approval queue

**Show profile**:
The reusable, approved identity and editorial defaults for the podcast, including its host, name, audience, official links, and standard promotional text.
_Avoid_: Episode metadata

**Episode metadata**:
User-approved information about one episode, including its participants and any supplied angle, biographies, links, sponsors, or current context.
_Avoid_: Show profile, inferred facts

**Current context**:
Optional user-supplied background that makes an episode's discussion relevant to its intended publication circumstances.
_Avoid_: Automatic web enrichment

**Thumbnail concept**:
Short overlay text paired with visual direction for a title concept; it is not a generated image.
_Avoid_: Thumbnail

**YouTube chapter**:
A copy-paste-ready timestamp and chapter title with no trailing description.
_Avoid_: Chapter subtitle

**Section boundary**:
A proposed cut point on the episode timeline for a future clip workflow; it is not an exported clip.
_Avoid_: Section

**Episode part**:
One of three consecutive portions that together cover the entire episode, in order, without omitted or repeated content.
_Avoid_: Excerpt, highlight

**Finished section**:
An episode part with its applicable transition audio and transition pauses included.
The first two sections have opening and closing transitions; the third has only an
opening transition and plays through the original episode ending. Its duration
includes all applicable elements.
_Avoid_: Episode part, section boundary

**Transition audio**:
An audio asset added before or after a future clip to provide an intentional opening or closing.
_Avoid_: Intro/outro
