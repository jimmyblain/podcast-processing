"""Controlled publishing responses; fixtures prove structure, not editorial acceptance."""
import json

def response_for(prompt):
    if 'STAGE: titles' in prompt:
        return json.dumps([{'title': title, 'category': ['topic/benefit', 'curiosity/story', 'bold-perspective'][i // 5],
            'thumbnail_text': 'Start With Care',
            'visual_direction': {'subject': 'Lish in close-up', 'expression': 'Thoughtful and warm',
                                 'composition': 'Portrait left, overlay right on a plain background'},
            'reasoning': 'The overlay invites a practical first step in the discussion.'}
            for i, title in enumerate([
                'Make Room for Honest Conversations', 'Listen Before Planning Your Reply', 'Find Words for Your Feelings',
                'Ask for What You Need With Care', 'Faith and the Work of Listening',
                'Why Do You Still Feel Unheard?', 'What Happens Before the Hard Conversation?',
                'What Is Your Silence Saying?', 'When Did Listening Become an Argument?', 'How Does Prayer Shape Your Words?',
                'Clarity Starts With You', 'Honesty Can Be Gentle', 'You Cannot Control Their Response',
                'Quiet Does Not Always Mean Peace', 'Understanding Takes Practice'])])
    if 'STAGE: chapters' in prompt:
        return json.dumps([{'start_time': 0, 'title': 'Honest conversation', 'boundary_id': 'anchor', 'reason': 'Format anchor'},
                           {'start_time': 20.5, 'title': 'Listen with care', 'boundary_id': 'turn-1', 'reason': 'Discussion turns to listening'},
                           {'start_time': 45, 'title': 'Prayer and practice', 'boundary_id': 'turn-2', 'reason': 'Moves to faith and prayer'}])
    return json.dumps({'hook': 'You can speak honestly and still make room to listen.',
        'overview': 'Lish Speaks explores honest communication, listening with care, and the role of prayer in finding your words.',
        'takeaways': ['Name your feelings before the conversation.', 'Listen before preparing your reply.', 'Practice speaking with care.'],
        'question': 'Which conversation could you approach with more care this week?',
        'invitation': 'Share your thoughts in the comments, subscribe, and send this to someone you want to understand.',
        'notes': []})



def compatible_response(prompt):
    context = json.loads(prompt.split('Evidence and authoritative inputs:\n', 1)[1].split('\nRepair', 1)[0])
    data = json.loads(response_for(prompt))
    if 'STAGE: chapters' in prompt:
        turns = [t for t in context['turns'] if t['start_time'] > 0]
        return json.dumps([data[0], *[
            {**data[min(i + 1, 2)], 'start_time': t['start_time'], 'boundary_id': t['boundary_id']}
            for i, t in enumerate(turns[:2])]])
    if 'STAGE: body' in prompt:
        names = [p['name'] for p in context['episode']['participants']]
        data['overview'] = ' and '.join(names) + ' explore honest communication, listening with care, and the role of prayer in finding your words.'
    return json.dumps(data)
