/* ==========================================================================
   MOVIRIS · Header (componente compartido)
   Inserta /header/index.html en <div id="site-header"></div> y marca la
   pestaña de la página actual. No llama a la API.
   ========================================================================== */

(() => {
  'use strict';

  const mount = document.getElementById('site-header');
  if (!mount) return;

  const normalize = (path) =>
    path.replace(/index\.html$/, '').replace(/\/+$/, '') || '/';

  function markCurrent() {
    const here = normalize(window.location.pathname);
    const tabs = mount.querySelectorAll('.hd-tab');
    let current = null;

    tabs.forEach((tab) => {
      const target = normalize(new URL(tab.href, window.location.origin).pathname);
      if (target === here) {
        tab.setAttribute('aria-current', 'page');
        current = tab;
      } else {
        tab.removeAttribute('aria-current');
      }
    });

    // En móvil, centra la pestaña activa dentro de la fila con scroll
    const nav = mount.querySelector('.hd-nav');
    if (nav && current && nav.scrollWidth > nav.clientWidth) {
      nav.scrollLeft = current.offsetLeft - (nav.clientWidth - current.offsetWidth) / 2;
    }
  }

  fetch('/header/index.html')
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.text();
    })
    .then((html) => {
      mount.innerHTML = html;
      markCurrent();
    })
    .catch(() => {
      // Respaldo mínimo para no dejar la página sin navegación
      mount.innerHTML =
        '<div class="hd-inner"><a class="hd-brand" href="/"><span class="hd-word">MOVIRIS</span></a></div>';
    });
})();
