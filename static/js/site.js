(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var inr = function (n) { return "₹" + Math.round(n).toLocaleString("en-IN"); };
  var cookie = function (n) { var m = document.cookie.match("(^|;)\\s*" + n + "=([^;]+)"); return m ? decodeURIComponent(m[2]) : ""; };

  // Reveal content as it enters the viewport; keep every section visible if
  // IntersectionObserver is unavailable or reduced motion is requested.
  var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealItems = $$(".sec-head, .tiles .tile, .grid .card, .aud-card, .places .place, .cta-band");
  if (!reducedMotion && "IntersectionObserver" in window) {
    revealItems.forEach(function (item, index) {
      item.setAttribute("data-reveal", "");
      item.style.setProperty("--reveal-delay", (index % 4) * 65 + "ms");
    });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: "0px 0px 45px 0px" });
    revealItems.forEach(function (item) { observer.observe(item); });
    document.documentElement.classList.add("motion-ready");
  }
  var header = $(".top");
  if (header) {
    var updateHeader = function () { header.classList.toggle("scrolled", window.scrollY > 14); };
    window.addEventListener("scroll", updateHeader, { passive: true });
    updateHeader();
  }
  var travelMenus = $$(".travel-menu");
  travelMenus.forEach(function (menu) {
    var search = $(".travel-search", menu), groups = $$(".travel-place", menu);
    var directTrips = $$(".travel-options > .travel-trip", menu);
    var empty = $(".travel-empty", menu);
    menu.addEventListener("toggle", function () {
      if (menu.open) {
        travelMenus.forEach(function (other) { if (other !== menu) other.open = false; });
        setTimeout(function () { search.focus(); }, 0);
      }
    });
    search.addEventListener("input", function () {
      var query = search.value.toLocaleLowerCase().trim(), shown = 0;
      groups.forEach(function (group) {
        var placeMatches = group.dataset.search.includes(query), matches = 0;
        $$(".travel-trip", group).forEach(function (link) {
          link.hidden = !placeMatches && !link.dataset.search.includes(query);
          if (!link.hidden) matches++;
        });
        group.hidden = matches === 0;
        shown += matches;
      });
      directTrips.forEach(function (link) {
        link.hidden = !link.dataset.search.includes(query);
        if (!link.hidden) shown++;
      });
      empty.hidden = shown > 0;
    });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        var first = $$(".travel-trip", menu).find(function (link) { return !link.hidden && !link.closest(".travel-place[hidden]"); });
        if (first) { e.preventDefault(); location.href = first.href; }
      }
      if (e.key === "Escape") { menu.open = false; $("summary", menu).focus(); }
    });
  });
  document.addEventListener("click", function (e) {
    travelMenus.forEach(function (menu) { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  });

  // mobile nav + filter toggle
  var burger = $(".burger"), nav = $("#nav");
  if (burger) burger.addEventListener("click", function () {
    var open = nav.classList.toggle("open"); burger.setAttribute("aria-expanded", open);
  });
  $$("[data-toggle]").forEach(function (b) {
    b.addEventListener("click", function () { $(b.dataset.toggle).classList.toggle("open"); });
  });
  var ff = $("#filter-form");
  if (ff) $$("select", ff).forEach(function (s) { s.addEventListener("change", function () { ff.submit(); }); });

  // save / like packages
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-save]"); if (!b) return;
    e.preventDefault();
    if (document.body.dataset.auth !== "1") {
      location.href = document.body.dataset.login + "?next=" + encodeURIComponent(location.pathname + location.search); return;
    }
    fetch(b.dataset.save, { method: "POST", headers: { "X-CSRFToken": cookie("csrftoken") }, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.login) { location.href = document.body.dataset.login; return; }
        $$('[data-save="' + b.dataset.save + '"]').forEach(function (x) {
          x.classList.toggle("on", d.saved); x.setAttribute("aria-pressed", d.saved);
        });
      });
  });

  // gallery
  var gal = $("[data-gal]");
  if (gal) {
    var more = $("[data-gal-more]");
    if (more) more.addEventListener("click", function () { gal.classList.add("open"); more.remove(); });
    var lb = $("#lb");
    gal.addEventListener("click", function (e) {
      var i = e.target.closest("[data-full]"); if (!i) return;
      $("img", lb).src = i.dataset.full; $("p", lb).textContent = i.dataset.cap || ""; lb.hidden = false;
    });
    lb.addEventListener("click", function (e) { if (e.target === lb || e.target.matches("[data-close]")) lb.hidden = true; });
  }

  // price calculator
  var cfgEl = $("#pkg-config"); if (!cfgEl) return;
  var cfg = JSON.parse(cfgEl.textContent), P = window.PKG, calc = $("#calc");
  var state = { adults: 2, children: 0 };
  var enq = $("#enq"), form = $("#enq-form");

  function compute() {
    var tier = ($('input[name="tier"]:checked', calc) || {}).value || "standard";
    var cityEl = $("#dep-city"), city = cityEl ? cityEl.value : "";
    var pax = state.adults + state.children;
    var base = state.adults * cfg.base + state.children * cfg.child;
    var hotel = (cfg.tiers[tier] || 0) * pax;
    var disc = Math.floor((base + hotel) * cfg.discount / 100 + 0.5);
    var sur = 0; cfg.departures.forEach(function (d) { if (d.city === city) sur = d.surcharge * pax; });
    var acts = [], actTotal = 0, ids = [];
    $$("[data-act]:checked", calc).forEach(function (c) {
      var a = cfg.activities.filter(function (x) { return String(x.id) === c.value; })[0];
      if (a) { acts.push(a.name); ids.push(a.id); actTotal += a.adult * state.adults + a.child * state.children; }
    });
    return { tier: tier, city: city, base: base, hotel: hotel, disc: disc, sur: sur, acts: acts, ids: ids, actTotal: actTotal, total: Math.max(base + hotel - disc + sur + actTotal, 0) };
  }
  function quoted(c) { return cfg.price_on_request || (state.children > 0 && cfg.child_price_on_request); }
  function totalLabel(c) { return quoted(c) ? "Price on request" : inr(c.total); }
  function label(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
  function summary(c) {
    var l = [P.title + " (" + P.code + ")", state.adults + " adult(s), " + state.children + " child(ren)", label(c.tier) + " hotels"];
    if (c.city) l.push("Departure: " + c.city);
    if (c.acts.length) l.push("Optional: " + c.acts.join(", "));
    l.push("Estimated total: " + totalLabel(c)); return l;
  }
  function render() {
    var c = compute(), b = $("#breakdown");
    var rows = [["Adults × " + state.adults, inr(state.adults * cfg.base)]];
    if (state.children) rows.push(["Children × " + state.children, inr(state.children * cfg.child)]);
    if (c.hotel) rows.push([label(c.tier) + " hotel upgrade", "+" + inr(c.hotel)]);
    if (c.disc) rows.push(["Offer " + cfg.discount + "% off", "−" + inr(c.disc), "disc"]);
    if (c.sur) rows.push(["Departure from " + c.city, "+" + inr(c.sur)]);
    if (c.actTotal) rows.push(["Optional experiences", "+" + inr(c.actTotal)]);
    if (quoted(c)) rows = [["Tour quote", "Price on request"]];
    b.innerHTML = rows.map(function (r) { return '<div class="' + (r[2] || "") + '"><dt>' + r[0] + "</dt><dd>" + r[1] + "</dd></div>"; }).join("");
    ["#total", "#total-m"].forEach(function (s) { var t = $(s); if (t) { t.textContent = totalLabel(c); } });
    var tt = $("#total"); tt.classList.remove("bump"); void tt.offsetWidth; tt.classList.add("bump");
    var text = "Hi, I'd like to enquire about:\n" + summary(c).join("\n") + "\n" + P.url;
    $("#wa-link").href = "https://wa.me/" + P.wa + "?text=" + encodeURIComponent(text);
    $("#mail-link").href = "mailto:" + P.mail + "?subject=" + encodeURIComponent("Enquiry: " + P.title + " (" + P.code + ")") + "&body=" + encodeURIComponent(text);
    return c;
  }
  $$(".stepper", calc).forEach(function (s) {
    var key = s.dataset.step, out = $("output", s);
    $$("button", s).forEach(function (b) {
      b.addEventListener("click", function () {
        var min = key === "adults" ? 1 : 0, max = key === "adults" ? 40 : 20;
        state[key] = Math.min(max, Math.max(min, state[key] + Number(b.dataset.d))); out.textContent = state[key]; render();
      });
    });
  });
  calc.addEventListener("change", render);

  // enquiry modal
  function openEnq() {
    var c = render();
    form.adults.value = state.adults; form.children.value = state.children; form.hotel_tier.value = c.tier;
    form.departure_city.value = c.city; form.activities.value = c.ids.join(",");
    $("#enq-sum-text").textContent = state.adults + "A" + (state.children ? " + " + state.children + "C" : "") + " · " + label(c.tier) + (c.city ? " · from " + c.city : "") + (c.acts.length ? " · " + c.acts.length + " add-on(s)" : "");
    $("#enq-total").textContent = totalLabel(c);
    $("#enq-form-wrap").hidden = false; $("#enq-done").hidden = true; $("#enq-err").textContent = "";
    enq.hidden = false; setTimeout(function () { form.name.focus(); }, 50);
  }
  $$("[data-open-enq]").forEach(function (b) { b.addEventListener("click", openEnq); });
  enq.addEventListener("click", function (e) { if (e.target === enq || e.target.matches("[data-close]")) enq.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { enq.hidden = true; var l = $("#lb"); if (l) l.hidden = true; } });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = $("button[type=submit]", form); btn.disabled = true; btn.textContent = "Sending…";
    fetch(form.action, { method: "POST", body: new FormData(form), credentials: "same-origin", headers: { "X-CSRFToken": cookie("csrftoken") || form.csrfmiddlewaretoken.value } })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        btn.disabled = false; btn.textContent = "Send inquiry";
        if (res.ok && res.d.ok) { $("#enq-ref").textContent = res.d.reference; $("#enq-form-wrap").hidden = true; $("#enq-done").hidden = false; }
        else { var er = res.d.errors || {}; $("#enq-err").textContent = Object.keys(er).map(function (k) { return k.replace("_", " ") + ": " + er[k]; }).join(" · ") || "Something went wrong. Please try again."; }
      })
      .catch(function () { btn.disabled = false; btn.textContent = "Send inquiry"; $("#enq-err").textContent = "Network error. Please try again or use WhatsApp."; });
  });
  render();
})();
