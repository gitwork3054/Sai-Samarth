(function () {
  "use strict";
  document.querySelectorAll("[data-updates-carousel]").forEach(function (root) {
    var slides = Array.from(root.querySelectorAll("[data-update-slide]"));
    if (slides.length < 2) return;
    var pause = root.querySelector("[data-update-pause]");
    var icon = root.querySelector("[data-update-pause-icon]");
    var count = root.querySelector("[data-update-count]");
    var status = root.querySelector("[data-update-status]");
    var stage = root.querySelector(".updates-stage");
    var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var index = 0, timer, focused = false, paused = motion.matches, start = null, swiped = false;
    root.querySelector(".updates-controls").hidden = false;
    function schedule() {
      clearTimeout(timer);
      pause.setAttribute("aria-label", paused ? "Resume automatic slideshow" : "Pause automatic slideshow");
      pause.setAttribute("aria-pressed", String(paused));
      icon.textContent = paused ? "▷" : "Ⅱ";
      if (!paused && !focused && !document.hidden) {
        timer = setTimeout(function () { show(index + 1, false); }, 4500);
      }
    }
    function show(next, manual) {
      var direction = next < index ? -1 : 1;
      index = (next + slides.length) % slides.length;
      slides.forEach(function (slide, i) {
        if (slide.getAnimations) slide.getAnimations().forEach(function (animation) { animation.cancel(); });
        slide.hidden = i !== index;
      });
      if (!motion.matches && slides[index].animate) {
        slides[index].animate([
          { transform: "translateX(" + (direction * 12) + "%)", opacity: 0.4 },
          { transform: "translateX(0)", opacity: 1 }
        ], { duration: 550, easing: "cubic-bezier(.22,1,.36,1)" });
      }
      count.textContent = String(index + 1).padStart(2, "0") + " / " + String(slides.length).padStart(2, "0");
      if (manual) status.textContent = "Update " + (index + 1) + " of " + slides.length + ": " + slides[index].querySelector("h3").textContent;
      schedule();
    }
    root.querySelector("[data-update-prev]").addEventListener("click", function () { show(index - 1, true); });
    root.querySelector("[data-update-next]").addEventListener("click", function () { show(index + 1, true); });
    pause.addEventListener("click", function () { paused = !paused; schedule(); });
    root.addEventListener("focusin", function (event) {
      focused = event.target.matches(":focus-visible");
      schedule();
    });
    root.addEventListener("focusout", function (event) { focused = root.contains(event.relatedTarget); schedule(); });
    stage.addEventListener("pointerdown", function (event) {
      if (event.pointerType === "mouse" || event.target.closest("button")) return;
      swiped = false;
      start = { x: event.clientX, y: event.clientY };
    });
    stage.addEventListener("pointerup", function (event) {
      if (!start) return;
      var dx = event.clientX - start.x, dy = event.clientY - start.y;
      start = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        swiped = true;
        show(index + (dx < 0 ? 1 : -1), true);
      }
    });
    stage.addEventListener("pointercancel", function () { start = null; });
    stage.addEventListener("click", function (event) {
      if (swiped) { event.preventDefault(); swiped = false; }
    }, true);
    root.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        show(index + (event.key === "ArrowLeft" ? -1 : 1), true);
      }
    });
    document.addEventListener("visibilitychange", schedule);
    motion.addEventListener("change", function (event) { paused = event.matches; schedule(); });
    schedule();
  });
})();
