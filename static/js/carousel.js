(function () {
  "use strict";

  function startCarousels() {
    var rails = Array.from(document.querySelectorAll(".auto-rail"));
    if (!rails.length) return;

    if (document.querySelector(".auto-rail [data-rail-copy]")) return;

    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    var states = rails.map(function (rail) {
      var originals = Array.from(rail.children);
      var state = {
        rail: rail,
        originals: originals,
        loopWidth: 0,
        step: 0,
        visible: true,
        paused: false,
        touchUntil: 0,
        nextAt: performance.now() + 1800,
        moving: false
      };

      function addCopy(item) {
        var copy = item.cloneNode(true);
        copy.dataset.railCopy = "";
        copy.setAttribute("aria-hidden", "true");
        copy.classList.add("is-visible");

        if (copy.matches("a, button")) copy.setAttribute("tabindex", "-1");
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
        state.loopWidth = firstCopy.offsetLeft - originals[0].offsetLeft;

        if (originals.length > 1) {
          state.step = originals[1].offsetLeft - originals[0].offsetLeft;
        } else {
          state.step = originals[0].getBoundingClientRect().width + 14;
        }

        originals.slice(1).forEach(addCopy);

        var groups = 1;
        while (
          rail.scrollWidth - rail.clientWidth < state.loopWidth + state.step &&
          groups < 10
        ) {
          originals.forEach(addCopy);
          groups++;
        }

        state.nextAt = performance.now() + 1800;
      }

      build();
      state.build = build;

      rail.addEventListener("mouseenter", function () {
        state.paused = true;
      });

      rail.addEventListener("mouseleave", function () {
        state.paused = false;
        state.nextAt = performance.now() + 900;
      });

      rail.addEventListener("focusin", function () {
        state.paused = true;
      });

      rail.addEventListener("focusout", function (event) {
        if (!rail.contains(event.relatedTarget)) {
          state.paused = false;
          state.nextAt = performance.now() + 900;
        }
      });

      rail.addEventListener("pointerdown", function () {
        state.touchUntil = performance.now() + 3000;
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

    function swipe(state, now) {
      if (state.moving || !state.step || !state.loopWidth) return;

      state.moving = true;
      state.rail.classList.add("is-swiping");

      var target = state.rail.scrollLeft + state.step;
      state.rail.scrollTo({ left: target, behavior: "smooth" });

      window.setTimeout(function () {
        if (state.rail.scrollLeft >= state.loopWidth - 2) {
          state.rail.style.scrollBehavior = "auto";
          state.rail.scrollLeft -= state.loopWidth;
          void state.rail.offsetWidth;
          state.rail.style.scrollBehavior = "";
        }

        state.rail.classList.remove("is-swiping");
        state.moving = false;
        state.nextAt = now + 2200;
      }, 620);
    }

    function animate(now) {
      if (!document.hidden) {
        states.forEach(function (state) {
          if (
            !state.visible ||
            state.paused ||
            state.moving ||
            now < state.touchUntil ||
            now < state.nextAt
          ) return;

          swipe(state, now);
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