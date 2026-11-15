/* ==========================================================================
   MOVIRIS · Bienvenida
   Red de puntos en canvas (fondo) y transición suave al entrar a la app.
   Sin dependencias. Respeta prefers-reduced-motion.
   ========================================================================== */

(() => {
  'use strict';

  const root = document.documentElement;
  const cta = document.getElementById('cta');
  const canvas = document.getElementById('network');
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduceMotion = motionQuery.matches;

  // Muestra el contenido aunque el canvas falle
  const reveal = () => root.classList.add('is-loaded');
  if (document.readyState === 'complete') {
    window.setTimeout(reveal, 80);
  } else {
    window.addEventListener('load', () => window.setTimeout(reveal, 80), { once: true });
  }
  window.setTimeout(reveal, 1600);

  // -------------------------------------------------------------------------
  // Red de puntos
  // -------------------------------------------------------------------------

  const LINK_DISTANCE = 140;
  const COLOR = '155, 166, 133'; // #9BA685

  let ctx = null;
  let width = 0;
  let height = 0;
  let nodes = [];
  let frameId = null;
  let resizeTimer = null;

  function seed() {
    const total = Math.max(30, Math.min(90, Math.round((width * height) / 16000)));
    nodes = Array.from({ length: total }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      r: 0.8 + Math.random() * 1.4,
    }));
  }

  function draw() {
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);

    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DISTANCE) {
          ctx.strokeStyle = `rgba(${COLOR}, ${((1 - dist / LINK_DISTANCE) * 0.28).toFixed(3)})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    ctx.fillStyle = `rgba(${COLOR}, 0.7)`;
    for (const n of nodes) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function step() {
    for (const n of nodes) {
      n.x += n.vx;
      n.y += n.vy;
      if (n.x < 0 || n.x > width) n.vx *= -1;
      if (n.y < 0 || n.y > height) n.vy *= -1;
    }
    draw();
    frameId = window.requestAnimationFrame(step);
  }

  function start() {
    if (reduceMotion || frameId !== null) return;
    frameId = window.requestAnimationFrame(step);
  }

  function stop() {
    if (frameId !== null) {
      window.cancelAnimationFrame(frameId);
      frameId = null;
    }
  }

  function resize() {
    ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
    if (reduceMotion) draw();
    else start();
  }

  if (canvas) {
    resize();
    window.addEventListener(
      'resize',
      () => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(resize, 140);
      },
      { passive: true }
    );
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
      else start();
    });
  }

  // -------------------------------------------------------------------------
  // Transición al entrar
  // -------------------------------------------------------------------------

  if (cta) {
    cta.addEventListener('click', (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (reduceMotion) return;
      event.preventDefault();
      root.classList.add('is-leaving');
      window.setTimeout(() => {
        window.location.href = cta.href;
      }, 300);
    });
  }
})();