(function () {
  "use strict";

  function startCarousels() {
    var rails = Array.from(document.querySelectorAll(".auto-rail"));
    if (!rails.length) return;

    // Prevent duplicate animation if the newest site.js already handles rails.
    if (document.querySelector(".auto-rail [data-rail-copy]")) return;

    var reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (reducedMotion) return;

    var states = rails.map(function (rail) {
      var originals = Array.from(rail.children);
      var state = {
        rail: rail,
        originals: originals,
        width: 0,
        visible: true,
        paused: false,
        touchUntil: 0
      };

      function addCopy(item) {
        var copy = item.cloneNode(true);
        copy.dataset.railCopy = "";
        copy.setAttribute("aria-hidden", "true");
        copy.classList.add("is-visible");

        if (copy.matches("a, button")) {
          copy.setAttribute("tabindex", "-1");
        }

        copy.querySelectorAll("a, button, input, [tabindex]").forEach(function (node) {
          node.setAttribute("tabindex", "-1");
        });

        rail.appendChild(copy);
        return copy;
      }

      function build() {
        rail.querySelectorAll("[data-rail-copy]").forEach(function (copy) {
          copy.remove();
        });

        rail.scrollLeft = 0;
        if (!originals.length) return;

        var firstCopy = addCopy(originals[0]);
        state.width = firstCopy.offsetLeft - originals[0].offsetLeft;

        originals.slice(1).forEach(addCopy);

        var groups = 1;
        while (
          rail.scrollWidth - rail.clientWidth < state.width + 2 &&
          groups < 20
        ) {
          originals.forEach(addCopy);
          groups++;
        }
      }

      build();
      state.build = build;

      rail.addEventListener("mouseenter", function () {
        state.paused = true;
      });

      rail.addEventListener("mouseleave", function () {
        state.paused = false;
      });

      rail.addEventListener("focusin", function () {
        state.paused = true;
      });

      rail.addEventListener("focusout", function (event) {
        if (!rail.contains(event.relatedTarget)) {
          state.paused = false;
        }
      });

      rail.addEventListener("pointerdown", function () {
        state.touchUntil = performance.now() + 2500;
      });

      return state;
    });

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          var state = states.find(function (item) {
            return item.rail === entry.target;
          });
          if (state) state.visible = entry.isIntersecting;
        });
      }, { rootMargin: "100px" });

      states.forEach(function (state) {
        observer.observe(state.rail);
      });
    }

    var lastFrame = performance.now();

    function animate(now) {
      var elapsed = Math.min(now - lastFrame, 50);
      lastFrame = now;

      if (!document.hidden) {
        states.forEach(function (state) {
          if (
            !state.visible ||
            state.paused ||
            now < state.touchUntil ||
            !state.width
          ) return;

          state.rail.scrollLeft += elapsed * 0.037;

          if (state.rail.scrollLeft >= state.width) {
            state.rail.scrollLeft -= state.width;
          }
        });
      }

      requestAnimationFrame(animate);
    }

    requestAnimationFrame(animate);

    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        states.forEach(function (state) {
          state.build();
        });
      }, 180);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startCarousels);
  } else {
    startCarousels();
  }
})();