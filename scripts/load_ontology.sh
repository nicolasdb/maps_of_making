#!/bin/bash

# Load ontology files (mom.ttl, iop.ttl) into Oxigraph named graphs.
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
if $CURL_PREFIX curl -X PUT \
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
if $CURL_PREFIX curl -X PUT \
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
if $CURL_PREFIX curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology/crosswalks/mom-to-okw.ttl \
  "$OXIGRAPH_URL/store?graph=urn:mak:crosswalk/mom-to-okw" 2>&1; then
  echo "    ✅ OKW crosswalk loaded"
else
  echo "    ❌ Failed to load OKW crosswalk"
  exit 1
fi

echo "✅ All ontologies and crosswalks loaded successfully"
