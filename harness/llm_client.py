from openai import AsyncOpenAI
import openai
import os
import time
import structlog

log = structlog.get_logger()


DEFAULT_MODEL = "google/gemma-3-12b-it"

# Set from config.yaml bot.model at startup; falls back to DEFAULT_MODEL.
MODEL = DEFAULT_MODEL

# Tier-2 escalation model (Story 6.11) — the single named reference to the
# stronger model used when agent.py's loop hits a Trigger A/B escalation.
# Previously hardcoded inside nl_to_sparql.py; now lives here since escalation
# is decided by agent.py's loop, not by nl_to_sparql itself (AC #3).
SONNET_MODEL = "anthropic/claude-sonnet-4-5"


REQUEST_TIMEOUT_SECONDS = 15.0


async def complete(
    prompt: str, model: str | None = None, max_tokens: int = 64, session_id: str = ""
) -> tuple[str, str, int]:
    """One LLM completion via OpenRouter. Returns (text, model_used, latency_ms)."""
    bound = log.bind(session_id=session_id)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env or environment")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=REQUEST_TIMEOUT_SECONDS,
        default_headers={
            "HTTP-Referer": "https://mapsofmaking.org",
            "X-Title": "maps-of-making spike",
        },
    )
    t0 = time.monotonic()
    resp = await client.chat.completions.create(
        model=model or MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    latency = int((time.monotonic() - t0) * 1000)
    if not resp.choices:
        bound.error("llm.empty_choices", model=resp.model, latency_ms=latency)
        return "", resp.model, latency
    text = resp.choices[0].message.content or ""
    bound.info("llm.completed", model=resp.model, latency_ms=latency)
    return text, resp.model, latency


class LLMRequestError(Exception):
    """Raised when the OpenRouter request itself fails (connection/status/timeout).
    Caller maps this to a graceful bedrock ack rather than letting it propagate."""


async def complete_with_system(
    system: str,
    user: str,
    model: str,
    temperature: float = 1.0,
    max_tokens: int = 512,
    session_id: str = "",
) -> tuple[str, str, int]:
    """LLM completion with separate system + user messages. Returns (text, model_used, latency_ms)."""
    bound = log.bind(session_id=session_id)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env or environment")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=REQUEST_TIMEOUT_SECONDS,
        default_headers={
            "HTTP-Referer": "https://mapsofmaking.org",
            "X-Title": "maps-of-making spike",
        },
    )
    t0 = time.monotonic()
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    latency = int((time.monotonic() - t0) * 1000)
    if not resp.choices:
        bound.error("llm.empty_choices", model=resp.model, latency_ms=latency)
        return "", resp.model, latency
    text = resp.choices[0].message.content or ""
    bound.info("llm.completed", model=resp.model, latency_ms=latency)
    return text, resp.model, latency


async def complete_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    model: str,
    tool_choice: str = "auto",
    temperature: float = 1.0,
    max_tokens: int = 512,
    session_id: str = "",
):
    """LLM completion with tool-calling. `messages` are user/assistant/tool turns
    (system prompt passed separately and prepended). Returns (text, tool_calls, model_used, latency_ms).
    tool_calls is resp.choices[0].message.tool_calls (may be None)."""
    bound = log.bind(session_id=session_id)
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env or environment")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=REQUEST_TIMEOUT_SECONDS,
        default_headers={
            "HTTP-Referer": "https://mapsofmaking.org",
            "X-Title": "maps-of-making spike",
        },
    )
    t0 = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, *messages],
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except (openai.APIConnectionError, openai.APIStatusError, openai.APITimeoutError) as exc:
        latency = int((time.monotonic() - t0) * 1000)
        bound.error("llm.request_failed", error=str(exc), latency_ms=latency)
        raise LLMRequestError(str(exc)) from exc
    latency = int((time.monotonic() - t0) * 1000)
    if not resp.choices:
        bound.error("llm.empty_choices", model=resp.model, latency_ms=latency)
        return "", None, resp.model, latency
    message = resp.choices[0].message
    text = message.content or ""
    tool_calls = message.tool_calls
    bound.info("llm.completed", model=resp.model, latency_ms=latency, tool_call_count=len(tool_calls or []))
    return text, tool_calls, resp.model, latency
