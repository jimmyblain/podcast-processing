"""Approved show defaults and explicitly confirmed episode participants (#12 I2)."""
from pathlib import Path

from .workspace import WorkspaceError
from .workspace_models import EpisodeMetadata, Participant, ShowProfile


def approved_show_profile() -> ShowProfile:
    return ShowProfile(approved=True, name="I'll Just Let Myself In", host='Lish Speaks',
        audience='People ready to take a chance on themselves—in creative work, careers, relationships, '
                 'and personal growth—who welcome honest conversation, practical encouragement, and a Christian perspective.',
        voice='Warm and familiar; candid and challenging; practical; faith-grounded; playful and human. '
              'Address listeners directly and refer to Lish in third person in the overview. Preserve Christian themes '
              'present in the episode; do not add religious claims, force slang, invent controversy or promise unsupported results.')


def confirmed_metadata(path: Path | None, solo: bool, guests: list[str] | None) -> EpisodeMetadata | None:
    if (solo and guests) or (path and (solo or guests)):
        raise WorkspaceError('Use --metadata, --solo or confirmed --guest names, not a mixture.')
    if path:
        return EpisodeMetadata.model_validate_json(path.read_bytes())
    if solo or guests:
        return EpisodeMetadata(solo=solo, participants=[Participant(name='Lish Speaks', role='host'),
            *[Participant(name=name, role='guest') for name in guests or []]])
    return None
