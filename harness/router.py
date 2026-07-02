import structlog

import agent
import agent_tools
import bernard
import intent_classifier
import nl_to_sparql
from message import Message

log = structlog.get_logger()


async def route(message: Message, session_id: str, adapter=None) -> str:
    """Classify the message and dispatch to the matching skill. `adapter` is
    optional (only the write path's CDN-propagation poll needs it) so
    existing callers/tests that don't pass one keep working."""
    # A pending write confirmation (from a prior propose_write) must be checked
    # before intent classification — a bare "yes" reply classifies as "unknown"
    # and would otherwise never reach agent.run()'s confirmation handling.
    if (message.room_id, message.user_id) in agent_tools.PENDING_ACTIONS:
        return await agent.run(message, session_id=session_id, adapter=adapter)

    intent = await intent_classifier.classify(message.text, session_id=session_id)

    if intent == "unknown":
        return await agent.run(message, session_id=session_id, adapter=adapter, fuzzy=True)

    if intent == "query":
        # query_commands.dispatch() is an unwired stub (always unknown_ack —
        # never finished post-6.3, discovered live during 6.10 verification).
        # Route through the same tool-calling agent as `unknown` until a
        # dedicated query dispatcher lands; not a "fuzzy" question so it's
        # excluded from fuzzy_questions analytics (fuzzy defaults False).
        return await agent.run(message, session_id=session_id, adapter=adapter)

    if intent == "nl_discovery":
        return await nl_to_sparql.dispatch(message, session_id=session_id)

    if intent == "write":
        return await agent.run(message, session_id=session_id, adapter=adapter)

    log.warning("router.intent_not_implemented", intent=intent, session_id=session_id)
    return bernard.unknown_ack()
