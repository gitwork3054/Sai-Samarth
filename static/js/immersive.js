/* Scroll-linked travel storytelling — progressive enhancement, no third-party dependencies. */
(() => {
  'use strict';
  const story = document.querySelector('[data-ss-story]');
  const hero = document.querySelector('[data-ss-hero]');
  if (!story && !hero) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let raf = 0;
  let current = -1;
  let panels = [], buttons = [], scrollArea, meter, index;

  if (story) {
    panels = [...story.querySelectorAll('[data-ss-panel]')];
    buttons = [...story.querySelectorAll('[data-ss-goto]')];
    scrollArea = story.querySelector('[data-ss-story-scroll]');
    meter = story.querySelector('[data-ss-meter]');
    index = story.querySelector('[data-ss-index]');
  }

  function activate(next) {
    if (next === current || !panels.length) return;
    current = next;
    panels.forEach((panel, i) => {
      const active = i === next;
      panel.classList.toggle('is-active', active);
      panel.setAttribute('aria-hidden', String(!active));
      panel.querySelectorAll('a').forEach(link => {
        if (active) link.removeAttribute('tabindex');
        else link.setAttribute('tabindex', '-1');
      });
    });
    buttons.forEach((button, i) => {
      button.classList.toggle('is-active', i === next);
      if (i === next) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    if (index) index.textContent = String(next + 1).padStart(2, '0');
  }

  function draw() {
    raf = 0;
    if (reduced.matches) return;
    if (story && story.classList.contains('ss-enhanced') && panels.length > 1) {
      const bounds = scrollArea.getBoundingClientRect();
      const span = Math.max(1, bounds.height - window.innerHeight + 68);
      const progress = Math.max(0, Math.min(1, -bounds.top / span));
      const frame = Math.min(panels.length - 1, Math.floor(progress * panels.length));
      activate(frame);
      if (meter) meter.style.width = (progress * 100).toFixed(2) + '%';
    }
    if (hero && window.innerWidth > 800) {
      const scenery = hero.querySelector('.ss-hero-scenery');
      const y = Math.max(0, Math.min(500, window.scrollY));
      if (scenery && hero.getBoundingClientRect().bottom > 0) {
        scenery.style.transform = 'translate3d(0,' + (y * .11).toFixed(1) + 'px,0) scale(1.065)';
      }
    }
  }

  function requestDraw() {
    if (!raf) raf = requestAnimationFrame(draw);
  }

  function setup() {
    if (!story) return;
    const desktop = window.innerWidth > 800 && !reduced.matches && panels.length > 1;
    story.classList.toggle('ss-enhanced', desktop);
    panels.forEach(panel => {
      if (!desktop) {
        panel.removeAttribute('aria-hidden');
        panel.querySelectorAll('a').forEach(link => link.removeAttribute('tabindex'));
      }
    });
    if (desktop) {
      current = -1;
      activate(0);
      requestDraw();
    }
  }

  if (story) {
    buttons.forEach(button => button.addEventListener('click', () => {
      const destination = Number(button.dataset.ssGoto);
      const count = panels.length;
      if (!scrollArea || !count) return;
      const maxTravel = Math.max(0, scrollArea.offsetHeight - window.innerHeight + 68);
      const target = window.scrollY + scrollArea.getBoundingClientRect().top +
        maxTravel * ((destination + .1) / count);
      window.scrollTo({ top: target, behavior: reduced.matches ? 'instant' : 'smooth' });
    }));
  }
  window.addEventListener('scroll', requestDraw, { passive: true });
  window.addEventListener('resize', () => { setup(); requestDraw(); }, { passive: true });
  if (reduced.addEventListener) reduced.addEventListener('change', setup);
  setup();
  requestDraw();
})();