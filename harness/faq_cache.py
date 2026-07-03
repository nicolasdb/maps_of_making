"""Tier-0 FAQ cache stub (Story 6.11). Dumb by design: one hand-seeded entry,
substring match, no embeddings. A hit does not bypass the model call — it
injects the entry's description+template as a hint into agent.run()'s system
prompt (see bernard_agent_prompt.FAQ_HINT_TEMPLATE); Gemma still decides how
to use it. Expanding coverage is deferred to a follow-up once Story 6.10's
fuzzy_questions table shows which questions are worth pre-validating."""

FAQ_ENTRIES = [
    {
        "trigger": "open now in berlin",
        "description": "Spaces open now in Berlin — matched via schema:addressLocality (city) and mom:openNow (liveness state), the pattern the map's own materializer already uses correctly.",
        "sparql_template": """PREFIX mom: <https://nicolasdb.github.io/mapsofmaking_ontology/ns#>
PREFIX schema: <https://schema.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?name ?city ?url WHERE {
  GRAPH ?g {
    ?s a mom:Space ;
       schema:name ?name ;
       mom:openNow "true"^^xsd:boolean ;
       mom:endpointUrl ?e .
    OPTIONAL { ?s schema:addressLocality ?city }
    OPTIONAL { ?s schema:url ?url }
    FILTER(STRSTARTS(STR(?g), "urn:mak:space/"))
    FILTER(CONTAINS(LCASE(STR(?city)), LCASE("berlin")))
  }
}
LIMIT 15""",
    },
]


def match(text: str) -> dict | None:
    """Simple substring match against each entry's trigger. First hit wins."""
    lower = text.lower()
    for entry in FAQ_ENTRIES:
        if entry["trigger"] in lower:
            return entry
    return None
