"""NL→SPARQL generation, exposed as the `query_sparql` tool (Story 6.11 —
formerly a standalone router-facing dispatch() for the nl_discovery intent,
Story 6.4). `generate_and_run()` is a plain callable wrapped by
agent_tools.query_sparql(); the caller supplies the model (no more hardcoded
model choice here — see AC #3)."""
import os
import re

import structlog

import llm_client
import sparql_client

log = structlog.get_logger()

_ONTOLOGY_CACHE: str | None = None

ONTOLOGY_CONSTRUCT = """
CONSTRUCT {
  ?cls a <http://www.w3.org/2002/07/owl#Class> ;
       <http://www.w3.org/2000/01/rdf-schema#label> ?label ;
       <http://www.w3.org/2000/01/rdf-schema#comment> ?comment .
  ?prop a <http://www.w3.org/2002/07/owl#DatatypeProperty> ;
        <http://www.w3.org/2000/01/rdf-schema#label> ?plabel ;
        <http://www.w3.org/2000/01/rdf-schema#domain> ?domain ;
        <http://www.w3.org/2000/01/rdf-schema#range> ?range .
  ?cls <http://www.w3.org/2004/02/skos/core#closeMatch> ?match .
}
WHERE {
  {
    GRAPH <urn:mak:ontology/iop> {
      { ?cls a <http://www.w3.org/2002/07/owl#Class> .
        OPTIONAL { ?cls <http://www.w3.org/2000/01/rdf-schema#label> ?label }
        OPTIONAL { ?cls <http://www.w3.org/2000/01/rdf-schema#comment> ?comment }
      }
      UNION
      { ?prop a <http://www.w3.org/2002/07/owl#DatatypeProperty> ;
              <http://www.w3.org/2000/01/rdf-schema#domain> ?domain ;
              <http://www.w3.org/2000/01/rdf-schema#range> ?range .
        OPTIONAL { ?prop <http://www.w3.org/2000/01/rdf-schema#label> ?plabel }
      }
      UNION
      { ?cls <http://www.w3.org/2004/02/skos/core#closeMatch> ?match }
    }
  }
  UNION
  {
    GRAPH <urn:mak:ontology/mom> {
      { ?cls a <http://www.w3.org/2002/07/owl#Class> .
        OPTIONAL { ?cls <http://www.w3.org/2000/01/rdf-schema#label> ?label }
      }
      UNION
      { ?prop a <http://www.w3.org/2002/07/owl#DatatypeProperty> ;
              <http://www.w3.org/2000/01/rdf-schema#domain> ?domain .
        OPTIONAL { ?prop <http://www.w3.org/2000/01/rdf-schema#label> ?plabel }
      }
    }
  }
}
"""

FORBIDDEN = re.compile(
    r'\b(DROP|INSERT|DELETE|UPDATE|CLEAR|CREATE|LOAD|MOVE|COPY|ADD)\b',
    re.IGNORECASE,
)

# Sanitize user input going into LLM prompt to prevent prompt injection
_SANITIZE = re.compile(r'[{}<>"\\' + r"\n\r\x00-\x1f]", re.ASCII)

PREFIX_BLOCK = """PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
PREFIX iop: <https://nicolasdb.github.io/mapsofmaking_ontology/iop#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

# Strips any PREFIX/BASE lines the model emits on its own (unreliable — see
# _ensure_prefixes) so ours always wins, never duplicates.
_PREFIX_LINE_RE = re.compile(r'^\s*(PREFIX|BASE)\s+\S*\s*<[^>]*>\s*$', re.IGNORECASE | re.MULTILINE)


def _ensure_prefixes(sparql: str) -> str:
    """Prepend PREFIX_BLOCK to the model's SELECT body, stripping any PREFIX
    lines it emitted itself. The prompt tells the model which prefixes exist
    but LLMs unreliably repeat that boilerplate in their own output — Oxigraph
    then 400s on an undeclared prefix. Don't depend on model compliance for
    something code can just guarantee (model-agnostic by construction)."""
    body = _PREFIX_LINE_RE.sub("", sparql).strip()
    return PREFIX_BLOCK + body


NL_TO_SPARQL_SYSTEM = """You are a SPARQL generator for a makerspace directory.
Prefixes (already declared for you — do NOT repeat PREFIX lines in your output):
  PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
  PREFIX schema: <https://schema.org/>
  PREFIX iop: <https://nicolasdb.github.io/mapsofmaking_ontology/iop#>
  PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

Graph shape (this is the one thing that varies between question types — copy it
exactly): each space's data lives in its OWN named graph, urn:mak:space/<slug>.
There is no single fixed graph name to query — you must wildcard it and filter:

  GRAPH ?g {{
    ?s a mom:Space ; schema:name ?name .
    ...
    FILTER(STRSTARTS(STR(?g), "urn:mak:space/"))
  }}

A space only counts as "registered"/"confirmed" (not just a seeded directory
listing) if it has a mom:endpointUrl. Make that triple OPTIONAL and bind a
?confirmed flag with BOUND() rather than requiring it — this way a single
query surfaces BOTH confirmed spaces AND unconfirmed/seeded ones that also
match, instead of silently hiding the unconfirmed ones. The caller needs both
counts: it reports confirmed matches with confidence, but must not go quiet
about unconfirmed data that exists — that's a real nudge signal for
coordinators to register. Never drop the OPTIONAL/BOUND pattern just because
the question sounds like it wants only "real" spaces.

Boolean fields (e.g. mom:openNow) are typed literals — match them as a typed
literal in the triple, not a bare comparison:

  ?s mom:openNow "true"^^xsd:boolean .    # for "open now"
  ?s mom:openNow "false"^^xsd:boolean .   # for "closed now"

Worked example (city + open state — adapt the FILTER/city string to the question):

  SELECT ?name ?city ?website ?confirmed WHERE {{
    GRAPH ?g {{
      ?s a mom:Space ;
         schema:name ?name ;
         mom:openNow "true"^^xsd:boolean .
      OPTIONAL {{ ?s schema:addressLocality ?city }}
      OPTIONAL {{ ?s schema:url ?website }}
      OPTIONAL {{ ?s mom:endpointUrl ?e }}
      BIND(BOUND(?e) AS ?confirmed)
      FILTER(STRSTARTS(STR(?g), "urn:mak:space/"))
      FILTER(CONTAINS(LCASE(STR(?city)), LCASE("berlin")))
    }}
  }} LIMIT 15

Worked example (tag/specialty + city):

  SELECT ?name ?city ?website ?confirmed WHERE {{
    GRAPH ?g {{
      ?s a mom:Space ;
         schema:name ?name ;
         schema:knowsAbout ?specialty .
      OPTIONAL {{ ?s schema:addressLocality ?city }}
      OPTIONAL {{ ?s schema:url ?website }}
      OPTIONAL {{ ?s mom:endpointUrl ?e }}
      BIND(BOUND(?e) AS ?confirmed)
      FILTER(STRSTARTS(STR(?g), "urn:mak:space/"))
      FILTER(CONTAINS(LCASE(STR(?specialty)), LCASE("laser")))
      FILTER(CONTAINS(LCASE(STR(?city)), LCASE("ghent")))
    }}
  }} LIMIT 15

Ontology context (available classes/properties beyond the ones shown above):
{ontology_slice}

Rules:
- Return ONLY a SPARQL SELECT query, starting with SELECT (not PREFIX — the
  prefixes above are already in scope). No explanation, no markdown.
- Query only urn:mak:space/<slug> graphs (via the GRAPH ?g wildcard above) or
  urn:mak:canary/<slug>. Never use DROP/INSERT/DELETE/UPDATE.
- Limit results to 15 unless the question implies otherwise.
- Use CONTAINS(LCASE(?x), LCASE("term")) for string matching.
"""

_FENCE_RE = re.compile(r"^```[a-z]*\n?|\n?```$", re.MULTILINE)


def _strip_fence(s: str) -> str:
    return _FENCE_RE.sub("", s).strip()


async def _load_ontology_cache() -> str:
    global _ONTOLOGY_CACHE
    try:
        turtle, _ = await sparql_client.run_construct(ONTOLOGY_CONSTRUCT)
        _ONTOLOGY_CACHE = turtle
        log.info("ontology.cache_loaded", length=len(turtle))
    except Exception as exc:
        log.warning("ontology.cache_load_failed", error=str(exc))
        _ONTOLOGY_CACHE = None  # keep None so next request retries
    return _ONTOLOGY_CACHE or ""


async def generate_and_run(question: str, model: str, session_id: str = "") -> dict:
    """LLM→SPARQL→execute. Caller (agent_tools.query_sparql) supplies the
    model — this module does not choose its own (AC #3). Returns a plain
    dict (bindings + sparql text + count) rather than a pre-formatted
    Bernard string; the agent's tool-calling loop decides how to present it."""
    global _ONTOLOGY_CACHE

    if _ONTOLOGY_CACHE is None or os.environ.get("RELOAD_ONTOLOGY") == "1":
        await _load_ontology_cache()

    if not _ONTOLOGY_CACHE:
        log.warning("ontology.cache_unavailable", session_id=session_id)
        return {"error": "ontology cache unavailable"}

    safe_text = _SANITIZE.sub(" ", question)

    try:
        raw, _, _ = await llm_client.complete_with_system(
            system=NL_TO_SPARQL_SYSTEM.format(ontology_slice=_ONTOLOGY_CACHE),
            user=safe_text,
            model=model,
            temperature=0.0,
            max_tokens=512,
            session_id=session_id,
        )
        sparql = _ensure_prefixes(_strip_fence(raw))
        log.info("sparql.generated", session_id=session_id, sparql=sparql)
    except Exception as exc:
        log.warning("llm.nl_sparql_failed", error=str(exc), session_id=session_id)
        return {"error": f"LLM error: {exc}"}

    if FORBIDDEN.search(sparql):
        log.warning(
            "sparql.security_rejected",
            session_id=session_id,
            sparql_preview=sparql[:120],
        )
        return {"error": "forbidden_sparql", "sparql": sparql}

    try:
        bindings, _ = await sparql_client.run_select(sparql)
    except Exception as exc:
        log.warning("sparql.nl_select_failed", error=str(exc), session_id=session_id, sparql=sparql)
        return {"error": str(exc), "sparql": sparql}

    return {"bindings": bindings, "sparql": sparql, "count": len(bindings)}
