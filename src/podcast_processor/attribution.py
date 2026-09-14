"""Conservative publishing attribution backed by clear, identified source sentences."""
import re
from difflib import SequenceMatcher

from .speech import clear_sentence_spans
from .workspace_models import EpisodeMetadata, PreservedTranscript

ATTRIBUTION_VERSION = 'conservative-attribution-v1'


def presence_sentence(metadata: EpisodeMetadata) -> str:
    names = [p.name for p in metadata.participants]
    listing = ' and '.join(names) if len(names) < 3 else ', '.join(names[:-1]) + ' and ' + names[-1]
    return f'This episode features {listing}.'


def supported_quotes(transcript: PreservedTranscript) -> list[dict]:
    names = {s.id: s.participant for s in transcript.speakers
             if s.participant and s.identity_status in ('supported', 'corrected')}
    quotes = []
    for turn in transcript.segments:
        if turn.speaker not in names:
            continue
        for sentence in re.finditer(r'\S.*?(?:[.!?](?=\s|$)|$)', turn.text):
            if any(start <= sentence.start() and sentence.end() <= end for start, end in clear_sentence_spans(turn)):
                quotes.append({'participant': names[turn.speaker], 'text': sentence.group(),
                               'turn_id': turn.id, 'speaker_id': turn.speaker})
    return quotes


def attribution_context(transcript: PreservedTranscript, metadata: EpisodeMetadata) -> dict:
    # The conversation already contains the clear source wording. Avoid repeating
    # the entire episode as a second quote catalog in every paid request.
    names = sorted({s.participant for s in transcript.speakers
                    if s.participant and s.identity_status in ('supported', 'corrected')})
    return {'presence_sentence': presence_sentence(metadata), 'supported_participants': names,
            'policy': 'Presence does not establish story ownership. Use neutral topic copy or an exact supported quote.'}


def validate_attribution(text: str, transcript: PreservedTranscript, metadata: EpisodeMetadata,
                         *, overview: bool = False, portrait: bool = False) -> None:
    """Fail closed on personal references outside narrowly supported renderings.

    Mapping alone cannot establish ownership of a paraphrased personal experience.
    Exact complete source sentences permit useful named quotes without pretending
    that a lexical similarity check verifies a paraphrase's meaning.
    """
    remaining = text.strip()
    if overview:
        presence = presence_sentence(metadata)
        if not remaining.startswith(presence):
            raise ValueError('Attribution: overview must start with the supplied presence_sentence, then neutral topic copy.')
        remaining = remaining[len(presence):].strip()
    for quote in supported_quotes(transcript):
        # The whole field must be the supported quotation: an appended clause can
        # otherwise change ownership or meaning while borrowing a valid citation.
        if remaining in (f'{quote["participant"]}: "{quote["text"]}"',
                         f'{quote["participant"]}: “{quote["text"]}”'):
            return
    aliases = {part for p in metadata.participants for part in re.findall(r'\w+', p.name.casefold())}
    aliases.update(part for s in transcript.speakers for a in s.associations if a.recognized_name
                   for part in re.findall(r'\w+', a.recognized_name.casefold()))
    first_names = {parts[0] for p in metadata.participants
                   if (parts := re.findall(r'\w+', p.name.casefold()))}
    if portrait:
        names = [name for p in metadata.participants for name in (p.name, p.name.split()[0])]
        if any(re.fullmatch(re.escape(name) + r'(?: in (?:close-up|a portrait)| portrait)?', remaining, re.I)
               for name in names):
            return
    tokens = re.findall(r"\w+", remaining.casefold())
    personal = re.search(r'\b(?:I|me|my|mine|myself|we|us|our|ours|ourselves|'
                         r'she|he|her|his|hers|him|herself|himself|they|their|theirs|them|themselves|'
                         r'host|guest|interviewee|interviewer)\b|\b(?:the|our) (?:founder|entrepreneur|mother|father)\b',
                         remaining, re.I)
    named = (any(token in aliases for token in tokens)
             or any(min(len(token), len(name)) >= 4 and SequenceMatcher(None, token, name).ratio() >= .8
                    for token in tokens for name in first_names))
    if named or personal or re.search(r'["“”]', remaining):
        raise ValueError('Attribution: unsupported personal reference or quotation. Use neutral topic-based copy '
                         'addressed to the listener; naming the roster does not prove ownership. A named quote must '
                         'occupy the whole field as Participant: "exact complete supported sentence". '
                         'Portrait subjects may use an approved name with "in close-up".')
