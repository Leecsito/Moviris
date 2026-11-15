/* ==========================================================================
   MOVIRIS · Explain
   Una sola llamada a /api/explain por clic. Sin historial ni chat.
   ========================================================================== */

(() => {
  'use strict';

  const t = (text, vars) => window.MovirisI18n.t(text, vars);
  let overlay = null;
  let dialog = null;
  let titleEl = null;
  let bodyEl = null;
  let closeBtn = null;
  let controller = null;

  function ensureModal() {
    if (overlay) return;

    overlay = document.createElement('div');
    overlay.className = 'explain-overlay';
    overlay.hidden = true;

    dialog = document.createElement('div');
    dialog.className = 'explain-dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'explain-title');

    const head = document.createElement('div');
    head.className = 'explain-head';

    titleEl = document.createElement('h2');
    titleEl.id = 'explain-title';
    titleEl.className = 'explain-title';

    closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'explain-close';
    closeBtn.setAttribute('aria-label', t('Cerrar'));
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', close);

    bodyEl = document.createElement('div');
    bodyEl.className = 'explain-body';

    head.append(titleEl, closeBtn);
    dialog.append(head, bodyEl);
    overlay.append(dialog);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) close();
    });
    document.body.appendChild(overlay);

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && overlay && !overlay.hidden) close();
    });
  }

  function renderTitle(payload) {
    const base = t('Explicar este gráfico');
    const title = payload && payload.title ? ` · ${payload.title}` : '';
    titleEl.textContent = base + title;
  }

  function setBody(text, isError = false) {
    bodyEl.textContent = text || '';
    bodyEl.classList.toggle('is-error', Boolean(isError));
  }

  function close() {
    if (controller) {
      controller.abort();
      controller = null;
    }
    if (overlay) overlay.hidden = true;
  }

  async function open(payload) {
    ensureModal();
    close();
    renderTitle(payload || {});
    setBody(t('Cargando...'));
    overlay.hidden = false;

    controller = new AbortController();
    const signal = controller.signal;

    try {
      const response = await fetch('/api/explain', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept-Language': window.MovirisI18n.lang,
        },
        body: JSON.stringify({ ...payload, lang: payload.lang || window.MovirisI18n.lang }),
        signal,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || t('No se pudo generar la explicación. Inténtalo de nuevo.'));
      }
      setBody(data.text || t('No se pudo generar la explicación. Inténtalo de nuevo.'));
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error(error);
      setBody(error.message || t('No se pudo generar la explicación. Inténtalo de nuevo.'), true);
    } finally {
      if (controller && controller.signal === signal) controller = null;
    }
  }

  window.MovirisExplain = { open, close };
})();
