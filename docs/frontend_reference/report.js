/* CascadeGuard demo report: scenario replay and comparison. Vanilla JS, offline, no libraries.
   All numbers come from the JSON block #replay-data (the same simulated run data as the CSVs). Nothing is computed
   or rounded here: values are shown exactly as stored. */
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("replay-data").textContent);
  var SCEN = DATA.scenarios;
  var L = 68, R = 10, T = 26, B = 20, PH = 132; // chart geometry in px; the width follows the container (see widthOf)
  function widthOf(el, pad) { return Math.max(280, Math.floor(el.clientWidth - pad)); }  // pad = the element's own padding

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function $(id) { return document.getElementById(id); }

  var PANELS = [
    { key: "replicas", label: "pods", cls: "s-blue", step: true, second: "ready", title: "Replicas (dotted = ready)" },
    { key: "cpu", label: "cores", cls: "s-coral", step: true, title: "CPU request per pod (cores)" },
    { key: "lag", label: "msgs", cls: "s-purple", step: false, title: "Kafka lag (msgs)" }
  ];

  function chart(sc, panel, idx, showTruth, showCursor, W) {
    var st = sc.states, t0 = st[0].t, t1 = st[st.length - 1].t, step = sc.step;
    var vmax = 0;
    st.forEach(function (s) { vmax = Math.max(vmax, s[panel.key]); });
    if (vmax <= 0) vmax = 1;
    function x(t) { return L + (t - t0) / (t1 - t0) * (W - L - R); }
    function y(v) { return T + (1 - v / vmax) * (PH - T - B); }
    var out = [];
    var tNow = st[idx].t;
    if (showTruth) {
      sc.truth.forEach(function (tr) {
        var a = Math.max(tr.start, t0), b = Math.min(tr.end, t1);
        out.push('<rect class="truth" x="' + x(a) + '" y="' + T + '" width="' + Math.max(0, x(b) - x(a)) + '" height="' + (PH - T - B) + '"/>');
      });
    }
    for (var i = 0; i <= idx; i++) {
      if (st[i].rebal) out.push('<rect class="rebal" x="' + x(st[i].t) + '" y="' + T + '" width="' + Math.max(2, x(st[i].t + step) - x(st[i].t)) + '" height="' + (PH - T - B) + '"/>');
    }
    out.push('<line class="axis" x1="' + L + '" y1="' + T + '" x2="' + L + '" y2="' + (PH - B) + '"/>');
    out.push('<line class="axis" x1="' + L + '" y1="' + (PH - B) + '" x2="' + (W - R) + '" y2="' + (PH - B) + '"/>');
    out.push('<text x="' + (L - 6) + '" y="' + (T + 8) + '" text-anchor="end">' + esc(vmax) + '</text>');
    out.push('<text x="' + (L - 6) + '" y="' + (PH - B) + '" text-anchor="end">0</text>');
    out.push('<text x="' + L + '" y="' + (PH - 4) + '">' + esc(t0) + ' s</text>');
    out.push('<text x="' + (W - R) + '" y="' + (PH - 4) + '" text-anchor="end">' + esc(t1) + ' s</text>');
    out.push('<text x="' + L + '" y="' + (T - 10) + '" style="font-weight:700">' + esc(panel.title) + "</text>");
    function path(key, cls) {
      var d = "";
      for (var k = 0; k <= idx; k++) {
        var px = x(st[k].t), py = y(st[k][key]);
        if (k === 0) d = "M" + px + " " + py;
        else d += panel.step ? " H" + px + " V" + py : " L" + px + " " + py;
      }
      out.push('<path class="' + cls + '" d="' + d + '"/>');
    }
    if (panel.second) path(panel.second, panel.cls + " s-thin");
    path(panel.key, panel.cls);
    sc.flags.forEach(function (f) {
      if (f.at <= tNow) out.push('<line class="flag" x1="' + x(f.at) + '" y1="' + T + '" x2="' + x(f.at) + '" y2="' + (PH - B) + '"/>');
    });
    if (showCursor) out.push('<line class="now" x1="' + x(tNow) + '" y1="' + T + '" x2="' + x(tNow) + '" y2="' + (PH - B) + '"/>');
    return '<svg class="chart" width="' + W + '" height="' + PH + '" viewBox="0 0 ' + W + " " + PH + '" role="img" aria-label="' + esc(panel.title + ", " + sc.id + ", up to t = " + tNow + " s") + '">' + out.join("") + "</svg>";
  }

  /* ---------------- replay ---------------- */
  var cur = 0, idx = 0, timer = null;
  var tabs = $("tabs"), play = $("play"), scrub = $("scrub");

  function stop() { if (timer) { clearInterval(timer); timer = null; } play.textContent = "Play"; play.setAttribute("aria-pressed", "false"); }
  function start() {
    var last = SCEN[cur].states.length - 1;
    if (idx >= last) idx = 0;
    play.textContent = "Pause"; play.setAttribute("aria-pressed", "true");
    timer = setInterval(function () {
      if (idx < last) { idx++; render(); } else { stop(); }
    }, 130);
  }
  function render() {
    var sc = SCEN[cur], s = sc.states[idx];
    $("replay-title").textContent = sc.id + " - " + sc.title;
    $("replay-desc").textContent = sc.description + " Controllers active: " + sc.controllers + ". Ground truth: " + sc.truth_text + ".";
    $("replay-timer").firstChild.nodeValue = "t = " + s.t + " s";
    var cw = widthOf($("charts"), 0);
    $("no-kafka").hidden = sc.kafka_traffic;
    $("charts").innerHTML = PANELS.map(function (p, i) { return chart(sc, p, idx, i === 0, true, cw); }).join("");
    scrub.max = sc.states.length - 1; scrub.value = idx;
    scrub.setAttribute("aria-valuetext", "t = " + s.t + " seconds");
    $("r-replicas").textContent = s.replicas; $("r-ready").textContent = s.ready; $("r-cpu").textContent = s.cpu;
    $("r-lag").textContent = s.lag; $("r-rebal").textContent = s.rebal ? "yes" : "no"; $("r-util").textContent = s.util;
    $("flaglist").innerHTML = sc.flags.length ? sc.flags.map(function (f) {
      return '<span class="tag' + (f.at <= s.t ? " on" : "") + '">FLAG ' + esc(f.method) + " @ " + esc(f.at) + " s</span>";
    }).join("") : '<span class="tag">No detector flag in this scenario</span>';
    Array.prototype.forEach.call(tabs.children, function (b, i) { b.setAttribute("aria-pressed", i === cur ? "true" : "false"); });
  }
  SCEN.forEach(function (sc, i) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn"; b.textContent = sc.short;
    b.addEventListener("click", function () { stop(); cur = i; idx = 0; render(); });
    tabs.appendChild(b);
  });
  play.addEventListener("click", function () { if (timer) stop(); else start(); });
  scrub.addEventListener("input", function () { idx = parseInt(scrub.value, 10); render(); });

  /* ---------------- control vs conflict comparison ---------------- */
  var control = SCEN.filter(function (s) { return s.truth_known && s.truth.length === 0; })[0];
  var conflicts = SCEN.filter(function (s) { return s.truth_known && s.truth.length > 0; });
  var ctabs = $("cmp-tabs"), cmpCur = 0;
  function cmpCard(sc, el) {
    var last = sc.states.length - 1;
    el.innerHTML = '<span class="tag ' + (sc.truth.length ? "tag--coral" : "tag--green") + '">' + (sc.truth.length ? "CONFLICT SCENARIO" : "CONTROL: NO CONFLICT") + "</span>" +
      "<h3>" + esc(sc.id) + "</h3>" +
      '<p class="note">' + esc(sc.title) + ". Flags: " + esc(sc.flags_n) + ". Expected type found: " + esc(sc.expected) + ". False alarms: " + esc(sc.false_alarms) + ".</p>" +
      (sc.kafka_traffic ? "" : '<p class="note"><b>No Kafka traffic:</b> orange rebalance bands are a modelling artefact.</p>') +
      chart(sc, PANELS[0], last, true, false, widthOf(el, 38)) + chart(sc, PANELS[2], last, false, false, widthOf(el, 38));
  }
  function renderCmp() {
    if (!control || !conflicts.length) return;
    cmpCard(control, $("cmp-left")); cmpCard(conflicts[cmpCur], $("cmp-right"));
    Array.prototype.forEach.call(ctabs.children, function (b, i) { b.setAttribute("aria-pressed", i === cmpCur ? "true" : "false"); });
  }
  conflicts.forEach(function (sc, i) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn"; b.textContent = sc.short;
    b.addEventListener("click", function () { cmpCur = i; renderCmp(); });
    ctabs.appendChild(b);
  });

  // optional deep link: report.html?replay=s2&step=40 opens that scenario at that step (also handy for screenshots)
  var q = new URLSearchParams(window.location.search);
  SCEN.forEach(function (sc, i) { if (sc.short === q.get("replay")) cur = i; });
  var wanted = parseInt(q.get("step"), 10);
  if (wanted >= 0 && wanted < SCEN[cur].states.length) idx = wanted;

  stop(); render(); renderCmp();
  var resizeTimer = null;
  window.addEventListener("resize", function () {  // redraw at the new width so text stays readable
    clearTimeout(resizeTimer); resizeTimer = setTimeout(function () { render(); renderCmp(); }, 120);
  });
  document.documentElement.className += " js";
})();
