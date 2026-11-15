/* ==========================================================================
   MOVIRIS · Inicio
   Solo revela los bloques al hacer scroll. No llama a la API.
   ========================================================================== */

(() => {
  'use strict';

  const items = Array.from(document.querySelectorAll('.reveal'));
  const show = (el) => el.classList.add('in');

  if (!('IntersectionObserver' in window) ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    items.forEach(show);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          show(entry.target);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  items.forEach((el) => observer.observe(el));

  // Respaldo: si algo falla, el contenido nunca queda oculto
  window.setTimeout(() => items.forEach(show), 3000);
})();
