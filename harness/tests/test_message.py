import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from message import Message


def test_message_fields():
    fields = {f.name for f in Message.__dataclass_fields__.values()}
    assert fields == {"text", "user_id", "room_id", "platform", "raw", "power_level", "event_id", "thread_id", "via_reaction", "is_mention"}


def test_message_normalises_matrix_event():
    raw_event = object()
    message = Message(text="!mom ping", user_id="@nicolas:matrix.org", room_id="!abc:matrix.org",
                       platform="matrix", raw=raw_event)
    assert message.text == "!mom ping"
    assert message.platform == "matrix"
    assert message.raw is raw_event
