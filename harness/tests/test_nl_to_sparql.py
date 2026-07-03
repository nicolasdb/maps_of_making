"""Tests for nl_to_sparql.py (Story 6.4; refactored to generate_and_run() in
Story 6.11 — no more router-facing dispatch(), no more RDF gap-triple writer;
model is now a required param, not a hardcoded string)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "infra" / "link_handler"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "infra"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import bernard
import nl_to_sparql
import sparql_client
import llm_client

MODEL = "test-model"


@pytest.fixture(autouse=True)
def _voice():
    bernard.load_voice()


@pytest.fixture(autouse=True)
def _reset_cache():
    nl_to_sparql._ONTOLOGY_CACHE = None
    yield
    nl_to_sparql._ONTOLOGY_CACHE = None


VALID_SPARQL = """SELECT ?name ?url WHERE {
  GRAPH ?g { ?s <https://schema.org/name> ?name ; <https://schema.org/url> ?url }
} LIMIT 15"""

BINDINGS_2 = [
    {"name": {"value": "OpenFab"}, "url": {"value": "https://openfab.be"}},
    {"name": {"value": "Fablab Brussels"}, "url": {"value": "https://fablab.brussels"}},
]


@pytest.mark.asyncio
async def test_sparql_injection_rejected(monkeypatch):
    """LLM returns a mutating statement → rejected before Oxigraph call."""
    monkeypatch.setattr(
        sparql_client, "run_construct",
        AsyncMock(return_value=("# ontology", 5)),
    )
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=("DROP GRAPH <urn:mak:space/test>; SELECT * WHERE {}", "m", 100)),
    )
    run_select_mock = AsyncMock()
    monkeypatch.setattr(sparql_client, "run_select", run_select_mock)

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert result["error"] == "forbidden_sparql"
    run_select_mock.assert_not_called()


@pytest.mark.asyncio
async def test_empty_result_returns_zero_count(monkeypatch):
    """Valid SPARQL, empty result → dict with count=0, no gap side-effect
    (gap-logging is now the agent's/log_gap's job, not this module's)."""
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(return_value=("# ontology", 5)))
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=(VALID_SPARQL, "m", 100)),
    )
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=([], 10)))

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert result["count"] == 0
    assert result["bindings"] == []


@pytest.mark.asyncio
async def test_successful_result_returns_bindings_and_sparql(monkeypatch):
    """run_select returns 2 bindings → dict with bindings, sparql text, count."""
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(return_value=("# ontology", 5)))
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=(VALID_SPARQL, "m", 100)),
    )
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=(BINDINGS_2, 10)))

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert result["bindings"] == BINDINGS_2
    assert result["count"] == 2
    assert "SELECT" in result["sparql"]


@pytest.mark.asyncio
async def test_llm_failure_returns_error(monkeypatch):
    """LLM raises → dict with an error key, no exception propagates."""
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(return_value=("# ontology", 5)))
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(side_effect=RuntimeError("OpenRouter timeout")),
    )

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert "error" in result
    assert "OpenRouter timeout" in result["error"]


@pytest.mark.asyncio
async def test_model_param_is_passed_through(monkeypatch):
    """generate_and_run no longer hardcodes a model — it forwards the
    caller-supplied model to complete_with_system (Story 6.11 AC #3)."""
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(return_value=("# ontology", 5)))
    complete_mock = AsyncMock(return_value=(VALID_SPARQL, "m", 100))
    monkeypatch.setattr(llm_client, "complete_with_system", complete_mock)
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=(BINDINGS_2, 10)))

    await nl_to_sparql.generate_and_run("makerspaces in Brussels", model="anthropic/claude-sonnet-4-5")

    assert complete_mock.call_args.kwargs["model"] == "anthropic/claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_ontology_cache_hit(monkeypatch):
    """Second generate_and_run call reuses cache — run_construct called only once."""
    run_construct_mock = AsyncMock(return_value=("# ontology", 5))
    monkeypatch.setattr(sparql_client, "run_construct", run_construct_mock)
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=(VALID_SPARQL, "m", 100)),
    )
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=(BINDINGS_2, 10)))

    await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)
    await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    run_construct_mock.assert_called_once()


@pytest.mark.asyncio
async def test_reload_ontology_env_refetches(monkeypatch):
    """RELOAD_ONTOLOGY=1 forces run_construct on every generate_and_run call."""
    run_construct_mock = AsyncMock(return_value=("# ontology", 5))
    monkeypatch.setattr(sparql_client, "run_construct", run_construct_mock)
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=(VALID_SPARQL, "m", 100)),
    )
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=(BINDINGS_2, 10)))
    monkeypatch.setenv("RELOAD_ONTOLOGY", "1")

    await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)
    await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert run_construct_mock.call_count == 2


@pytest.mark.asyncio
async def test_ontology_cache_unavailable_returns_error(monkeypatch):
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(side_effect=RuntimeError("down")))

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert "error" in result


# ---------------------------------------------------------------------------
# PREFIX injection (live bug, 2026-07-02): a raw query with no PREFIX lines
# but prefixed names (mom:, schema:) is invalid SPARQL — Oxigraph 400s on an
# undeclared prefix, confirmed live via direct curl. The prompt tells the
# model the prefixes exist but does not reliably get repeated in its output
# — the fix must not depend on model compliance.
# ---------------------------------------------------------------------------

def test_ensure_prefixes_adds_block_when_missing():
    raw = "SELECT ?name WHERE { GRAPH ?g { ?s a mom:Space ; schema:name ?name } }"
    result = nl_to_sparql._ensure_prefixes(raw)
    assert result.startswith("PREFIX mom:")
    assert "PREFIX schema:" in result
    assert raw in result


def test_ensure_prefixes_strips_model_emitted_prefix_lines():
    raw = 'PREFIX mom: <http://wrong/>\nSELECT ?name WHERE { GRAPH ?g { ?s a mom:Space } }'
    result = nl_to_sparql._ensure_prefixes(raw)
    assert result.count("PREFIX mom:") == 1
    assert "http://wrong/" not in result


@pytest.mark.asyncio
async def test_generate_and_run_output_always_has_prefixes(monkeypatch):
    """Regression guard for the live 400: generate_and_run's returned sparql
    must always be parseable on its own — never rely on the model to have
    included PREFIX lines."""
    monkeypatch.setattr(sparql_client, "run_construct", AsyncMock(return_value=("# ontology", 5)))
    monkeypatch.setattr(
        llm_client, "complete_with_system",
        AsyncMock(return_value=("SELECT ?name WHERE { GRAPH ?g { ?s a mom:Space ; schema:name ?name } }", "m", 100)),
    )
    monkeypatch.setattr(sparql_client, "run_select", AsyncMock(return_value=([], 10)))

    result = await nl_to_sparql.generate_and_run("makerspaces in Brussels", model=MODEL)

    assert result["sparql"].startswith("PREFIX mom:")
