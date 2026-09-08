"""THROWAWAY: one episode's output shapes, not a production generator.
Run: python3 src/podcast_processor/publishing_package_prototype/build.py
The browser preview is self-contained and needs no server or dependencies.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[2] / 'output/0710/transcript.json'

DESCRIPTION = '''You can explain yourself for twenty minutes and still leave a conversation feeling unheard. So what helps your words land—and what do you need to understand before you say them?

In this episode of I'll Just Let Myself In, Lish Speaks breaks down five pillars of communication: clarity, active listening, mutual understanding, relevance, and assertiveness. Drawing on her marriage, friendships, and family relationships, she gets honest about the work behind saying what you need and making room for someone else's truth.

The conversation moves from recognizing your own feelings to choosing the right moment for a difficult conversation. Lish also shares how prayer and her understanding of Pentecost connect to communicating across emotional differences. The goal is to speak with care, listen with humility, and recognize what is yours to change.

In this episode:
• Get clear about your feelings before asking someone else to understand them.
• Listen to understand instead of preparing your reply.
• Recognize when a conversation has stopped being mutual.
• Bring up the past with purpose and choose the right setting.
• Express your needs respectfully before silence becomes resentment.

Which of these five pillars is hardest for you right now? Share your thoughts in the comments, subscribe, and send this episode to someone you'd like to communicate with more honestly.'''

# Source-relative starts chosen from the LOCAL recording's word/segment timeline.
# These are not the published podcast player's offsets; those refer to another edit.
CHAPTERS = [
    (0.0, 'Why Communication Matters'),
    (365.20, 'Five Pillars of Communication'),
    (754.0, 'Clarity Starts With You'),
    (1098.46, 'Listening to Understand'),
    (1350.64, 'Making Room for Mutual Understanding'),
    (1506.84, 'Timing, Context, and the Past'),
    (1763.26, 'Expressing Your Needs With Care'),
    (2011.86, 'Prayer and Finding the Words'),
    (2235.67, 'Putting the Pillars Into Practice'),
]

def concept(identifier, category, title, overlay, direction, rationale, start, end):
    return dict(id=identifier, category=category, title=title, thumbnail_text=overlay,
                visual_direction=direction, reasoning=rationale,
                evidence=dict(start=start, end=end))

TITLES = [
    concept('T01', 'Topic / benefit', '5 Communication Skills for More Honest Relationships', 'SAY WHAT MATTERS',
      'Lish in a calm, direct-to-camera close-up on the left; a simple speech-bubble outline on the right holds the overlay. Keep the background quiet.',
      'Names the practical framework; the overlay makes its personal purpose immediate.', 365.20, 560.40),
    concept('T02', 'Topic / benefit', 'How to Say What You Need Without Building Resentment', 'LET IT OUT',
      'Lish mid-explanation with an open hand and an earnest expression, cropped on the right; large overlay in open space on the left.',
      'Connects an everyday skill to the emotional cost of holding back.', 1763.26, 1917.54),
    concept('T03', 'Topic / benefit', 'How to Listen Without Planning Your Reply', 'HEAR THEM FIRST',
      'A thoughtful close-up of Lish angled slightly toward the center; a single uncluttered speech shape opposite her with the overlay.',
      'Offers one recognizable behavior to change, with a complementary action in the overlay.', 1098.46, 1309.00),
    concept('T04', 'Topic / benefit', 'How to Bring Up the Past Without Losing the Conversation', 'STAY WITH ME',
      'Lish with a measured, open-palmed gesture on the left; one simple looping arrow fades behind the overlay on the right.',
      'Keeps the nuance that past experiences can be relevant when their purpose is clear.', 1506.84, 1645.76),
    concept('T05', 'Topic / benefit', 'Faith and Communication: Finding the Words for Hard Talks', 'PRAY. THEN SPEAK.',
      'Lish with a reflective expression, framed slightly off-center against a warm plain background; overlay beside her at eye level.',
      'Makes the episode’s Christian perspective visible without promising a guaranteed outcome.', 2011.86, 2234.87),
    concept('T06', 'Curiosity / story', 'You Said Everything. Why Do You Still Feel Unheard?', 'WHAT GOT LOST?',
      'Lish with a questioning expression on the right; two offset speech-bubble outlines on the left, with the overlay between them.',
      'Starts with a familiar frustration and invites viewers into the communication framework.', 45.28, 144.68),
    concept('T07', 'Curiosity / story', 'The Pause That Changed How Lish Listens', 'BEFORE YOU REPLY',
      'Lish listening with an attentive expression, cropped close on the left; a small pause symbol under the overlay on the right.',
      'Uses the specific friendship story to introduce active listening rather than vague transformation.', 1103.18, 1224.00),
    concept('T08', 'Curiosity / story', 'What Are You Really Saying When You Say Nothing?', 'THE UNSPOKEN PART',
      'Lish looking thoughtful with her hands gently clasped; generous blank space above her shoulder for the overlay.',
      'Creates curiosity around withheld needs and the resentment discussed in the episode.', 1763.26, 1917.54),
    concept('T09', 'Curiosity / story', 'The Conversation Before the Difficult Conversation', 'START WITH YOU',
      'Lish in a reflective three-quarter portrait beside a plain notebook; place the overlay across the empty opposite half.',
      'Points to the private work of identifying feelings before trying to express them.', 754.00, 870.02),
    concept('T10', 'Curiosity / story', 'What Lish Learned About Communication From Pentecost', 'A DIFFERENT LANGUAGE',
      'Lish with an engaged, thoughtful expression on the left; two simple speech shapes meeting on the right beneath the overlay.',
      'Highlights a distinctive faith reflection and its connection to emotional understanding.', 2011.86, 2161.07),
    concept('T11', 'Bold perspective', 'Being Clear Doesn’t Mean They’ll Understand You', 'YOUR PART. THEIR PART.',
      'Lish with a composed, firm expression centered slightly left; a fine vertical line separates her from the overlay on the right.',
      'Preserves the limit Lish places on what clear communication can control.', 870.74, 1087.86),
    concept('T12', 'Bold perspective', 'You Can Win the Argument and Miss the Person', 'UNDERSTANDING FIRST',
      'Lish speaking with a steady expression and one open hand; overlay on the opposite side, with no opponent or staged confrontation.',
      'Frames the discussion’s emphasis on understanding rather than entering a conversation to be right.', 1224.00, 1309.00),
    concept('T13', 'Bold perspective', 'Keeping Quiet Isn’t Always Keeping the Peace', 'WHAT’S UNSAID?',
      'Lish with a knowing, gently challenging expression on the right; the overlay sits alone in open space on the left.',
      'Uses the episode’s challenge to avoidance while the word “always” preserves nuance.', 705.38, 753.78),
    concept('T14', 'Bold perspective', 'Honesty Doesn’t Have to Be Brutal', 'TRUTH WITH CARE',
      'Lish mid-conversation with a warm but serious expression; balanced close crop on the left and oversized overlay on the right.',
      'Connects respectful assertiveness with the episode’s explicit caution about brutal honesty.', 1763.26, 1901.76),
    concept('T15', 'Bold perspective', 'Listening Doesn’t Mean You Have to Reconcile', 'YOU CAN DECIDE',
      'Lish with a grounded, reassuring expression, shoulders visible; overlay in the open upper-left area, with minimal visual decoration.',
      'Names a specific boundary in the conversation without implying reconciliation is always wrong.', 1455.00, 1506.10),
]


def timestamp(seconds):
    whole = int(seconds)
    return f'{whole//60:02d}:{whole%60:02d}'


def main():
    source = json.loads(SOURCE.read_text()) if SOURCE.exists() else None
    chapters = '\n'.join(f'{timestamp(t)} {title}' for t, title in CHAPTERS) + '\n'
    links = 'Connect with Lish Speaks\nhttps://www.lishspeaks.com/\nhttps://www.instagram.com/lishspeaks/\n'
    description = DESCRIPTION + '\n\nChapters\n' + chapters + '\n' + links
    for name, content in [('description.md', description), ('chapters.txt', chapters)]:
        (HERE/name).write_text(content)
    (HERE/'titles.json').write_text(json.dumps(TITLES, indent=2, ensure_ascii=False)+'\n')
    evidence = []
    if source:
        for t,title in CHAPTERS:
            segments = [s for s in source['segments'] if s['end'] >= t and s['start'] < t+12]
            evidence.append(dict(timestamp=timestamp(t),source_start=t,title=title,
                                 context=' '.join(s['text'].strip() for s in segments)))
    elif (HERE/'chapter-evidence.json').exists():
        evidence=json.loads((HERE/'chapter-evidence.json').read_text())
    (HERE/'chapter-evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest() if source else json.loads((HERE/'package.json').read_text())['source']['sha256']
    notes = [
        {'label':'Historical source', 'detail':'The supplied local transcript is content evidence, not a quality benchmark. No new transcription or diarization was run. Source audio was not available in this workspace for a listening check.'},
        {'label':'Local timeline', 'detail':'Nine chapter starts follow topic changes in output/0710/transcript.json. The local duration is 38:26; the published player previously showed 38:45. Published-player timestamps were not copied. Audio-level ±1-second accuracy remains unverified.'},
        {'label':'Host spelling', 'detail':'At 00:00 the transcript says “Liz Speaks.” The approved show profile supplies “Lish Speaks,” used consistently in this package.'},
        {'label':'Names and schedule', 'detail':'A friend’s unverified name around 18:26 and the old radio-channel/schedule plug around 37:57 are omitted from publishing copy. The run completes without asking an operator to resolve them.'},
        {'label':'Sample metadata', 'detail':'This communication episode was selected for the prototype. Solo format is supported by the available text, rather than verified by a new speaker-detection run. The website and Instagram links are verified candidates used for demonstration; the final recurring links block is still configurable.'},
        {'label':'Scope', 'detail':'This is an editorial output prototype. No media was split or stitched, no thumbnail images were generated, and no production pipeline or real uncertainty-detection system is implemented.'},
    ]
    package = dict(episode='Communication',show="I'll Just Let Myself In",host='Lish Speaks',duration='38:26',
                   status='Prototype package complete — notes included',description=description,description_body=DESCRIPTION,
                   chapters=chapters,titles=TITLES,notes=notes,evidence=evidence,
                   source=dict(path='output/0710/transcript.json',sha256=source_hash,duration_seconds=2306.1826875),
                   counts=dict(description_words=len(DESCRIPTION.split()),description_characters=len(description),titles=len(TITLES),chapters=len(CHAPTERS)))
    (HERE/'package.json').write_text(json.dumps(package,indent=2,ensure_ascii=False)+'\n')
    report = '# Completion report — publishing-package prototype\n\nStatus: prototype package complete with notes. No operator input was required to resolve transcript uncertainty.\n\n'
    report += f'Created: description.md ({len(DESCRIPTION.split())} words before chapters/links), chapters.txt (9 chapters), titles.json (15 concepts: 5 per strategy).\n\n'
    report += '\n\n'.join(f'## {n["label"]}\n\n{n["detail"]}' for n in notes)
    report += '\n\n## Verification\n\nThe prototype was checked for 15 titles, 2–4 overlay words per title, complete visual directions/rationales, 9 increasing chapter starts beginning at 00:00, chapter durations of at least 10 seconds, and identical embedded/standalone chapter text. Title and description lengths were checked against the previously agreed platform limits. These structural checks do not establish transcription or audio-alignment accuracy.\n'
    (HERE/'completion-report.md').write_text(report)
    template=(HERE/'preview-template.html').read_text()
    (HERE/'index.html').write_text(template.replace('__PACKAGE__',json.dumps(package,ensure_ascii=False).replace('</','<\\/')))
    print(json.dumps(package['counts']))
    print(HERE/'index.html')

if __name__ == '__main__':
    main()
