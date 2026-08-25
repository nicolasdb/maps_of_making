#!/bin/bash

# Load ontology files (mom.ttl, iop.ttl, sup.ttl) + crosswalks + supplier lists
# into Oxigraph named graphs.
#
# All curl calls use -f: without it curl exits 0 on an HTTP 4xx/5xx, so a failed
# load printed a green checkmark. That masking hid a deploy that had been writing
# to the wrong triplestore entirely (2026-08-25).
# Usage: bash scripts/load_ontology.sh [OXIGRAPH_URL]
# Default: OXIGRAPH_URL=http://localhost:7878
#
# In distrobox environments, automatically uses container IP or distrobox-host-exec.

set -e

cd "$(dirname "$0")/.."

OXIGRAPH_URL="${1:-http://localhost:7878}"
CURL_PREFIX=""

# Check if we need distrobox-host-exec (running in distrobox, trying to access host container)
if ! curl -s -m 1 "$OXIGRAPH_URL/health" > /dev/null 2>&1; then
  if command -v distrobox-host-exec > /dev/null 2>&1; then
    # Try to get container IP from host
    CONTAINER_IP=$(distrobox-host-exec podman inspect maps-oxigraph 2>/dev/null | grep -A 5 "maps_of_making_internal" | grep '"IPAddress":' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if [ ! -z "$CONTAINER_IP" ]; then
      echo "Note: Using container IP ($CONTAINER_IP) to access Oxigraph"
      OXIGRAPH_URL="http://$CONTAINER_IP:7878"
      CURL_PREFIX="distrobox-host-exec"
    fi
  fi
fi

echo "Loading ontologies into Oxigraph at $OXIGRAPH_URL..."

# Load MOM ontology
echo "  Loading mom.ttl → <urn:mak:ontology/mom>..."
if $CURL_PREFIX curl -fsS -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology/mom.ttl \
  "$OXIGRAPH_URL/store?graph=urn:mak:ontology/mom" 2>&1; then
  echo "    ✅ MOM ontology loaded"
else
  echo "    ❌ Failed to load MOM ontology"
  exit 1
fi

# Load IoP ontology
echo "  Loading iop.ttl → <urn:mak:ontology/iop>..."
if $CURL_PREFIX curl -fsS -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology/iop/iop.ttl \
  "$OXIGRAPH_URL/store?graph=urn:mak:ontology/iop" 2>&1; then
  echo "    ✅ IoP ontology loaded"
else
  echo "    ❌ Failed to load IoP ontology"
  exit 1
fi

# Load OKW crosswalk
echo "  Loading mom-to-okw.ttl → <urn:mak:crosswalk/mom-to-okw>..."
if $CURL_PREFIX curl -fsS -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology/crosswalks/mom-to-okw.ttl \
  "$OXIGRAPH_URL/store?graph=urn:mak:crosswalk/mom-to-okw" 2>&1; then
  echo "    ✅ OKW crosswalk loaded"
else
  echo "    ❌ Failed to load OKW crosswalk"
  exit 1
fi

# Load supplier vocabulary (Story 10.1 — shared mom: terms, horizontal)
echo "  Loading sup.ttl → <urn:mak:ontology/sup>..."
if $CURL_PREFIX curl -fsS -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology/sup.ttl \
  "$OXIGRAPH_URL/store?graph=urn:mak:ontology/sup" 2>&1; then
  echo "    ✅ Supplier vocabulary loaded"
else
  echo "    ❌ Failed to load supplier vocabulary"
  exit 1
fi

# Load per-space supplier lists (Story 10.1 — content, vertical).
#
# Plain Turtle, with the named graph coming from the load URL — same as mom.ttl above.
# Verified against Oxigraph 0.5.7 rather than assumed:
#   PUT  ?graph=… + TriG   → 400 "Named graphs are not allowed"
#   POST /store   + TriG   → 204 but MERGES (a deleted supplier would never go away)
#   PUT  ?graph=… + Turtle → replaces that one graph  ← idempotent, what we want
#
# NOTE: this reaches Oxigraph on its INTERNAL address. The public /sparql/update
# endpoint stays nginx-403 (NFR-S7: link_handler is the sole writer through the
# public surface). Loading here opens no new write surface.
shopt -s nullglob
SUPPLIER_LISTS=(data/supplier-lists/*.ttl)
if [ ${#SUPPLIER_LISTS[@]} -eq 0 ]; then
  echo "  No supplier lists in data/supplier-lists/ — skipping"
else
  for LIST in "${SUPPLIER_LISTS[@]}"; do
    SPACE=$(basename "$LIST" .ttl)
    echo "  Loading $LIST → <urn:mak:suppliers/$SPACE>..."
    if $CURL_PREFIX curl -fsS -X PUT \
      -H "Content-Type: text/turtle" \
      --data-binary @"$LIST" \
      "$OXIGRAPH_URL/store?graph=urn:mak:suppliers/$SPACE" 2>&1; then
      echo "    ✅ $SPACE supplier list loaded"
    else
      echo "    ❌ Failed to load $SPACE supplier list"
      exit 1
    fi
  done
fi

echo "✅ All ontologies, crosswalks and supplier lists loaded successfully"
