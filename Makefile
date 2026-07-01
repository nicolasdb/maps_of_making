REMOTE      := hetzner
REMOTE_APP  := /home/nicolas/maps_of_making
REMOTE_GW   := /home/nicolas/hetzner-gateway/nginx/conf.d

# Files/dirs excluded from app sync
# data/ holds runtime state (oxigraph DB, nginx logs) — never overwrite from local
RSYNC_EXCLUDE := \
	--exclude='.git/' \
	--exclude='_bmad/' \
	--exclude='_bmad-output/' \
	--exclude='archive/' \
	--exclude='*.mp4' \
	--exclude='*.zip' \
	--exclude='.claude/' \
	--exclude='gateway-nginx/' \
	--exclude='node_modules/' \
	--exclude='venv/' \
	--exclude='__pycache__/' \
	--exclude='*.pyc' \
	--exclude='.pytest_cache/' \
	--exclude='data/'

.PHONY: sync sync-app sync-gateway publish startdev rebuild seed-spaceapi seed-bundle bundle-to-csv csv-to-bundle heartbeat devdeploy reset vps-rebuild vps-seed vps-reset help endpoint deploy-genjson bernard-copy load-ontology vps-load-ontology
.PHONY: mac-up mac-down mac-init mac-reset mac-heartbeat mac-test
.PHONY: c-reset c-activate c-demo c-all
.PHONY: ca-reachable ca-timeout ca-dns-fail ca-http-error caxis-a
.PHONY: cb-seeded cb-confirmed cb-aging cb-zombie cb-dead cb-closed caxis-b c-demo-on c-demo-off
.PHONY: cc-open cc-shut caxis-c
.PHONY: check-docs vps-stage-scripts _vps-push
.PHONY: vps-c-reset vps-c-activate vps-cb-confirmed vps-cb-aging vps-cb-zombie vps-cb-dead vps-cb-closed
.PHONY: vps-cc-open vps-cc-shut vps-c-demo-on vps-c-demo-off

CANARY_SERVED := web/canary/mother-sands.json
CANARY_SCENARIO := source venv/bin/activate && python3 scripts/canary_scenarios.py

# ── Canary execution selectors ───────────────────────────────────────────────
# Every canary Oxigraph/snapshot/API mutation runs INSIDE the link-handler container
# through scripts/canary_ops.py. The ONLY thing that differs between local and VPS is
# how we invoke it. The vps-* twins override CANARY_OPS + PUSH_STEP; everything else is
# shared, so a local command and its vps- twin run the identical recipe.
LOCAL_CEXEC  := podman exec maps-link-handler
REMOTE_CEXEC := ssh $(REMOTE) docker exec maps-link-handler
CANARY_OPS   ?= $(LOCAL_CEXEC) python3 /app/scripts/canary_ops.py
VPS_OPS      := $(REMOTE_CEXEC) python3 /app/scripts/canary_ops.py
# PUSH_STEP publishes the authored web/canary/mother-sands.json to the single public
# endpoint — both local AND VPS heartbeats fetch that URL (intended: exercises the real
# fetch pipeline). vps- twins override PUSH_STEP to also stage the JSON into the VPS
# container and clear its ETag. See memory/project_canary_public_url_and_vps_parity.md.
PUSH_STEP    ?= $(MAKE) endpoint

# ── Docs staleness tripwire ──────────────────────────────────────────────────
# Greps the LIVE planning + architecture docs for known-dead architecture facts
# (Epic 3.5 supersessions, canonical-namespace migration). Pure stdlib python3,
# no venv needed. Run before committing doc changes / in CI. See scripts/check_docs.py.
check-docs:
	@python3 scripts/check_docs.py

## ── Mac / Docker local dev ───────────────────────────────────────────────────
## These targets replace the Podman-based startdev/rebuild/reset workflow on macOS.
## They use docker compose with the mac overlay (infra/docker-compose.mac.yml) and
## include OHM (Open Hardware Manager) for OKW integration testing.
##
## Quick start:
##   make mac-up    — start all services (MoM + OHM)
##   make mac-init  — load ontologies + seed test data + heartbeat
##   make mac-test  — run E2E integration test suite
##   make mac-down  — stop all services (data persists)
##   make mac-reset — DESTRUCTIVE: wipe data and re-init

MAC_COMPOSE := docker compose -f infra/docker-compose.yml -f infra/docker-compose.mac.yml
MAC_SERVICES := maps-nginx oxigraph mak-link-handler ohm
MAC_OHM_URL ?= http://localhost:8001/v1
MAC_SPARQL_URL ?= http://localhost:8080/sparql/query
MAC_SPARQL_UPDATE_URL ?= http://localhost:7878/update

## Start MoM + OHM services on Mac. Creates required data dirs if missing.
mac-up:
	@mkdir -p data/tasks data/logs/nginx data/oxigraph data/bot-keys data/ohm
	@if [ ! -f infra/nginx/.htpasswd ]; then \
		echo "→ generating .htpasswd (admin:devadmin)..."; \
		printf '%s' "$$(openssl passwd -apr1 devadmin)" | xargs -I{} sh -c 'echo "admin:{}" > infra/nginx/.htpasswd'; \
	fi
	$(MAC_COMPOSE) up -d $(MAC_SERVICES)
	@echo "→ waiting for services to be healthy..."
	@timeout 60 sh -c 'until curl -sf http://localhost:8080/health > /dev/null 2>&1; do sleep 2; done' && echo "  ✅ nginx ready" || echo "  ⚠️  nginx health check timed out"
	@timeout 60 sh -c 'until curl -sf http://localhost:7878/health > /dev/null 2>&1; do sleep 2; done' && echo "  ✅ oxigraph ready" || echo "  ⚠️  oxigraph health check timed out"
	@timeout 90 sh -c 'until curl -sf http://localhost:8001/health > /dev/null 2>&1; do sleep 3; done' && echo "  ✅ ohm ready" || echo "  ⚠️  ohm health check timed out"
	@echo "✓ stack up — map: http://localhost:8080  sparql: http://localhost:8080/sparql/query  ohm: http://localhost:8001"

## Stop all Mac services (data in data/ persists).
mac-down:
	$(MAC_COMPOSE) down
	@echo "✓ stack stopped (data persists in data/)"

## Load ontologies + crosswalk, seed test data, trigger heartbeat.
## Safe to re-run (all operations are idempotent). Run once after mac-up.
mac-init:
	@echo "→ loading ontologies and OKW crosswalk..."
	bash scripts/load_ontology.sh http://localhost:7878
	@echo "→ seeding test spaces (SpaceAPI test batch)..."
	OXIGRAPH_ENDPOINT=http://localhost:7878 PYTHONPATH=infra/link_handler:scripts \
		python3 scripts/seed_spaceapi.py --list data/seed-lists/test-batch.json --network test-batch --force
	@echo "→ seeding EU fabnet sample (bundle with activities)..."
	OXIGRAPH_ENDPOINT=http://localhost:7878 PYTHONPATH=infra/link_handler:scripts \
		python3 scripts/seed_bundle.py --bundle data/seed-lists/fabnet_eu_sample.json --network fabnet --source fabnet-world --force
	@echo "→ triggering heartbeat (materializes spaces.geojson)..."
	$(MAKE) mac-heartbeat
	@echo "✓ init complete — map has data, SPARQL endpoint live"

## Trigger an immediate heartbeat cycle (re-fetches live SpaceAPI endpoints, rematerializes GeoJSON).
mac-heartbeat:
	curl -sf -X POST http://localhost:8080/api/heartbeat/run \
		-H "X-Link-Secret: $$(grep LINK_SECRET .env | cut -d= -f2)" \
		--max-time 180 | python3 -c "import json,sys; d=json.load(sys.stdin); print('heartbeat:', d)"

## Run the OHM×MoM E2E integration test suite.
## Requires mac-up + mac-init to have been run first.
mac-test:
	@echo "→ running E2E integration tests..."
	PYTHONPATH=infra/link_handler:scripts \
	OHM_BASE_URL=$(MAC_OHM_URL) \
	MOM_SPARQL_URL=$(MAC_SPARQL_URL) \
	MOM_SPARQL_UPDATE_URL=$(MAC_SPARQL_UPDATE_URL) \
		python3 -m pytest tests/test_ohm_mom_integration.py -v --tb=short 2>&1
	@echo "✓ integration tests complete"

## DESTRUCTIVE: wipe all local data and re-initialize from scratch.
## Loses ALL seeded spaces, Oxigraph triples, and OHM facilities.
mac-reset:
	@echo "⚠  This will wipe data/oxigraph/, data/tasks/, data/ohm/ and reinitialize."
	@read -p "   Type 'reset' to confirm: " ans && [ "$$ans" = "reset" ] || (echo "aborted"; exit 1)
	$(MAC_COMPOSE) down
	rm -rf data/oxigraph/* data/tasks/snapshot_store.db data/tasks/heartbeat_log.db \
		data/tasks/gap_log.txt data/tasks/oxigraph.db data/ohm/* web/data/spaces.geojson
	$(MAKE) mac-up
	@sleep 3
	$(MAKE) mac-init
	@echo "✓ mac-reset complete"

help:
	@echo "── DOCS ─────────────────────────────────────────────────────────────"
	@echo "make check-docs    — fail if a superseded architecture fact reappears in live docs"
	@echo "── MAC / DOCKER (local dev on macOS, includes OHM) ──────────────────"
	@echo "make mac-up        — start MoM + OHM stack (Docker, no Podman needed)"
	@echo "make mac-init      — load ontologies + seed test data + heartbeat (run after mac-up)"
	@echo "make mac-heartbeat — trigger immediate heartbeat cycle"
	@echo "make mac-test      — run OHM×MoM E2E integration tests"
	@echo "make mac-down      — stop all services (data persists)"
	@echo "make mac-reset     — DESTRUCTIVE: wipe data and re-initialize"
	@echo "── LOCAL (Podman/Fedora) ────────────────────────────────────────────"
	@echo "make startdev      — start local stack without rebuilding"
	@echo "make rebuild       — full local cycle: down → build → up + health wait"
	@echo "make seed-spaceapi — import directory.spaceapi.io federation directory (~244 spaces)"
	@echo "make seed-bundle BUNDLE=… NETWORK=… [SOURCE=…] — seed local Path B bundle (grey/claimable pins, no endpoint)"
	@echo "make bundle-to-csv BUNDLE=… CSV=… — dump a messy bundle to a curation CSV"
	@echo "make csv-to-bundle CSV=… BUNDLE=… — convert a curated CSV to a seed bundle"
	@echo "make load-ontology — load mom.ttl + iop.ttl + OKW crosswalk into Oxigraph (auto-run by devdeploy)"
	@echo "make heartbeat     — trigger immediate heartbeat cycle locally"
	@echo "make devdeploy     — rebuild + seed + heartbeat (mirrors publish, locally)"
	@echo "make reset         — DESTRUCTIVE: wipe Oxigraph + heartbeat DB, then devdeploy"
	@echo "── VPS ──────────────────────────────────────────────────────────────"
	@echo "make publish       — push code: sync + down/up --build + heartbeat + gateway reload (no seed)"
	@echo "make sync          — sync everything (app + gateway confs)"
	@echo "make sync-app      — sync project root (excl. dev artifacts) to VPS"
	@echo "make sync-gateway  — sync gateway nginx confs (manual reload needed)"
	@echo "make deploy-genjson — push web/genjson/ only + nginx reload (fast wizard dev loop)"
	@echo "make vps-rebuild   — rebuild containers on VPS (no sync — code must be current)"
	@echo "make vps-seed [LIST=… NETWORK=…] — seed SpaceAPI list on VPS (default: directory.spaceapi.io, network=spaceapi)"
	@echo "make vps-seed-bundle BUNDLE=… NETWORK=… [SOURCE=…] — seed Path B bundle (grey/claimable pins, no endpoint)"
	@echo "make vps-reset     — DESTRUCTIVE: wipe VPS Oxigraph + SQLite, rebuild, reload canary only"
	@echo "── CANARY ───────────────────────────────────────────────────────────"
	@echo "make c-reset      — restore canary from baseline (seeded, no endpointUrl)"
	@echo "make c-activate   — add mom:endpointUrl to canary (simulates claiming step)"
	@echo "make c-demo-on    — turn on seconds-scale canary thresholds (live demo)"
	@echo "make c-demo-off   — restore normal day-scale thresholds"
	@echo "make c-demo       — seeded→confirmed→aging→zombie→dead→closed lifecycle chain"
	@echo "make c-all        — run all scenarios across all axes"
	@echo "make ca-{reachable,timeout,dns-fail,http-error}     — Axis A"
	@echo "make cb-{seeded,confirmed,aging,zombie,dead,closed} — Axis B"
	@echo "make cc-{open,shut}                              — Axis C"
	@echo "make caxis-{a,b,c}   — run full axis"
	@echo "make endpoint     — push canary JSON + logo to VPS"
	@echo "── CANARY ON VPS ─────────────────────────────────────────────────────"
	@echo "make vps-c-reset / vps-c-activate            — seed/claim canary ON VPS"
	@echo "make vps-cb-{aging,zombie,dead,closed}       — Axis B lifecycle ON VPS"
	@echo "make vps-cc-{open,shut}                      — Axis C ON VPS"
	@echo "make vps-c-demo-{on,off}                     — toggle demo thresholds ON VPS"
	@echo "  (twins run the same recipe; mutations go to VPS Oxigraph over ssh)"

## Start local dev stack (rootless Podman, dev port overrides, from host OS)
startdev:
	podman compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d

## Full local container cycle: down → build → up + health check wait
## Use after code changes. Persists Oxigraph data (data/ is a volume mount).
rebuild:
	podman compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml down
	podman compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d --build
	@echo "→ waiting for link-handler to be healthy..."
	@timeout 60 sh -c 'until podman exec maps-link-handler python3 -c "import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\")" 2>/dev/null; do sleep 3; done' && echo ok || echo "warning: health check timed out"

## Trigger an immediate heartbeat cycle locally — populates Zone 3, rematerializes GeoJSON
heartbeat:
	podman exec maps-link-handler python3 -c \
	  "import httpx; r = httpx.post('http://localhost:8000/api/heartbeat/run', timeout=180); print('heartbeat:', r.status_code)"

## Seed a SpaceAPI endpoint list into local Oxigraph. LIST = URL or local path
## (default: directory.spaceapi.io). NETWORK = filter-chip slug (default: spaceapi).
## Examples:
##   make seed-spaceapi
##   make seed-spaceapi LIST=data/seed-lists/test-batch.json NETWORK=test-batch
seed-spaceapi:
	source venv/bin/activate && python scripts/seed_spaceapi.py --list "$(LIST)" --network "$(NETWORK)" --force
	$(MAKE) heartbeat

## CSV pivot for batch imports (see docs/seed-import-runbook.md). Curate a clean CSV
## by hand, then convert to a canonical bundle — we don't auto-parse messy sources.
##   make bundle-to-csv BUNDLE=data/seed-lists/BE.spaces.json CSV=/tmp/be.csv  # dump to curate
##   make csv-to-bundle CSV=/tmp/be-clean.csv BUNDLE=data/seed-lists/BE.bundle.json
CSV ?= /tmp/seed.csv
bundle-to-csv:
	source venv/bin/activate && python scripts/seed_csv.py to-csv --bundle "$(BUNDLE)" --out "$(CSV)"
csv-to-bundle:
	source venv/bin/activate && python scripts/seed_csv.py to-bundle --csv "$(CSV)" --out "$(BUNDLE)"

## Seed a bundle of mom:Space records into local Oxigraph (Path B — no endpoint).
## BUNDLE = URL or local path (JSON array or {spaces:[…]} wrapper). NETWORK = filter
## slug. SOURCE = mom:source tag (default: scraped-<NETWORK>). Records become grey/
## seeded pins; coordinators claim them in place by registering a SpaceAPI URL.
## Examples:
##   make seed-bundle BUNDLE=data/seed-lists/BE.spaces.json NETWORK=be
seed-bundle:
	source venv/bin/activate && python scripts/seed_bundle.py --bundle "$(BUNDLE)" --network "$(NETWORK)" $(if $(SOURCE),--source "$(SOURCE)") --force
	@echo "→ rematerializing GeoJSON..."
	$(LOCAL_CEXEC) python3 -c "import httpx; r = httpx.post('http://localhost:8000/api/rematerialize', timeout=60); print('rematerialize:', r.status_code)"
	@echo "✓ local bundle seeded (network=$(NETWORK))"

## Load mom.ttl + iop.ttl into Oxigraph named graphs (urn:mak:ontology/{mom,iop}).
## Idempotent (PUT replaces the graph). Dormant scaffold for the Epic 6 NL→SPARQL bot —
## the live heartbeat/materialize path does NOT query these graphs yet. Folded into
## devdeploy so a fresh stack always carries the vocabulary. See
## docs/architecture/08-semantic-layer.md.
load-ontology:
	bash scripts/load_ontology.sh http://localhost:7878

## Parity twin: load ontologies into the VPS Oxigraph. Runs the same script on the
## VPS host against the published :7878 port. sync-app must have pushed scripts/ +
## ontology/ first. NOT auto-run by `publish` (idempotent, but kept opt-in).
vps-load-ontology:
	ssh $(REMOTE) 'cd $(REMOTE_APP) && bash scripts/load_ontology.sh http://localhost:7878'

## Full local pipeline: rebuild + load ontology + heartbeat (no bulk seed — Story 3.4b clean slate)
## Pre-seeded spaces load via coordinator URL onboarding or fresh canary injection.
devdeploy: rebuild load-ontology heartbeat
	@echo "✓ local dev stack live — map at http://localhost:8080"

## DESTRUCTIVE: wipe Oxigraph triplestore + heartbeat DB, then full reseed via devdeploy.
## Loses ALL coordinator-registered spaces. Use before demos / fresh-state tests.
## On VPS, the equivalent is intentionally manual — see data-lifecycle.md.
reset:
	@echo "⚠  This will wipe data/oxigraph/ and data/tasks/snapshot_store.db"
	@echo "   Coordinator-registered spaces will be lost."
	@read -p "   Type 'reset' to confirm: " ans && [ "$$ans" = "reset" ] || (echo "aborted"; exit 1)
	podman compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml down
	rm -rf data/oxigraph/* data/tasks/snapshot_store.db data/tasks/heartbeat_log.db data/tasks/gap_log.txt data/tasks/oxigraph.db web/data/spaces.geojson
	@sleep 2
	$(MAKE) devdeploy
	@echo "✓ reset complete — refresh your browser at http://localhost:8080"

## Push latest code: sync → docker down → up --build → heartbeat → gateway reload.
## Does NOT touch data/ (rsync excludes it) and does NOT seed — use `make vps-reset`
## to factory-reset, or `make vps-seed LIST=…` to add a network. Heartbeat refreshes
## already-claimed spaces so the map updates immediately instead of waiting 10min.
publish: sync-app
	@echo "→ full stack restart + rebuild on VPS..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker compose -f infra/docker-compose.yml down && docker compose -f infra/docker-compose.yml up -d --build'
	@echo "→ waiting for link-handler to be healthy..."
	ssh $(REMOTE) 'timeout 90 sh -c "until docker exec maps-link-handler python3 -c \"import urllib.request; urllib.request.urlopen('"'"'http://localhost:8000/health'"'"')\" 2>/dev/null; do sleep 3; done" && echo ok'
	@echo "→ triggering immediate heartbeat cycle (refreshes claimed spaces + rematerializes GeoJSON)..."
	ssh $(REMOTE) 'docker exec maps-link-handler python3 -c "import httpx; r = httpx.post(\"http://localhost:8000/api/heartbeat/run\", timeout=300); print(\"heartbeat:\", r.status_code)"'
	@echo "→ reloading gateway nginx (clears stale upstream cache after maps-nginx recreate)..."
	ssh $(REMOTE) 'docker exec nginx-gateway nginx -s reload'
	@echo "✓ published — map live"

## Push everything (app + gateway confs)
sync: sync-app sync-gateway

## Push project root to VPS — all files except dev-only artifacts
sync-app:
	rsync -avz --delete $(RSYNC_EXCLUDE) \
		. \
		$(REMOTE):$(REMOTE_APP)/
	@echo "✓ app synced to $(REMOTE):$(REMOTE_APP)"

## Rebuild containers on VPS without syncing — use when code is already current on VPS
## (e.g. after a server-side config edit). If local code changed, use make publish instead.
vps-rebuild:
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker compose -f infra/docker-compose.yml down && docker compose -f infra/docker-compose.yml up -d --build'

## Seed a SpaceAPI endpoint list onto the VPS. LIST = URL or local path (default:
## directory.spaceapi.io). NETWORK = filter-chip slug (default: spaceapi).
## Runs the seed script inside the link-handler container; no venv needed on VPS.
## Examples:
##   make vps-seed                                                   # full SpaceAPI directory
##   make vps-seed LIST=data/seed-lists/test-batch.json NETWORK=test-batch
##   make vps-seed LIST=https://example.org/my-list.json NETWORK=vow
LIST    ?= https://directory.spaceapi.io/
NETWORK ?= spaceapi
vps-seed:
	@echo "→ staging seed script into maps-link-handler..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker cp scripts/seed_spaceapi.py maps-link-handler:/app/scripts/seed_spaceapi.py'
	@case "$(LIST)" in \
	  http://*|https://*) \
	    echo "→ seeding from URL: $(LIST) (network=$(NETWORK))..." ; \
	    ssh $(REMOTE) 'docker exec -e OXIGRAPH_ENDPOINT=http://oxigraph:7878 -e PYTHONPATH=/app maps-link-handler python3 /app/scripts/seed_spaceapi.py --list "$(LIST)" --network "$(NETWORK)" --force' ;; \
	  *) \
	    echo "→ uploading local list $(LIST) → VPS /tmp → container..." ; \
	    scp -q "$(LIST)" $(REMOTE):/tmp/mom-seed-list.json ; \
	    ssh $(REMOTE) 'docker cp /tmp/mom-seed-list.json maps-link-handler:/tmp/seed-list.json && rm -f /tmp/mom-seed-list.json' ; \
	    echo "→ seeding from file: $(LIST) (network=$(NETWORK))..." ; \
	    ssh $(REMOTE) 'docker exec -e OXIGRAPH_ENDPOINT=http://oxigraph:7878 -e PYTHONPATH=/app maps-link-handler python3 /app/scripts/seed_spaceapi.py --list /tmp/seed-list.json --network "$(NETWORK)" --force' ;; \
	esac
	@echo "→ triggering heartbeat cycle..."
	ssh $(REMOTE) 'docker exec maps-link-handler python3 -c "import httpx; r = httpx.post(\"http://localhost:8000/api/heartbeat/run\", timeout=300); print(\"heartbeat:\", r.status_code)"'
	@echo "→ rematerializing GeoJSON..."
	ssh $(REMOTE) 'docker exec maps-link-handler python3 -c "import httpx; r = httpx.post(\"http://localhost:8000/api/rematerialize\", timeout=30); print(\"rematerialize:\", r.status_code)"'
	@echo "✓ VPS seeded (network=$(NETWORK))"

## Seed a bundle of mom:Space JSON-LD records (Path B — spaces without an endpoint).
## BUNDLE = URL or local path to a JSON array of records. NETWORK = filter-chip slug.
## SOURCE = mom:source tag (default: scraped-<NETWORK>). Records become grey/seeded
## pins that coordinators can later claim in place by registering a SpaceAPI URL.
## Examples:
##   make vps-seed-bundle BUNDLE=data/archive/moms_seed.json NETWORK=vow
BUNDLE  ?= data/archive/moms_seed.json
SOURCE  ?=
vps-seed-bundle:
	@echo "→ staging bundle seed script into maps-link-handler..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker cp scripts/seed_bundle.py maps-link-handler:/app/scripts/seed_bundle.py'
	@case "$(BUNDLE)" in \
	  http://*|https://*) \
	    echo "→ seeding bundle from URL: $(BUNDLE) (network=$(NETWORK))..." ; \
	    ssh $(REMOTE) 'docker exec -e OXIGRAPH_ENDPOINT=http://oxigraph:7878 -e PYTHONPATH=/app maps-link-handler python3 /app/scripts/seed_bundle.py --bundle "$(BUNDLE)" --network "$(NETWORK)" $(if $(SOURCE),--source "$(SOURCE)") --force' ;; \
	  *) \
	    echo "→ uploading local bundle $(BUNDLE) → VPS /tmp → container..." ; \
	    scp -q "$(BUNDLE)" $(REMOTE):/tmp/mom-seed-bundle.json ; \
	    ssh $(REMOTE) 'docker cp /tmp/mom-seed-bundle.json maps-link-handler:/tmp/seed-bundle.json && rm -f /tmp/mom-seed-bundle.json' ; \
	    echo "→ seeding from file: $(BUNDLE) (network=$(NETWORK))..." ; \
	    ssh $(REMOTE) 'docker exec -e OXIGRAPH_ENDPOINT=http://oxigraph:7878 -e PYTHONPATH=/app maps-link-handler python3 /app/scripts/seed_bundle.py --bundle /tmp/seed-bundle.json --network "$(NETWORK)" $(if $(SOURCE),--source "$(SOURCE)") --force' ;; \
	esac
	@echo "→ rematerializing GeoJSON..."
	ssh $(REMOTE) 'docker exec maps-link-handler python3 -c "import httpx; r = httpx.post(\"http://localhost:8000/api/rematerialize\", timeout=60); print(\"rematerialize:\", r.status_code)"'
	@echo "✓ VPS bundle seeded (network=$(NETWORK))"

## DESTRUCTIVE: VPS analog of `make reset`. Wipes Oxigraph store + SQLite
## (heartbeat_log, snapshot_store) and materialized GeoJSON on the VPS, then
## rebuilds containers and seeds only the Mother Sands canary. Use to factory-
## reset the deployment; claim additional URLs afterwards through the admin UI.
vps-reset:
	@echo "⚠  This will wipe data/oxigraph/ and data/tasks/*.db on $(REMOTE)."
	@echo "   All coordinator-registered spaces will be lost. Only the Mother Sands"
	@echo "   canary will be reloaded."
	@read -p "   Type 'vps-reset' to confirm: " ans && [ "$$ans" = "vps-reset" ] || (echo "aborted"; exit 1)
	@echo "→ stopping containers on VPS..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker compose -f infra/docker-compose.yml down'
	@echo "→ wiping Oxigraph + SQLite + materialized GeoJSON on VPS..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && rm -rf data/oxigraph/* data/tasks/snapshot_store.db data/tasks/heartbeat_log.db data/tasks/gap_log.txt data/tasks/oxigraph.db web/data/spaces.geojson'
	@echo "→ rebuilding containers on VPS..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker compose -f infra/docker-compose.yml up -d --build'
	@echo "→ waiting for link-handler to be healthy..."
	ssh $(REMOTE) 'timeout 90 sh -c "until docker exec maps-link-handler python3 -c \"import urllib.request; urllib.request.urlopen('"'"'http://localhost:8000/health'"'"')\" 2>/dev/null; do sleep 3; done" && echo ok'
	@echo "→ staging canary loader + ops + payload into container..."
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker cp scripts/load_canary.py maps-link-handler:/app/scripts/load_canary.py && docker cp scripts/canary_ops.py maps-link-handler:/app/scripts/canary_ops.py && docker exec maps-link-handler mkdir -p /app/web/canary && docker cp web/canary/mother-sands.json maps-link-handler:/app/web/canary/mother-sands.json'
	@echo "→ loading Mother Sands canary into Oxigraph..."
	ssh $(REMOTE) 'docker exec -e OXIGRAPH_URL=http://oxigraph:7878 -e PYTHONPATH=/app maps-link-handler python3 /app/scripts/load_canary.py'
	@echo "→ rematerializing GeoJSON..."
	ssh $(REMOTE) 'docker exec maps-link-handler python3 -c "import httpx; r = httpx.post(\"http://localhost:8000/api/rematerialize\", timeout=30); print(\"rematerialize:\", r.status_code)"'
	@echo "→ reloading gateway nginx (clears stale upstream cache after maps-nginx restart)..."
	ssh $(REMOTE) 'docker exec nginx-gateway nginx -s reload'
	@echo "✓ vps-reset complete — only Mother Sands canary in graph; claim additional URLs through the admin UI."

## ── CANARY ───────────────────────────────────────────────────────────────────
## Mother Sands diagnostic canary — three-axis fault attribution tool.
## Single source of truth: https://mapsofmaking.org/canary/mother-sands.json
## Scenario cycle: make cb-zombie → writes web/canary/mother-sands.json → push to VPS → heartbeat
## See docs/canary-setup.md and docs/canary-operator-runbook.md for full guide.

## Push canary JSON + logo to VPS static server
endpoint:
	@mkdir -p web/canary
	rsync -avz web/canary/mother-sands.json $(REMOTE):$(REMOTE_APP)/web/canary/
	rsync -avz web/mother-sands-logo.png $(REMOTE):$(REMOTE_APP)/web/
	@echo "✓ canary + logo pushed → https://mapsofmaking.org/canary/mother-sands.json"

## Restore web/canary/mother-sands.json from committed baseline (seeded state, no endpoint URL)
## Also removes mom:endpointUrl from Oxigraph so heartbeat skips it — simulates fresh seeded space.
## $(PUSH_STEP) publishes the JSON to the public endpoint; $(CANARY_OPS) runs the graph/
## snapshot mutations in-container (local: podman / vps twin: ssh docker). See top selectors.
c-reset:
	@mkdir -p web/canary
	cp data/canary/baseline.json $(CANARY_SERVED)
	@chmod 644 $(CANARY_SERVED)
	$(PUSH_STEP)
	$(CANARY_OPS) load
	$(CANARY_OPS) clear-endpoint
	$(CANARY_OPS) wipe-snapshot
	$(CANARY_OPS) heartbeat
	@echo "✓ canary reset to seeded baseline"

## Add mom:endpointUrl to canary (simulates the operator "claiming" their space).
## After c-reset the canary is seeded with no endpointUrl, so the heartbeat
## transformer skips it (no mom:updatedAt → Axis B silent). This target adds the
## endpointUrl back so the next heartbeat runs the full fetch→diff→updatedAt
## path against the canary. Lets us skip the manual claiming flow during dev.
c-activate:
	$(CANARY_OPS) set-endpoint
	$(CANARY_OPS) heartbeat
	@echo "✓ canary activated — Axis B (mom:updatedAt) will advance on content change"

## ── Axis A — Reachability ────────────────────────────────────────────────────

ca-reachable:
	$(CANARY_SCENARIO) a-reachable
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat

ca-timeout:
	$(CANARY_SCENARIO) a-timeout
	@echo "  → MODE=timeout: endpoint accepts TCP but never replies"
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat

ca-dns-fail:
	@echo "  → point the heartbeat at an unresolvable URL to test DNS failure"
	@echo "  → see docs/canary-operator-runbook.md#axis-a-dns-fail"

ca-http-error:
	$(CANARY_SCENARIO) a-http-error
	@echo "  → MODE=503: endpoint returns Service Unavailable"
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat

caxis-a: ca-reachable ca-timeout ca-dns-fail ca-http-error
	@echo "✓ Axis A complete"

## ── Axis B — Lifecycle Freshness ─────────────────────────────────────────────
## Naming:
##   cb-seeded    = no endpointUrl yet — alias of c-reset (clean slate, no claim)
##   cb-confirmed = endpointUrl registered, recent updated_at — alias of c-activate
##   cb-aging/zombie/dead = real updated_at exists but is back-dated to land in
##                          that bucket (real pipeline ran; only the timestamp
##                          is shifted)
##   cb-closed    = explicit operator-declared closure (terminal-by-declaration);
##                  distinct from cb-dead (terminal-by-inactivity)
## Back-dating ($(CANARY_OPS) backdate N) rewrites mom:updatedAt in the canary graph
## and re-emits the GeoJSON. No re-fetch — preserves the live scenario payload.

# With ext_canary.thresholdMode on the canary's thresholds_override compresses the
# bucket walk to seconds; pick a days value above the relevant compressed threshold.
cb-aging:
	$(CANARY_SCENARIO) b-aging
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	$(CANARY_OPS) backdate 45

cb-zombie:
	$(CANARY_SCENARIO) b-zombie
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	$(CANARY_OPS) backdate 120

cb-dead:
	$(CANARY_SCENARIO) b-zombie
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	$(CANARY_OPS) backdate 365

cb-closed:
	$(CANARY_SCENARIO) b-closed
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	$(CANARY_OPS) declare-closed

# cb-seeded = clean slate (no endpoint, no claim)
cb-seeded: c-reset

# cb-confirmed = fresh content + opted-out open/close (state.open="opted-out")
# Shows confirmed lifecycle without an open/closed pill — baseline Axis B state.
# cc-open / cc-shut restore state.open to a boolean if needed.
cb-confirmed:
	$(CANARY_SCENARIO) b-confirmed
	$(PUSH_STEP)
	$(CANARY_OPS) set-endpoint
	$(CANARY_OPS) heartbeat
	@echo "✓ canary confirmed (opted-out open/close — no open/closed pill)"

caxis-b: cb-seeded cb-confirmed cb-aging cb-zombie cb-dead cb-closed
	@echo "✓ Axis B complete"

## ── Axis C — Open/Close Boolean ──────────────────────────────────────────────

cc-open:
	$(CANARY_SCENARIO) c-openclose-open
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat

cc-shut:
	$(CANARY_SCENARIO) c-openclose-shut
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat

caxis-c: cc-open cc-shut
	@echo "✓ Axis C complete"

## ── Group runners ────────────────────────────────────────────────────────────

c-all: caxis-a caxis-b caxis-c
	@echo "✓ All canary scenarios complete"

## ── Demo cycle ───────────────────────────────────────────────────────────────
## c-demo-on / c-demo-off toggle seconds-scale thresholds for the canary feature only.
## With demo mode ON, after cb-confirmed the canary naturally walks aging → zombie →
## dead in ~minutes against the real (recent) mom:updatedAt. Use cb-aging/zombie/dead/
## closed to pin a specific bucket via back-dating instead of waiting.

## Demo mode lives in the canary payload itself (ext_canary.thresholdMode).
## Single source of truth — the canary endpoint tells the link-handler whether
## to emit a compressed thresholds_override. Symmetric with how simulatedAge
## injects state into the payload.
c-demo-on:
	$(CANARY_SCENARIO) threshold-mode on
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	@echo "✓ canary demo thresholds ON (aging≈30s, zombie≈60s, dead≈120s)"

c-demo-off:
	$(CANARY_SCENARIO) threshold-mode off
	$(PUSH_STEP)
	$(CANARY_OPS) heartbeat
	@echo "✓ canary demo thresholds OFF (normal day-scale)"

c-demo: c-reset c-activate cb-aging cb-zombie cb-dead cb-closed
	@echo "✓ demo cycle complete — Mother Sands walked seeded → confirmed → aging → zombie → dead → closed"

## ── VPS canary twins ─────────────────────────────────────────────────────────
## Each vps-* twin runs the IDENTICAL recipe as its local counterpart, but directs all
## Oxigraph/snapshot/API mutations at the VPS container over ssh (CANARY_OPS override)
## and publishes+stages the authored JSON + clears the VPS ETag (PUSH_STEP override).
## Authoring (canary_scenarios.py) still runs locally on the host venv — git stays the
## single source of truth; the result is pushed to the public endpoint as usual.

## Copy the in-container canary scripts onto the VPS container (no dev bind-mounts there).
vps-stage-scripts:
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker cp scripts/canary_ops.py maps-link-handler:/app/scripts/canary_ops.py && docker cp scripts/load_canary.py maps-link-handler:/app/scripts/load_canary.py'

## VPS publish: push JSON to public endpoint, stage it into the VPS container, clear ETag.
_vps-push:
	$(MAKE) endpoint
	ssh $(REMOTE) 'cd $(REMOTE_APP) && docker exec maps-link-handler mkdir -p /app/web/canary && docker cp web/canary/mother-sands.json maps-link-handler:/app/web/canary/mother-sands.json'
	$(VPS_OPS) clear-etag

vps-c-reset: vps-stage-scripts
	$(MAKE) c-reset CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-c-activate: vps-stage-scripts
	$(MAKE) c-activate CANARY_OPS='$(VPS_OPS)'

vps-cb-confirmed: vps-stage-scripts
	$(MAKE) cb-confirmed CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cb-aging: vps-stage-scripts
	$(MAKE) cb-aging CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cb-zombie: vps-stage-scripts
	$(MAKE) cb-zombie CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cb-dead: vps-stage-scripts
	$(MAKE) cb-dead CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cb-closed: vps-stage-scripts
	$(MAKE) cb-closed CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cc-open: vps-stage-scripts
	$(MAKE) cc-open CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-cc-shut: vps-stage-scripts
	$(MAKE) cc-shut CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-c-demo-on: vps-stage-scripts
	$(MAKE) c-demo-on CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

vps-c-demo-off: vps-stage-scripts
	$(MAKE) c-demo-off CANARY_OPS='$(VPS_OPS)' PUSH_STEP='$(MAKE) _vps-push'

## Push gateway nginx confs only (triggers manual nginx reload on VPS)
sync-gateway:
	rsync -avz \
		infra/gateway-nginx/ \
		$(REMOTE):$(REMOTE_GW)/
	@echo "✓ gateway confs synced to $(REMOTE):$(REMOTE_GW)"
	@echo "  → reload nginx manually if conf changed: ssh $(REMOTE) 'docker exec nginx-gateway nginx -s reload'"

## Push only web/genjson/ static files to VPS + reload nginx — fast wizard dev loop
## Does NOT rebuild containers; use make publish when backend (link_handler) changes.
bernard-copy:
	python3 -c "import yaml, json, sys; json.dump(yaml.safe_load(open('web/genjson/bernard_copy.yaml')), open('web/genjson/bernard_copy.json','w'), ensure_ascii=False, indent=2)"
	@echo "✓ bernard_copy.json regenerated"

deploy-genjson: bernard-copy
	rsync -avz web/genjson/ $(REMOTE):$(REMOTE_APP)/web/genjson/
	ssh $(REMOTE) 'docker exec nginx-gateway nginx -s reload'
	@echo "✓ genjson deployed → https://genjson.mapsofmaking.org"
