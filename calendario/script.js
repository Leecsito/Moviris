/* ==========================================================================
   MOVIRIS · Calendario
   Matriz año × mes con rampa de color, mes actual frente a la mediana,
   períodos críticos y detalle diario del mes elegido.

   Lee el área de interés de la URL o de localStorage['moviris.aoi'], que
   guarda la pestaña Mapa.
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
  const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

  // pos = posición de la métrica dentro de los valores devueltos por la API
  const METRICS = {
    cell_days: { pos: 0, label: 'celdas-día activas' },
    detections: { pos: 1, label: 'detecciones' },
    critical: { pos: 2, label: 'celdas-día críticas' },
    unusual: { pos: 3, label: 'celdas-día inusuales' },
  };

  // Rampa secuencial YlOrBr (ColorBrewer), apta para daltonismo
  const RAMP = ['#fed98e', '#fec44f', '#fe9929', '#d95f0e', '#993404'];

  const state = {
    aoi: { ...DEFAULT_AOI },
    usingDefault: true,
    conf: '0',
    metric: 'cell_days',
    data: null,
    sel: null,        // { y, m }
    monthData: null,
  };
  let monthToken = 0;

  // -------------------------------------------------------------------------
  // Utilidades
  // -------------------------------------------------------------------------

  const pad = (n) => String(n).padStart(2, '0');
  const round3 = (v) => fmtCoord.format(v);

  function compact(n) {
    if (n >= 10000) return `${Math.round(n / 1000)}k`;
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace('.', ',')}k`;
    return String(n);
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

  const metricValue = (row) => row[2 + METRICS[state.metric].pos];
  const metricLabel = () => METRICS[state.metric].label;

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
      `Lat ${round3(a.south)} a ${round3(a.north)} · Lon ${round3(a.west)} a ${round3(a.east)}` +
      (state.usingDefault ? ' · Zona por defecto (Ecuador continental)' : '');
  }

  // -------------------------------------------------------------------------
  // Escala de color por cuantiles
  // -------------------------------------------------------------------------

  function makeScale(values) {
    const v = values.filter((x) => x > 0).sort((a, b) => a - b);
    if (!v.length) return null;
    const quantiles = [0.2, 0.4, 0.6, 0.8].map((q) => v[Math.floor(q * (v.length - 1))]);
    const breaks = [...new Set(quantiles)];
    const n = breaks.length + 1;
    const rampIndex = (c) => (n === 1 ? 2 : Math.round((c * (RAMP.length - 1)) / (n - 1)));
    const classOf = (x) => {
      let i = 0;
      while (i < breaks.length && x > breaks[i]) i += 1;
      return i;
    };
    const range = (a, b) => (a === b ? fmt.format(a) : `${fmt.format(a)}–${fmt.format(b)}`);
    const labels = Array.from({ length: n }, (_, i) => {
      if (n === 1) return fmt.format(v[0]);
      if (i === 0) return range(1, breaks[0]);
      if (i === n - 1) return `más de ${fmt.format(breaks[n - 2])}`;
      return range(breaks[i - 1] + 1, breaks[i]);
    });
    return { n, classOf, rampIndex, labels };
  }

  function paint(scale, value) {
    if (value <= 0 || !scale) return { cls: 'is-zero', style: '' };
    const idx = scale.rampIndex(scale.classOf(value));
    const fg = idx >= 3 ? '#F7F7EC' : '#2A3520';
    return { cls: '', style: `background:${RAMP[idx]};color:${fg}` };
  }

  // -------------------------------------------------------------------------
  // Cobertura de cada mes
  // -------------------------------------------------------------------------

  function monthInfo(y, m) {
    const d = state.data;
    const start = `${y}-${pad(m)}-01`;
    const end = `${y}-${pad(m)}-${pad(new Date(Date.UTC(y, m, 0)).getUTCDate())}`;
    const covered = start <= d.max_date && end >= d.min_date;
    const partial = covered && (start < d.min_date || end > d.max_date);
    return { start, end, covered, partial };
  }

  // -------------------------------------------------------------------------
  // Matriz año × mes
  // -------------------------------------------------------------------------

  function renderMatrix() {
    const d = state.data;
    const byKey = new Map(d.months.map((r) => [`${r[0]}-${r[1]}`, r]));
    const minYear = Number(d.min_date.slice(0, 4));
    const maxYear = Number(d.max_date.slice(0, 4));
    const years = [];
    for (let y = maxYear; y >= minYear; y -= 1) years.push(y);

    const valueAt = (y, m) => (byKey.has(`${y}-${m}`) ? metricValue(byKey.get(`${y}-${m}`)) : 0);

    // Escala con los meses completos; si no hay ninguno, con todos
    const all = [];
    const complete = [];
    for (const y of years) {
      for (let m = 1; m <= 12; m += 1) {
        const info = monthInfo(y, m);
        if (!info.covered) continue;
        all.push(valueAt(y, m));
        if (!info.partial) complete.push(valueAt(y, m));
      }
    }
    const scale = makeScale(complete.some((x) => x > 0) ? complete : all);

    const head = MONTHS_SHORT.map((m) => `<th scope="col">${m}</th>`).join('');
    const rows = years.map((y) => {
      let total = 0;
      const cells = [];
      for (let m = 1; m <= 12; m += 1) {
        const info = monthInfo(y, m);
        if (!info.covered) {
          cells.push('<td><button class="cell is-empty" type="button" disabled tabindex="-1" aria-hidden="true"></button></td>');
          continue;
        }
        const v = valueAt(y, m);
        total += v;
        const p = paint(scale, v);
        const selected = state.sel && state.sel.y === y && state.sel.m === m;
        const classes = ['cell', p.cls, info.partial ? 'is-partial' : '', selected ? 'is-selected' : '']
          .filter(Boolean).join(' ');
        const text = `${MONTHS[m - 1]} ${y}: ${fmt.format(v)} ${metricLabel()}${info.partial ? ' (mes incompleto)' : ''}`;
        cells.push(
          `<td><button class="${classes}" style="${p.style}" type="button" data-y="${y}" data-m="${m}" ` +
          `title="${text}" aria-label="${text}" aria-pressed="${selected ? 'true' : 'false'}">${compact(v)}</button></td>`
        );
      }
      return `<tr><th class="year" scope="row">${y}</th>${cells.join('')}<td class="total" title="${fmt.format(total)}">${compact(total)}</td></tr>`;
    });

    $('matrix-wrap').innerHTML =
      `<table class="matrix"><thead><tr><th class="year" scope="col">Año</th>${head}<th scope="col">Total</th></tr></thead>` +
      `<tbody>${rows.join('')}</tbody></table>`;

    renderLegend(scale);
    renderHighlights(years, valueAt);
  }

  function renderLegend(scale) {
    const items = ['<li><span class="swatch" style="background:#F7F7EC"></span>Sin focos</li>'];
    if (scale) {
      for (let i = 0; i < scale.n; i += 1) {
        items.push(`<li><span class="swatch" style="background:${RAMP[scale.rampIndex(i)]}"></span>${scale.labels[i]}</li>`);
      }
    }
    $('legend').innerHTML = items.join('');
  }

  // -------------------------------------------------------------------------
  // Resumen: año, mes del año y mes más intenso
  // -------------------------------------------------------------------------

  function renderHighlights(years, valueAt) {
    const label = metricLabel();
    const fullYears = years.filter((y) => {
      for (let m = 1; m <= 12; m += 1) {
        const info = monthInfo(y, m);
        if (!info.covered || info.partial) return false;
      }
      return true;
    });
    const pool = fullYears.length ? fullYears : years;

    const yearTotal = (y) => {
      let t = 0;
      for (let m = 1; m <= 12; m += 1) if (monthInfo(y, m).covered) t += valueAt(y, m);
      return t;
    };

    let bestYear = null;
    for (const y of pool) {
      const t = yearTotal(y);
      if (!bestYear || t > bestYear.t) bestYear = { y, t };
    }

    const perMonth = Array.from({ length: 12 }, () => 0);
    for (const y of pool) {
      for (let m = 1; m <= 12; m += 1) if (monthInfo(y, m).covered) perMonth[m - 1] += valueAt(y, m);
    }
    let bestMonth = 0;
    perMonth.forEach((t, i) => {
      if (t > perMonth[bestMonth]) bestMonth = i;
    });

    let peak = null;
    for (const y of years) {
      for (let m = 1; m <= 12; m += 1) {
        const info = monthInfo(y, m);
        if (!info.covered || info.partial) continue;
        const v = valueAt(y, m);
        if (!peak || v > peak.v) peak = { y, m, v };
      }
    }

    if (!bestYear || bestYear.t === 0) {
      $('hl-year').textContent = '—';
      $('hl-year-sub').textContent = 'Sin actividad en esta área';
      $('hl-month').textContent = '—';
      $('hl-month-sub').textContent = '';
      $('hl-peak').textContent = '—';
      $('hl-peak-sub').textContent = '';
      return;
    }

    $('hl-year').textContent = String(bestYear.y);
    $('hl-year-sub').textContent = `${fmt.format(bestYear.t)} ${label}`;
    $('hl-month').textContent = MONTHS[bestMonth];
    $('hl-month-sub').textContent = `${fmt.format(perMonth[bestMonth])} ${label} en ${pool.length} ${pool.length === 1 ? 'año' : 'años'}`;
    if (peak) {
      $('hl-peak').textContent = `${MONTHS[peak.m - 1]} ${peak.y}`;
      $('hl-peak-sub').textContent = `${fmt.format(peak.v)} ${label}`;
    }
  }

  // -------------------------------------------------------------------------
  // Mes actual frente a la mediana
  // -------------------------------------------------------------------------

  function renderCompare() {
    const cur = state.data.current;
    const pos = METRICS[state.metric].pos;
    const value = cur.values[pos];
    const median = cur.median ? cur.median[pos] : null;
    const span = cur.day === 1 ? 'día 1' : `días 1–${cur.day}`;
    let html = `<p class="compare-title">${MONTHS[cur.month - 1]} ${cur.year}, ${span}</p>`;

    if (median === null) {
      html += '<p class="compare-sub">Aún no hay años anteriores para comparar.</p>';
      $('compare').innerHTML = html;
      return;
    }

    const first = cur.years[0];
    const last = cur.years[cur.years.length - 1];
    html += `<p class="compare-sub">Mediana del mismo tramo en ${cur.years.length} ${cur.years.length === 1 ? 'año' : 'años'} (${first}–${last}). Medida: ${metricLabel()}.</p>`;

    const max = Math.max(value, median, 1);
    const bar = (name, v, extra) =>
      `<div class="bar-row"><span>${name}</span><div class="bar-track"><span class="bar-fill ${extra}" style="width:${(v / max) * 100}%"></span></div><strong>${fmtDec.format(v)}</strong></div>`;
    html += bar('Este año', value, '') + bar('Mediana', median, 'is-median');

    let delta;
    if (median > 0) {
      const pct = Math.round(((value - median) / median) * 100);
      delta = pct === 0 ? 'Igual que la mediana.' : `${pct > 0 ? '+' : '−'}${Math.abs(pct)} % frente a la mediana.`;
    } else {
      delta = value > 0 ? 'La mediana es 0: no hay referencia para comparar.' : 'Sin actividad, igual que la mediana.';
    }
    html += `<p class="delta">${delta}</p>`;
    $('compare').innerHTML = html;
  }

  // -------------------------------------------------------------------------
  // Períodos críticos
  // -------------------------------------------------------------------------

  function renderWeeks() {
    const weeks = state.data.weeks;
    if (!weeks.length) {
      $('weeks').innerHTML = '<li><span>No hay semanas críticas en esta área.</span></li>';
      return;
    }
    $('weeks').innerHTML = weeks.map((w) =>
      `<li><strong>${w[0]} · semana ${w[1]}</strong>` +
      `<span>${fmt.format(w[4])} celdas-día críticas · ${fmt.format(w[5])} inusuales · ${fmt.format(w[2])} activas</span></li>`
    ).join('');
  }

  // -------------------------------------------------------------------------
  // Detalle diario
  // -------------------------------------------------------------------------

  async function loadMonth() {
    const { y, m } = state.sel;
    const token = ++monthToken;
    try {
      const data = await getJson(`/api/calendario/month?${areaQuery({ year: y, month: m })}`);
      if (token !== monthToken) return;
      state.monthData = data;
      renderMonth();
    } catch (error) {
      if (token === monthToken) setMsg(error.message, true);
    }
  }

  function renderMonth() {
    const { y, m } = state.sel;
    const info = monthInfo(y, m);
    const d = state.data;
    const byDate = new Map(state.monthData.days.map((r) => [r[0], r]));
    const pos = METRICS[state.metric].pos;
    const scale = makeScale(state.monthData.days.map((r) => r[1 + pos]));

    $('detail-title').textContent = `${MONTHS[m - 1]} ${y}`;
    const to = info.end < d.max_date ? info.end : d.max_date;
    const link = new URLSearchParams({
      south: state.aoi.south, north: state.aoi.north, west: state.aoi.west, east: state.aoi.east,
      from: info.start < d.min_date ? d.min_date : info.start, to, conf: state.conf,
    });
    $('map-link').href = `/mapa/?${link}`;

    const lead = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7;
    const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate();
    const parts = WEEKDAYS.map((w) => `<div class="dow">${w}</div>`);
    for (let i = 0; i < lead; i += 1) parts.push('<div class="day is-blank"></div>');

    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = `${y}-${pad(m)}-${pad(day)}`;
      if (date > d.max_date || date < d.min_date) {
        parts.push(`<div class="day is-future" title="Sin datos"><span class="day-num">${day}</span><span class="day-val">·</span></div>`);
        continue;
      }
      const row = byDate.get(date) || [date, 0, 0, 0, 0];
      const v = row[1 + pos];
      const p = paint(scale, v);
      const text = `${day} de ${MONTHS[m - 1].toLowerCase()}: ${fmt.format(row[1])} celdas-día activas, ` +
        `${fmt.format(row[2])} detecciones, ${fmt.format(row[3])} críticas, ${fmt.format(row[4])} inusuales`;
      const dot = row[3] > 0 ? '<span class="day-dot" aria-hidden="true"></span>' : '';
      parts.push(
        `<div class="day ${p.cls}" style="${p.style}" title="${text}" aria-label="${text}">` +
        `${dot}<span class="day-num">${day}</span><span class="day-val">${compact(v)}</span></div>`
      );
    }
    $('month').innerHTML = parts.join('');
  }

  // -------------------------------------------------------------------------
  // Carga y eventos
  // -------------------------------------------------------------------------

  function renderAll() {
    renderMatrix();
    renderCompare();
    renderWeeks();
  }

  async function load() {
    setMsg('');
    try {
      state.data = await getJson(`/api/calendario/matrix?${areaQuery()}`);
    } catch (error) {
      setMsg(error.message || 'No se pudieron consultar los datos.', true);
      return;
    }
    const d = state.data;
    if (!state.sel) state.sel = { y: Number(d.max_date.slice(0, 4)), m: Number(d.max_date.slice(5, 7)) };
    renderAll();
    await loadMonth();
  }

  $('matrix-wrap').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-y]');
    if (!button) return;
    state.sel = { y: Number(button.dataset.y), m: Number(button.dataset.m) };
    renderMatrix();
    loadMonth();
  });

  $('metric').addEventListener('change', (event) => {
    state.metric = event.target.value;
    if (!state.data) return;
    renderAll();
    if (state.monthData) renderMonth();
  });

  $('conf').addEventListener('change', (event) => {
    state.conf = event.target.value;
    saveConf();
    load();
  });

  $('btn-csv').addEventListener('click', async () => {
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
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `moviris_celdas_${start}_${end}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      setMsg('');
    } catch (error) {
      setMsg(error.message || 'No se pudo generar el CSV.', true);
    } finally {
      button.disabled = false;
    }
  });

  readInitial();
  $('conf').value = state.conf;
  renderAoi();
  load();
})();
