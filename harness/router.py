import structlog

import agent
import agent_tools
import bernard
import faq_cache
import intent_classifier
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

    # Tier 0 (Story 6.11): a FAQ-cache hit skips intent classification but
    # NOT the model call — it injects a validated-pattern hint into
    # agent.run()'s system prompt. A miss falls through to classify() below,
    # unchanged.
    faq_entry = faq_cache.match(message.text)
    if faq_entry is not None:
        hint = f"{faq_entry['description']}\n{faq_entry['sparql_template']}"
        return await agent.run(message, session_id=session_id, adapter=adapter, faq_hint=hint)

    intent = await intent_classifier.classify(message.text, session_id=session_id)

    if intent == "unknown":
        return await agent.run(message, session_id=session_id, adapter=adapter, fuzzy=True)

    if intent in ("query", "nl_discovery"):
        # query_commands.dispatch() is an unwired stub (always unknown_ack —
        # never finished post-6.3, discovered live during 6.10 verification).
        # nl_discovery used to dispatch directly to nl_to_sparql.dispatch();
        # that path is collapsed into agent.run() too (Story 6.11) — SPARQL
        # generation is now a tool (query_sparql) the loop can call. Neither
        # is a "fuzzy" question so both are excluded from fuzzy_questions
        # analytics (fuzzy defaults False).
        return await agent.run(message, session_id=session_id, adapter=adapter)

    if intent == "write":
        return await agent.run(message, session_id=session_id, adapter=adapter)

    log.warning("router.intent_not_implemented", intent=intent, session_id=session_id)
    return bernard.unknown_ack()
