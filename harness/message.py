from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    text: str
    user_id: str
    room_id: str
    platform: str
    raw: Any
    power_level: int = 0
    event_id: str = ""
    thread_id: str = ""  # thread root event_id; set when message arrives inside a Matrix thread
    via_reaction: bool = False  # True when synthesized from an m.reaction confirm-emoji; event_id is then the reacted-to message's id, not the reaction's own id
    is_mention: bool = False  # True when the event's m.mentions.user_ids names the bot, or the raw body contains a literal "@bernard" — set by the adapter, not inferred from display-name text alone (Story 6.10 fix: a sentence merely starting with "bernard" is not an address)
