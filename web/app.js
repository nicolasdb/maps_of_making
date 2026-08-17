// Maps of Making — hi-fi prototype
// Fullscreen MapLibre + slide-in drawers. Minimal cognitive load.
// Data: /data/spaces.geojson (GeoJSON FeatureCollection materialized from Oxigraph).

(function () {
  'use strict';

  // ───────────────────────────── thresholds (Story 3.10)
  // Single named fallback for the missing-thresholds error path (AC 6).
  // Numbers mirror infra/link_handler/config.yaml so a missing header degrades visibly
  // but does not silently render everything `confirmed`. Real values come from the
  // file-level `thresholds` block in spaces.geojson.
  const FALLBACK_THRESHOLDS = {
    endpoint_health: {
      unresponsive_minutes_threshold: 10,
      warning_minutes_threshold: 30,
      broken_minutes_threshold: 60,
    },
    operational_state: {
      aging_days_threshold: 30,
      zombie_days_threshold: 90,
      dead_days_threshold: 180,
    },
  };

  // ───────────────────────────── state
  const state = {
    spaces: [],
    thresholds: FALLBACK_THRESHOLDS,
    filters: {
      networks: new Set(),     // empty = all
      countries: new Set(),
      statuses: new Set(),
      specialties: new Set(),
    },
    search: '',
    selectedId: null,
    openDrawer: null,          // 'find' | 'preset' | 'addurl' | 'detail' | 'bot' | null
    embed: { centerId: null },
    _lastMapStyle: 'dim',      // track last applied style to avoid redundant setStyle() calls
    _fsSelected: null,         // id currently flagged selected via GL feature-state
    _initialViewport: false,   // true when initMap centered on ?lat/?lon (viewport-first)
  };

  // ───────────────────────────── embed mode
  // Cross-origin-safe: window.frameElement throws SecurityError across origins (the real
  // embed case), so detect via window.self !== window.top. `?embed=1` forces it for previews.
  const IS_EMBED = (() => {
    try {
      const forced = new URLSearchParams(window.location.search).get('embed');
      if (forced === '1' || forced === 'true') return true;
    } catch {}
    try { return window.self !== window.top; } catch { return true; }
  })();

  // ───────────────────────────── dom helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const escHtml = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  function el(tag, attrs = {}, children = []) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') n.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(n.style, v);
      else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, '');
      else if (v === false || v == null) {}
      else n.setAttribute(k, v);
    }
    for (const c of [].concat(children)) {
      if (c == null) continue;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return n;
  }

  // ───────────────────────────── data
  async function loadData() {
    const res = await fetch('/data/spaces.geojson?t=' + Date.now());
    if (!res.ok) {
      console.error(`[loadData] Network error: HTTP ${res.status} ${res.statusText}`);
      document.body.classList.add('data-load-error');
      const loader = document.getElementById('loader');
      if (loader) {
        loader.innerHTML = '';
        loader.appendChild(el('div', { class: 'hand', style: { color: 'var(--accent)' } }, ['Map data temporarily unavailable']));
        loader.appendChild(el('div', { class: 'mono' }, ['Try refreshing the page']));
      }
      state.spaces = [];
      return;
    }
    let json;
    try {
      json = await res.json();
    } catch (e) {
      console.error('[loadData] JSON parse error:', e.message);
      document.body.classList.add('data-load-error');
      state.spaces = [];
      return;
    }
    ingestGeoJSON(json);
  }

  // Centralized GeoJSON → state ingestion. Sets state.spaces AND state.thresholds.
  // Story 3.10: thresholds are required for live axis computation; missing block is
  // logged loud and falls back to FALLBACK_THRESHOLDS so we never silently render
  // everything as `confirmed`.
  function ingestGeoJSON(json) {
    const features = json.features || [];
    // Materialization stamp — lets the post-register refetch tell a rebuilt corpus
    // from the cached one. Presence of a slug cannot: a re-registration claims a
    // space that is already in the file, so "is it there?" is true before the
    // background rematerialize has run at all.
    state.geojsonGeneratedAt = json.generated_at || null;
    state.spaces = features.map((f) => ({
      ...f.properties,
      coordinates: {
        lat: f.geometry.coordinates[1],
        lon: f.geometry.coordinates[0],
      },
    }));
    const th = json.thresholds;
    if (!th || !th.endpoint_health || !th.operational_state
        || Object.keys(th.endpoint_health).length === 0
        || Object.keys(th.operational_state).length === 0) {
      console.error('[ingestGeoJSON] thresholds block missing/empty — using FALLBACK_THRESHOLDS. Pipeline contract violated.');
      state.thresholds = FALLBACK_THRESHOLDS;
    } else {
      state.thresholds = th;
    }
  }

  // ───────────────────────────── map
  // Dev: OpenFreeMap (CORS-enabled, no key). Production: swap TILES_URL to self-hosted PMTiles on VPS.
  const TILES_URL = 'https://tiles.openfreemap.org/planet';

  // Basemap transitions dark→light between z6 (space/organism view) and z9 (street/find view).
  // No manual theme toggle — the zoom level IS the theme.
  function buildStyle() {
    const z0 = 6, z1 = 9; // transition zone
    const lerp = (dark, light) => ['interpolate', ['linear'], ['zoom'], z0, dark, z1, light];
    const bg    = lerp('#1a1a2e', '#e8e8e8');
    const water = lerp('#16213e', '#c0d0d8');
    const road  = lerp('#333355', '#bbbbbb');
    const bldg  = lerp('#0f3460', '#d0d0d0');
    const label = lerp('#cccccc', '#555555');
    return {
      version: 8,
      glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
      sources: {
        ofm: {
          type: 'vector',
          url: TILES_URL,
          attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> © <a href="https://openfreemap.org">OpenFreeMap</a>',
        },
        terrain: {
          type: 'raster-dem',
          tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
          encoding: 'terrarium',
          tileSize: 256,
          maxzoom: 15,
          attribution: 'Terrain: <a href="https://aws.amazon.com/public-datasets/terrain/">AWS Open Data</a>',
        },
      },
      layers: [
        { id: 'background',  type: 'background', paint: { 'background-color': bg } },
        { id: 'hillshade', type: 'hillshade', source: 'terrain',
          paint: {
            'hillshade-shadow-color': '#0d1020',
            'hillshade-highlight-color': '#2a2a4a',
            'hillshade-accent-color': '#1a1a2e',
            'hillshade-exaggeration': ['interpolate', ['linear'], ['zoom'], 2, 0.4, 6, 0.3, 9, 0.15],
            'hillshade-illumination-direction': 315,
          } },
        { id: 'landcover',   type: 'fill', source: 'ofm', 'source-layer': 'landcover',   paint: { 'fill-color': bg, 'fill-opacity': 0.6 } },
        { id: 'water',       type: 'fill', source: 'ofm', 'source-layer': 'water',       paint: { 'fill-color': water } },
        { id: 'waterways',   type: 'line', source: 'ofm', 'source-layer': 'waterway',
          filter: ['in', ['get', 'class'], ['literal', ['river', 'canal']]],
          minzoom: 9,
          paint: { 'line-color': water,
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.5, 14, 2],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0, 11, 1] } },
        { id: 'landuse',     type: 'fill', source: 'ofm', 'source-layer': 'landuse',     paint: { 'fill-color': bg, 'fill-opacity': 0.4 } },
        { id: 'roads-minor', type: 'line', source: 'ofm', 'source-layer': 'transportation',
          filter: ['in', ['get', 'class'], ['literal', ['minor', 'service', 'track', 'path']]],
          paint: { 'line-color': road, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.3, 14, 1.5] } },
        { id: 'roads-major', type: 'line', source: 'ofm', 'source-layer': 'transportation',
          filter: ['in', ['get', 'class'], ['literal', ['primary', 'secondary', 'tertiary', 'trunk', 'motorway']]],
          paint: { 'line-color': road, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 12, 3],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0, 8, 1] } },
        { id: 'buildings',   type: 'fill', source: 'ofm', 'source-layer': 'building',   paint: { 'fill-color': bldg, 'fill-opacity': 0.8 } },
        { id: 'labels-cities', type: 'symbol', source: 'ofm', 'source-layer': 'place',
          filter: ['in', ['get', 'class'], ['literal', ['city']]],
          layout: { 'text-field': ['coalesce', ['get', 'name:en'], ['get', 'name']],
            'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 5, 11, 10, 14], 'text-max-width': 8 },
          paint: { 'text-color': label, 'text-halo-color': bg, 'text-halo-width': 1.5,
            'text-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0, 7, 1] } },
        { id: 'labels-towns', type: 'symbol', source: 'ofm', 'source-layer': 'place',
          filter: ['in', ['get', 'class'], ['literal', ['town']]],
          layout: { 'text-field': ['coalesce', ['get', 'name:en'], ['get', 'name']],
            'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 11, 14, 13], 'text-max-width': 8 },
          paint: { 'text-color': label, 'text-halo-color': bg, 'text-halo-width': 1.5,
            'text-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0, 12, 1] } },
      ],
    };
  }

  let map;
  function initMap() {
    // Story 5.0 AC5 — viewport-first: read ?lat/?lon BEFORE constructing the map so the
    // first tile fetch is the local area (no flyTo on cold load). Absent → world overview.
    const p = new URLSearchParams(window.location.search);
    const qlat = parseFloat(p.get('lat'));
    const qlon = parseFloat(p.get('lon'));
    const hasViewport = !isNaN(qlat) && !isNaN(qlon) && qlat >= -90 && qlat <= 90 && qlon >= -180 && qlon <= 180;
    state._initialViewport = hasViewport;
    // Compute initial camera before constructing the map — one position, no correction later.
    let initCamera;
    if (hasViewport) {
      initCamera = { center: [qlon, qlat], zoom: 13 };
    } else if (state.spaces.length > 1) {
      const pct = (arr, p) => { const s = [...arr].sort((a, b) => a - b); return s[Math.floor((s.length - 1) * p)]; };
      const lons = state.spaces.map(s => s.coordinates?.lon).filter(v => typeof v === 'number' && v >= -180 && v <= 180);
      const lats = state.spaces.map(s => s.coordinates?.lat).filter(v => typeof v === 'number' && v >= -90 && v <= 90);
      initCamera = { bounds: [[pct(lons, 0.05), pct(lats, 0.05)], [pct(lons, 0.95), pct(lats, 0.95)]], fitBoundsOptions: { padding: 80, maxZoom: 7 } };
    } else {
      initCamera = { center: [10, 48], zoom: 4 };
    }
    map = new maplibregl.Map({
      container: 'map',
      style: buildStyle(),
      hash: false,
      minZoom: 1.5,
      attributionControl: { compact: true },
      ...initCamera,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    const _zoomEl = document.getElementById('legend-zoom');
    const _updateZoom = () => { if (_zoomEl) _zoomEl.textContent = 'z' + map.getZoom().toFixed(1); };
    map.on('zoom', _updateZoom);
    map.on('load', _updateZoom);
    map.once('idle', () => {
      document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
    });

    const dismissLoader = () => {
      const ld = $('#loader');
      if (!ld) return;
      ld.style.transition = 'opacity 300ms';
      ld.style.opacity = '0';
      setTimeout(() => ld.remove(), 320);
    };
    // Idempotent ready(): safe to call from styledata, load, or the fallback timeout.
    // styledata fires when the style is parsed (before tiles), so the loader dismisses early
    // and markers render; load fires again once tiles are painted for a clean re-render.
    let readyFired = false;
    const ready = () => {
      if (!readyFired) { readyFired = true; map.resize(); dismissLoader(); }
      try { refreshSpacesLayer(); } catch {}
    };
    map.on('styledata', ready);
    map.on('load', ready);
    // Fallback: tiles blocked or very slow.
    setTimeout(ready, 1500);

    // Close drawers + deselect when clicking the map background (not on a GL point).
    map.on('click', (e) => {
      const hits = map.queryRenderedFeatures(e.point, { layers: ['spaces-point'] });
      if (hits && hits.length) return;
      if (state.selectedId) {
        state.selectedId = null;
        highlightSelected();
      }
      if (state.openDrawer === 'detail') setDrawer(null);
    });
  }

  // ───────────────────────────── GL point-field substrate (Story 5.0)
  // One GeoJSON source + circle/glyph layers replace the per-space DOM markers.
  // Colours are authored in state-colour-ladder.html (two surfaces: Daylight = parchment,
  // Depth = dark) and auto-selected by zoom. `shut` is a
  // dimmed green, never black (retires the old .map-marker.shut black-dot bug).
  const LADDER = {
    daylight: { seeded: '#A89F94', confirmed: '#378ADD', open: '#5DCAA5', shut: '#1D9E75', aging: '#C9963F', zombie: '#6A6A72', dead: '#5A5A60', broken: '#E24B4A' },
    depth:    { seeded: '#555560', confirmed: '#378ADD', open: '#5DCAA5', shut: '#1D9E75', aging: '#C9963F', zombie: '#6A6A72', dead: '#5A5A60', broken: '#E24B4A' },
  };
  // Continental read: identity axis only. Staleness (axis B) is not decision-relevant
  // at 2000km and renders as noise — it returns at z9 with the glyphs.
  // Derived from LADDER so a palette edit cannot desync the two tables: only the
  // states that collapse are named here. `aging` folds into claimed-blue (a stale
  // listing is still a claimed space); `broken`, `zombie` and `dead` keep their
  // greys — a space we cannot reach is not a working claimed space, and painting
  // it blue at 2000km is an honesty cost the map does not need to pay.
  function ladderFar(surface) {
    return { ...LADDER[surface], aging: LADDER[surface].confirmed, broken: LADDER[surface].zombie };
  }
  // Dedicated neon for the open-pulse halo — must pop on both surfaces.
  // Stroke gives non-colour separation; seeded/dead/zombie read as hollow/faint rings.
  const LADDER_STROKE = {
    daylight: { seeded: '#A09C90', dead: '#7A786E', zombie: '#8A8C80', default: '#1E1D1A' },
    depth:    { seeded: '#3A3A42', dead: '#3A3A42', zombie: '#3A3A42', default: '#0D0D0F' },
  };
  const KINDS = ['seeded', 'confirmed', 'open', 'shut', 'aging', 'zombie', 'dead', 'broken'];
  // NFR-A4: colour must not be the sole differentiator. Short glyphs render in Noto Sans.
  const KIND_GLYPH = { broken: '×', aging: '!', zombie: '…', dead: '+' };

  function currentSurface() {
    return 'depth'; // basemap transitions by zoom; dots use the depth palette on both surfaces
  }

  // Build a FeatureCollection from spaces, skipping invalid coords (guard preserved
  // from the retired renderMarkers()). Each feature carries `id` + computed `kind`.
  function buildFeatureCollection(spaces) {
    const features = [];
    for (const s of spaces) {
      const lat = s.coordinates?.lat, lon = s.coordinates?.lon;
      if (typeof lat !== 'number' || typeof lon !== 'number' || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        console.warn('[buildFeatureCollection] skipping space with invalid coords:', s.id, lat, lon);
        continue;
      }
      features.push({
        type: 'Feature',
        id: s.id,
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { id: s.id, kind: computeMarker(s), name: s.name, city: s.city, country: s.country },
      });
    }
    return { type: 'FeatureCollection', features };
  }

  function colorMatchExpr(table) {
    const expr = ['match', ['get', 'kind']];
    for (const k of KINDS) expr.push(k, table[k]);
    expr.push(table.seeded); // fallback
    return expr;
  }
  // Zoom-staged ladder: identity-only below z9, full ladder from z9 up.
  // `step`, not `interpolate` — a blend between two palettes invents intermediate
  // colours that match no legend chip (amber→blue passes through mud). Detail on a
  // map appears by zoom level, like street labels; it does not cross-fade. The only
  // thing that transitions here is the day/night basemap.
  function ladderColorExpr(surface) {
    return ['step', ['zoom'],
      colorMatchExpr(ladderFar(surface)),
      9, colorMatchExpr(LADDER[surface])];
  }
  function strokeMatchExpr(surface) {
    const t = LADDER_STROKE[surface];
    return ['match', ['get', 'kind'], 'seeded', t.seeded, 'dead', t.dead, 'zombie', t.zombie, t.default];
  }
  // Single continuous radius ramp: a field of light at world zoom (z2) growing to
  // street-scale pins by z12+. Radius is the one property that ramps continuously;
  // colour and glyphs step at z9 (see ladderColorExpr).
  const RADIUS_STOPS = [[1.5, 1], [2, 2.2], [6, 3.5], [9, 9], [12, 12], [16, 16], [18, 22]];
  const DOT_SCALE = 0.5;
function radiusExpr(densityMul) {
    const e = ['interpolate', ['linear'], ['zoom']];
    for (const [z, r] of RADIUS_STOPS) e.push(z, r * densityMul);
    return e;
  }
function glyphColorExpr(surface) {
    return ['case', ['==', ['get', 'kind'], 'broken'], '#ffffff', surface === 'depth' ? '#F0EDE0' : '#1E1D1A'];
  }

  // Idempotent — safe to call after every setStyle (which wipes custom sources/layers).
  function ensureSpacesLayers() {
    if (!map || !map.getStyle()) return false;
    const surface = currentSurface();
    if (!map.getSource('spaces')) {
      map.addSource('spaces', { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, promoteId: 'id' });
    }
    // Beacon halo: rAF-driven A→B ripple. Transitions zeroed so setPaintProperty
    // takes effect immediately — no 300ms GL interpolation fighting the 16ms loop.
    if (!map.getLayer('spaces-glow')) {
      map.addLayer({ id: 'spaces-glow', type: 'circle', source: 'spaces',
        filter: ['==', ['get', 'kind'], 'open'],
        paint: {
          // Glow transitions with the basemap: bright algae on dark, deeper on light.
          'circle-color': ['interpolate', ['linear'], ['zoom'], 6, '#9FE1CB', 9, '#0F6E56'],
          'circle-opacity': 0,
          'circle-radius': 0,
          'circle-blur': 0.8,
          'circle-opacity-transition': { duration: 0, delay: 0 },
          'circle-radius-transition': { duration: 0, delay: 0 },
        } });
    }
    if (!map.getLayer('spaces-point')) {
      map.addLayer({ id: 'spaces-point', type: 'circle', source: 'spaces',
        layout: {
          // seeded always renders below registered dots (lower sort key = drawn first)
          'circle-sort-key': ['match', ['get', 'kind'], 'seeded', 0, 1],
        },
        paint: {
          'circle-color': ladderColorExpr(surface),
          'circle-radius': radiusExpr(DOT_SCALE),
          'circle-opacity': 1.0,
          'circle-stroke-width': ['case',
            ['boolean', ['feature-state', 'selected'], false], 2.5,
            ['==', ['get', 'kind'], 'seeded'], 0.5,
            1.2],
          'circle-stroke-color': ['case', ['boolean', ['feature-state', 'selected'], false], '#FFFFFF', strokeMatchExpr(surface)],
          'circle-stroke-opacity': ['interpolate', ['linear'], ['zoom'], 6, 0, 9, 1],
        } });
    }
    if (!map.getLayer('spaces-glyph')) {
      // minzoom 9: below that the glyphs are 1–2px smudges and staleness is not
      // decision-relevant anyway. Same hard z9 cut as the colour ladder, so the
      // amber dot and its `!` arrive together — a full-strength staleness colour
      // with no glyph to disambiguate it would be the worst of both.
      map.addLayer({ id: 'spaces-glyph', type: 'symbol', source: 'spaces',
        minzoom: 9,
        filter: ['in', ['get', 'kind'], ['literal', Object.keys(KIND_GLYPH)]],
        layout: {
          'text-field': ['match', ['get', 'kind'], 'broken', '×', 'aging', '!', 'zombie', '…', 'dead', '+', ''],
          'text-font': ['Noto Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 8, 12, 13],
          'text-allow-overlap': true,
          'text-ignore-placement': true,
        },
        paint: {
          'text-color': glyphColorExpr(surface),
        } });
    }
    wireSpacesClick();
    startBeacon();
    return true;
  }

  // Re-apply surface-dependent paint + radius. findActive = flat pin size for visibility.
  function applyLadderPaint(findActive = false) {
    const surface = currentSurface();
    if (map.getLayer('spaces-point')) {
      map.setPaintProperty('spaces-point', 'circle-color', ladderColorExpr(surface));
      map.setPaintProperty('spaces-point', 'circle-radius',
        findActive ? 6 : radiusExpr(DOT_SCALE));
      map.setPaintProperty('spaces-point', 'circle-stroke-color',
        ['case', ['boolean', ['feature-state', 'selected'], false], '#FFFFFF', strokeMatchExpr(surface)]);
    }
    if (map.getLayer('spaces-glyph')) map.setPaintProperty('spaces-glyph', 'text-color', glyphColorExpr(surface));
  }

  function isFindActive() {
    return state.search.trim().length >= 2 ||
      state.filters.networks.size > 0 || state.filters.countries.size > 0 ||
      state.filters.statuses.size > 0 || state.filters.specialties.size > 0;
  }

  // The one entry point replacing renderMarkers(): ensure layers exist, push fresh data,
  // re-apply paint + selection. Safe to call before the style is loaded (no-op until ready).
  function refreshSpacesLayer() {
    if (!map || !map.isStyleLoaded()) return;
    if (!ensureSpacesLayers()) return;
    const fc = buildFeatureCollection(filteredSpaces());
    const src = map.getSource('spaces');
    if (src) src.setData(fc);
    applyLadderPaint(isFindActive());
    if (state.selectedId) highlightSelected();
    updateCounts();
  }

  function wireSpacesClick() {
    if (map._spacesClickWired) return;
    map._spacesClickWired = true;
    map.on('click', 'spaces-point', (e) => {
      const f = e.features && e.features[0];
      if (!f) return;
      const s = state.spaces.find((x) => x.id === f.properties.id);
      if (!s) return;
      if (IS_EMBED) showEmbedPopup(s, f.properties.kind, f.geometry.coordinates);
      else selectSpace(s.id, { fly: false });
    });
    map.on('mouseenter', 'spaces-point', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'spaces-point', () => { map.getCanvas().style.cursor = ''; });
  }

  // Beacon: A→B ripple on open spaces. Transitions on the layer are zeroed so
  // setPaintProperty takes effect in the same frame — no 300ms GL easing fighting the loop.
  let _beaconRAF = null;
  function startBeacon() {
    if (_beaconRAF) return;
    const PERIOD = 2400;
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const tick = () => {
      _beaconRAF = requestAnimationFrame(tick);
      if (!map.getLayer('spaces-glow')) return;
      if (reduce) {
        map.setPaintProperty('spaces-glow', 'circle-opacity', 0);
        return;
      }
      const phase = (performance.now() % PERIOD) / PERIOD; // 0→1, snap
      const dotMul = DOT_SCALE;
      // ease-out expand: fast growth, slow tail; opacity zeroes well before the snap
      const expand = 1 - Math.pow(1 - phase, 2);
      map.setPaintProperty('spaces-glow', 'circle-radius',
        ['interpolate', ['linear'], ['zoom'], 2, dotMul * (4 + expand * 10), 9, dotMul * (8 + expand * 18), 16, dotMul * (14 + expand * 30)]);
      map.setPaintProperty('spaces-glow', 'circle-opacity', Math.pow(1 - phase, 1.8) * 0.85);
    };
    _beaconRAF = requestAnimationFrame(tick);
  }

  // Lightweight popup for embedded maps — no full detail drawer, just identity + a way out.
  let _embedPopup = null;
  function showEmbedPopup(s, kind, lngLat) {
    if (_embedPopup) _embedPopup.remove();
    const badgeKindClass = { open: 'sp-badge-open', shut: 'sp-badge-shut', confirmed: 'sp-badge-confirmed', broken: 'sp-badge-broken', seeded: 'sp-badge-seeded' };
    const kindLabel = { seeded: 'unclaimed', confirmed: 'claimed' };
    const deepLink = `https://mapsofmaking.org/?space=${encodeURIComponent(s.id)}`;

    const logoBox = el('div', { class: 'sp-logo' });
    if (s.logo) {
      const img = document.createElement('img');
      img.src = s.logo; img.alt = '';
      img.onerror = () => { img.remove(); logoBox.classList.add('is-placeholder'); logoBox.appendChild(_logoPlaceholder()); };
      logoBox.appendChild(img);
    } else {
      logoBox.classList.add('is-placeholder');
      logoBox.appendChild(_logoPlaceholder());
    }

    const node = el('div', { class: 'embed-popup' }, [
      el('div', { class: 'sp-hero' }, [
        el('div', { class: 'sp-name-row' }, [
          el('div', { class: 'sp-name' }, [s.name || s.id]),
          logoBox,
        ]),
        s.address ? el('div', { class: 'sp-address' }, [s.address]) : null,
        el('div', { class: 'sp-badges-row' }, [
          el('span', { class: `sp-badge ${badgeKindClass[kind] || 'sp-badge-tag'}` }, [kindLabel[kind] || kind]),
          ...(s.network_memberships || []).map((n) => el('span', { class: 'sp-badge sp-badge-tag' }, [n.split('/').pop().toUpperCase()])),
        ]),
      ]),
      el('div', { class: 'ep-footer' }, [
        el('a', { class: 'ep-link', href: deepLink, target: '_blank', rel: 'noopener' }, ['Open on mapsofmaking.org ↗']),
      ]),
    ]);
    _embedPopup = new maplibregl.Popup({ offset: 16, closeButton: true, closeOnClick: true, maxWidth: '280px' })
      .setLngLat(lngLat)
      .setDOMContent(node)
      .addTo(map);
  }

  // ───────────────────────────── live freshness axes (Story 3.10)
  // f(token, now, thresholds) evaluated at view time. Storage holds raw tokens only.
  function _ageMinutes(iso) {
    if (!iso) return null;
    const t = new Date(iso.endsWith('Z') ? iso : iso + 'Z').getTime();
    if (isNaN(t)) return null;
    return (Date.now() - t) / 60000;
  }
  function _ageDays(iso) {
    const m = _ageMinutes(iso);
    return m == null ? null : m / 1440;
  }

  // Axis A — endpoint health. Returns 'broken'|'warning'|'unresponsive'|'fresh'.
  function computeAxisA(s, thresholds) {
    if (!s) return 'broken';
    if (s.last_fetch_status === 'unreachable') return 'broken';
    if (!s.observed_at) return 'broken'; // never-observed → cannot claim healthy
    const t = (thresholds && thresholds.endpoint_health) || FALLBACK_THRESHOLDS.endpoint_health;
    const age = _ageMinutes(s.observed_at);
    if (age == null) return 'broken';
    if (age >= t.broken_minutes_threshold) return 'broken';
    if (age >= t.warning_minutes_threshold) return 'warning';
    if (age >= t.unresponsive_minutes_threshold) return 'unresponsive';
    return 'fresh';
  }

  // Returns updated_at as epoch ms, or null. Single anchor for Axis B and the
  // status-bar "updated X ago" line. updated_at is set by the pipeline at first
  // fetch (backfill) or on content change — both paths produce reliable ISO timestamps.
  // last_open_change (state.lastchange) is intentionally excluded: spaces self-report
  // it unreliably (stale 2013–2019 timestamps) and the pipeline backfill makes it
  // unnecessary as a fallback.
  function _lastActivity(s) {
    if (!s || s.updated_at == null) return null;
    const v = s.updated_at;
    const n = Number(v);
    if (!isNaN(n) && n > 1e8) return n * 1000;
    const iso = String(v);
    const t = new Date(iso.endsWith('Z') ? iso : iso + 'Z').getTime();
    return isNaN(t) ? null : t;
  }

  // Axis B — content lifecycle. Returns 'dead'|'zombie'|'aging'|'confirmed'.
  // Null _lastActivity → oldest supported state (never observed to change). Per AC 2
  // Dev Notes: do NOT crash, do NOT silently render `confirmed`.
  function computeAxisB(s, thresholds) {
    // Story 3.10 B1: per-feature override beats the global thresholds.
    // Used by canary demo mode to compress aging/zombie/dead to seconds-scale
    // so the bucket walk is observable in a live demo.
    const override = s && s.thresholds_override && s.thresholds_override.operational_state;
    const t = override || (thresholds && thresholds.operational_state) || FALLBACK_THRESHOLDS.operational_state;
    if (!s) return 'dead';
    const lastMs = _lastActivity(s);
    if (lastMs == null) return 'dead';
    const age = (Date.now() - lastMs) / 86400000;
    if (age >= t.dead_days_threshold) return 'dead';
    if (age >= t.zombie_days_threshold) return 'zombie';
    if (age >= t.aging_days_threshold) return 'aging';
    return 'confirmed';
  }

  // Axis C — operational liveness. Current source claim, does not age.
  // 'open'  = state.open=true   → green dot
  // 'shut'  = state.open=false  → dimmed green dot (operator-declared closed-right-now)
  // 'opt-out' = state field absent/unknown → C contributes nothing, fall through.
  function computeAxisC(s) {
    if (!s || s.open_now === undefined || s.open_now === null) return 'opt-out';
    return s.open_now === true ? 'open' : 'shut';
  }

  // Combined marker — precedence (per user, Axis C iteration):
  //   dead/zombie/aging (B) → broken (A) → open/shut (C) → confirmed → seeded.
  // Rationale: long-term silence (B) is louder than a transient endpoint blip (A);
  // a broken endpoint is louder than the current open/shut claim (we can't trust it).
  function computeMarker(s) {
    if (!s) return 'seeded';
    const b = computeAxisB(s, state.thresholds);
    if (_lastActivity(s) != null && (b === 'dead' || b === 'zombie' || b === 'aging')) return b;
    const a = computeAxisA(s, state.thresholds);
    if (a === 'broken' && s.observed_at) return 'broken';
    const c = computeAxisC(s);
    if (c === 'open') return 'open';
    if (c === 'shut') return 'shut';
    if (_lastActivity(s) != null || s.observed_at) return 'confirmed';
    return 'seeded';
  }

  // GL feature-state selection (replaces DOM classList). Clears the prior selection,
  // flags the current one. Guarded — the source may not be loaded yet on cold deep-links.
  function highlightSelected() {
    if (!map || !map.getSource('spaces')) return;
    if (state._fsSelected && state._fsSelected !== state.selectedId) {
      try { map.setFeatureState({ source: 'spaces', id: state._fsSelected }, { selected: false }); } catch {}
    }
    if (state.selectedId) {
      try { map.setFeatureState({ source: 'spaces', id: state.selectedId }, { selected: true }); } catch {}
    }
    state._fsSelected = state.selectedId;
  }

  function selectSpace(id, opts = {}) {
    state.selectedId = id;
    highlightSelected();
    renderDetail();
    // If add-url is open, don't hijack; else open detail drawer
    if (state.openDrawer !== 'addurl') setDrawer('detail');
    if (opts.fly) {
      const s = state.spaces.find((x) => x.id === id);
      if (s) map.flyTo({ center: [s.coordinates.lon, s.coordinates.lat], zoom: Math.max(map.getZoom(), 8), speed: 1.2 });
    }
  }

  // ───────────────────────────── camera fit
  function flyToOverview() {
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const pct = (arr, p) => { const s = [...arr].sort((a, b) => a - b); return s[Math.floor((s.length - 1) * p)]; };
    const lons = state.spaces.map(s => s.coordinates?.lon).filter(v => typeof v === 'number' && v >= -180 && v <= 180);
    const lats = state.spaces.map(s => s.coordinates?.lat).filter(v => typeof v === 'number' && v >= -90 && v <= 90);
    if (lons.length < 2 || lats.length < 2) return;
    map.fitBounds([[pct(lons, 0.05), pct(lats, 0.05)], [pct(lons, 0.95), pct(lats, 0.95)]],
      { padding: 80, maxZoom: 7, animate: !reduce });
  }

  let _fitTimer = null;
  function fitToMatches(matches) {
    if (!matches.length || matches.length > 400) return;
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (matches.length === 1) {
      map.flyTo({ center: [matches[0].coordinates.lon, matches[0].coordinates.lat], zoom: 13, animate: !reduce });
      return;
    }
    const lons = matches.map((s) => s.coordinates?.lon).filter((v) => typeof v === 'number');
    const lats = matches.map((s) => s.coordinates?.lat).filter((v) => typeof v === 'number');
    if (lons.length < 2) return;
    map.fitBounds(
      [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: 80, maxZoom: 11, animate: !reduce }
    );
  }
  function debouncedFit(matches) {
    clearTimeout(_fitTimer);
    _fitTimer = setTimeout(() => fitToMatches(matches), 350);
  }

  // ───────────────────────────── filtering
  function normalize(str) {
    return (str || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function filteredSpaces() {
    const f = state.filters;
    const q = normalize(state.search.trim());
    return state.spaces.filter((s) => {
      if (f.networks.size && !(s.network_memberships || []).some((n) => f.networks.has(n))) return false;
      if (f.countries.size && !f.countries.has(s.country_code)) return false;
      if (f.statuses.size) {
        const tag = computeMarker(s);
        if (!f.statuses.has(tag)) return false;
      }
      if (f.specialties.size && !(s.specialties || []).some((sp) => f.specialties.has(sp))) return false;
      if (q.length >= 2) {
        const countryStr = countryLabel(s.country_code) + ' ' + (s.country_code || '');
        const hay = normalize(s.name + ' ' + s.city + ' ' + countryStr + ' ' + (s.specialties || []).join(' ') + ' ' + (s.network_memberships || []).join(' '));
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function updateCounts() {
    if (IS_EMBED) return; // all targets are hidden chrome in embed mode
    const visible = filteredSpaces();
    const total = state.spaces.length;
    $('#results-count').textContent = String(visible.length);
    $('#drawer-count').textContent = `${visible.length} / ${total}`;
    renderResultsList(visible);
    renderPresetPreview();
  }

  // ───────────────────────────── filter chips
  // Returns spaces matching all active filters EXCEPT the named group — so chip counts
  // for that group reflect "how many would match if I add this chip" rather than the
  // already-filtered set (which would collapse unselected chips to 0).
  function filteredSpacesExcluding(excludeGroup) {
    const f = state.filters;
    const q = normalize(state.search.trim());
    return state.spaces.filter((s) => {
      if (excludeGroup !== 'networks' && f.networks.size && !(s.network_memberships || []).some((n) => f.networks.has(n))) return false;
      if (excludeGroup !== 'countries' && f.countries.size && !f.countries.has(s.country_code)) return false;
      if (excludeGroup !== 'statuses' && f.statuses.size) {
        if (!f.statuses.has(computeMarker(s))) return false;
      }
      if (excludeGroup !== 'specialties' && f.specialties.size && !(s.specialties || []).some((sp) => f.specialties.has(sp))) return false;
      if (q.length >= 2) {
        const countryStr = countryLabel(s.country_code) + ' ' + (s.country_code || '');
        const hay = normalize(s.name + ' ' + s.city + ' ' + countryStr + ' ' + (s.specialties || []).join(' ') + ' ' + (s.network_memberships || []).join(' '));
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function buildFilterChips() {
    const networks = unique(state.spaces.flatMap((s) => s.network_memberships))
      .map((n) => [n, n.split('/').pop().toUpperCase()]);
    const countries = unique(state.spaces.map((s) => s.country_code)).filter(Boolean);
    // Matches computeMarker's collapsed label. Real fix (orthogonal health/freshness
    // vs open/shut axes) is deferred → Epic 5. See deferred-work.md.
    const statuses = ['seeded', 'confirmed', 'open', 'shut', 'broken', 'aging', 'zombie', 'dead'];
    const specialties = unique(state.spaces.flatMap((s) => s.specialties)).sort();
    const active = isFindActive();

    renderChips('#chips-network', networks, state.filters.networks, {}, filteredSpacesExcluding('networks'), active);
    renderChips('#chips-country', countries.map((c) => [c, countryLabel(c)]), state.filters.countries, {}, filteredSpacesExcluding('countries'), active);
    const chipLabel = { seeded: 'unclaimed', confirmed: 'claimed', open: 'open now', shut: 'closed now', aging: 'going quiet', zombie: 'unreachable', dead: 'closed' };
    renderChips('#chips-status', statuses.map((s) => [s, chipLabel[s] || s]), state.filters.statuses, { swatch: true }, filteredSpacesExcluding('statuses'), active);
    renderChips('#chips-spec', specialties, state.filters.specialties, {}, filteredSpacesExcluding('specialties'), active);
  }

  function renderChips(selector, values, set, opts = {}, base = null, hideZero = false) {
    const host = $(selector);
    host.innerHTML = '';
    const countBase = base || state.spaces;
    // Pre-compute match counts
    const counts = new Map();
    for (const v of values) {
      const [val] = Array.isArray(v) ? v : [v, v];
      let count = 0;
      for (const s of countBase) {
        if (chipMatches(selector, s, val)) count++;
      }
      counts.set(val, count);
    }
    for (const v of values) {
      const [val, label] = Array.isArray(v) ? v : [v, v];
      const count = counts.get(val) || 0;
      if (hideZero && count === 0 && !set.has(val)) continue;
      const btn = el('button', { class: 'chip', 'aria-pressed': set.has(val) ? 'true' : 'false', type: 'button' }, [
        opts.swatch ? el('span', { class: `pin-swatch ${val}` }) : null,
        label.replace(/-/g, ' '),
        el('span', { class: 'count' }, [String(count)])
      ]);
      btn.addEventListener('click', () => {
        if (set.has(val)) set.delete(val); else set.add(val);
        btn.setAttribute('aria-pressed', set.has(val) ? 'true' : 'false');
        buildFilterChips();
        refreshSpacesLayer();
        debouncedFit(filteredSpaces());
      });
      host.appendChild(btn);
    }
  }

  function chipMatches(selector, s, val) {
    if (selector === '#chips-network') return (s.network_memberships || []).includes(val);
    if (selector === '#chips-country') return s.country_code === val;
    if (selector === '#chips-status') return computeMarker(s) === val;
    if (selector === '#chips-spec') return (s.specialties || []).includes(val);
    return false;
  }

  const COUNTRY_LABELS = {
    FR: '🇫🇷 France', DE: '🇩🇪 Germany', BE: '🇧🇪 Belgium', NL: '🇳🇱 Netherlands',
    CH: '🇨🇭 Switzerland', AT: '🇦🇹 Austria', LU: '🇱🇺 Luxembourg',
    GB: '🇬🇧 United Kingdom', IT: '🇮🇹 Italy', ES: '🇪🇸 Spain',
    CZ: '🇨🇿 Czechia', PL: '🇵🇱 Poland', SI: '🇸🇮 Slovenia', RS: '🇷🇸 Serbia',
    DK: '🇩🇰 Denmark', SE: '🇸🇪 Sweden', NO: '🇳🇴 Norway', FI: '🇫🇮 Finland',
    'sol-3': '🌍 Sol-3',
  };
  function countryLabel(c) { return COUNTRY_LABELS[c] || c; }

  function unique(arr) { return Array.from(new Set(arr)); }

  // ───────────────────────────── results list
  function renderResultsList(visible) {
    const host = $('#results-list');
    host.innerHTML = '';
    if (!visible.length) {
      const resetBtn = el('button', { class: 'btn', style: { marginTop: '8px' }, type: 'button' }, ['Reset']);
      resetBtn.addEventListener('click', () => $('#btn-reset-filters').click());
      host.appendChild(el('div', { style: { padding: '24px 14px', color: 'var(--muted)', fontSize: '13px' } }, [
        'No spaces match — try widening your Find',
        el('br'),
        resetBtn,
      ]));
      return;
    }
    for (const s of visible.slice(0, 200)) {
      const kind = computeMarker(s);
      const locationParts = [s.city, countryLabel(s.country_code)].filter(Boolean);
      const locationStr = locationParts.join(', ');
      const networkStr = (s.network_memberships || []).length ? ' · ' + s.network_memberships.map((n) => n.split('/').pop().toUpperCase()).join(' · ') : '';
      const item = el('button', { class: 'result', 'data-sid': s.id, 'aria-current': state.selectedId === s.id ? 'true' : 'false', type: 'button' }, [
        el('span', { class: `pin-swatch ${kind}`, style: { marginTop: '2px' } }),
        el('div', { style: { flex: 1, minWidth: 0 } }, [
          el('div', { class: 'name' }, [s.name]),
          el('div', { class: 'meta' }, [locationStr + networkStr]),
          el('div', { class: 'tags' }, (s.specialties || []).slice(0, 4).map((sp) => el('span', { class: 'tag' }, [sp]))),
        ]),
        el('span', { class: `status-label ${kind}`, style: { alignSelf: 'flex-start' } }, [kind])
      ]);
      host.appendChild(item);
    }
  }

  // ───────────────────────────── detail drawer helpers
  function _logoPlaceholder() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '22'); svg.setAttribute('height', '22'); svg.setAttribute('viewBox', '0 0 20 20'); svg.setAttribute('fill', 'none');
    svg.innerHTML = '<rect x="3" y="3" width="14" height="14" stroke="#8a8070" stroke-width="1.4"/><circle cx="7" cy="7.5" r="1.4" fill="#8a8070"/><polyline points="3,14 7,10 10,13 13,10 17,14" stroke="#8a8070" stroke-width="1.4" fill="none"/>';
    return svg;
  }

  // Detect double-encoded UTF-8 (mojibake) in a space's text fields — e.g. an
  // endpoint that serves "Universität" as "UniversitÃ¤t". We never repair the
  // data (the raw snapshot stays byte-for-byte as served); we only surface the
  // anomaly to coordinators in the Source Data zone. The signature is a stray
  // Ã/Â immediately followed by another high code point.
  const _MOJIBAKE_RE = /[\u00C2\u00C3][\u0080-\u00FF]/;
  function _detectEncodingIssue(s) {
    const sample = s.address || '';
    if (_MOJIBAKE_RE.test(sample)) return sample;
    for (const f of [s.name, s.description, s.opening_hours, s.next_event]) {
      if (typeof f === 'string' && _MOJIBAKE_RE.test(f)) return f;
    }
    return null;
  }

  function _contactChannel(key) {
    const SVG_ICONS = {
      email: '<path d="M1.5 3h11l-5.5 5L1.5 3zm-1 1v7.5c0 .3.2.5.5.5h12c.3 0 .5-.2.5-.5V4l-6.5 5.5L.5 4z"/>',
      twitter: '<path d="M13 1.5L8.5 6.7l5 5.8H11L7.5 8.4 3.5 12.5H1l4.7-5.4L1.2 1.5H4L7.2 5l3.7-3.5H13z"/>',
      mastodon: '<path d="M7 1C4.2 1 2 3 2 5.5v3C2 10.5 3.8 12 6 12c.4.6.9 1 1 1s.6-.4 1-1c2.2 0 4-1.5 4-3.5v-3C12 3 9.8 1 7 1zm0 1.5c2 0 3.5 1.3 3.5 3V9c0 1.1-1.1 2-2.5 2l-.4.6-.6-.6C5.6 11 4.5 10.1 4.5 9V5.5C4.5 4.3 5.8 2.5 7 2.5zM5.5 5v3.5h1V5h-1zm2 0v3.5h1V5h-1z"/>',
      facebook: '<path d="M8.5 2H7C5.9 2 5 2.9 5 4v1H3.5v2H5v5h2V7h1.5l.5-2H7V4.2c0-.4.2-.7.7-.7H8.5V2z"/>',
    };
    const URL_KEYS = new Set(['twitter', 'mastodon', 'facebook', 'website', 'ml', 'blog']);
    const TEXT_LABELS = { phone: '[ph]', irc: '[#]', website: '↗', ml: '↗', matrix: '[mx]', foursquare: '[fs]' };

    const action = URL_KEYS.has(key) ? 'url' : 'copy';
    let node;
    if (SVG_ICONS[key]) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 14 14'); svg.setAttribute('fill', 'currentColor');
      svg.setAttribute('width', '15'); svg.setAttribute('height', '15');
      svg.innerHTML = SVG_ICONS[key];
      node = svg;
    } else {
      const label = TEXT_LABELS[key] || '[' + key.slice(0, 2) + ']';
      node = document.createTextNode(label);
    }
    return { node, action };
  }

  // ───────────────────────────── detail drawer
  function renderDetail() {
    const body = $('#detail-body');
    body.innerHTML = '';
    const s = state.spaces.find((x) => x.id === state.selectedId);
    if (!s) {
      body.appendChild(el('div', { style: { padding: '24px', color: 'var(--muted)' } }, ['Click a pin to see details.']));
      return;
    }
    const kind = computeMarker(s);
    // Share CTA in drawer header (hidden on mobile via CSS)
    const drawerHead = document.querySelector('#drawer-detail .drawer-head');
    let shareBtn = drawerHead && drawerHead.querySelector('.share-cta');
    const SHARE_SVG = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="11" cy="3" r="1.6"/><circle cx="11" cy="11" r="1.6"/><circle cx="3" cy="7" r="1.6"/><line x1="9.7" y1="3.7" x2="4.3" y2="6.3"/><line x1="4.3" y1="7.7" x2="9.7" y2="10.3"/></svg>';
    if (drawerHead && !shareBtn) {
      shareBtn = el('button', { class: 'share-cta', title: 'Copy profile link', style: { marginLeft: 'auto', width: '28px', height: '28px', border: '1.5px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'transparent', cursor: 'pointer', borderRadius: '2px', marginRight: '0' } }, []);
      shareBtn.innerHTML = SHARE_SVG;
      const closeBtn = drawerHead.querySelector('.close');
      drawerHead.insertBefore(shareBtn, closeBtn);
    }
    if (shareBtn) {
      shareBtn.onclick = () => {
        // Story 5.0 AC5 — append coords so the shared link opens local-first (viewport-first).
        const url = window.location.origin + '/?space=' + s.id
          + `&lat=${s.coordinates.lat.toFixed(5)}&lon=${s.coordinates.lon.toFixed(5)}`;
        navigator.clipboard.writeText(url).then(() => {
          shareBtn.textContent = '✓';
          setTimeout(() => { shareBtn.innerHTML = SHARE_SVG; }, 1500);
        }).catch(() => {});
      };
    }
    const networkLabel = (urn) => urn.split('/').pop().toUpperCase();

    // ── Hero ──
    const logoBox = el('div', { class: 'sp-logo' });
    if (s.logo) {
      const img = document.createElement('img');
      img.src = s.logo;
      img.alt = '';
      img.onerror = () => { img.remove(); logoBox.classList.add('is-placeholder'); logoBox.appendChild(_logoPlaceholder()); };
      logoBox.appendChild(img);
    } else {
      logoBox.classList.add('is-placeholder');
      logoBox.appendChild(_logoPlaceholder());
    }
    const badgeKindClass = { open: 'sp-badge-open', shut: 'sp-badge-shut', confirmed: 'sp-badge-confirmed', broken: 'sp-badge-broken', seeded: 'sp-badge-seeded' };
    const kindLabel = { seeded: 'unclaimed', confirmed: 'claimed' };
    body.appendChild(el('div', { class: 'sp-hero' }, [
      el('div', { class: 'sp-name-row' }, [
        el('div', { class: 'sp-name' }, [s.name]),
        logoBox,
      ]),
      el('div', { class: 'sp-address' }, [s.address || el('em', { class: 'sp-fact-empty' }, ['address not provided'])]),
      el('div', { class: 'sp-badges-row' }, [
        el('span', { class: `sp-badge ${badgeKindClass[kind] || 'sp-badge-tag'}` }, [kindLabel[kind] || kind]),
        ...(s.network_memberships || []).map((n) => el('span', { class: 'sp-badge sp-badge-tag' }, [networkLabel(n)])),
        s.open_for_hosting ? el('span', { class: 'sp-badge sp-badge-tag' }, ['open for hosting']) : null,
      ]),
    ]));

    // ── Synthetic canary label (Mother Sands only) ──
    if (s.id === 'mother-sands') {
      const observedAt = s.observed_at || null;
      const ageStr = observedAt ? `Snapshot age: ${timeAgo(observedAt)} ago (observed_at: ${observedAt})` : 'No clean snapshot yet';
      body.appendChild(el('div', { class: 'sp-canary-label', style: { padding: '8px 16px', background: 'var(--rule)', borderRadius: '2px', margin: '8px 0', fontSize: '0.82em', color: 'var(--paper)', lineHeight: '1.4' } }, [
        el('strong', {}, ['Synthetic reference space']),
        ' — Mother Sands is MOM\'s diagnostic canary — a reference space we control to test our own data pipeline.',
        el('div', { style: { marginTop: '4px', fontFamily: 'monospace' } }, [ageStr]),
      ]));
    }

    // ── Status bar (non-seeded) ──
    if (kind !== 'seeded') {
      const dotClass = ['aging', 'zombie'].includes(kind) ? 'sp-dot sp-dot-stale'
        : kind === 'broken' ? 'sp-dot sp-dot-error' : 'sp-dot';
      const statusPhrases = { open: 'Reports open now', shut: 'Reports close now', confirmed: 'Claimed', broken: 'Endpoint issue', aging: 'Going quiet', zombie: 'Unreachable', dead: 'Permanently closed' };
      const phrase = statusPhrases[kind] || kind;
      const lastMs = _lastActivity(s);
      body.appendChild(el('div', { class: 'sp-status-bar' }, [
        el('div', { class: 'sp-status-left' }, [
          el('div', { class: dotClass }),
          el('span', {}, [phrase]),
        ]),
        el('div', { class: 'sp-status-right' }, [
          'updated ' + (lastMs != null ? timeAgo(new Date(lastMs).toISOString()) + ' ago' : 'unknown')
        ]),
      ]));
    }

    // ── Quick Facts (non-seeded) ──
    if (kind !== 'seeded') {
      const factsKids = [
        el('span', { class: 'sp-fact-key' }, ['Description']),
        el('span', { class: 'sp-fact-val' }, [s.description || el('em', { class: 'sp-fact-empty' }, ['—'])]),
        el('span', { class: 'sp-fact-key' }, ['Website']),
        el('span', { class: 'sp-fact-val' }, [s.website
          ? el('a', { href: s.website, target: '_blank', rel: 'noopener' }, [s.website.replace(/^https?:\/\//, '')])
          : el('em', { class: 'sp-fact-empty' }, ['—'])]),
        el('span', { class: 'sp-fact-key' }, ['Hours']),
        el('span', { class: 'sp-fact-val' }, [s.opening_hours || el('em', { class: 'sp-fact-empty' }, ['—'])]),
      ];
      // Next event — always rendered (— when missing) so visitors see the gap
      factsKids.push(el('span', { class: 'sp-fact-key' }, ['Next event']));
      factsKids.push(el('span', { class: 'sp-fact-val' }, [s.next_event || el('em', { class: 'sp-fact-empty' }, ['—'])]));

      // Contact — always rendered
      factsKids.push(el('span', { class: 'sp-fact-key' }, ['Contact']));
      const hasContact = s.contact && typeof s.contact === 'object' && Object.keys(s.contact).length > 0;
      if (hasContact) {
        const channelsDiv = el('div', { class: 'sp-channels' });
        Object.entries(s.contact).forEach(([key, val]) => {
          const { node: iconNode, action } = _contactChannel(key);
          const btn = el('button', { class: 'sp-channel', title: `${key}: ${val}` }, []);
          btn.appendChild(iconNode);
          btn.addEventListener('click', () => {
            if (action === 'url') {
              const safeVal = String(val);
              if (safeVal.startsWith('https://') || safeVal.startsWith('http://')) {
                window.open(safeVal, '_blank', 'noopener');
              }
            } else {
              navigator.clipboard.writeText(String(val)).then(() => {
                btn.textContent = '✓';
                setTimeout(() => { btn.innerHTML = ''; btn.appendChild(_contactChannel(key).node); }, 1500);
              }).catch(() => {});
            }
          });
          channelsDiv.appendChild(btn);
        });
        factsKids.push(el('span', { class: 'sp-fact-val' }, [channelsDiv]));
      } else {
        factsKids.push(el('span', { class: 'sp-fact-val' }, [el('em', { class: 'sp-fact-empty' }, ['—'])]));
      }
      body.appendChild(el('div', { class: 'sp-section' }, [
        el('div', { class: 'sp-section-label' }, ['Quick Facts']),
        el('div', { class: 'sp-facts' }, factsKids),
      ]));
    }

    // ── Specialties ──
    if (s.specialties && s.specialties.length > 0) {
      body.appendChild(el('div', { class: 'sp-section' }, [
        el('div', { class: 'sp-section-label' }, ['Specialties']),
        el('div', { class: 'sp-pills' }, s.specialties.map((sp) => el('span', { class: 'sp-pill' }, [sp]))),
      ]));
    }

    // ── Embed CTA (desktop-only via CSS) ──
    if (kind !== 'seeded') {
      const embedBtn = el('button', { class: 'sp-embed-btn' }, []);
      embedBtn.innerHTML = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><polyline points="4.5,3 1.5,7 4.5,11"/><polyline points="9.5,3 12.5,7 9.5,11"/><line x1="8.2" y1="2.5" x2="5.8" y2="11.5"/></svg> Embed this space →';
      embedBtn.addEventListener('click', () => embedSpace(s.id));
      body.appendChild(el('div', { class: 'sp-section sp-embed-wrap' }, [embedBtn]));
    }

    // ── What your data unlocks / state banners ──
    {
      if (kind === 'seeded') {
        const bannerDiv = el('div', { class: 'sp-section', style: { cursor: 'pointer' } }, [
          el('div', { class: 'sp-section-label' }, ['Unclaimed space']),
          el('div', { style: { fontSize: '13px', color: 'var(--muted)', marginTop: '4px' } }, ['This space appears in a public directory. Register your endpoint to claim it and keep your information live on the map.']),
        ]);
        bannerDiv.addEventListener('click', () => setDrawer('addurl'));
        body.appendChild(bannerDiv);
      } else if (kind === 'broken') {
        const lastOkAgo = s.observed_at ? ` Last successful fetch ${timeAgo(s.observed_at)} ago.` : '';
        const headline = s.last_fetch_error || 'Endpoint unreachable';
        body.appendChild(el('div', { class: 'sp-section' }, [
          el('div', { class: 'sp-section-label' }, ['Endpoint issue']),
          el('div', { style: { fontSize: '13px', color: 'var(--error, #c0392b)', marginTop: '4px' } }, [`${headline}.${lastOkAgo}`]),
        ]));
      } else if (kind === 'aging') {
        const agingAgo = s.observed_at ? ` — last fetched ${timeAgo(s.observed_at)} ago` : '';
        body.appendChild(el('div', { class: 'sp-section' }, [
          el('div', { class: 'sp-section-label' }, ['Heads up']),
          el('div', { style: { fontSize: '13px', color: 'var(--muted)', marginTop: '4px' } }, [`Going quiet${agingAgo}. Data may be slightly stale.`]),
        ]));
      } else if (kind === 'zombie') {
        const zombieAgo = s.observed_at ? `. Last seen ${timeAgo(s.observed_at)} ago` : '';
        body.appendChild(el('div', { class: 'sp-section' }, [
          el('div', { class: 'sp-section-label' }, ['Heads up']),
          el('div', { style: { fontSize: '13px', color: 'var(--error, #c0392b)', marginTop: '4px' } }, [`Unreachable for a while — information may be outdated${zombieAgo}.`]),
        ]));
      } else if (kind === 'dead') {
        body.appendChild(el('div', { class: 'sp-section' }, [
          el('div', { class: 'sp-section-label' }, ['Space status']),
          el('div', { style: { fontSize: '13px', color: 'var(--muted)', marginTop: '4px' } }, ['This space is permanently closed.']),
        ]));
      }

      // Stepped unlock section — confirmed or broken-with-guidance
      const showUnlock = (kind === 'confirmed') || (kind === 'broken' && s.next_unlock);
      if (showUnlock) {
        const unlockSection = el('div', { class: 'sp-section' }, [
          el('div', { class: 'sp-section-label' }, ['What your data unlocks']),
        ]);
        if (s.subset === 'spaceapi:compatible') {
          const step = el('div', { class: 'sp-unlock-step' }, [
            el('div', { class: 'sp-unlock-marker done' }, ['✓']),
            el('div', { class: 'sp-unlock-body' }, []),
          ]);
          step.querySelector('.sp-unlock-body').innerHTML = '<strong>Full SpaceAPI compatibility</strong> — interoperable with mapall.space.';
          unlockSection.appendChild(step);
        } else {
          const stepDone = el('div', { class: 'sp-unlock-step' }, [
            el('div', { class: 'sp-unlock-marker done' }, ['✓']),
            el('div', { class: 'sp-unlock-body' }, []),
          ]);
          stepDone.querySelector('.sp-unlock-body').innerHTML = "<strong>You're here.</strong> Space is registered on the map.";
          unlockSection.appendChild(stepDone);
          if (s.next_unlock) {
            const stepNext = el('div', { class: 'sp-unlock-step' }, [
              el('div', { class: 'sp-unlock-marker next' }, ['→']),
              el('div', { class: 'sp-unlock-body' }, []),
            ]);
            stepNext.querySelector('.sp-unlock-body').innerHTML = '<strong>Level up.</strong> ' + s.next_unlock.replace(/<|>/g, (c) => c === '<' ? '&lt;' : '&gt;');
            unlockSection.appendChild(stepNext);
          }
        }
        body.appendChild(unlockSection);
      }
    }

    // ── Source Data — desktop only, non-seeded ──
    if (window.innerWidth >= 768 && kind !== 'seeded') {
      const zone3 = el('div', { class: 'detail-section zone-source', style: { padding: '12px 14px' } }, [
        el('div', { class: 'sp-section-header' }, [
          el('div', { class: 'sp-section-label' }, ['Source Data']),
          s.endpoint_url ? el('a', { href: s.endpoint_url, target: '_blank', rel: 'noopener', class: 'sp-section-label', style: { textDecoration: 'none', marginBottom: '0' } }, ['↗ Open source']) : null,
        ]),
        el('div', { class: 'raw-content', style: { color: 'var(--muted)', fontSize: '11px' } }, ['Loading source data…']),
      ]);
      // Coordinator-facing data-quality flag — surfaced, never repaired (the raw
      // snapshot below stays exactly as the endpoint served it).
      const encIssue = _detectEncodingIssue(s);
      if (encIssue) {
        zone3.insertBefore(
          el('div', { class: 'sp-data-warning', style: { display: 'flex', gap: '6px', alignItems: 'flex-start', margin: '6px 0 2px', padding: '7px 9px', border: '1px solid var(--error, #c0392b)', borderRadius: '2px', fontSize: '11px', lineHeight: '1.4', color: 'var(--error, #c0392b)' } }, [
            el('span', { style: { flex: '0 0 auto' } }, ['⚠']),
            el('span', {}, ['Encoding issue in source — non-UTF-8 characters arrive corrupted (e.g. ', el('code', {}, [encIssue.match(_MOJIBAKE_RE)[0]]), '). The space owner should serve UTF-8; the raw response below is shown unaltered.']),
          ]),
          zone3.querySelector('.raw-content')
        );
      }
      body.appendChild(zone3);
      const rawEl = zone3.querySelector('.raw-content');

      const _loadZone3 = () => {
        if (!rawEl) return;
        rawEl.innerHTML = '';
        fetch(`/api/space/${s.id}/raw`)
          .then(r => r.json())
          .then(result => {
            if (!rawEl) return;
            rawEl.innerHTML = '';
            if (result.error || result.truncated) {
              rawEl.textContent = result.truncated ? 'Source data exceeds display limit.' : 'Source unavailable.';
              if (rawEl.parentElement) {
                rawEl.parentElement.querySelector('.sp-refresh-btn')?.remove();
                rawEl.parentElement.appendChild(_makeRefreshBtn(null));
              }
              return;
            }
            const termWrap = el('div', { class: 'sp-terminal-wrap' }, [
              el('div', { class: 'sp-terminal-head' }, [
                el('span', { class: 'sp-terminal-head-label' }, ['JSON · Endpoint Response']),
                el('span', { class: 'sp-terminal-head-meta' }, [s.observed_at ? new Date(s.observed_at).toLocaleString() : '—']),
              ]),
            ]);
            const pre = document.createElement('pre');
            pre.className = 'json sp-terminal-body';
            pre.appendChild(jsonHighlight(result.raw));
            termWrap.appendChild(pre);
            rawEl.appendChild(termWrap);
            const trustLine = el('div', { class: 'sp-trust-line' }, ['The map only reads & enhances your data — it never edits the source.']);
            rawEl.appendChild(trustLine);
            if (rawEl.parentElement) {
              rawEl.parentElement.querySelector('.sp-refresh-btn')?.remove();
              rawEl.parentElement.appendChild(_makeRefreshBtn(s.observed_at));
            }
          })
          .catch(() => {
            if (rawEl) {
              rawEl.textContent = 'Source unavailable.';
              if (rawEl.parentElement) {
                rawEl.parentElement.querySelector('.sp-refresh-btn')?.remove();
                rawEl.parentElement.appendChild(_makeRefreshBtn(null));
              }
            }
          });
      };

      const _makeRefreshBtn = (lastFetched) => {
        const btn = document.createElement('button');
        btn.className = 'sp-refresh-btn';
        btn.title = 'Refresh data from endpoint';
        btn.innerHTML = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M12.5 2v3.5h-3.5"/><path d="M12.3 5.3A5.5 5.5 0 1 1 10.1 2.5"/></svg> Refresh from endpoint'
          + (lastFetched ? `<span class="sp-refresh-meta">fetched ${timeAgo(lastFetched)} ago</span>` : '');
        btn.addEventListener('click', () => {
          btn.disabled = true;
          btn.innerHTML = '… Refreshing';
          const msgEl = btn.nextSibling && btn.nextSibling.className === 'sp-refresh-msg' ? btn.nextSibling : null;
          if (msgEl) msgEl.remove();
          fetch(`/api/heartbeat-space/${s.id}`, { method: 'POST' })
            .then(r => r.json().then(body => ({ ok: r.ok, status: r.status, body })))
            .then(({ ok, status, body }) => {
              btn.innerHTML = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M12.5 2v3.5h-3.5"/><path d="M12.3 5.3A5.5 5.5 0 1 1 10.1 2.5"/></svg> Refresh from endpoint';
              btn.disabled = false;
              if (status === 429) {
                const msg = document.createElement('span');
                msg.className = 'sp-refresh-msg';
                const retryAfter = body?.detail?.retry_after_seconds;
                msg.textContent = retryAfter ? `Refreshed recently — try again in ${retryAfter}s` : 'Refreshed recently — try again shortly';
                btn.after(msg);
                setTimeout(() => msg.remove(), 3000);
              } else if (ok) {
                fetch(`/data/spaces.geojson?t=${Date.now()}`)
                  .then(r => r.json())
                  .then(geoJson => {
                    ingestGeoJSON(geoJson);
                    refreshSpacesLayer();
                    renderDetail();
                  })
                  .catch(() => {})
                  .finally(() => _loadZone3());
              } else {
                const msg = document.createElement('span');
                msg.className = 'sp-refresh-msg sp-refresh-msg--error';
                msg.textContent = 'Refresh failed — try again later';
                btn.after(msg);
                setTimeout(() => msg.remove(), 3000);
              }
            })
            .catch(() => {
              btn.innerHTML = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M12.5 2v3.5h-3.5"/><path d="M12.3 5.3A5.5 5.5 0 1 1 10.1 2.5"/></svg> Refresh from endpoint';
              btn.disabled = false;
              const msg = document.createElement('span');
              msg.className = 'sp-refresh-msg sp-refresh-msg--error';
              msg.textContent = 'Refresh failed — try again later';
              btn.after(msg);
              setTimeout(() => msg.remove(), 3000);
            });
        });
        return btn;
      };

      _loadZone3();
    }
  }

  function timeAgo(iso) {
    if (!iso) return 'never';
    const t = new Date(iso.endsWith('Z') ? iso : iso + 'Z').getTime();
    if (isNaN(t)) return 'unknown';
    const sec = (Date.now() - t) / 1000;
    if (sec < 60) return `${Math.round(sec)}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    if (sec < 86400) return `${Math.round(sec / 3600)}h`;
    return `${Math.round(sec / 86400)}d`;
  }


  function jsonHighlight(obj) {
    const txt = JSON.stringify(obj, null, 2);
    // minimal syntax highlight
    const frag = document.createDocumentFragment();
    const re = /("(?:\\(?:u[0-9a-fA-F]{4}|.)|[^"\\])*")(\s*:)?|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
    let last = 0, m;
    while ((m = re.exec(txt))) {
      if (m.index > last) frag.appendChild(document.createTextNode(txt.slice(last, m.index)));
      if (m[1]) {
        const span = document.createElement('span');
        span.className = m[2] ? 'k' : 's';
        span.textContent = m[1] + (m[2] || '');
        frag.appendChild(span);
      } else if (m[3]) {
        const span = document.createElement('span');
        span.className = 'c'; span.textContent = m[3]; frag.appendChild(span);
      } else if (m[4]) {
        const span = document.createElement('span');
        span.className = 'n'; span.textContent = m[4]; frag.appendChild(span);
      }
      last = re.lastIndex;
    }
    if (last < txt.length) frag.appendChild(document.createTextNode(txt.slice(last)));
    return frag;
  }

  // ───────────────────────────── preset & embed
  function applyUrlParams() {
    const p = new URLSearchParams(window.location.search);
    if (p.has('networks')) p.get('networks').split(',').filter(Boolean).forEach((n) => state.filters.networks.add(n));
    if (p.has('country'))  p.get('country').split(',').filter(Boolean).forEach((c) => state.filters.countries.add(c));
    if (p.has('status'))   p.get('status').split(',').filter(Boolean).forEach((s) => state.filters.statuses.add(s));
    if (p.has('specialty')) p.get('specialty').split(',').filter(Boolean).forEach((s) => state.filters.specialties.add(s));
    if (p.has('q')) state.search = p.get('q');
    // viewport + space selection applied after map loads
    const bbox = p.get('bbox');
    const center = p.get('center');
    const spaceId = p.get('space');
    // Story 5.0 AC5 — when ?lat/?lon were present, initMap already centered the map there
    // (viewport-first). state._initialViewport tells us to select WITHOUT a flyTo on cold load.
    const viewportFirst = state._initialViewport;
    if (bbox || center || spaceId) {
      map.once('load', () => {
        if (bbox) {
          const [west, south, east, north] = bbox.split(',').map(Number);
          if ([west, south, east, north].every((n) => !isNaN(n))) {
            map.fitBounds([[west, south], [east, north]], { animate: false });
          }
        } else if (center) {
          const [lat, lon] = center.split(',').map(Number);
          if (!isNaN(lat) && !isNaN(lon)) map.jumpTo({ center: [lon, lat], zoom: 13 });
        }
        // (?lat/?lon needs no jump here — initMap consumed it as the initial center.)
        const target = spaceId && state.spaces.find((x) => x.id === spaceId);
        if (target) {
          if (IS_EMBED) {
            // no detail drawer in embed — lightweight popup. Only fly if we're not
            // already centered on the deep-linked viewport (AC5) — AC6 legacy still flies.
            if (!viewportFirst) {
              map.flyTo({ center: [target.coordinates.lon, target.coordinates.lat], zoom: Math.max(map.getZoom(), 8), speed: 1.2 });
            }
            showEmbedPopup(target, computeMarker(target), [target.coordinates.lon, target.coordinates.lat]);
          } else {
            // viewport-first → no flyTo on cold load; legacy (?space only) → graceful fly (AC6).
            selectSpace(spaceId, { fly: !viewportFirst });
          }
        }
      });
    }
  }

  function renderPresetPreview() {
    const visible = filteredSpaces();
    $('#pp-count').textContent = String(visible.length);
    const parts = [];
    if (state.filters.networks.size) parts.push(`networks=${[...state.filters.networks].join(',')}`);
    if (state.filters.countries.size) parts.push(`country=${[...state.filters.countries].join(',')}`);
    if (state.filters.statuses.size) parts.push(`status=${[...state.filters.statuses].join(',')}`);
    if (state.filters.specialties.size) parts.push(`specialty=${[...state.filters.specialties].join(',')}`);
    if (state.search) parts.push(`q=${encodeURIComponent(state.search)}`);
    const q = parts.join('&') || 'all';
    $('#pp-filters').textContent = q;

    const bbox = map ? (() => {
      const b = map.getBounds();
      return `${b.getWest().toFixed(2)},${b.getSouth().toFixed(2)},${b.getEast().toFixed(2)},${b.getNorth().toFixed(2)}`;
    })() : '—';

    const name = $('#preset-name').value.trim() || 'untitled-preset';
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const base = window.location.origin + window.location.pathname;
    const paramParts = [`preset=${slug}`, q !== 'all' ? q : null, `bbox=${bbox}`];
    if (state.embed.centerId) {
      // single-space embed: ?space= selects/pops the space (overrides bbox on load).
      // Story 5.0 AC5 — append the space's coords so the embed loads local-first.
      paramParts.push(`space=${encodeURIComponent(state.embed.centerId)}`);
      const cs = state.spaces.find((x) => x.id === state.embed.centerId);
      if (cs && cs.coordinates) {
        paramParts.push(`lat=${cs.coordinates.lat.toFixed(5)}`, `lon=${cs.coordinates.lon.toFixed(5)}`);
      }
    }
    const shareUrl = `${base}?${paramParts.filter(Boolean).join('&')}`;

    const iframe = `<figure style="margin:0">\n  <iframe src="${shareUrl}"\n          width="100%" height="520"\n          style="border:1.5px solid #1a1a1a;display:block"\n          title="${name}"\n          loading="lazy"></iframe>\n  <figcaption>Source: <a href="https://mapsofmaking.org">Maps of Making</a> · Apache 2.0</figcaption>\n</figure>`;

    $('#code-iframe-text').textContent = iframe;
    $('#code-url-text').textContent = shareUrl;
  }

  function embedSpace(id) {
    const s = state.spaces.find((x) => x.id === id);
    if (!s) return;
    $('#preset-name').value = s.name;
    state.embed.centerId = id;
    if (map) map.flyTo({ center: [s.coordinates.lon, s.coordinates.lat], zoom: Math.max(map.getZoom(), 10), speed: 1.2 });
    setDrawer('preset');
  }

  // ───────────────────────────── add URL
  let _addUrlOriginalHTML = null;

  function _resetAddUrlForm() {
    if (_addUrlOriginalHTML === null) return;
    // Skip if form is already in initial state (avoid double-init on first open)
    const result = $('#url-result');
    const input = $('#existing-url-input');
    if (result && !result.innerHTML && input && !input.value) return;
    $('.addurl-body').innerHTML = _addUrlOriginalHTML;
    _wireAddUrlHandlers();
  }

  function _wireAddUrlHandlers() {
    $('#btn-fetch-url').addEventListener('click', _onFetchUrl);
    const revealBtn = $('#btn-reveal-url');
    if (revealBtn) {
      revealBtn.addEventListener('click', () => {
        const fork = $('#url-fork');
        if (!fork) return;
        const opening = !fork.classList.contains('open');
        fork.classList.toggle('open', opening);
        revealBtn.setAttribute('aria-expanded', opening ? 'true' : 'false');
        if (opening) {
          // Focus after the reveal animation so the field is in place
          setTimeout(() => { const inp = $('#existing-url-input'); if (inp) inp.focus(); }, 300);
        }
      });
    }
    const ctaBtn = $('#btn-wizard-cta');
    if (ctaBtn) {
      ctaBtn.addEventListener('click', () => {
        const draft = localStorage.getItem('genjson_draft');
        const url = draft
          ? 'https://genjson.mapsofmaking.org/?resume=1'
          : 'https://genjson.mapsofmaking.org/';
        window.open(url, '_blank', 'noopener');
      });
    }
  }

  async function _onFetchUrl() {
    const out = $('#url-result');
    const url = $('#existing-url-input').value.trim();
    if (!url) { out.innerHTML = ''; out.appendChild(el('span', { style: { color: 'var(--accent)' } }, ['✗ enter a URL first.'])); return; }
    // Basic URL validation
    if (!url.startsWith('http://') && !url.startsWith('https://')) { out.innerHTML = ''; out.appendChild(el('span', { style: { color: 'var(--accent)' } }, ['✗ URL must start with http:// or https://'])); return; }
    out.innerHTML = ''; out.appendChild(el('span', { style: { color: 'var(--muted)' } }, ['→ resolving DNS…']));
    let data;
    try {
      const resp = await fetch('/api/validate-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      if (!resp.ok && resp.headers.get('content-type')?.includes('text/html')) {
        out.innerHTML = '';
        out.appendChild(el('span', { style: { color: 'var(--accent)' } }, [`✗ API error: HTTP ${resp.status} — backend may be down`]));
        return;
      }
      data = await resp.json();
    } catch (e) {
      out.innerHTML = '';
      out.appendChild(el('span', { style: { color: 'var(--accent)' } }, [`✗ Network error: ${e.message}`]));
      return;
    }

    const lines = [];
    let blocking = false;

    if (!data.reachable) {
      lines.push({ ok: false, text: `not reachable — ${escHtml(data.error || 'unreachable')}` });
      blocking = true;
    } else {
      lines.push({ ok: true, text: `reachable (${escHtml(data.status_code)} OK)` });
      if (!data.schema_valid) {
        lines.push({ ok: false, text: `schema not recognised — ${escHtml(data.error || 'missing name or space field')}` });
        blocking = true;
      } else {
        const schemaLabel = {
          'spaceapi:compatible': 'SpaceAPI v14 compatible',
          'mom:card': 'SpaceAPI — full detail card',
          'mom:required': 'SpaceAPI — pin only (missing website / opening hours)',
        }[data.subset] || 'schema recognised';
        lines.push({ ok: true, text: schemaLabel });
        lines.push({ ok: true, text: `name: ${escHtml(data.name_found)}` });
        if (!data.coords_found) {
          lines.push({ ok: false, text: 'coordinates missing — add lat/lon under location or schema:geo' });
          blocking = true;
        } else {
          lines.push({ ok: true, text: `coordinates found (${escHtml(data.lat)}, ${escHtml(data.lon)})` });
        }
      }
    }

    out.innerHTML = lines.map((l, i) => {
      const icon = l.warn ? '⚠' : l.ok ? '✓' : '✗';
      const color = l.warn ? 'var(--yellow, #b8860b)' : l.ok ? 'var(--green)' : 'var(--accent)';
      return `<div class="check-line" style="--i:${i};animation-delay:calc(0.1s * var(--i));color:${color};">${icon} ${l.text}</div>`;
    }).join('');

    if (blocking) {
      out.innerHTML += '<div style="color:var(--muted);margin-top:6px;font-size:11px;">↩ Fix the issues above and try again.</div>';
      return;
    }

    const btn = el('button', { id: 'btn-confirm-register', class: 'btn btn-primary', style: 'margin-top:10px;' }, ['Confirm & register your space →']);
    out.appendChild(btn);

    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Registering…';
      let reg;
      // Stamp of the corpus we are looking at now, so the refetch below can tell
      // "the server rebuilt it" from "the server has not got to it yet".
      const baselineStamp = state.geojsonGeneratedAt;
      try {
        const resp = await fetch('/api/register-url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        });
        // Read as text first: nginx returns an HTML error page on 502/504, and
        // `resp.json()` would surface that as a JSON.parse complaint — the parser's
        // problem reported as the server's verdict.
        const raw = await resp.text();
        try {
          reg = JSON.parse(raw);
        } catch (_) {
          reg = null;
        }
        // An unreadable body means we do not know what happened server-side, and the
        // write may well have landed. Say exactly that rather than naming a status as
        // if it were a verdict — including on a 2xx, where "failed: HTTP 200" would be
        // the same lie in a new costume.
        if (!reg || typeof reg !== 'object') {
          if (resp.ok || resp.status >= 500) {
            throw new Error(`the server did not return a readable answer (HTTP ${resp.status}). Your space may still have been registered — reload the map before retrying.`);
          }
          throw new Error(`HTTP ${resp.status}`);
        }
        if (!resp.ok) throw new Error(reg.detail?.error || `HTTP ${resp.status}`);
      } catch (e) {
        btn.disabled = false;
        btn.textContent = 'Confirm & register your space →';
        out.appendChild(el('div', { style: { color: 'var(--accent)', marginTop: '6px' } }, [`✗ Registration failed: ${e.message}`]));
        return;
      }

      const spaceName = reg.space_name || 'Your space';
      // space_uri is "urn:mak:space/{slug}" — extract the slug as the local ID.
      // The server may return a URI whose slug differs from the one derived from the
      // submitted name (endpoint-dedup and claim-merge reuse the existing graph), so
      // trust the response over any local guess, and check the shape before using it
      // to navigate.
      const rawSpaceId = (reg.space_uri || '').split('/').pop() || '';
      const spaceId = /^[a-zA-Z0-9_-]{1,64}$/.test(rawSpaceId) ? rawSpaceId : null;
      const hasSpace = Boolean(spaceId);

      // Refresh map state — clear filters first so the new space is always visible
      state.filters.networks.clear();
      state.filters.countries.clear();
      state.filters.statuses.clear();
      state.filters.specialties.clear();
      // The server rematerializes spaces.geojson in a background task, so the first
      // refetch usually still holds the pre-registration corpus. Wait for a NEW
      // materialization stamp, not for the slug: a re-registration claims a space
      // that is already in the file, so a slug check would pass instantly against
      // stale data and report a flip that has not happened.
      // Backoff 1/2/4/8/16s ≈ 31s — the rematerialize is a whole-corpus rebuild.
      let corpusRebuilt = false;
      for (let attempt = 0; attempt < 6; attempt++) {
        if (attempt > 0) await new Promise((r) => setTimeout(r, 1000 * 2 ** (attempt - 1)));
        try {
          const geoResp = await fetch(`/data/spaces.geojson?t=${Date.now()}`);
          if (!geoResp.ok) continue;
          const geoJson = await geoResp.json();
          // A proxied error body parses as valid JSON and would empty the map.
          if (geoJson?.type !== 'FeatureCollection' || !Array.isArray(geoJson.features)) continue;
          const fresh = !baselineStamp || geoJson.generated_at !== baselineStamp;
          // Only pay for the re-ingest + chip rebuild when the payload actually
          // changed, so the user does not watch the filter bar flicker five times.
          if (!fresh && attempt > 0) continue;
          ingestGeoJSON(geoJson);
          if (state.selectedId && !state.spaces.find((s) => s.id === state.selectedId)) {
            state.selectedId = null;
          }
          buildFilterChips();
          refreshSpacesLayer();
          if (fresh) { corpusRebuilt = true; break; }
        } catch (_) { /* non-fatal — try again */ }
      }
      // Honest about what we actually observed: the registration is committed either
      // way (the server answered 200 before deferring the slow tail), but whether the
      // dot on the map reflects it yet is something we either saw or did not.
      const landed = corpusRebuilt && (!spaceId || state.spaces.some((s) => s.id === spaceId));

      // Build subset progress message
      const subset = reg.subset || 'none';
      const unlockMsg = reg.unlock_message;
      const nextUnlock = reg.next_unlock;
      const subsetBadge = subset !== 'none' ? `<span class="status-label" style="display:inline-block;margin-left:8px;">${escHtml(subset)}</span>` : '';

      let subsetSection = '';
      if (unlockMsg) {
        subsetSection = `
          <div style="margin-top:16px;padding:12px;background:var(--note-bg);border-radius:4px;">
            <div style="margin-bottom:8px;">Your data unlocks: <strong>${escHtml(unlockMsg)}</strong></div>
            ${nextUnlock ? `<div style="color:var(--muted);font-size:13px;">To unlock ${escHtml(reg.next_subset || 'full compatibility')}: ${escHtml(nextUnlock)}</div>` : ''}
            <div style="color:var(--muted);font-size:12px;margin-top:8px;">
              <a href="https://github.com/SpaceApi/schema" target="_blank" rel="noopener">See schema guide →</a>
            </div>
          </div>
        `;
      }

      // Two truths, told apart. `landed` = we saw the rebuilt corpus carry the space;
      // otherwise the write is committed but the map has not caught up, and claiming
      // a flip we did not observe is the same false verdict as the old parse error,
      // pointing the other way.
      const headline = landed
        ? `✓ ${escHtml(spaceName)} is live on the map!${subsetBadge}`
        : `✓ ${escHtml(spaceName)} is registered.${subsetBadge}`;
      const subline = landed
        ? 'Your pin has flipped from ⚪ to 🔵.'
        : 'The map is still rebuilding — your pin will appear within a minute. Reload if you want to watch for it.';
      $('.addurl-body').innerHTML = `
        <div style="text-align:center;padding:20px 0;">
          <div style="font-size:22px;margin-bottom:8px;">${headline}</div>
          <div style="color:var(--muted);margin-bottom:18px;">${subline}</div>
          ${subsetSection}
          ${landed ? '<div style="color:var(--muted);font-size:12px;margin-top:16px;">Opening your space profile…</div>' : ''}
        </div>`;
      // Only fly to the profile when the space is actually in state.spaces — otherwise
      // selectSpace would open on nothing.
      if (hasSpace && landed) {
        setTimeout(() => {
          closeDrawer('addurl');
          selectSpace(spaceId, { fly: true });
        }, unlockMsg ? 4000 : 2000);
      }
    });
  }

  function initAddUrl() {
    _addUrlOriginalHTML = $('.addurl-body').innerHTML;
    _wireAddUrlHandlers();
  }

  // ───────────────────────────── drawers / UI wiring
  function setDrawer(name) {
    // Detail & addurl share the right slot — close the other first
    const prev = state.openDrawer;
    if (prev && prev !== name) closeDrawer(prev);
    if (!name) { state.openDrawer = null; return; }
    state.openDrawer = name;
    const id = ({
      find: 'drawer-find', preset: 'drawer-preset',
      addurl: 'drawer-addurl', detail: 'drawer-detail', bot: 'bot-drawer'
    })[name];
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.add('open');
    node.setAttribute('aria-hidden', 'false');
    // Sync top-bar pressed state
    syncTopbar();
    // Focus handling
    const focusable = node.querySelector('input, button, [tabindex]');
    if (focusable && name !== 'detail') focusable.focus({ preventScroll: true });
    // Update preset code if opening preset
    if (name === 'preset') renderPresetPreview();
    // Reset addurl form when re-opening (clears post-confirmation screen)
    if (name === 'addurl') { _resetAddUrlForm(); }
  }
  function closeDrawer(name) {
    const id = ({
      find: 'drawer-find', preset: 'drawer-preset',
      addurl: 'drawer-addurl', detail: 'drawer-detail', bot: 'bot-drawer'
    })[name];
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.remove('open');
    node.setAttribute('aria-hidden', 'true');
    if (state.openDrawer === name) state.openDrawer = null;
    syncTopbar();
  }
  function toggleDrawer(name) {
    if (state.openDrawer === name) closeDrawer(name);
    else setDrawer(name);
  }
  function syncTopbar() {
    $('#btn-find').setAttribute('aria-pressed', state.openDrawer === 'find' ? 'true' : 'false');
    $('#btn-preset').setAttribute('aria-pressed', state.openDrawer === 'preset' ? 'true' : 'false');
    $('#btn-addurl').setAttribute('aria-pressed', state.openDrawer === 'addurl' ? 'true' : 'false');
    $('#btn-bot').setAttribute('aria-expanded', state.openDrawer === 'bot' ? 'true' : 'false');
    // When bot drawer is open, hide the FAB
    $('#btn-bot').style.display = state.openDrawer === 'bot' ? 'none' : 'flex';
  }

  function wireUI() {
    const logoEl = $('#logo-shortcut');
    if (logoEl) {
      const openMS = () => selectSpace('mother-sands', { fly: true });
      logoEl.addEventListener('click', openMS);
      logoEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openMS(); }
      });
    }
    $('#btn-find').addEventListener('click', () => toggleDrawer('find'));

    // Delegated result selection — uses pointerdown (not click) because the scroll container
    // causes slight movement on touchpad taps which suppresses the browser's click event.
    // preventDefault only fires on pointerup after no meaningful move, so touch-scroll still works.
    let _pdTarget = null, _pdX = 0, _pdY = 0;
    $('#results-list').addEventListener('pointerdown', (e) => {
      if (e.button !== 0 && e.pointerType !== 'touch') return;
      const btn = e.target.closest('.result[data-sid]');
      if (!btn) return;
      _pdTarget = btn; _pdX = e.clientX; _pdY = e.clientY;
    });
    $('#results-list').addEventListener('pointerup', (e) => {
      if (!_pdTarget) return;
      const dx = Math.abs(e.clientX - _pdX), dy = Math.abs(e.clientY - _pdY);
      const btn = _pdTarget;
      _pdTarget = null;
      if (dx > 8 || dy > 8) return; // scroll gesture — ignore
      e.preventDefault();
      selectSpace(btn.dataset.sid, { fly: true });
    });
    $('#results-list').addEventListener('pointercancel', () => { _pdTarget = null; });
$('#btn-preset').addEventListener('click', () => {
      // Toolbar entry = filter-preset builder; start clean (embedSpace path sets these).
      if (state.openDrawer !== 'preset') { state.embed.centerId = null; $('#preset-name').value = ''; }
      toggleDrawer('preset');
    });
    $('#btn-addurl').addEventListener('click', () => toggleDrawer('addurl'));
    $('#btn-bot').addEventListener('click', () => toggleDrawer('bot'));
    // Near me (AC5b)
    $('#btn-nearme').addEventListener('click', function nearMeClick() {
      if (!navigator.geolocation) {
        console.warn('[near-me] geolocation API unavailable');
        return;
      }
      const btn = $('#btn-nearme');
      const original = btn.innerHTML;
      btn.innerHTML = '<span aria-hidden="true">⏳</span> <span class="label">Locating…</span>';
      btn.disabled = true;

      function onSuccess(pos) {
        btn.innerHTML = original;
        btn.disabled = false;
        map.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 12 });
      }
      function onError(err) {
        btn.innerHTML = original;
        btn.disabled = false;
        if (err.code === 1) {
          console.warn('[near-me] geolocation permission denied');
        } else if (err.code === 3) {
          console.warn('[near-me] geolocation timeout (15s exceeded)');
        } else {
          console.warn('[near-me] geolocation error', err.code, err.message);
        }
      }

      // Use Permissions API first on browsers that support it (Android Chrome 88+)
      // This ensures the permission prompt fires in the same user-gesture tick.
      if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then(function(result) {
          console.log('[near-me] permission state:', result.state);
          // 'granted', 'prompt', or 'denied'
          if (result.state === 'denied') {
            onError({ code: 1, message: 'Permission denied' });
          } else if (result.state === 'prompt') {
            // State is 'prompt' — show dialog with getCurrentPosition
            navigator.geolocation.getCurrentPosition(onSuccess, onError,
              { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
          } else {
            // State is 'granted' — proceed directly
            navigator.geolocation.getCurrentPosition(onSuccess, onError,
              { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
          }
        }).catch(function() {
          // Permissions API failed — fall back to direct call
          navigator.geolocation.getCurrentPosition(onSuccess, onError,
            { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
        });
      } else {
        navigator.geolocation.getCurrentPosition(onSuccess, onError,
          { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
      }
    });
    $$('[data-close]').forEach((b) => b.addEventListener('click', () => closeDrawer(b.dataset.close)));

    // ESC: if Find is open and active → reset first; second press closes
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (state.openDrawer === 'find' && isFindActive()) {
          $('#btn-reset-filters').click();
          return;
        }
        if (state.openDrawer) { closeDrawer(state.openDrawer); return; }
      }
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        setDrawer('find');
      }
    });

    // Search
    const si = $('#search-input');
    si.addEventListener('input', () => {
      state.search = si.value;
      buildFilterChips();
      refreshSpacesLayer();
      debouncedFit(filteredSpaces());
    });

    $('#btn-reset-filters').addEventListener('click', () => {
      state.filters.networks.clear();
      state.filters.countries.clear();
      state.filters.statuses.clear();
      state.filters.specialties.clear();
      state.search = '';
      const searchInput = $('#search-input');
      searchInput.value = '';
      searchInput.dispatchEvent(new Event('input', { bubbles: true }));
      flyToOverview();
    });

    // Preset name → re-render code
    $('#preset-name').addEventListener('input', renderPresetPreview);
    // Copy buttons
    $$('[data-copy]').forEach((b) => b.addEventListener('click', async () => {
      const id = b.dataset.copy;
      const elem = $('#' + id + '-text');
      if (!elem) {
        console.warn(`[copy] element not found: ${id}-text`);
        return;
      }
      const txt = elem.textContent;
      const original = b.textContent;
      try {
        await navigator.clipboard.writeText(txt);
        b.textContent = 'copied!';
        setTimeout(() => b.textContent = original, 1200);
      } catch (e) {
        b.textContent = 'copy failed';
        setTimeout(() => b.textContent = original, 1200);
      }
    }));

    // Keep preset preview bbox fresh as map moves
    if (map && !map._presetPreviewListenerAdded) {
      map._presetPreviewListenerAdded = true;
      map.on('moveend', () => { if (state.openDrawer === 'preset') renderPresetPreview(); });
    }
  }


  // ───────────────────────────── DevTools probe (Story 5.0: GL renders the field of
  // light, so marker-vs-projection drift no longer exists). Dumps currently-rendered
  // spaces-point features for spot-checking ladder colours / counts.
  window.__driftProbe = () => {
    if (!map.getLayer('spaces-point')) { console.warn('spaces-point layer not ready'); return []; }
    const rows = map.queryRenderedFeatures({ layers: ['spaces-point'] })
      .map((f) => ({ id: f.properties.id, kind: f.properties.kind, name: f.properties.name }));
    console.table(rows);
    return rows;
  };
  window.__map = () => map;

  // ───────────────────────────── embed detection
  if (IS_EMBED) document.body.classList.add('embed-mode');

  // ───────────────────────────── boot
  (async function boot() {
    try {
      await loadData();
      // wait for maplibre
      if (typeof maplibregl === 'undefined') {
        await new Promise((r) => {
          const iv = setInterval(() => { if (typeof maplibregl !== 'undefined') { clearInterval(iv); r(); } }, 40);
        });
      }
      // Register PMTiles protocol — used when TILES_URL switches to self-hosted pmtiles:// in production
      if (typeof pmtiles !== 'undefined') {
        const protocol = new pmtiles.Protocol({ metadata: true });
        maplibregl.addProtocol('pmtiles', protocol.tile);
      }
      // Embed mode: slim render path. No chrome wiring, no preferences, no poller —
      // just map + markers + the deep-linked view. Keeps the host page lightweight.
      if (IS_EMBED) {
        initMap();
        applyUrlParams();
        // refreshSpacesLayer fires from initMap's ready(); applyUrlParams handles bbox/center/space.
        return;
      }

      initMap();
      applyUrlParams();
      buildFilterChips();
      initAddUrl();
      wireUI();
      // Sync search input value from URL-restored state
      if (state.search) $('#search-input').value = state.search;
      updateCounts();

      // Auto-refresh: poll heartbeat last-run timestamp every 60s.
      // When a new cycle completes, soft-reload GeoJSON without touching map pan/zoom.
      let _lastKnownRun = null;
      setInterval(async () => {
        try {
          const r = await fetch('/api/heartbeat/last-run');
          if (!r.ok) return;
          const { last_run } = await r.json();
          if (!last_run) return;
          if (_lastKnownRun === null) { _lastKnownRun = last_run; return; }
          if (last_run === _lastKnownRun) return;
          _lastKnownRun = last_run;
          const geo = await fetch(`/data/spaces.geojson?t=${Date.now()}`);
          if (!geo.ok) return;
          const geoJson = await geo.json();
          ingestGeoJSON(geoJson);
          buildFilterChips();
          refreshSpacesLayer();
          renderDetail();
          updateCounts();
        } catch (_) {}
      }, 60_000);
    } catch (e) {
      console.error(e);
      $('#loader').innerHTML = `<div class="hand" style="color: var(--accent)">Couldn't load seed data.</div><div class="mono">${e.message}</div>`;
    }
  })();
})();
