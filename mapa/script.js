/* ==========================================================================
   MOVIRIS · Mapa
   Área de interés (dibujada, coordenadas o zonas rápidas), rango de fechas,
   celdas de focos y descarga CSV.

   Estado compartido con Calendario y Dashboard:
     localStorage['moviris.aoi.v2'] = { south, north, west, east, from, to, conf }
   ========================================================================== */

(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const I18N = window.MovirisI18n;
  const t = (text, vars) => I18N.t(text, vars);
  const fmt = { format: (value) => I18N.number(value) };
  const STORE_KEY = 'moviris.aoi.v2';
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

  // Vista mundial por defecto. Los límites ±85° evitan los extremos de Mercator.
  const DEFAULT_AOI = { south: -85, north: 85, west: -180, east: 180 };
  const PRESETS = {
    mundo: DEFAULT_AOI,
    america_norte: { south: 7, north: 83, west: -170, east: -50 },
    america_central: { south: 6, north: 24, west: -118, east: -58 },
    america_sur: { south: -56, north: 13, west: -82, east: -34 },
    europa: { south: 34, north: 72, west: -25, east: 45 },
    africa: { south: -35, north: 38, west: -20, east: 55 },
    asia: { south: -11, north: 82, west: 25, east: 180 },
    oceania: { south: -48, north: 0, west: 110, east: 180 },
  };

  const STATE_COLORS = { critical: '#A94438', unusual: '#B58A2E', normal: '#637545' };
  // Rampa secuencial YlOrBr (ColorBrewer), apta para daltonismo
  const RAMP = ['#fed98e', '#fec44f', '#fe9929', '#d95f0e', '#993404'];

  const AOI_STYLE = {
    color: '#455230', weight: 2, dashArray: '6 4',
    fillColor: '#637545', fillOpacity: 0.06, interactive: false,
  };
  const PREVIEW_STYLE = { ...AOI_STYLE, dashArray: '3 3', fillOpacity: 0.12 };

  const state = { aoi: { ...DEFAULT_AOI }, from: '', to: '', conf: '0', color: 'state' };
  let meta = null;
  let lastData = null;
  let aoiRect = null;
  let cellsLayer = null;
  let controller = null;
  let viewTimer = null;
  let suppressViewReloadUntil = 0;

  // Dibujo del área: dos clics en esquinas opuestas
  let drawing = false;
  let corner = null;
  let preview = null;

  // -------------------------------------------------------------------------
  // Utilidades
  // -------------------------------------------------------------------------

  const round3 = (v) => Math.round(v * 1000) / 1000;

  function addDays(iso, days) {
    const d = new Date(`${iso}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  function setMsg(text, isError = false) {
    const el = $('msg');
    el.textContent = text || '';
    el.hidden = !text;
    el.classList.toggle('is-error', Boolean(text) && isError);
  }

  function setLoading(on) {
    $('loading').hidden = !on;
    $('btn-apply').disabled = on;
  }

  async function getJson(url, options) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Error ${res.status} al consultar los datos.`);
    return data;
  }

  // -------------------------------------------------------------------------
  // Estado inicial: URL, luego lo guardado, luego valores por defecto
  // -------------------------------------------------------------------------

  function readInitial() {
    const params = new URLSearchParams(window.location.search);
    let saved = {};
    try {
      saved = JSON.parse(window.localStorage.getItem(STORE_KEY) || '{}') || {};
    } catch (e) {
      saved = {};
    }
    const pick = (key) => (params.has(key) ? params.get(key) : saved[key]);

    const aoi = {};
    for (const key of ['south', 'north', 'west', 'east']) aoi[key] = parseFloat(pick(key));
    if (Object.values(aoi).every(Number.isFinite) && aoi.south < aoi.north && aoi.west < aoi.east) {
      state.aoi = aoi;
    }

    const from = pick('from');
    const to = pick('to');
    if (DATE_RE.test(from || '') && DATE_RE.test(to || '') && from <= to) {
      state.from = from;
      state.to = to;
    }
    const conf = String(pick('conf'));
    if (['0', '1', '2'].includes(conf)) state.conf = conf;
  }

  function persist() {
    const data = { ...state.aoi, from: state.from, to: state.to, conf: state.conf };
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(data));
    } catch (e) { /* almacenamiento no disponible */ }
    window.history.replaceState(null, '', `${window.location.pathname}?${new URLSearchParams(data)}`);
  }

  // -------------------------------------------------------------------------
  // Mapa
  // -------------------------------------------------------------------------

  const map = L.map('map', { preferCanvas: true, minZoom: 2 }).setView([20, 0], 2);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // Leaflet necesita recalcular su tamaño cuando cambia el layout responsive
  // (por ejemplo, al pasar de panel lateral a mapa arriba del panel).
  const mapWrap = document.querySelector('.map-wrap');
  let mapResizeTimer = null;

  function refreshMapSize() {
    window.clearTimeout(mapResizeTimer);
    mapResizeTimer = window.setTimeout(() => {
      map.invalidateSize({ pan: false });
    }, 120);
  }

  if ('ResizeObserver' in window && mapWrap) {
    new ResizeObserver(refreshMapSize).observe(mapWrap);
  } else {
    window.addEventListener('resize', refreshMapSize, { passive: true });
  }
  window.addEventListener('orientationchange', refreshMapSize, { passive: true });

  function setAoi(aoi, fit) {
    state.aoi = { ...aoi };
    for (const key of ['north', 'south', 'west', 'east']) $(key).value = round3(aoi[key]);
    const bounds = [[aoi.south, aoi.west], [aoi.north, aoi.east]];
    if (aoiRect) aoiRect.setBounds(bounds);
    else aoiRect = L.rectangle(bounds, AOI_STYLE).addTo(map);
    if (fit) {
      suppressViewReloadUntil = Date.now() + 900;
      map.fitBounds(bounds, { padding: [24, 24], animate: false });
    }
  }

  function readAoiInputs() {
    const aoi = {};
    for (const key of ['south', 'north', 'west', 'east']) aoi[key] = parseFloat($(key).value);
    return aoi;
  }

  // -------------------------------------------------------------------------
  // Dibujo del área
  // -------------------------------------------------------------------------

  function stopDrawing() {
    drawing = false;
    corner = null;
    if (preview) {
      map.removeLayer(preview);
      preview = null;
    }
    $('map').classList.remove('is-drawing');
    $('btn-draw').classList.remove('is-on');
    $('btn-draw').textContent = t('Dibujar área');
    $('draw-hint').hidden = true;
  }

  function startDrawing() {
    stopDrawing();
    drawing = true;
    map.closePopup();
    $('map').classList.add('is-drawing');
    $('btn-draw').classList.add('is-on');
    $('btn-draw').textContent = t('Cancelar dibujo');
    $('draw-hint').hidden = false;
  }

  map.on('click', (event) => {
    if (!drawing) return;
    if (!corner) {
      corner = event.latlng;
      preview = L.rectangle([corner, corner], PREVIEW_STYLE).addTo(map);
      return;
    }
    const a = corner;
    const b = event.latlng;
    stopDrawing();
    if (Math.abs(a.lat - b.lat) < 0.01 || Math.abs(a.lng - b.lng) < 0.01) {
      setMsg(t('El área es demasiado pequeña. Dibuja un rectángulo más grande.'), true);
      return;
    }
    setAoi({
      south: Math.min(a.lat, b.lat), north: Math.max(a.lat, b.lat),
      west: Math.min(a.lng, b.lng), east: Math.max(a.lng, b.lng),
    }, false);
    apply();
  });

  map.on('mousemove', (event) => {
    if (drawing && corner && preview) preview.setBounds([corner, event.latlng]);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && drawing) stopDrawing();
  });

  // -------------------------------------------------------------------------
  // Consulta y dibujo de celdas
  // -------------------------------------------------------------------------

  function readControls() {
    state.from = $('from').value;
    state.to = $('to').value;
    state.conf = $('conf').value;
    state.color = $('color-mode').value;
  }

  function validate() {
    const aoi = readAoiInputs();
    if (!Object.values(aoi).every(Number.isFinite)) return t('Completa los cuatro límites del área.');
    if (aoi.south >= aoi.north || aoi.west >= aoi.east) {
      return t('Área no válida: el sur debe ser menor que el norte y el oeste menor que el este.');
    }
    if (!DATE_RE.test($('from').value) || !DATE_RE.test($('to').value)) return t('Elige las dos fechas.');
    if ($('from').value > $('to').value) return t('La fecha inicial debe ser anterior a la final.');
    return '';
  }

  function bboxParams(bbox, grid) {
    const params = new URLSearchParams({
      south: bbox.south, north: bbox.north, west: bbox.west, east: bbox.east,
      start: state.from, end: state.to, conf: state.conf,
    });
    if (grid) params.set('grid', grid);
    return params;
  }

  function currentView() {
    const b = map.getBounds();
    const south = Math.max(state.aoi.south, b.getSouth());
    const north = Math.min(state.aoi.north, b.getNorth());
    const west = Math.max(state.aoi.west, b.getWest());
    const east = Math.min(state.aoi.east, b.getEast());
    if (south >= north || west >= east) return { ...state.aoi };
    return { south, north, west, east };
  }

  // Cuadrícula de la vista: gruesa de lejos, fina de cerca. El objetivo es
  // cubrir toda el área visible con <= 20.000 celdas agregadas.
  const GRID_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5];
  const ZOOM_GRID = {
    1: 1, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.25,
    6: 0.2, 7: 0.1, 8: 0.05, 9: 0.02, 10: 0.01,
  };

  function gridForView(bbox) {
    const latSpan = bbox.north - bbox.south;
    const lonSpan = bbox.east - bbox.west;
    const areaGrid = Math.sqrt((latSpan * lonSpan) / 20000) || 0.01;
    const zoom = Math.max(1, Math.min(10, Math.round(map.getZoom())));
    const base = ZOOM_GRID[zoom] || 0.01;
    const desired = Math.max(0.01, Math.min(base, areaGrid));
    return GRID_STEPS.find((step) => step >= desired) || GRID_STEPS[GRID_STEPS.length - 1];
  }

  function cellsQuery(bbox = currentView()) {
    return bboxParams(bbox, gridForView(bbox));
  }

  function csvQuery() {
    return bboxParams(state.aoi);
  }

  async function apply() {
    const problem = validate();
    if (problem) {
      setMsg(problem, true);
      return;
    }
    state.aoi = readAoiInputs();
    setAoi(state.aoi, false);
    readControls();
    window.clearTimeout(viewTimer);

    if (controller) controller.abort();
    controller = new AbortController();
    setMsg('');
    setLoading(true);
    try {
      const data = await getJson(`/api/mapa/cells?${cellsQuery()}`, { signal: controller.signal });
      lastData = data;
      render(data);
      persist();
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error(error);
      setMsg(t('No se pudieron cargar los datos.'), true);
    } finally {
      setLoading(false);
    }
  }

  async function refreshCells() {
    if (!state.from || !state.to || drawing) return;
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const data = await getJson(`/api/mapa/cells?${cellsQuery()}`, { signal: controller.signal });
      lastData = data;
      render(data);
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error(error);
      setMsg(t('No se pudieron cargar los datos.'), true);
    }
  }

  function scheduleViewRefresh() {
    if (drawing || Date.now() < suppressViewReloadUntil) return;
    window.clearTimeout(viewTimer);
    viewTimer = window.setTimeout(refreshCells, 280);
  }

  map.on('moveend zoomend', scheduleViewRefresh);

  function rangeLabel(from, to) {
    if (from === to) return `${from} ${t(from === 1 ? 'día' : 'días')}`;
    return `${from}–${to} ${t('días')}`;
  }

  function intensityScale(rows, idx) {
    const days = rows.map((r) => r[idx.days]).sort((a, b) => a - b);
    const quantiles = [0.2, 0.4, 0.6, 0.8].map((q) => days[Math.floor(q * (days.length - 1))]);
    const breaks = [...new Set(quantiles)];
    const n = breaks.length + 1;
    const colors = n === 1
      ? [RAMP[2]]
      : Array.from({ length: n }, (_, i) => RAMP[Math.round((i * (RAMP.length - 1)) / (n - 1))]);
    const classOf = (v) => {
      let i = 0;
      while (i < breaks.length && v > breaks[i]) i += 1;
      return i;
    };
    const labels = colors.map((_, i) => {
      if (n === 1) return `${days[0]} ${t(days[0] === 1 ? 'día' : 'días')} ${t('con focos')}`;
      if (i === 0) return rangeLabel(1, breaks[0]);
      if (i === n - 1) return t('más de {n} días', { n: breaks[n - 2] });
      return rangeLabel(breaks[i - 1] + 1, breaks[i]);
    });
    return { colors, classOf, labels };
  }

  function renderLegend(items) {
    $('legend').innerHTML = items
      .map((it) => `<li><span class="swatch" style="background:${it.color}"></span>${it.label}</li>`)
      .join('');
  }

  function render(data) {
    const idx = Object.fromEntries(data.columns.map((name, i) => [name, i]));
    const rows = data.cells;
    const s = data.summary;

    if (cellsLayer) map.removeLayer(cellsLayer);
    cellsLayer = null;

    $('k-cells').textContent = fmt.format(s.cells);
    $('k-days').textContent = fmt.format(s.cell_days);
    $('k-det').textContent = fmt.format(s.detections);
    $('k-crit').textContent = fmt.format(s.critical_days);
    $('k-unus').textContent = fmt.format(s.unusual_days);

    const trunc = $('trunc');
    const grid = Number(data.grid) || 0.01;
    const aggregated = grid > 0.011;
    trunc.hidden = !data.truncated && !aggregated;
    if (data.truncated) {
      trunc.textContent = t('Se dibujan las {shown} celdas más activas de {total}. Acerca el mapa para ver más detalle o reduce el área y las fechas.', {
        shown: fmt.format(data.shown),
        total: fmt.format(s.cells),
      });
    } else if (aggregated) {
      trunc.textContent = t('Vista agregada a {grid}° para mostrar toda el área. Acerca el mapa para ver más detalle.', {
        grid: I18N.number(grid, { maximumFractionDigits: 2 }),
      });
    }

    if (!rows.length) {
      renderLegend([]);
      setMsg(t('No hay focos en esta área y rango de fechas.'));
      return;
    }

    let colorOf;
    if (state.color === 'intensity') {
      const scale = intensityScale(rows, idx);
      colorOf = (r) => scale.colors[scale.classOf(r[idx.days])];
      renderLegend(scale.colors.map((color, i) => ({ color, label: scale.labels[i] })));
    } else {
      colorOf = (r) => {
        if (r[idx.critical_days] > 0) return STATE_COLORS.critical;
        if (r[idx.unusual_days] > 0) return STATE_COLORS.unusual;
        return STATE_COLORS.normal;
      };
      renderLegend([
        { color: STATE_COLORS.critical, label: t('Con días críticos') },
        { color: STATE_COLORS.unusual, label: t('Con días inusuales (sin críticos)') },
        { color: STATE_COLORS.normal, label: t('Solo días normales') },
      ]);
    }

    const markers = rows.map((r) => {
      const marker = L.circleMarker([r[idx.lat], r[idx.lon]], {
        radius: Math.max(3, Math.min(8, 2 + Math.sqrt(r[idx.days]))),
        fillColor: colorOf(r), fillOpacity: 0.8,
        color: '#F7F7EC', weight: 0.5, opacity: 0.7,
      });
      marker.on('click', () => {
        if (!drawing) openPopup(r, idx);
      });
      return marker;
    });
    cellsLayer = L.layerGroup(markers).addTo(map);
  }

  function openPopup(r, idx) {
    const frp = r[idx.frp_max];
    L.popup()
      .setLatLng([r[idx.lat], r[idx.lon]])
      .setContent(
        `<strong>${t('Celda')} ${I18N.coordinate(r[idx.lat])}, ${I18N.coordinate(r[idx.lon])}</strong>` +
        `${t('Días con focos')}: ${fmt.format(r[idx.days])}<br>` +
        `${t('Detecciones')}: ${fmt.format(r[idx.detections])}<br>` +
        `${t('FRP máximo')}: ${frp === null ? '—' : `${I18N.decimal(frp)} MW`}<br>` +
        `${t('Días críticos')}: ${fmt.format(r[idx.critical_days])}<br>` +
        `${t('Días inusuales')}: ${fmt.format(r[idx.unusual_days])}<br>` +
        `${t('Último foco')}: ${I18N.date(r[idx.last_date])}`
      )
      .openOn(map);
  }

  // -------------------------------------------------------------------------
  // Descarga CSV
  // -------------------------------------------------------------------------

  async function downloadCsv() {
    const problem = validate();
    if (problem) {
      setMsg(problem, true);
      return;
    }
    state.aoi = readAoiInputs();
    readControls();
    const button = $('btn-csv');
    button.disabled = true;
    setMsg(t('Preparando el CSV…'));
    try {
      const res = await fetch(`/api/mapa/csv?${csvQuery()}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Error ${res.status} al generar el CSV.`);
      }
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `moviris_cell_days_${state.from}_${state.to}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      setMsg('');
    } catch (error) {
      console.error(error);
      setMsg(t('No se pudo generar el CSV.'), true);
    } finally {
      button.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // Eventos
  // -------------------------------------------------------------------------

  $('btn-draw').addEventListener('click', () => (drawing ? stopDrawing() : startDrawing()));
  $('btn-apply').addEventListener('click', apply);
  $('btn-csv').addEventListener('click', downloadCsv);

  $('btn-clear').addEventListener('click', () => {
    stopDrawing();
    setAoi(DEFAULT_AOI, true);
    apply();
  });

  $('preset').addEventListener('change', (event) => {
    const preset = PRESETS[event.target.value];
    event.target.value = '';
    if (!preset) return;
    stopDrawing();
    setAoi(preset, true);
    apply();
  });

  for (const key of ['north', 'south', 'west', 'east']) {
    $(key).addEventListener('change', () => {
      const aoi = readAoiInputs();
      if (Object.values(aoi).every(Number.isFinite) && aoi.south < aoi.north && aoi.west < aoi.east) {
        setAoi(aoi, true);
        setMsg('');
      } else {
        setMsg(t('Área no válida: el sur debe ser menor que el norte y el oeste menor que el este.'), true);
      }
    });
  }

  document.querySelectorAll('[data-range]').forEach((chip) => {
    chip.addEventListener('click', () => {
      if (!meta) return;
      const range = chip.dataset.range;
      const from = range === 'all' ? meta.min_date : addDays(meta.max_date, -Number(range));
      $('from').value = from < meta.min_date ? meta.min_date : from;
      $('to').value = meta.max_date;
      apply();
    });
  });

  $('color-mode').addEventListener('change', () => {
    state.color = $('color-mode').value;
    if (lastData) render(lastData);
  });

  // -------------------------------------------------------------------------
  // Arranque
  // -------------------------------------------------------------------------

  async function init() {
    readInitial();
    setAoi(state.aoi, true);
    $('conf').value = state.conf;
    $('color-mode').value = state.color;

    try {
      meta = await getJson('/api/mapa/meta');
    } catch (error) {
      console.error(error);
      setMsg(t('No se pudieron cargar los datos.'), true);
      return;
    }

    for (const id of ['from', 'to']) {
      $(id).min = meta.min_date;
      $(id).max = meta.max_date;
    }
    if (!state.from) {
      state.to = meta.max_date;
      const from = addDays(meta.max_date, -90);
      state.from = from < meta.min_date ? meta.min_date : from;
    }
    $('from').value = state.from;
    $('to').value = state.to;
    apply();
  }

  init();
})();
