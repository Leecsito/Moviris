/* ==========================================================================
   MOVIRIS · Dashboard
   Indicadores, actividad por año, anomalías, estacionalidad y comparación
   entre detecciones y celdas-día (armonización de sensores).

   Lee el área de interés de la URL o de localStorage['moviris.aoi'], que
   guarda la pestaña Mapa. Gráficos con Chart.js (CDN).
   ========================================================================== */

(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const fmt = new Intl.NumberFormat('es-EC');
  const fmtDec = new Intl.NumberFormat('es-EC', { maximumFractionDigits: 1 });
  const fmtCoord = new Intl.NumberFormat('es-EC', { maximumFractionDigits: 3 });
  const STORE_KEY = 'moviris.aoi';

  const DEFAULT_AOI = { south: -5.01, north: 1.45, west: -81.1, east: -75.2 };
  const MONTHS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
    'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  const MONTHS_SHORT = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

  const POS = { cell_days: 0, detections: 1, critical: 2, unusual: 3 };
  const LABELS = {
    cell_days: 'Celdas-día activas',
    detections: 'Detecciones',
    critical: 'Celdas-día críticas',
    unusual: 'Celdas-día inusuales',
  };

  const C = {
    ink: '#2A3520', dark: '#455230', primary: '#637545', sage: '#9BA685',
    secondary: '#6B7557', ember: '#A94438', card: '#F7F7EC',
    grid: 'rgba(155, 166, 133, 0.3)',
  };
  const MONO = 'ui-monospace, "SFMono-Regular", "Cascadia Mono", Menlo, Consolas, monospace';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = {
    aoi: { ...DEFAULT_AOI },
    usingDefault: true,
    conf: '0',
    metric: 'cell_days',
    selYear: null,
    data: null,
  };
  const charts = {};

  // -------------------------------------------------------------------------
  // Utilidades
  // -------------------------------------------------------------------------

  const pad = (n) => String(n).padStart(2, '0');
  const sum = (arr) => arr.reduce((a, b) => a + b, 0);
  const mean = (arr) => (arr.length ? sum(arr) / arr.length : null);

  function median(arr) {
    if (!arr.length) return null;
    const s = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  function setMsg(text, isError = false) {
    const el = $('msg');
    el.textContent = text || '';
    el.hidden = !text;
    el.classList.toggle('is-error', Boolean(text) && isError);
  }

  async function getJson(url) {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Error ${res.status} al consultar los datos.`);
    return data;
  }

  function areaQuery(extra = {}) {
    const a = state.aoi;
    return new URLSearchParams({
      south: a.south, north: a.north, west: a.west, east: a.east, conf: state.conf, ...extra,
    });
  }

  function download(blob, name) {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  }

  // -------------------------------------------------------------------------
  // Área de interés: URL, luego lo guardado por el mapa, luego por defecto
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
      state.usingDefault = false;
    }
    const conf = String(pick('conf'));
    if (['0', '1', '2'].includes(conf)) state.conf = conf;
  }

  function saveConf() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORE_KEY) || '{}') || {};
      window.localStorage.setItem(STORE_KEY, JSON.stringify({ ...saved, ...state.aoi, conf: state.conf }));
    } catch (e) { /* almacenamiento no disponible */ }
  }

  function renderAoi() {
    const a = state.aoi;
    $('aoi-text').textContent =
      `Lat ${fmtCoord.format(a.south)} a ${fmtCoord.format(a.north)} · Lon ${fmtCoord.format(a.west)} a ${fmtCoord.format(a.east)}` +
      (state.usingDefault ? ' · Zona por defecto (Ecuador continental)' : '');
  }

  // -------------------------------------------------------------------------
  // Modelo de datos: años, meses y cobertura
  // -------------------------------------------------------------------------

  function buildModel() {
    const d = state.data;
    const minY = Number(d.min_date.slice(0, 4));
    const maxY = Number(d.max_date.slice(0, 4));
    const years = [];
    for (let y = minY; y <= maxY; y += 1) years.push(y);

    const monthValues = new Map(d.months.map((r) => [`${r[0]}-${r[1]}`, r.slice(2)]));
    const val = (y, m, p) => (monthValues.get(`${y}-${m}`) || [0, 0, 0, 0])[p];
    const yearSum = (y, p) => {
      let t = 0;
      for (let m = 1; m <= 12; m += 1) t += val(y, m, p);
      return t;
    };
    const isFull = (y) => `${y}-01-01` >= d.min_date && `${y}-12-31` <= d.max_date;
    const monthCovered = (y, m) => {
      const start = `${y}-${pad(m)}-01`;
      const end = `${y}-${pad(m)}-${pad(new Date(Date.UTC(y, m, 0)).getUTCDate())}`;
      return start <= d.max_date && end >= d.min_date;
    };
    return { years, full: years.filter(isFull), val, yearSum, isFull, monthCovered, minY, maxY };
  }

  // -------------------------------------------------------------------------
  // Gráficos
  // -------------------------------------------------------------------------

  const hasChart = () => typeof window.Chart === 'function';

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: reduceMotion ? false : { duration: 300 },
      plugins: {
        legend: { labels: { color: C.ink, boxWidth: 12, font: { family: MONO, size: 11 } } },
        tooltip: { titleFont: { family: MONO }, bodyFont: { family: MONO } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: C.secondary, font: { family: MONO, size: 10 } } },
        y: { beginAtZero: true, grid: { color: C.grid }, ticks: { color: C.secondary, font: { family: MONO, size: 10 } } },
      },
    };
  }

  function setEmpty(canvasId, message) {
    const box = $(canvasId).parentElement;
    box.classList.toggle('is-empty', Boolean(message));
    if (message) box.dataset.empty = message;
  }

  function draw(key, canvasId, config) {
    if (charts[key]) {
      charts[key].destroy();
      delete charts[key];
    }
    if (!config) return;
    setEmpty(canvasId, '');
    charts[key] = new window.Chart($(canvasId), config);
  }

  function clearChart(key, canvasId, message) {
    if (charts[key]) {
      charts[key].destroy();
      delete charts[key];
    }
    setEmpty(canvasId, message);
  }

  // 01 · Actividad por año
  function renderYears(m) {
    const p = POS[state.metric];
    const values = m.years.map((y) => m.yearSum(y, p));
    const fullValues = m.full.map((y) => m.yearSum(y, p));
    const avg = mean(fullValues);

    const config = {
      type: 'bar',
      data: {
        labels: m.years,
        datasets: [
          {
            label: LABELS[state.metric],
            data: values,
            backgroundColor: m.years.map((y) => (m.isFull(y) ? C.dark : C.sage)),
            order: 2,
          },
          ...(avg === null ? [] : [{
            type: 'line',
            label: 'Media de años completos',
            data: m.years.map(() => avg),
            borderColor: C.ember,
            borderDash: [6, 4],
            borderWidth: 2,
            pointRadius: 0,
            order: 1,
          }]),
        ],
      },
      options: baseOptions(),
    };
    if (hasChart()) draw('years', 'c-years', config);

    let best = null;
    const pool = m.full.length ? m.full : m.years;
    for (const y of pool) {
      const v = m.yearSum(y, p);
      if (!best || v > best.v) best = { y, v };
    }
    $('cap-years').textContent = avg === null
      ? 'Aún no hay años completos para calcular la media. Las barras claras son años incompletos.'
      : `Media de ${m.full.length} años completos: ${fmtDec.format(avg)}. Año más activo: ${best.y} (${fmt.format(best.v)}). Las barras claras son años incompletos.`;
  }

  // 02 · Anomalía anual
  function renderAnomaly(m) {
    const p = POS[state.metric];
    const fullValues = m.full.map((y) => m.yearSum(y, p));
    const avg = mean(fullValues);

    if (m.full.length < 3 || !avg) {
      clearChart('anomaly', 'c-anomaly', 'Se necesitan al menos 3 años completos con actividad.');
      $('cap-anomaly').textContent = '';
      return;
    }
    const pct = fullValues.map((v) => ((v - avg) / avg) * 100);
    if (hasChart()) {
      const options = baseOptions();
      options.scales.y.beginAtZero = false;
      options.scales.y.ticks.callback = (v) => `${v} %`;
      options.plugins.legend.display = false;
      options.plugins.tooltip.callbacks = { label: (ctx) => `${fmtDec.format(ctx.parsed.y)} % frente a la media` };
      draw('anomaly', 'c-anomaly', {
        type: 'bar',
        data: {
          labels: m.full,
          datasets: [{ label: 'Anomalía (%)', data: pct, backgroundColor: pct.map((v) => (v >= 0 ? C.ember : C.primary)) }],
        },
        options,
      });
    }
    const above = pct.filter((v) => v > 0).length;
    let top = 0;
    pct.forEach((v, i) => {
      if (Math.abs(v) > Math.abs(pct[top])) top = i;
    });
    $('cap-anomaly').textContent =
      `${above} de ${m.full.length} años quedaron por encima de la media. Mayor desviación: ${m.full[top]} (${pct[top] > 0 ? '+' : '−'}${fmtDec.format(Math.abs(pct[top]))} %).`;
  }

  // 03 · Estacionalidad
  function fillYearSelect(m) {
    const select = $('year-sel');
    const years = [...m.years].reverse();
    if (!years.includes(state.selYear)) state.selYear = years[0];
    select.innerHTML = years.map((y) => `<option value="${y}">${y}</option>`).join('');
    select.value = String(state.selYear);
  }

  function renderSeason(m) {
    const p = POS[state.metric];
    const base = m.full.length ? m.full : m.years;
    const med = Array.from({ length: 12 }, (_, i) => median(base.map((y) => m.val(y, i + 1, p))));
    const current = Array.from({ length: 12 }, (_, i) =>
      (m.monthCovered(state.selYear, i + 1) ? m.val(state.selYear, i + 1, p) : null));

    if (hasChart()) {
      draw('season', 'c-season', {
        type: 'bar',
        data: {
          labels: MONTHS_SHORT,
          datasets: [
            { label: `Mediana (${base.length} ${base.length === 1 ? 'año' : 'años'})`, data: med, backgroundColor: C.sage, order: 2 },
            {
              type: 'line', label: String(state.selYear), data: current, borderColor: C.ink,
              backgroundColor: C.ink, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: false, order: 1,
            },
          ],
        },
        options: baseOptions(),
      });
    }

    let top = 0;
    med.forEach((v, i) => {
      if (v > med[top]) top = i;
    });
    $('cap-season').textContent = med[top] > 0
      ? `Mes más activo según la mediana: ${MONTHS[top]} (${fmtDec.format(med[top])}). La mediana usa ${m.full.length ? 'años completos' : 'todos los años disponibles'}.`
      : 'Sin actividad en esta área.';
  }

  // 04 · Detecciones frente a celdas-día
  function renderIndex(m) {
    const det = m.full.map((y) => m.yearSum(y, POS.detections));
    const cd = m.full.map((y) => m.yearSum(y, POS.cell_days));
    const detAvg = mean(det);
    const cdAvg = mean(cd);

    if (m.full.length < 2 || !detAvg || !cdAvg) {
      clearChart('index', 'c-index', 'Se necesitan al menos 2 años completos con actividad.');
      $('cap-index').textContent = '';
      return;
    }
    if (hasChart()) {
      const options = baseOptions();
      options.scales.y.ticks.callback = (v) => `${v}`;
      draw('index', 'c-index', {
        type: 'line',
        data: {
          labels: m.full,
          datasets: [
            { label: 'Detecciones', data: det.map((v) => (v / detAvg) * 100), borderColor: C.ember, backgroundColor: C.ember, borderWidth: 2, pointRadius: 3, tension: 0.2 },
            { label: 'Celdas-día activas', data: cd.map((v) => (v / cdAvg) * 100), borderColor: C.dark, backgroundColor: C.dark, borderWidth: 2, pointRadius: 3, tension: 0.2 },
          ],
        },
        options,
      });
    }
    $('cap-index').textContent =
      'Índice 100 = media de los años completos. Las detecciones aumentan cuando entran más satélites; las celdas-día cuentan cada celda una sola vez por día. ' +
      'Si las líneas se separan, el cambio viene de los sensores y no del fuego.';
  }

  // 05 · Cobertura por familia de sensores
  function renderCoverage() {
    const rows = state.data.coverage;
    if (!rows.length) {
      clearChart('coverage', 'c-coverage', 'Sin datos de sensores en esta área.');
      $('cap-coverage').textContent = '';
      return;
    }
    if (hasChart()) {
      const options = baseOptions();
      options.scales.x.stacked = true;
      options.scales.y.stacked = true;
      draw('coverage', 'c-coverage', {
        type: 'bar',
        data: {
          labels: rows.map((r) => r[0]),
          datasets: [
            { label: 'Solo MODIS', data: rows.map((r) => r[1]), backgroundColor: C.sage },
            { label: 'MODIS y VIIRS', data: rows.map((r) => r[2]), backgroundColor: C.primary },
            { label: 'Solo VIIRS', data: rows.map((r) => r[3]), backgroundColor: C.ink },
          ],
        },
        options,
      });
    }
    $('cap-coverage').textContent =
      'Celdas-día activas del área según qué familia de sensores las detectó. Muestra el paso de MODIS a VIIRS y el período en que ambos observan.';
  }

  // -------------------------------------------------------------------------
  // Indicadores y render general
  // -------------------------------------------------------------------------

  function renderKpis() {
    const t = state.data.totals;
    $('k-cells').textContent = fmt.format(t.cells);
    $('k-days').textContent = fmt.format(t.cell_days);
    $('k-det').textContent = fmt.format(t.detections);
    $('k-crit').textContent = fmt.format(t.critical);
    $('k-unus').textContent = fmt.format(t.unusual);
  }

  function renderAll() {
    const m = buildModel();
    renderKpis();
    fillYearSelect(m);
    renderYears(m);
    renderAnomaly(m);
    renderSeason(m);
    renderIndex(m);
    renderCoverage();
  }

  async function load() {
    setMsg('');
    try {
      state.data = await getJson(`/api/dashboard/summary?${areaQuery()}`);
    } catch (error) {
      setMsg(error.message || 'No se pudieron consultar los datos.', true);
      return;
    }
    if (!hasChart()) {
      setMsg('No se pudo cargar la librería de gráficos (Chart.js). Revisa tu conexión a internet.', true);
    }
    renderAll();
  }

  // -------------------------------------------------------------------------
  // Descargas
  // -------------------------------------------------------------------------

  async function downloadCells() {
    if (!state.data) return;
    const button = $('btn-csv');
    const { min_date: start, max_date: end } = state.data;
    button.disabled = true;
    setMsg('Preparando el CSV…');
    try {
      const res = await fetch(`/api/mapa/csv?${areaQuery({ start, end })}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Error ${res.status} al generar el CSV.`);
      }
      download(await res.blob(), `moviris_celdas_${start}_${end}.csv`);
      setMsg('');
    } catch (error) {
      setMsg(error.message || 'No se pudo generar el CSV.', true);
    } finally {
      button.disabled = false;
    }
  }

  function downloadSummary() {
    if (!state.data) return;
    const m = buildModel();
    const cells = new Map(state.data.year_cells.map((r) => [r[0], r[1]]));
    const cdAvg = mean(m.full.map((y) => m.yearSum(y, POS.cell_days)));
    const lines = ['anio,anio_completo,celdas_dia_activas,detecciones,celdas_dia_criticas,celdas_dia_inusuales,celdas_con_focos,anomalia_celdas_dia_pct'];
    for (const y of m.years) {
      const cd = m.yearSum(y, POS.cell_days);
      const anomaly = m.isFull(y) && cdAvg ? (((cd - cdAvg) / cdAvg) * 100).toFixed(1) : '';
      lines.push([
        y, m.isFull(y) ? 'si' : 'no', cd, m.yearSum(y, POS.detections), m.yearSum(y, POS.critical),
        m.yearSum(y, POS.unusual), cells.get(y) || 0, anomaly,
      ].join(','));
    }
    download(new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' }), 'moviris_resumen_anual.csv');
  }

  function downloadPng(key) {
    const chart = charts[key];
    if (!chart) {
      setMsg('Este gráfico no tiene datos para descargar.', true);
      return;
    }
    const link = document.createElement('a');
    link.href = chart.toBase64Image('image/png', 1);
    link.download = `moviris_${key}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  // -------------------------------------------------------------------------
  // Eventos y arranque
  // -------------------------------------------------------------------------

  // Fondo de las imágenes PNG descargadas
  if (hasChart()) {
    window.Chart.register({
      id: 'moviris-bg',
      beforeDraw(chart) {
        const ctx = chart.canvas.getContext('2d');
        ctx.save();
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = C.card;
        ctx.fillRect(0, 0, chart.width, chart.height);
        ctx.restore();
      },
    });
  }

  $('metric').addEventListener('change', (event) => {
    state.metric = event.target.value;
    if (state.data) renderAll();
  });

  $('conf').addEventListener('change', (event) => {
    state.conf = event.target.value;
    saveConf();
    load();
  });

  $('year-sel').addEventListener('change', (event) => {
    state.selYear = Number(event.target.value);
    if (state.data) renderSeason(buildModel());
  });

  $('btn-csv').addEventListener('click', downloadCells);
  $('btn-summary').addEventListener('click', downloadSummary);
  document.querySelectorAll('.btn-png').forEach((button) => {
    button.addEventListener('click', () => downloadPng(button.dataset.chart));
  });

  readInitial();
  $('conf').value = state.conf;
  renderAoi();
  load();
})();
