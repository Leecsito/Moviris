/* ==========================================================================
   MOVIRIS · ETL de focos de calor
   Subida de CSV, ejecución del ETL y resumen. Sin estadísticas, mapas ni
   parámetros: esa información pertenece a la aplicación principal.
   ========================================================================== */

'use strict';

const API = {
  upload: '/api/upload',
  uploadDelete: (uploadId) => `/api/uploads/${encodeURIComponent(uploadId)}`,
  run: '/api/etl/run',
  status: '/api/etl/status',
  health: '/api/health',
};

const STEPS = [
  {
    key: 'extract',
    stages: ['Descubriendo archivos', 'Analizando fuentes', 'Fuentes analizadas'],
  },
  {
    key: 'transform',
    stages: ['Agregando celdas-día', 'Agregación completa'],
  },
  {
    key: 'baseline',
    stages: ['Construyendo línea base', 'Evaluando anomalías', 'Anomalías evaluadas'],
  },
  {
    key: 'status',
    stages: [
      'Detectando fuentes no vegetales',
      'Escribiendo staging',
      'Staging listo',
    ],
  },
  {
    key: 'load',
    stages: ['Sincronizando Turso', 'Sincronizado', 'Completado'],
  },
];

const state = {
  files: [],
  uploading: false,
  deleting: false,
  running: false,
  jobId: null,
  pollTimer: null,
  pollFailures: 0,
  mode: 'local',
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const numberFmt = new Intl.NumberFormat('es-EC');
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ESCAPES[char]);

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

function setText(selector, value) {
  const element = $(selector);
  if (!element) return;
  element.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? numberFmt.format(number) : '—';
}

function formatSize(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB'];
  let size = value / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(1)} ${units[index]}`;
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const total = Math.max(0, Math.round(Number(seconds)));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes < 60) return `${minutes} min ${rest} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

function formatCsvNames(names) {
  const shown = names.slice(0, 3).join(', ');
  return names.length > 3 ? `${shown} +${names.length - 3} más` : shown;
}

function makeKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatApiError(error) {
  if (!error) return 'Error desconocido.';
  const parts = [error.message, error.detail, error.hint].filter(Boolean);
  if (Array.isArray(error.payload?.rejected)) {
    parts.push(...error.payload.rejected.slice(0, 3));
  }
  return Array.from(new Set(parts)).join(' · ');
}

async function api(path, options = {}) {
  const response = await fetch(path, { cache: 'no-store', ...options });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }
  if (!response.ok) {
    const error = new Error(data?.error || `Error HTTP ${response.status}`);
    error.status = response.status;
    error.detail = data?.detail;
    error.hint = data?.hint;
    error.payload = data;
    throw error;
  }
  return data;
}

function setUploadMessage(message, type = '') {
  const element = $('#uploadMessage');
  if (!element) return;
  element.textContent = message || '';
  element.classList.toggle('is-error', type === 'error');
  element.classList.toggle('is-success', type === 'success');
}

// ---------------------------------------------------------------------------
// Estado de conexión
// ---------------------------------------------------------------------------

function setConnection(mode, text, title) {
  const element = $('#connection');
  if (!element) return;
  element.dataset.state = mode;
  element.title = title || text;
  setText('#connectionText', text);
}

async function loadHealth() {
  try {
    const data = await api(API.health);
    const mode = data?.mode || data?.database?.mode || 'local';
    state.mode = mode;

    if (mode === 'local') {
      const ok = data?.database?.ok !== false;
      setConnection(
        'local',
        'Modo local',
        ok
          ? 'Turso desactivado (TURSO_ENABLED=false). El resultado queda en el staging local.'
          : 'Modo local. Aún no hay un staging disponible; ejecuta el ETL.'
      );
      setText('#footerStatus', 'Modo local');
      return;
    }

    const database = data?.database || {};
    if (database.ok) {
      const latency =
        database.latency_ms !== null && database.latency_ms !== undefined
          ? ` · ${Math.round(database.latency_ms)} ms`
          : '';
      setConnection('ok', 'Turso conectado', `Host: ${database.host || '—'}${latency}`);
      setText('#footerStatus', 'Turso conectado');
    } else {
      setConnection(
        'error',
        'Turso sin conexión',
        database.error || 'No se pudo conectar con Turso.'
      );
      setText('#footerStatus', 'Turso sin conexión');
    }
  } catch (error) {
    setConnection('error', 'Sin conexión', 'No se pudo consultar el estado del servidor.');
    setText('#footerStatus', 'Sin conexión');
  }
}

// ---------------------------------------------------------------------------
// Lista de archivos
// ---------------------------------------------------------------------------

function renderFiles() {
  const list = $('#fileList');
  const empty = $('#emptyFiles');
  const count = $('#fileCount');
  if (!list) return;

  if (!state.files.length) {
    list.innerHTML = '';
    empty?.classList.remove('is-hidden');
    if (count) count.textContent = '0 archivos';
    return;
  }

  empty?.classList.add('is-hidden');
  if (count) {
    count.textContent = `${state.files.length} archivo${state.files.length === 1 ? '' : 's'}`;
  }

  list.innerHTML = state.files
    .map((entry) => {
      const kind = entry.kind === 'zip' ? 'ZIP' : 'CSV';
      const meta = [entry.sizeLabel || formatSize(entry.size)];
      if (entry.kind === 'zip') {
        meta.push(`${entry.batchCount || entry.csvNames.length || 0} CSV`);
      } else {
        meta.push(entry.nrt ? 'NRT' : 'Archivo');
      }
      const names =
        entry.kind === 'zip' && entry.csvNames.length
          ? `<span class="file-meta">${esc(formatCsvNames(entry.csvNames))}</span>`
          : '';
      const error = entry.error
        ? `<span class="file-meta is-error">${esc(entry.error)}</span>`
        : '';
      const statusLabel =
        entry.status === 'uploading' ? 'Subiendo…' : entry.status === 'error' ? 'Error' : 'Listo';
      const statusClass =
        entry.status === 'ready' ? 'is-ready' : entry.status === 'error' ? 'is-error' : '';
      const disabled =
        state.running || state.uploading || state.deleting || entry.status === 'uploading';
      return `
        <li class="file-item">
          <span class="file-kind">${kind}</span>
          <div class="file-info">
            <span class="file-name" title="${esc(entry.name)}">${esc(entry.name)}</span>
            <span class="file-meta">${esc(meta.join(' · '))}</span>
            ${names}
            ${error}
          </div>
          <span class="file-status ${statusClass}">${statusLabel}</span>
          <button class="remove-button" type="button" data-key="${esc(
            entry.key
          )}" ${disabled ? 'disabled' : ''} aria-label="Quitar ${esc(entry.name)}">Quitar</button>
        </li>`;
    })
    .join('');
}

function updateRunButton() {
  const ready = state.files.filter(
    (entry) => entry.status === 'ready' && entry.uploadId
  ).length;
  const button = $('#runBtn');
  if (button) {
    button.disabled = state.running || state.uploading || state.deleting || ready === 0;
    button.textContent = state.running ? 'Ejecutando…' : 'Ejecutar ETL';
  }
  const dropzone = $('#dropzone');
  if (dropzone) {
    dropzone.classList.toggle('is-uploading', state.running || state.uploading);
  }
}

async function uploadOne(entry) {
  const form = new FormData();
  form.append('files', entry.file, entry.name);
  try {
    const data = await api(API.upload, { method: 'POST', body: form });
    const batch = data?.batch;
    if (!batch) throw new Error('El servidor no devolvió el lote de archivos.');
    entry.uploadId = batch.id || data.upload_id || null;
    entry.status = 'ready';
    entry.sizeLabel = batch.size_label || entry.sizeLabel;
    entry.batchCount = Number(batch.file_count) || 1;
    entry.csvNames = Array.isArray(batch.files) ? batch.files.map((file) => file.name) : [];
    entry.nrt =
      entry.csvNames.length > 0 &&
      Array.isArray(batch.files) &&
      batch.files.every((file) => file.kind === 'nrt');
    entry.error = '';
    if (Array.isArray(data.rejected) && data.rejected.length) {
      entry.error = `${data.rejected.length} archivo(s) descartado(s): ${data.rejected[0]}`;
    }
  } catch (error) {
    entry.status = 'error';
    entry.uploadId = null;
    entry.error = formatApiError(error);
  }
  renderFiles();
}

async function uploadFiles(selected) {
  if (state.uploading || state.running) return;
  const files = Array.from(selected || []);
  if (!files.length) return;

  const valid = files.filter((file) => /\.(csv|zip)$/i.test(file.name));
  if (valid.length !== files.length) {
    setUploadMessage('Solo se aceptan archivos .csv o .zip.', 'error');
  }

  const entries = [];
  for (const file of valid) {
    const duplicate = state.files.some(
      (entry) => entry.name === file.name && entry.size === file.size
    );
    if (duplicate) {
      setUploadMessage(`“${file.name}” ya está en la lista.`, 'error');
      continue;
    }
    const entry = {
      key: makeKey(),
      file,
      name: file.name,
      size: file.size,
      kind: /\.zip$/i.test(file.name) ? 'zip' : 'csv',
      status: 'uploading',
      uploadId: null,
      sizeLabel: formatSize(file.size),
      batchCount: 0,
      csvNames: [],
      nrt: false,
      error: '',
    };
    state.files.push(entry);
    entries.push(entry);
  }

  if (!entries.length) {
    renderFiles();
    return;
  }

  state.uploading = true;
  renderFiles();
  updateRunButton();

  let index = 0;
  for (const entry of entries) {
    index += 1;
    setUploadMessage(`Subiendo ${index} de ${entries.length}: ${entry.name}`, '');
    await uploadOne(entry);
  }

  state.uploading = false;
  renderFiles();
  updateRunButton();

  const ready = entries.filter((entry) => entry.status === 'ready').length;
  const failed = entries.filter((entry) => entry.status === 'error').length;
  const notes = entries.filter((entry) => entry.status === 'ready' && entry.error);
  if (failed) {
    setUploadMessage(
      `${ready} listo(s), ${failed} con error. Revisa el detalle en la lista.`,
      'error'
    );
  } else if (notes.length) {
    setUploadMessage(`${ready} listo(s). ${notes[0].error}`, 'error');
  } else {
    setUploadMessage(`${ready} archivo(s) listos para procesar.`, 'success');
  }
}

async function removeFile(key) {
  if (state.running || state.uploading || state.deleting) return;
  const entry = state.files.find((item) => item.key === key);
  if (!entry) return;

  if (!entry.uploadId) {
    state.files = state.files.filter((item) => item.key !== key);
    setUploadMessage('Archivo quitado de la lista.', '');
    renderFiles();
    updateRunButton();
    return;
  }

  state.deleting = true;
  renderFiles();
  updateRunButton();
  try {
    await api(API.uploadDelete(entry.uploadId), { method: 'DELETE' });
    state.files = state.files.filter((item) => item.key !== key);
    setUploadMessage('Archivo eliminado.', 'success');
  } catch (error) {
    if (error.status === 404) {
      state.files = state.files.filter((item) => item.key !== key);
      setUploadMessage('El archivo ya no estaba en el servidor; se quitó de la lista.', '');
    } else {
      setUploadMessage(formatApiError(error), 'error');
    }
  } finally {
    state.deleting = false;
    renderFiles();
    updateRunButton();
  }
}

// ---------------------------------------------------------------------------
// Progreso y ejecución
// ---------------------------------------------------------------------------

function currentStepIndex(job, percent) {
  const stage = String(job.stage || '');
  const found = STEPS.findIndex((step) => step.stages.includes(stage));
  if (found >= 0) return found;
  if (percent < 20) return 0;
  if (percent < 45) return 1;
  if (percent < 65) return 2;
  if (percent < 82) return 3;
  return 4;
}

function updateSteps(job, percent) {
  const current = currentStepIndex(job, percent);
  const done = job.status === 'done';
  const failed = job.status === 'error';
  const loadSkipped =
    done && job.summary && job.summary.pushed === false;

  $$('#steps li').forEach((item, index) => {
    item.classList.remove('is-active', 'is-done', 'is-error', 'is-skipped');
    item.title = '';
    if (failed) {
      if (index < current) item.classList.add('is-done');
      else if (index === current) item.classList.add('is-error');
      return;
    }
    if (done) {
      if (loadSkipped && index === STEPS.length - 1) {
        item.classList.add('is-skipped');
        item.title = 'Turso está desactivado: el resultado quedó en el staging local.';
      } else {
        item.classList.add('is-done');
      }
      const label = item.querySelector('span:last-child');
      if (label && index === STEPS.length - 1) {
        label.textContent = loadSkipped ? 'Load (omitido)' : 'Load';
      }
      return;
    }
    if (index < current) item.classList.add('is-done');
    else if (index === current) item.classList.add('is-active');
  });
}

function renderJob(job) {
  const percent = Math.max(0, Math.min(100, Number(job.percent) || 0));
  setText('#stageLabel', job.stage || 'Procesando…');
  setText('#percentLabel', `${Math.round(percent)}%`);
  setText('#stageMessage', job.message || '');

  const fill = $('#progressFill');
  if (fill) fill.style.width = `${percent}%`;
  const track = $('#progressTrack');
  if (track) track.setAttribute('aria-valuenow', String(Math.round(percent)));

  updateSteps(job, percent);
  if (job.status === 'error') {
    showError(job.error || 'El proceso terminó con un error.');
  }
}

function resetProgress() {
  setText('#stageLabel', 'Iniciando');
  setText('#percentLabel', '0%');
  setText('#stageMessage', '');
  const fill = $('#progressFill');
  if (fill) fill.style.width = '0%';
  $('#progressTrack')?.setAttribute('aria-valuenow', '0');
  $$('#steps li').forEach((item) => {
    item.classList.remove('is-active', 'is-done', 'is-error', 'is-skipped');
    item.title = '';
  });
  const loadLabel = $('#steps li[data-step="load"] span:last-child');
  if (loadLabel) loadLabel.textContent = 'Load';
}

function showProgress(visible) {
  $('#progressPanel')?.classList.toggle('is-hidden', !visible);
}

function showSummary(job) {
  const summary = job.summary || {};
  setText('#sumRead', formatNumber(summary.detections));
  setText('#sumDaily', formatNumber(summary.daily_rows));
  setText('#sumBaseline', formatNumber(summary.baseline_rows));
  setText('#sumMask', formatNumber(summary.mask_rows));
  setText('#summaryTime', formatDuration(job.elapsed_seconds));

  const note = $('#summaryNote');
  if (note) {
    if (summary.pushed) {
      note.textContent = 'Datos cargados en Turso.';
    } else if (summary.mode === 'local' || state.mode === 'local') {
      note.textContent =
        'Datos guardados en el staging local. Turso está desactivado (TURSO_ENABLED=false).';
    } else {
      note.textContent = 'Datos guardados en el staging local. No se sincronizó con Turso.';
    }
  }
  $('#summaryPanel')?.classList.remove('is-hidden');
}

function hideSummary() {
  $('#summaryPanel')?.classList.add('is-hidden');
}

function errorHint(message) {
  const text = String(message || '').toLowerCase();
  if (
    text.includes('turso') ||
    text.includes('libsql') ||
    text.includes('token') ||
    text.includes('auth')
  ) {
    return 'Revisa TURSO_DATABASE_URL y TURSO_AUTH_TOKEN en .env. Para trabajar sin Turso, deja TURSO_ENABLED=false.';
  }
  if (
    text.includes('columna') ||
    text.includes('latitude') ||
    text.includes('longitude') ||
    text.includes('acq_date')
  ) {
    return 'Cada CSV debe incluir las columnas latitude, longitude y acq_date.';
  }
  if (text.includes('staging')) {
    return 'No se encontró el staging local. Vuelve a ejecutar el ETL.';
  }
  return '';
}

function showError(message) {
  const text = message || 'Error desconocido.';
  setText('#errorText', text);
  const hint = errorHint(text);
  const hintElement = $('#errorHint');
  if (hintElement) {
    hintElement.textContent = hint;
    hintElement.classList.toggle('is-hidden', !hint);
  }
  $('#errorBox')?.classList.remove('is-hidden');
  hideSummary();
}

function hideError() {
  $('#errorBox')?.classList.add('is-hidden');
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  state.pollFailures = 0;
  pollJob();
  state.pollTimer = window.setInterval(pollJob, 1000);
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const data = await api(`${API.status}?job_id=${encodeURIComponent(state.jobId)}`);
    state.pollFailures = 0;
    const job = data?.job;
    if (!job) throw new Error('El servidor no encontró el trabajo.');

    renderJob(job);

    if (job.status !== 'running') {
      stopPolling();
      state.running = false;
      renderFiles();
      updateRunButton();
      if (job.status === 'done') {
        showSummary(job);
      } else {
        showError(job.error || 'El proceso terminó con un error.');
      }
      await loadHealth();
    }
  } catch (error) {
    state.pollFailures += 1;
    if (state.pollFailures >= 5) {
      stopPolling();
      state.running = false;
      renderFiles();
      updateRunButton();
      showError('Se perdió la conexión con el servidor. Recarga la página.');
    }
  }
}

async function runETL() {
  if (state.running) return;
  const ready = state.files.filter(
    (entry) => entry.status === 'ready' && entry.uploadId
  );
  if (!ready.length) {
    setUploadMessage('Sube al menos un archivo válido antes de ejecutar el ETL.', 'error');
    return;
  }

  state.running = true;
  state.jobId = null;
  stopPolling();
  hideError();
  hideSummary();
  setUploadMessage('');
  resetProgress();
  showProgress(true);
  renderFiles();
  updateRunButton();

  try {
    const data = await api(API.run, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        upload_ids: ready.map((entry) => entry.uploadId),
        include_nrt: true,
        exclude_current_year: true,
        replace: true,
        push: true,
      }),
    });
    if (!data?.job?.id) throw new Error('El servidor no devolvió el trabajo.');
    state.jobId = data.job.id;
    renderJob(data.job);
    startPolling();
  } catch (error) {
    state.running = false;
    renderFiles();
    updateRunButton();
    showError(formatApiError(error));
  }
}

async function restoreRunningJob() {
  try {
    const data = await api(API.status);
    const job = data?.job;
    if (job && job.kind === 'etl' && job.status === 'running') {
      state.jobId = job.id;
      state.running = true;
      showProgress(true);
      renderJob(job);
      renderFiles();
      updateRunButton();
      startPolling();
    }
  } catch {
    /* Si no hay un trabajo previo, no hay nada que restaurar. */
  }
}

// ---------------------------------------------------------------------------
// Eventos e inicio
// ---------------------------------------------------------------------------

function bindEvents() {
  const dropzone = $('#dropzone');
  const fileInput = $('#fileInput');
  if (dropzone && fileInput) {
    dropzone.addEventListener('click', (event) => {
      if (event.target.closest('button')) return;
      if (state.running || state.uploading) return;
      fileInput.click();
    });
    dropzone.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      if (state.running || state.uploading) return;
      fileInput.click();
    });
    $('#browseBtn')?.addEventListener('click', (event) => {
      event.stopPropagation();
      if (state.running || state.uploading) return;
      fileInput.click();
    });
    fileInput.addEventListener('change', () => {
      const files = Array.from(fileInput.files || []);
      fileInput.value = '';
      uploadFiles(files);
    });

    ['dragenter', 'dragover'].forEach((name) => {
      dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!state.running && !state.uploading) dropzone.classList.add('is-dragover');
      });
    });
    ['dragleave', 'drop'].forEach((name) => {
      dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (name === 'dragleave' && dropzone.contains(event.relatedTarget)) return;
        dropzone.classList.remove('is-dragover');
      });
    });
    dropzone.addEventListener('drop', (event) => {
      if (state.running || state.uploading) return;
      uploadFiles(event.dataTransfer?.files);
    });
  }

  $('#fileList')?.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-key]');
    if (button) removeFile(button.dataset.key);
  });

  $('#runBtn')?.addEventListener('click', runETL);
}

document.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  renderFiles();
  updateRunButton();
  loadHealth();
  restoreRunningJob();
});
