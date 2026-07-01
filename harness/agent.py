"""Bernard tool-calling agent entry point (Story 6.9 spike).

Wires harness/llm_client.complete_with_tools over the harness/agent_tools.py
registry. This is the write intent's real path (router.py's write stub used
to just return unknown_ack()) and, optionally, a unified path for free-text
read questions too.
"""
import asyncio
import json
import time

import structlog
from pydantic import ValidationError

import agent_tools
import bernard
import bernard_agent_prompt
import commands
import llm_client
from bot import git_ops
from bot.git_ops import NoChangeError, NoDeployKeyError, NoEndpointError, UnsupportedHostError
from message import Message

log = structlog.get_logger()

MAX_TOOL_ITERATIONS = 4


async def run(message: Message, session_id: str = "", adapter=None) -> str:
    bound = log.bind(session_id=session_id, room_id=message.room_id, user_id=message.user_id)

    # Confirmation is reaction-only (Story 6.9 follow-up) — a single ✅ is the
    # one signal, not typed "yes" plus reaction as equivalent options. See
    # MatrixAdapter._on_reaction for how via_reaction messages are synthesized.
    pending_key = (message.room_id, message.user_id)
    if pending_key in agent_tools.PENDING_ACTIONS and message.via_reaction:
        return await _confirm_pending(pending_key, message, bound, adapter)

    tools = agent_tools.build_tools(message.power_level)
    messages = [{"role": "user", "content": message.text}]

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            text, tool_calls, _model, _latency = await llm_client.complete_with_tools(
                system=bernard_agent_prompt.SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
                model=llm_client.MODEL,
                session_id=session_id,
            )
        except (llm_client.LLMRequestError, ValueError) as exc:
            bound.warning("agent.llm_failed", error=str(exc))
            return bernard.unknown_ack()

        if not tool_calls:
            return text or bernard.unknown_ack()

        messages.append({
            "role": "assistant",
            "content": text or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            result = await _dispatch_tool(tc, message, bound)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, default=str),
            })

    bound.warning("agent.max_tool_iterations_exceeded")
    return bernard.unknown_ack()


async def _dispatch_tool(tc, message: Message, bound) -> dict:
    name = tc.function.name
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        return {"error": "invalid_arguments"}

    try:
        if name == "read_space":
            return await agent_tools.read_space(args.get("slug_or_room", ""), message.room_id)
        if name == "query_map":
            kind = args.pop("kind", "")
            return {"result": await agent_tools.query_map(kind, **{k: v for k, v in args.items() if v is not None})}
        if name == "log_gap":
            await agent_tools.log_gap(
                args.get("raw_request", message.text),
                args.get("note", ""),
                args.get("gap_kind", "capability"),
                room_id=message.room_id,
            )
            return {"logged": True}
        if name == "propose_write":
            return await agent_tools.propose_write(
                args["field_path"], args["new_value"],
                room_id=message.room_id, user_id=message.user_id, power_level=message.power_level,
                thread_root=message.thread_id or message.event_id,
            )
        return {"error": f"unknown_tool:{name}"}
    except Exception as exc:
        bound.warning("agent.tool_failed", tool=name, error=str(exc))
        return {"error": str(exc)}


def _stringify_for_poll(value) -> str:
    """commands._poll_and_refresh / _values_match compare against a string
    value (as literal-command callers always pass one) — mirror that shape
    for the agent path's already-coerced Python values."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


async def _confirm_pending(pending_key: tuple[str, str], message: Message, bound, adapter=None) -> str:
    authorized_by = message.user_id
    pending = agent_tools.PENDING_ACTIONS[pending_key]

    # The reaction must land on the actual confirm-ask message, not just any
    # prior message from this user — event_id is the reacted-to message id
    # (see MatrixAdapter._on_reaction).
    if pending.get("prompt_event_id") and message.event_id != pending["prompt_event_id"]:
        bound.info("agent.confirm_reaction_wrong_message")
        return ""  # silently ignore — this reaction was on an unrelated message

    if time.monotonic() - pending["created_at"] > agent_tools.PENDING_ACTION_TTL_SECONDS:
        agent_tools.PENDING_ACTIONS.pop(pending_key, None)
        bound.info("agent.confirm_expired")
        return bernard.write_confirmation_expired_ack()

    agent_tools.PENDING_ACTIONS.pop(pending_key, None)
    space_id = pending["space_id"]
    field_path = pending["field_path"]
    value = pending["proposed_value"]

    try:
        sha = await git_ops.commit_json(space_id, field_path, value, authorized_by)
    except NoChangeError:
        return bernard.already_set_ack(state=str(value))
    except NoDeployKeyError:
        bound.warning("agent.confirm_no_key")
        return bernard.no_deploy_key_ack()
    except (NoEndpointError, UnsupportedHostError) as exc:
        bound.warning("agent.confirm_failed", error=str(exc))
        return bernard.update_failed_ack()
    except ValidationError as exc:
        bound.warning("agent.confirm_invalid_shape", error=str(exc))
        return bernard.update_failed_ack()
    except Exception as exc:
        bound.warning("agent.confirm_failed", error=str(exc))
        return bernard.update_failed_ack()

    bound.info("agent.confirm_succeeded", sha=sha, field_path=field_path)
    if adapter is not None:
        # Reuse commands._poll_and_refresh as-is — same CDN-propagation
        # follow-up the literal !mom update/open/close path already gets.
        # `message` carries the confirm-ask's thread_id, so this follow-up
        # lands in the same thread too.
        asyncio.create_task(
            commands._poll_and_refresh(space_id, field_path, _stringify_for_poll(value), sha, adapter, message)
        )
    return bernard.update_committed_ack(sha, field_path, str(value))
