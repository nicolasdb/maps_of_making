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
