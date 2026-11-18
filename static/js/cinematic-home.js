(function () {
  'use strict';
  var motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var scenes = Array.prototype.slice.call(document.querySelectorAll('.cinema-scene'));
  var hero = document.querySelector('.hero-copy');
  var frame = null;
  function clear() {
    scenes.forEach(function (scene) {
      scene.style.removeProperty('--scene-float');
      scene.style.removeProperty('--place-float');
      scene.style.removeProperty('--scene-scale');
    });
    if (hero) hero.style.removeProperty('--hero-drift');
  }
  function paint() {
    frame = null;
    if (motion.matches || document.hidden) { clear(); return; }
    var height = window.innerHeight || 1;
    scenes.forEach(function (scene) {
      var rect = scene.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > height) return;
      var progress = Math.max(-1, Math.min(1, (height / 2 - (rect.top + rect.height / 2)) / height));
      scene.style.setProperty('--scene-float', (progress * 18).toFixed(1) + 'px');
      scene.style.setProperty('--place-float', (progress * 7).toFixed(1) + 'px');
      scene.style.setProperty('--scene-scale', (1 + progress * .012).toFixed(3));
    });
    if (hero) hero.style.setProperty('--hero-drift', Math.min(window.scrollY * .035, 15).toFixed(1) + 'px');
  }
  function schedule() { if (!frame) frame = window.requestAnimationFrame(paint); }
  window.addEventListener('scroll', schedule, {passive:true});
  window.addEventListener('resize', schedule, {passive:true});
  document.addEventListener('visibilitychange', schedule);
  if (motion.addEventListener) motion.addEventListener('change', schedule);
  schedule();
})();
