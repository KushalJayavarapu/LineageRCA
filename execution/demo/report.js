/* LineageRCA demo report: investigation replay. Vanilla JS, offline, no libraries.
   Every number and sentence comes from the JSON block #replay-data (the same run data that wrote the CSV files, formatted by Python).
   Nothing is rounded or computed here; the only arithmetic is bar geometry. Nothing starts by itself: play is always a user action. */
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("replay-data").textContent);
  var SC = DATA.scenarios, REL = DATA.rel_threshold;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function $(id) { return document.getElementById(id); }
  var cur = 0, step = 0, timer = null;
  var tabs = $("tabs"), play = $("play"), scrub = $("scrub");

  /* ---- the investigation as a list of steps: anomaly, suspects, one replay per suspect, result ---- */
  function stepsOf(sc) {
    var st = [{kind: "anomaly"}];
    if (sc.alarm) {
      st.push({kind: "suspects"});
      sc.verdicts.forEach(function (v, i) { st.push({kind: "replay", i: i}); });
    }
    st.push({kind: "result"});
    return st;
  }
  function stateAt(sc, k) {
    var st = stepsOf(sc), s = {suspectsKnown: false, upTo: -1, active: -1, result: false};
    for (var j = 0; j <= k; j++) {
      if (st[j].kind === "suspects") s.suspectsKnown = true;
      if (st[j].kind === "replay") { s.upTo = st[j].i; s.active = j === k ? st[j].i : -1; }
      if (st[j].kind === "result") s.result = true;
    }
    return s;
  }
  function stepTitle(sc, st) {
    if (st.kind === "anomaly") return sc.alarm ? "the monitor flags an anomaly" : "the monitor stays silent";
    if (st.kind === "suspects") return "suspects are shortlisted";
    if (st.kind === "replay") return "replay of " + sc.verdicts[st.i].table;
    return "result";
  }

  /* ---- lineage graph (inline SVG), wide and narrow layouts so the text stays readable ---- */
  var LAYOUTS = {
    wide: {w: 640, h: 248, nw: 150, nh: 58, pos: {raw_orders: [20, 12], raw_customers: [20, 92], raw_fx_rates: [20, 172], cleaned_orders: [245, 92], daily_revenue_agg: [470, 92]}},
    narrow: {w: 300, h: 300, nw: 132, nh: 58, pos: {raw_orders: [6, 6], raw_customers: [6, 76], raw_fx_rates: [6, 146], cleaned_orders: [162, 76], daily_revenue_agg: [162, 206]}}
  };
  var EDGES = [["raw_orders", "cleaned_orders"], ["raw_customers", "cleaned_orders"], ["raw_fx_rates", "cleaned_orders"], ["cleaned_orders", "daily_revenue_agg"]];

  function graph(sc, s, step) {
    var narrow = $("graph").clientWidth < 560, L = narrow ? LAYOUTS.narrow : LAYOUTS.wide, out = [];
    out.push('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#1A1A1A"/></marker></defs>');
    EDGES.forEach(function (e) {
      var a = L.pos[e[0]], b = L.pos[e[1]], vertical = narrow && e[0] === "cleaned_orders";
      var slot = {raw_orders: 0.22, raw_customers: 0.5, raw_fx_rates: 0.78}[e[0]] || 0.5;   // spread the arrowheads along the target's edge
      var x1 = vertical ? a[0] + L.nw / 2 : a[0] + L.nw, y1 = vertical ? a[1] + L.nh : a[1] + L.nh / 2;
      var x2 = vertical ? b[0] + L.nw / 2 : b[0], y2 = vertical ? b[1] : b[1] + L.nh * slot;
      out.push('<line class="edge" x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" marker-end="url(#arrow)"/>');
    });
    var suspects = sc.suspects.map(function (x) { return x.table; });
    Object.keys(L.pos).forEach(function (name) {
      var p = L.pos[name], cls = ["node"], parts = [], vi = -1;
      sc.verdicts.forEach(function (v, i) { if (v.table === name && i <= s.upTo) vi = i; });
      if (s.suspectsKnown && suspects.indexOf(name) >= 0) cls.push("suspect");
      if (sc.monitor && sc.monitor.table === name) { cls.push("anomaly"); parts.push("ANOMALY"); }
      else if (s.suspectsKnown && suspects.indexOf(name) >= 0 && vi < 0) parts.push("suspect");
      if (vi >= 0) { cls.push("n-" + sc.verdicts[vi].verdict); parts.push(sc.verdicts[vi].verdict); }
      if (s.active >= 0 && sc.verdicts[s.active].table === name) cls.push("active");
      var star = s.result && sc.truth.indexOf(name) >= 0 ? "★ true cause (scoring only)" : "";
      out.push('<g class="' + cls.join(" ") + '"><rect x="' + p[0] + '" y="' + p[1] + '" width="' + L.nw + '" height="' + L.nh + '"/>' +
        '<text class="big" x="' + (p[0] + 8) + '" y="' + (p[1] + 18) + '">' + esc(name) + "</text>" +
        '<text x="' + (p[0] + 8) + '" y="' + (p[1] + 34) + '">' + esc(parts.join(" · ")) + "</text>" +
        (star ? '<text x="' + (p[0] + 8) + '" y="' + (p[1] + 50) + '" style="font-size:9px">' + esc(star) + "</text>" : "") + "</g>");
    });
    return '<svg class="viz" viewBox="0 0 ' + L.w + " " + L.h + '" role="img" aria-label="Lineage graph of the five tables, step ' + (step + 1) + '">' + out.join("") + "</svg>";
  }

  /* ---- bar chart of deviations: the anomalous run, then each replay as it is revealed ---- */
  function bars(sc, s) {
    var items = [], thr = sc.alarm ? sc.monitor.threshold : REL, title;
    if (sc.alarm) {
      title = sc.monitor.metric + " deviation vs the 7-day median";
      items.push({label: "anomalous run", d: sc.monitor.deviation, cls: "", shown: true});
      sc.verdicts.forEach(function (v, i) { items.push({label: "replay: " + v.table, d: v.after, cls: "b-" + v.verdict, shown: i <= s.upTo}); });
    } else {
      title = "day-" + 11 + " deviations (the monitor stays silent)";
      sc.silent.forEach(function (m) { items.push({label: m.metric, d: m.dev, cls: "b-silent", shown: true}); });
    }
    var W = Math.max(280, $("bars").clientWidth), H = 260, T = 50, B = 70, mid, M = thr.v;
    items.forEach(function (it) { M = Math.max(M, Math.abs(it.d.v)); });
    M = M * 1.35;
    mid = T + (H - T - B) / 2;
    function y(v) { return mid - v / M * ((H - T - B) / 2); }
    var out = ['<rect class="band" x="0" y="' + y(thr.v) + '" width="' + W + '" height="' + (y(-thr.v) - y(thr.v)) + '"/>',
      '<line class="zero" x1="0" x2="' + W + '" y1="' + mid + '" y2="' + mid + '"/>',
      '<text class="big" x="8" y="16">' + esc(title) + "</text>",
      '<text x="8" y="32" style="font-size:10px">green band = inside the monitor threshold (±' + esc(thr.s) + ")</text>"];
    var slot = W / items.length, bw = Math.min(70, slot * 0.6);
    items.forEach(function (it, i) {
      var cx = slot * i + slot / 2, y0 = y(Math.max(it.d.v, 0)), h = Math.abs(y(it.d.v) - mid);
      var parts = it.label.split(/(?<=[:_]) ?/);
      if (it.shown) {
        out.push('<rect class="bar ' + it.cls + '" x="' + (cx - bw / 2) + '" y="' + y0 + '" width="' + bw + '" height="' + Math.max(h, 2) + '"/>');
        out.push('<text class="big" text-anchor="middle" x="' + cx + '" y="' + (it.d.v >= 0 ? y0 - 5 : y0 + h + 13) + '">' + esc(it.d.s) + "</text>");
      } else {
        out.push('<text text-anchor="middle" x="' + cx + '" y="' + (mid - 6) + '" style="opacity:.5">not yet</text>');
      }
      parts.slice(0, 4).forEach(function (t, k) {
        out.push('<text text-anchor="middle" x="' + cx + '" y="' + (H - B + 18 + k * 12) + '" style="font-size:10px;opacity:' + (it.shown ? 1 : 0.5) + '">' + esc(t) + "</text>");
      });
    });
    return '<svg class="viz" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="' + esc(title) + '">' + out.join("") + "</svg>";
  }

  /* ---- readout text for the current step ---- */
  function dl(pairs) { return "<dl>" + pairs.map(function (p) { return "<div><dt>" + esc(p[0]) + "</dt><dd>" + p[1] + "</dd></div>"; }).join("") + "</dl>"; }
  function changesText(sc) {
    return sc.changes.length ? sc.changes.map(function (c) { return esc(c.table + " (" + c.change_type + ", snapshot " + c.snapshot_id + ")"); }).join("; ") : "none";
  }
  function readout(sc, st, k, n) {
    var head = "Step " + (k + 1) + " of " + n + ": " + stepTitle(sc, st), body = "";
    if (st.kind === "anomaly" && sc.alarm) {
      var m = sc.monitor;
      body = dl([["Table", esc(m.table)], ["Metric", esc(m.metric)], ["Observed", esc(m.observed)], ["Expected", esc(m.expected)],
        ["Deviation", esc(m.deviation.s)], ["Threshold", "±" + esc(m.threshold.s)]]) +
        "<p>Change commits recorded on the incident day: " + changesText(sc) + ".</p>";
    } else if (st.kind === "anomaly") {
      body = "<p>No metric left its normal range, so no investigation starts. Change commits recorded on the incident day: " + changesText(sc) + ".</p>";
    } else if (st.kind === "suspects") {
      body = sc.suspects.length ? "<p>" + sc.suspects.map(function (x) { return "<b>" + esc(x.table) + "</b> (last change: " + esc(x.change_type) + ")"; }).join("; ") +
        ".</p><p>Suspects are the anomalous table and the tables upstream of it that had a change commit after the last healthy run.</p>" : "<p>No suspects.</p>";
    } else if (st.kind === "replay") {
      var v = sc.verdicts[st.i];
      body = dl([["Suspect", esc(v.table)], ["Pre-change snapshot", esc(v.snapshot)], ["Repeats", esc(v.runs)], ["Deviation before", esc(v.before.s)],
        ["Deviation after", esc(v.after.s)], ["Verdict", '<span class="tag v-' + esc(v.verdict) + '">' + esc(v.verdict) + "</span>"], ["Compute (s)", esc(v.seconds)]]) +
        "<p>" + esc(v.explanation) + "</p>";
    } else {
      body = dl(sc.methods.map(function (mm) {
        return [mm.name, esc(mm.blame) + ' <span class="tag ' + (mm.correct ? "tag--green" : "tag--coral") + '">' + (mm.correct ? "right" : "wrong") + "</span>"];
      })) + "<p>Ground truth (scoring only): " + esc(sc.truth.join(", ") || "none") + ". \"nobody\" means that method blamed no table.</p>";
    }
    return "<h4>" + esc(head) + "</h4>" + body;
  }

  function render() {
    var sc = SC[cur], st = stepsOf(sc), s = stateAt(sc, step);
    $("replay-title").textContent = sc.id;
    $("replay-desc").textContent = sc.description;
    $("step-label").textContent = "step " + (step + 1) + " / " + st.length;
    $("graph").innerHTML = graph(sc, s, step);
    $("bars").innerHTML = bars(sc, s);
    $("readout").innerHTML = readout(sc, st[step], step, st.length);
    scrub.max = st.length - 1; scrub.value = step;
    scrub.setAttribute("aria-valuetext", "step " + (step + 1) + " of " + st.length + ": " + stepTitle(sc, st[step]));
    Array.prototype.forEach.call(tabs.children, function (b, i) { b.setAttribute("aria-pressed", i === cur ? "true" : "false"); });
  }
  function stop() { if (timer) { clearInterval(timer); timer = null; } play.textContent = "Play"; play.setAttribute("aria-pressed", "false"); }
  function start() {
    var last = stepsOf(SC[cur]).length - 1;
    if (step >= last) step = 0;
    play.textContent = "Pause"; play.setAttribute("aria-pressed", "true"); render();
    timer = setInterval(function () { if (step < last) { step++; render(); } else { stop(); } }, 1800);
  }
  SC.forEach(function (sc, i) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn"; b.textContent = sc.short + " · " + sc.title; b.title = sc.id;
    b.addEventListener("click", function () { stop(); cur = i; step = 0; render(); });
    tabs.appendChild(b);
  });
  play.addEventListener("click", function () { if (timer) stop(); else start(); });
  scrub.addEventListener("input", function () { stop(); step = parseInt(scrub.value, 10); render(); });

  // deep link, also used for screenshots: report.html?scenario=s5&step=3
  var q = new URLSearchParams(window.location.search);
  SC.forEach(function (sc, i) { if (sc.short === q.get("scenario")) cur = i; });
  var wanted = parseInt(q.get("step"), 10);
  if (wanted >= 0 && wanted < stepsOf(SC[cur]).length) step = wanted;
  stop(); render();
  var resizeTimer = null;
  window.addEventListener("resize", function () { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 120); });
})();
