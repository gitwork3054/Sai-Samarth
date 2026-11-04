(function () {
  "use strict";
  document.querySelectorAll("[data-updates-carousel]").forEach(function (root) {
    var slides = Array.from(root.querySelectorAll("[data-update-slide]"));
    if (slides.length < 2) return;
    var dots = Array.from(root.querySelectorAll("[data-update-dot]"));
    var pause = root.querySelector("[data-update-pause]");
    var status = root.querySelector("[data-update-status]");
    var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var index = 0, timer, hovered = false, focused = false, paused = motion.matches;
    root.querySelectorAll(".updates-arrows, .updates-controls").forEach(function (el) { el.hidden = false; });
    function schedule() {
      clearTimeout(timer);
      pause.textContent = paused ? "Resume rotation" : "Pause rotation";
      if (!paused && !hovered && !focused && !document.hidden) {
        timer = setTimeout(function () { show(index + 1, false); }, 6000);
      }
    }
    function show(next, manual) {
      index = (next + slides.length) % slides.length;
      slides.forEach(function (slide, i) { slide.hidden = i !== index; });
      dots.forEach(function (dot, i) { dot.setAttribute("aria-current", String(i === index)); });
      if (manual) status.textContent = "Update " + (index + 1) + " of " + slides.length + ": " + slides[index].querySelector("h3").textContent;
      schedule();
    }
    root.querySelector("[data-update-prev]").addEventListener("click", function () { show(index - 1, true); });
    root.querySelector("[data-update-next]").addEventListener("click", function () { show(index + 1, true); });
    dots.forEach(function (dot, i) { dot.addEventListener("click", function () { show(i, true); }); });
    pause.addEventListener("click", function () { paused = !paused; schedule(); });
    root.addEventListener("mouseenter", function () { hovered = true; schedule(); });
    root.addEventListener("mouseleave", function () { hovered = false; schedule(); });
    root.addEventListener("focusin", function () { focused = true; schedule(); });
    root.addEventListener("focusout", function (event) { focused = root.contains(event.relatedTarget); schedule(); });
    document.addEventListener("visibilitychange", schedule);
    motion.addEventListener("change", function (event) { paused = event.matches; schedule(); });
    schedule();
  });
})();
