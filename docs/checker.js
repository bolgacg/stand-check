/* The checks from study/checker.py, ported line for line so the page can re-check the two
   hotfire logs in the browser and plant faults into them. The coda compares every site score
   this file computes with the score the Python build computed. */
(function (root) {
  'use strict';
  var ALWAYS = 1000, NO_RANGE = -1, MIN_FLAT = 5, RANGE_MARGIN = 0.1, PERSIST = 3;
  var W_ELEC = 0.1, W_POS = 1.5, POS_TOL = 10;
  var FLAT_LIMIT = { p_fast: 0.05, p_slow: 0.5, load: 0.5, temp: 3.0, pos: 2.0, flow: 2.0, density: 2.0 };
  // added after the measured runs (PLAN.md changes 4 and 5)
  var RAIL_MIN = { p_fast: 10, p_slow: 10, load: 10, temp: 52, pos: 10, flow: 10, density: 54 };
  var SIMPLE_FLAT = 100, SIMPLE_GAP = 0.5;

  function longestTrue(mask) {
    var best = 0, bestStart = 0, cur = 0, start = 0;
    for (var i = 0; i < mask.length; i++) {
      if (mask[i]) { if (!cur) start = i; cur++; if (cur > best) { best = cur; bestStart = start; } }
      else cur = 0;
    }
    return [best, bestStart];
  }
  function median(a) {
    var s = Float64Array.from(a).sort(), n = s.length;
    if (!n) return NaN;
    return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
  }
  function eqPrev(x) { var m = new Uint8Array(Math.max(0, x.length - 1)); for (var i = 1; i < x.length; i++) m[i - 1] = x[i] === x[i - 1] ? 1 : 0; return m; }

  function flat(t, x) {
    if (x.length < 2) return [0, 0, 0];
    var r = longestTrue(eqPrev(x));
    if (!r[0]) return [1, 0, 0];
    var n = r[0] + 1, i = r[1];
    return [n, i, t[i + n - 1] - t[i]];
  }
  function stuck(t, x, cls) {
    var f = flat(t, x), limit = FLAT_LIMIT[cls];
    return { score: f[0] >= MIN_FLAT ? f[2] / limit : 0, samples: f[0], start: t[f[1]], seconds: f[2], limit: limit,
             whole: f[0] >= x.length - 1, value: x[f[1]] };
  }
  function rail(t, x, cls) {
    var hi = -Infinity, lo = Infinity, best = [0, 0, null, ''];
    for (var i = 0; i < x.length; i++) { if (x[i] > hi) hi = x[i]; if (x[i] < lo) lo = x[i]; }
    [[hi, 'highest'], [lo, 'lowest']].forEach(function (vw) {
      var m = new Uint8Array(x.length); for (var j = 0; j < x.length; j++) m[j] = x[j] === vw[0] ? 1 : 0;
      var r = longestTrue(m); if (r[0] > best[0]) best = [r[0], r[1], vw[0], vw[1]];
    });
    var n = best[0], k = best[1], lim = RAIL_MIN[cls];
    var text = n >= x.length ? 'never leaves one value, ' + fmtVal(best[2])
      : 'sits at its own ' + best[3] + ' value, ' + fmtVal(best[2]) + ', for ' + n + ' samples (' + fmtDur(t[k + n - 1] - t[k]) + ') from t = ' + fmtT(t[k]) + ' (limit ' + lim + ' samples)';
    return { score: n / lim, text: text };
  }
  function simpleFlat(t, x) { return flat(t, x)[0] / SIMPLE_FLAT; }
  function simpleGap(t) {
    var dt = [], mx = -Infinity;
    for (var i = 1; i < t.length; i++) { var d = t[i] - t[i - 1]; if (d <= 0) return ALWAYS; dt.push(d); if (d > mx) mx = d; }
    return Math.max(0, (mx / median(dt) - 1) / SIMPLE_GAP);
  }
  function rangeMstar(t, x, lo, hi) {
    var span = Math.max(hi - lo, 1e-9 * Math.max(1, Math.abs(hi))), n = x.length, e = new Float64Array(n);
    for (var i = 0; i < n; i++) e[i] = Math.max((lo - x[i]) / span, (x[i] - hi) / span);
    var best = -Infinity, bj = 0;
    if (n >= PERSIST) {
      for (var j = 0; j <= n - PERSIST; j++) {
        var w = e[j]; for (var k = 1; k < PERSIST; k++) w = Math.min(w, e[j + k]);
        if (w > best) { best = w; bj = j; }
      }
    } else for (var q = 0; q < n; q++) if (e[q] > best) { best = e[q]; bj = q; }
    return { m: best, t: t[bj], value: x[bj], lo: lo, hi: hi, span: span };
  }
  function chanceRepeatRows(xs) {
    var n = xs[0].length, p = 1;
    xs.forEach(function (x) { var m = eqPrev(x), s = 0; for (var i = 0; i < m.length; i++) s += m[i]; p *= Math.max(s / m.length, 1e-12); });
    if (p >= 1) return Infinity;
    return Math.max(1, Math.log(100 * n) / Math.log(1 / p));
  }
  function integrity(t, live, declaredRate) {
    var n = t.length, parts = {}, ev = {}, dt = new Float64Array(n - 1), back = 0, pos = [], jmax = 0;
    for (var i = 1; i < n; i++) { dt[i - 1] = t[i] - t[i - 1]; if (dt[i - 1] <= 0) back++; else pos.push(dt[i - 1]); if (dt[i - 1] > dt[jmax]) jmax = i - 1; }
    if (back) { parts.order = ALWAYS; ev.order = back + ' timestamp' + (back === 1 ? '' : 's') + ' repeat or run backwards'; }
    var med = median(pos), dev = pos.map(function (d) { return Math.abs(d - med); });
    var jit = 1.4826 * median(dev) / med, a0 = Math.max(0.5, 4 * jit);
    parts.gap = Math.max(0, (dt[jmax] / med - 1) / a0);
    ev.gap = 'longest interval ' + fmtDur(dt[jmax]) + ' at t = ' + fmtT(t[jmax]) + ' against a normal ' + fmtDur(med) + ' (limit ' + fmtDur(med * (1 + a0)) + ')';
    if (declaredRate) {
      var expected = (t[n - 1] - t[0]) * declaredRate + 1, short = 1 - n / expected;
      parts.short = Math.max(0, short) / 0.02;
      ev.short = n + ' rows where ' + declaredRate + ' a second gives ' + Math.round(expected) + ' (' + (100 * short).toFixed(1) + ' percent short, limit 2)';
    }
    if (live.length >= 3) {
      var same = new Uint8Array(n - 1).fill(1);
      live.forEach(function (x) { for (var i = 1; i < n; i++) if (x[i] !== x[i - 1]) same[i - 1] = 0; });
      var r = longestTrue(same), lim = chanceRepeatRows(live);
      parts.repeat = isFinite(lim) ? r[0] / lim : 0;
      if (r[0]) ev.repeat = r[0] + ' row' + (r[0] === 1 ? '' : 's') + ' in a row repeat the previous row in all ' + live.length + ' live channels at t = ' + fmtT(t[r[1] + 1]) + ' (chance allows ' + lim.toFixed(1) + ')';
    }
    var worst = null, score = 0;
    Object.keys(parts).forEach(function (k) { if (worst === null || parts[k] > score) { score = parts[k]; worst = k; } });
    return { score: score, parts: parts, text: ev, worst: worst };
  }
  function ages(t, cmd) {
    var a = new Float64Array(t.length), last = -Infinity, edges = 0;
    for (var i = 0; i < t.length; i++) {
      if (i > 0 && cmd[i] !== cmd[i - 1]) { last = t[i]; edges++; }
      a[i] = isFinite(last) ? t[i] - last : 1e3;
    }
    return [a, edges];
  }
  function windowsMaxOfMin(v) {
    var best = 0, bj = 0;
    if (v.length < PERSIST) { for (var q = 0; q < v.length; q++) if (v[q] > best) { best = v[q]; bj = q; } return [best, bj]; }
    for (var j = 0; j <= v.length - PERSIST; j++) {
      var w = v[j]; for (var k = 1; k < PERSIST; k++) w = Math.min(w, v[j + k]);
      if (j === 0 || w > best) { best = w; bj = j; }
    }
    return [best, bj];
  }
  function valveElectrical(t, cmd, v, batt) {
    var r = ages(t, cmd), age = r[0], w = new Float64Array(t.length);
    for (var i = 0; i < t.length; i++) {
      var on = v[i] >= 0.75 * batt[i], off = v[i] <= 0.5 * batt[i];
      var mism = (cmd[i] > 0.5 && !on) || (cmd[i] < 0.5 && !off);
      w[i] = (mism ? age[i] : 0) / W_ELEC;
    }
    var b = windowsMaxOfMin(w), j = b[1];
    var text = b[0] > 0 ? 'commanded ' + (cmd[j] > 0.5 ? 'on' : 'off') + ', output ' + fmtVal(v[j]) + ' V (battery ' + fmtVal(batt[j]) + ' V) at t = ' + fmtT(t[j]) + ', ' + fmtDur(age[j]) + ' after the last command (limit ' + fmtDur(W_ELEC) + ')'
      : 'output followed ' + changes(r[1], 'command change') + ' within ' + fmtDur(W_ELEC);
    return { score: b[0], text: text, t: t[j] };
  }
  function valvePosition(t, sp, p) {
    var r = ages(t, sp), age = r[0], w = new Float64Array(t.length);
    for (var i = 0; i < t.length; i++) w[i] = Math.min(age[i] / W_POS, Math.abs(p[i] - sp[i]) / POS_TOL);
    var b = windowsMaxOfMin(w), j = b[1];
    var text = b[0] > 1 ? 'position ' + fmtVal(p[j]) + ' against setpoint ' + fmtVal(sp[j]) + ' at t = ' + fmtT(t[j]) + ', ' + fmtDur(age[j]) + ' after the last change (limits ' + POS_TOL + ' degrees, ' + fmtDur(W_POS) + ')'
      : 'within ' + POS_TOL + ' degrees of its setpoint by ' + fmtDur(W_POS) + ' after ' + changes(r[1], 'change', true);
    return { score: b[0], text: text, t: t[j] };
  }

  /* ---------- one hotfire log: every site, as the Python build scores it ---------- */
  function liveArrays(run) {
    return Object.keys(run.channels).filter(function (c) { return run.channels[c].role === 'live'; }).map(function (c) { return run.channels[c].x; });
  }
  function siteScore(run, key) {
    var kind = key.split(':')[0], name = key.slice(kind.length + 1);
    if (kind === 'stream') { var g = integrity(run.t, liveArrays(run), run.declaredRate); return { score: g.score, m: NO_RANGE, ev: g, simple: simpleGap(run.t), rail: NO_RANGE }; }
    if (kind === 'channel') {
      var ch = run.channels[name], s = stuck(run.t, ch.x, ch.cls), r = rangeMstar(run.t, ch.x, ch.lo, ch.hi), ra = rail(run.t, ch.x, ch.cls);
      return { score: Math.max(s.score, Math.max(0, r.m) / RANGE_MARGIN), m: r.m, stuck: s, range: r, simple: simpleFlat(run.t, ch.x), rail: ra.score, railText: ra.text };
    }
    var v = run.valves.filter(function (q) { return q.name === name; })[0], fb = run.channels[v.fb];
    var res = v.kind === 'electrical' ? valveElectrical(run.t, v.cmd, fb.x, v.batt) : valvePosition(run.t, v.cmd, fb.x);
    var m = fb.role === 'valve' ? rangeMstar(run.t, fb.x, fb.lo, fb.hi).m : NO_RANGE;
    return { score: res.score, m: m, ev: res, simple: NO_RANGE, rail: NO_RANGE };
  }
  function siteKeys(run) {
    var keys = ['stream:telemetry'];
    Object.keys(run.channels).forEach(function (c) { if (run.channels[c].role === 'live') keys.push('channel:' + c); });
    run.valves.forEach(function (v) { keys.push('valve:' + v.name); });
    return keys;
  }
  function verdict(run, key, s) {
    var kind = key.split(':')[0];
    if (kind === 'stream') return s.score > 1 ? s.ev.text[s.ev.worst] : 'complete: ' + s.ev.text.gap;
    if (kind === 'channel') {
      if (s.stuck.score > 1) return s.stuck.whole ? 'never changed: ' + fmtVal(s.stuck.value) + ' for the whole record'
        : 'flat at ' + fmtVal(s.stuck.value) + ' for ' + fmtDur(s.stuck.seconds) + ' from t = ' + fmtT(s.stuck.start) + ' (limit ' + fmtDur(s.stuck.limit) + ')';
      if (Math.max(0, s.m) / RANGE_MARGIN > 1) return rangeText(s.range);
      return 'moving and inside its range';
    }
    return s.ev.text;
  }
  function rangeText(r) {
    return 'reads ' + fmtVal(r.value) + ' at t = ' + fmtT(r.t) + '; limits ' + fmtVal(r.lo - RANGE_MARGIN * r.span) + ' to ' + fmtVal(r.hi + RANGE_MARGIN * r.span);
  }

  /* ---------- planting, as study/inject.py does it, at a chosen time ---------- */
  function copyRun(run) {
    var n = { id: run.id, label: run.label, t: run.t, declaredRate: run.declaredRate, channels: {}, valves: [] };
    Object.keys(run.channels).forEach(function (c) { var ch = run.channels[c]; n.channels[c] = Object.assign({}, ch); });
    run.valves.forEach(function (v) { n.valves.push(Object.assign({}, v)); });
    return n;
  }
  function residualNoise(x, n, avoid) {
    var k = 21, h = 10, len = x.length;
    if (len < k + n + 2) return new Float64Array(n);
    var start = avoid[0] >= n ? 0 : (len - n >= avoid[1] ? len - n : 0), out = new Float64Array(n);
    for (var i = 0; i < n; i++) {
      var j = start + i, win = [];
      for (var q = j - h; q <= j + h; q++) win.push(x[Math.min(len - 1, Math.max(0, q))]);
      out[i] = x[j] - median(win);
    }
    return out;
  }
  function quantum(x) {
    var d = [], q = Infinity;
    for (var i = 1; i < x.length; i++) { var a = Math.abs(x[i] - x[i - 1]); if (a > 0) { d.push(a); if (a < q) q = a; } }
    if (!d.length) return 0;
    for (var j = 0; j < d.length; j++) if (Math.abs(d[j] / q - Math.round(d[j] / q)) >= 1e-6) return 0;
    return q;
  }
  function idxAt(t, v) { var lo = 0, hi = t.length; while (lo < hi) { var m = (lo + hi) >> 1; if (t[m] < v) lo = m + 1; else hi = m; } return lo; }

  /* kind: flat | flat_noisy | rows_missing | rows_repeated | valve_late; size in seconds or rows; at = time */
  function plant(run, key, kind, size, at) {
    var name = key.slice(key.indexOf(':') + 1), n = copyRun(run), t = run.t, i, j, x;
    if (kind === 'rows_missing' || kind === 'rows_repeated') {
      i = Math.max(1, Math.min(idxAt(t, at), t.length - size - 2));
      if (kind === 'rows_missing') {
        var keep = function (a) { return Array.prototype.slice.call(a, 0, i).concat(Array.prototype.slice.call(a, i + size)); };
        n.t = keep(t);
        Object.keys(n.channels).forEach(function (c) { n.channels[c].x = keep(run.channels[c].x); });
        n.valves.forEach(function (v, k) { v.cmd = keep(run.valves[k].cmd); if (v.batt) v.batt = keep(run.valves[k].batt); });
      } else {
        var rep = function (a) { var b = a.slice(); for (var q = i; q < i + size; q++) b[q] = a[i - 1]; return b; };
        Object.keys(n.channels).forEach(function (c) { n.channels[c].x = rep(run.channels[c].x); });
        n.valves.forEach(function (v, k) { v.cmd = rep(run.valves[k].cmd); if (v.batt) v.batt = rep(run.valves[k].batt); });
      }
      return { run: n, t0: t[i], t1: t[Math.min(t.length - 1, i + size)] };
    }
    if (kind === 'flat' || kind === 'flat_noisy') {
      var ch = run.channels[name];
      i = Math.max(1, idxAt(t, at));
      j = Math.max(i + 1, idxAt(t, t[i - 1] + size + 1e-12));
      j = Math.min(j, t.length);
      x = ch.x.slice();
      var noise = kind === 'flat_noisy' ? residualNoise(ch.x, j - i, [i, j]) : null, qn = kind === 'flat_noisy' ? quantum(ch.x) : 0;
      for (var q = i; q < j; q++) {
        var v = x[i - 1] + (noise ? noise[q - i] : 0);
        x[q] = qn ? Math.round(v / qn) * qn : v;
      }
      n.channels[name].x = x;
      return { run: n, t0: t[i - 1], t1: t[j - 1] };
    }
    var vi = 0; run.valves.forEach(function (v, k) { if (v.name === name) vi = k; });
    var vv = run.valves[vi], fbName = vv.fb, fb = run.channels[fbName], edges = [];
    for (var e = 1; e < t.length; e++) if (vv.cmd[e] !== vv.cmd[e - 1]) edges.push(e);
    if (!edges.length) return null;
    var best = edges[0]; edges.forEach(function (e2) { if (Math.abs(t[e2] - at) < Math.abs(t[best] - at)) best = e2; });
    var nxt = edges.filter(function (e2) { return e2 > best; })[0], s0 = best, s1 = nxt === undefined ? t.length : nxt;
    x = fb.x.slice();
    var pre = fb.x[s0 - 1], nz = residualNoise(fb.x, s1 - s0, [s0, s1]), qv = quantum(fb.x);
    for (var r = s0; r < s1; r++) {
      var src = t[r] - size, late;
      if (size === 'never' || src < t[s0]) late = null;
      else { var k2 = Math.max(s0, Math.min(s1 - 1, idxAt(t, src))); late = fb.x[k2]; }
      if (late === null) { late = pre + nz[r - s0]; if (qv) late = Math.round(late / qv) * qv; }
      x[r] = late;
    }
    n.channels[fbName].x = x;
    return { run: n, t0: t[s0], t1: t[s1 - 1], fb: fbName, edge: t[s0] };
  }

  function changes(n, noun, each) { return n === 1 ? 'its one ' + noun : (each ? 'each of ' : 'all ') + n + ' ' + noun + 's'; }
  function fmtVal(v) {
    v = +v; if (v === 0) return '0';
    var a = Math.abs(v);
    if (a >= 1000) return Math.round(v).toLocaleString('en-GB');
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return (+v.toPrecision(3)).toString();
  }
  function fmtDur(s) {
    if (s >= 1) return s.toFixed(2) + ' s';
    if (s >= 0.001) return s >= 0.01 ? (s * 1000).toFixed(0) + ' ms' : (s * 1000).toFixed(1) + ' ms';
    return (s * 1e6).toFixed(0) + ' microseconds';
  }
  function fmtT(s) { return (+s).toFixed(3) + ' s'; }

  root.SC = { stuck: stuck, rangeMstar: rangeMstar, integrity: integrity, valveElectrical: valveElectrical, valvePosition: valvePosition,
    siteScore: siteScore, siteKeys: siteKeys, verdict: verdict, plant: plant, fmtVal: fmtVal, fmtDur: fmtDur, RANGE_MARGIN: RANGE_MARGIN,
    SIMPLE_FLAT: SIMPLE_FLAT,
    FLAT_LIMIT: FLAT_LIMIT };
})(typeof window !== 'undefined' ? window : globalThis);
