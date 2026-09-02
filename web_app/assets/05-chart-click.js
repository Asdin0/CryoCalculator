(function () {
  "use strict";

  var bound = null;

  function nativeSet(input, value) {
    var setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value").set;
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function tidy(value) {
    return isFinite(value) ? Number(value.toPrecision(4)) : null;
  }

  function plot() {
    return document.querySelector("#chart .js-plotly-plot");
  }

  function at(event) {
    var gd = plot();
    var layout = gd && gd._fullLayout;
    if (!layout || !layout.xaxis || !layout.yaxis) return null;

    var drag = gd.querySelector(".nsewdrag");
    if (!drag) return null;

    var box = drag.getBoundingClientRect();
    return {
      kelvin: layout.xaxis.p2d(event.clientX - box.left),
      pressure: layout.yaxis.p2d(event.clientY - box.top),
      layout: layout
    };
  }

  function handle(event) {
    var point = at(event);
    if (!point) return;
    var layout = point.layout;

    var meta = layout.meta || {};
    var scale = typeof meta.t_scale === "number" ? meta.t_scale : 1;
    var offset = typeof meta.t_offset === "number" ? meta.t_offset : 0;

    var t = tidy(point.kelvin * scale + offset);
    var p = tidy(point.pressure);

    if (t === null || p === null || p <= 0) return;

    var f = fields();
    if (!f) return;

    nativeSet(f.t, t);
    if (!f.densityMode) nativeSet(f.p, p);
  }

  function fields() {
    var t = document.getElementById("in-t");
    var p = document.getElementById("in-p");
    if (!t || !p) return null;
    var label = document.getElementById("in-p-label");
    return {
      t: t, p: p,
      densityMode: !!label && label.textContent.trim() === "Densità"
    };
  }

  var sweeps = 0;

  function sweep(axis, fixed, lo, hi, p_unit) {
    var input = document.getElementById("scan-request");
    if (!input || !isFinite(fixed) || !isFinite(lo) || !isFinite(hi)) return;
    if (fixed <= 0 || lo <= 0 || hi <= 0) return;
    sweeps += 1;
    nativeSet(input, JSON.stringify({
      axis: axis, fixed: fixed, lo: lo, hi: hi,
      pu: p_unit || "bar", n: sweeps
    }));
  }

  var DRAG_FLOOR = 10;

  var origin = null;

  function onDown(event) {
    origin = { x: event.clientX, y: event.clientY, point: at(event) };
  }

  function clamp(value, range) {
    var lo = Math.pow(10, Math.min(range[0], range[1]));
    var hi = Math.pow(10, Math.max(range[0], range[1]));
    return Math.min(Math.max(value, lo), hi);
  }

  function onUp(event) {
    var start = origin;
    origin = null;
    if (!start || !start.point) return;

    var dx = event.clientX - start.x;
    var dy = event.clientY - start.y;
    if (Math.abs(dx) < DRAG_FLOOR && Math.abs(dy) < DRAG_FLOOR) {
      handle(event);
      return;
    }

    var end = at(event);
    if (!end) return;
    var layout = end.layout;
    var p_unit = (layout.meta || {}).p_unit;

    var t0 = clamp(start.point.kelvin, layout.xaxis.range);
    var t1 = clamp(end.kelvin, layout.xaxis.range);
    var p0 = clamp(start.point.pressure, layout.yaxis.range);
    var p1 = clamp(end.pressure, layout.yaxis.range);

    if (Math.abs(dx) >= Math.abs(dy)) {

      sweep("isobar", p0, t0, t1, p_unit);
    } else {
      sweep("isotherm", t0, p0, p1, p_unit);
    }
  }

  var STEP = 0.02;
  var STEP_COARSE = 0.10;

  var ARROWS = {
    ArrowLeft: [-1, 0], ArrowRight: [1, 0],
    ArrowUp: [0, 1], ArrowDown: [0, -1]
  };

  function onKey(event) {
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    var gd = plot();
    var layout = gd && gd._fullLayout;
    var f = fields();
    if (!layout || !f) return;

    var key = event.key.toLowerCase();
    if (key === "i" || key === "b") {
      var meta = layout.meta || {};
      var scale = typeof meta.t_scale === "number" ? meta.t_scale : 1;
      var shift = typeof meta.t_offset === "number" ? meta.t_offset : 0;
      var shownT = parseFloat(f.t.value);
      if (!isFinite(shownT)) return;
      var kelvin = (shownT - shift) / scale;

      if (key === "i") {
        var p = layout.yaxis.range;
        sweep("isotherm", kelvin, Math.pow(10, p[0]), Math.pow(10, p[1]), meta.p_unit);
      } else {

        if (f.densityMode) return;
        var pressure = parseFloat(f.p.value);
        if (!isFinite(pressure) || pressure <= 0) return;
        var t = layout.xaxis.range;
        sweep("isobar", pressure, Math.pow(10, t[0]), Math.pow(10, t[1]), meta.p_unit);
      }
      event.preventDefault();
      return;
    }

    var direction = ARROWS[event.key];
    if (!direction) return;

    var factor = 1 + (event.shiftKey ? STEP_COARSE : STEP);
    var moved = false;

    if (direction[0] !== 0) {

      var meta = layout.meta || {};
      var scale = typeof meta.t_scale === "number" ? meta.t_scale : 1;
      var offset = typeof meta.t_offset === "number" ? meta.t_offset : 0;
      var shown = parseFloat(f.t.value);
      if (isFinite(shown)) {
        var kelvin = (shown - offset) / scale;
        kelvin = direction[0] > 0 ? kelvin * factor : kelvin / factor;
        var next = tidy(kelvin * scale + offset);
        if (next !== null) {
          nativeSet(f.t, next);
          moved = true;
        }
      }
    }

    if (direction[1] !== 0 && !f.densityMode) {
      var pressure = parseFloat(f.p.value);
      if (isFinite(pressure) && pressure > 0) {
        var stepped = tidy(direction[1] > 0 ? pressure * factor : pressure / factor);
        if (stepped !== null && stepped > 0) {
          nativeSet(f.p, stepped);
          moved = true;
        }
      }
    }

    if (moved) event.preventDefault();
  }

  function describe() {
    var gd = plot();
    var drag = gd && gd.querySelector(".nsewdrag");
    var f = fields();
    if (!drag || !f) return;

    var text = f.densityMode
      ? "Piano pressione-temperatura. Le frecce sinistra e destra spostano la " +
        "temperatura; su e giù non agiscono, perché il secondo campo porta una densità " +
        "e l'asse verticale è una pressione. Maiusc allarga il passo. Il tasto I traccia " +
        "un'isoterma sull'intervallo visibile."
      : "Piano pressione-temperatura. Le frecce spostano lo stato: sinistra e destra la " +
        "temperatura, su e giù la pressione. Maiusc allarga il passo. I tasti I e B " +
        "tracciano un'isoterma e un'isobara sull'intervallo visibile; con il mouse, " +
        "trascinare fa lo stesso fra i due estremi del trascinamento.";

    if (drag.getAttribute("aria-label") !== text) {
      drag.setAttribute("aria-label", text);
    }
  }

  function bind() {
    var gd = plot();
    if (!gd || !gd._fullLayout) return;

    var drag = gd.querySelector(".nsewdrag");
    if (!drag || drag === bound) return;

    drag.style.cursor = "crosshair";

    drag.setAttribute("tabindex", "0");
    drag.setAttribute("role", "application");

    drag.addEventListener("mousedown", onDown);
    drag.addEventListener("keydown", onKey);
    bound = drag;
  }

  function pass() {
    bind();
    describe();
  }

  function start() {
    pass();

    document.addEventListener("mouseup", onUp);
    new MutationObserver(pass).observe(document.body, {
      childList: true, subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
