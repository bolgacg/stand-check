/* Everything the page shows is drawn from D (data.js, written by study/build_page_data.py). */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var NS = 'http://www.w3.org/2000/svg';
  var H = D.headline;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function pct(a, b, d) { return b ? (100 * a / b).toFixed(d || 0) : '0'; }
  function words(n) { return n === 0 ? 'none' : String(n); }
  function svgEl(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, str, attrs) {
    var t = svgEl('text', Object.assign({ x: x, y: y, 'font-family': 'IBM Plex Sans, system-ui, sans-serif', 'font-size': 11, fill: '#5b6470' }, attrs || {}), parent);
    t.textContent = str;
    return t;
  }
  function niceTicks(lo, hi, n) {
    var span = hi - lo || 1, step = Math.pow(10, Math.floor(Math.log10(span / n))), err = span / n / step;
    if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
    var out = []; for (var v = Math.ceil(lo / step) * step; v <= hi + 1e-12; v += step) out.push(+v.toPrecision(12));
    return out;
  }
  function tickLabel(v) { var a = Math.abs(v); return a >= 1000 ? Math.round(v).toLocaleString('en-GB') : a >= 10 || v === 0 ? String(+v.toFixed(1)) : String(+v.toPrecision(3)); }
  function siteKindOf(k) { return D.roc.siteKinds[k]; }

  /* ---------------- header ---------------- */
  function header() {
    $('#dek').innerHTML = 'Before anyone analyses a test, someone has to trust its data: that no rows went missing, no sensor froze ' +
      'and each valve followed its command. I wrote a checker that reads a raw log and a channel map and prints a pass or fail ' +
      'report for each run, and ran it on <b>' + D.totals.runs + ' public test-stand runs</b> from three projects. It finds faults a range limit cannot see, ' +
      'and it is blind to a sensor that freezes but keeps its noise.';
    var nk = H.perKind.flat_noisy;
    var q = [
      ['What does it catch that a range limit cannot?', pct(H.caught, H.planted) + ' percent of the faults I planted into real runs; a range limit set from the stand\'s other runs catches ' + words(H.caughtRange) + '.'],
      ['How often does it raise a false alarm?', 'On ' + H.falseChecker + ' of ' + H.healthy + ' healthy sites in the measured runs, as often as the range limit.'],
      ['What did it find in the real public logs?', H.realChecker + ' of the ' + H.realTotal + ' problems I found in them by hand; the range limit flags ' + H.realRange + '.'],
      ['Where does it lose?', 'It catches ' + nk.checker + ' of ' + nk.n + ' sensors frozen with their noise kept, and it misses saturated pressure sensors in ' + D.extra.clipRuns + ' of the DLR tests.']
    ];
    $('#qgrid').innerHTML = q.map(function (x, i) { return '<div' + (i === 3 ? ' class="loss"' : '') + '><b>' + x[0] + '</b>' + x[1] + '</div>'; }).join('');
    $('#bluf-last').textContent = H.caughtRange === 0 ? 'A range limit catches none of these faults, because a frozen sensor, a missing row or a late valve never leaves the normal range.'
      : 'A range limit catches few of these faults, because a frozen sensor, a missing row or a late valve rarely leaves the normal range.';
    $('#nper').textContent = D.nPer;
    $('#bluf-h2').textContent = 'The checker catches ' + pct(H.caught, H.planted) + ' percent of planted faults; a range limit catches ' + words(H.caughtRange);
    $('#buildinfo').textContent = 'built ' + D.built + (D.code ? ' from code ' + D.code : '');
  }

  /* ---------------- the answer chart ---------------- */
  var ROWS = [{ k: null, label: 'All planted faults' }, { k: 'rows_missing' }, { k: 'rows_repeated' }, { k: 'flat' }, { k: 'valve_late' }, { k: 'flat_noisy', loss: true }];
  var mDesc = D.roc.healthy.map(function (h) { return h[2]; }).sort(function (a, b) { return b - a; });
  function sOf(pos) { return Math.pow(20, (pos - 50) / 50); }
  function atSetting(s) {
    var hs = D.roc.healthy, k = 0;
    hs.forEach(function (h) { if (h[1] > s) k++; });
    var mThr = k < mDesc.length ? mDesc[k] : -Infinity, kr = 0;
    hs.forEach(function (h) { if (h[2] > mThr) kr++; });
    var rows = ROWS.map(function (r) {
      var ki = r.k === null ? -1 : D.roc.kinds.indexOf(r.k), n = 0, c = 0, g = 0;
      D.roc.planted.forEach(function (p) { if (ki >= 0 && p[0] !== ki) return; n++; if (p[3] > s) c++; if (p[4] > mThr) g++; });
      return { r: r, n: n, c: c, g: g, ki: ki };
    });
    return { k: k, kr: kr, n: hs.length, rows: rows, mThr: mThr };
  }
  function bluf() {
    var bars = $('#bars');
    bars.innerHTML = ROWS.map(function (r, i) {
      var ki = r.k === null ? -1 : D.roc.kinds.indexOf(r.k);
      var label = r.k === null ? r.label : D.roc.kindNames[ki];
      return '<div class="brow' + (r.k === null ? ' all' : '') + (r.loss ? ' loss' : '') + '" data-i="' + i + '"><div class="bl">' + label +
        '<small id="bn' + i + '"></small></div><div class="btrack"><div class="floor"></div><div class="bar c"></div><div class="bar r"></div>' +
        '<div class="bval c"></div><div class="bval r"></div></div></div>';
    }).join('');
    $('#ticks').innerHTML = [0, 25, 50, 75, 100].map(function (v) { return '<span style="left:' + v + '%">' + v + '%</span>'; }).join('');
    var sl = $('#sslider');
    function draw() {
      var s = sOf(+sl.value), res = atSetting(s);
      $('#slabel').textContent = s.toFixed(2);
      res.rows.forEach(function (row, i) {
        var el = bars.querySelector('.brow[data-i="' + i + '"]'), tr = $('.btrack', el);
        var fc = row.n ? row.c / row.n : 0, fg = row.n ? row.g / row.n : 0;
        $('.bar.c', el).style.width = (100 * fc) + '%';
        $('.bar.r', el).style.width = (100 * fg) + '%';
        var fl = res.k / res.n;
        placeVal($('.bval.c', el), fc, sh(fc) + '  ' + row.c + ' of ' + row.n, tr, '#fff', fl);
        placeVal($('.bval.r', el), fg, sh(fg) + '  ' + row.g + ' of ' + row.n, tr, '#1a1d21', fl);
        $('#bn' + i).textContent = row.n + ' planted';
      });
      positionFloor(res.k / res.n);
      $('#blufstat').innerHTML =
        '<div><div class="k">Planted faults caught</div><div class="n">' + res.rows[0].c + ' / ' + res.rows[0].g + '</div><div class="s">checker / range limit, of ' + res.rows[0].n + '</div></div>' +
        '<div><div class="k">Healthy sites flagged</div><div class="n">' + res.k + ' / ' + res.kr + '</div><div class="s">checker / range limit, of ' + res.n + ' in the measured runs</div></div>' +
        '<div><div class="k">Random flagging catches</div><div class="n">' + pct(res.k, res.n, 1) + '%</div><div class="s">flagging as many sites as the checker, blindly</div></div>';
    }
    function positionFloor(f) {
      bars.querySelectorAll('.floor').forEach(function (fl) { fl.style.left = (100 * f) + '%'; });
    }
    function sh(f) { return f > 0 && f < 0.01 ? (100 * f).toFixed(1) + '%' : Math.round(100 * f) + '%'; }
    function placeVal(v, f, str, tr, inside, floor) {
      v.textContent = str;
      var w = tr.clientWidth, tw = v.offsetWidth || 90;
      if (f * w + tw + 6 > w) { v.style.left = Math.max(4, f * w - tw - 6) + 'px'; v.style.color = inside; }
      else { v.style.left = (Math.max(f, floor + 0.004) * w + 6) + 'px'; v.style.color = ''; }
    }
    sl.addEventListener('input', draw);
    window.addEventListener('resize', draw);
    draw();
  }

  /* ---------------- the stands ---------------- */
  function standsTable() {
    var t = $('#standtable');
    $('thead', t).innerHTML = '<tr><th>Stand</th><th>Published by</th><th>Licence</th><th class="r">Runs</th><th class="r">Fit / measured</th></tr>';
    $('tbody', t).innerHTML = D.roc.stands.map(function (k) {
      var s = D.stands[k];
      return '<tr><td><b>' + esc(s.title) + '</b><div class="small">' + esc(s.what) + '</div></td><td>' + esc(s.publisher) +
        '<div class="small"><a href="' + s.url + '">' + esc(s.where) + '</a></div></td><td><a href="' + s.licence_url + '">' + esc(s.licence) +
        '</a></td><td class="r num">' + s.runs + (s.emptyFiles ? '<div class="small">+' + s.emptyFiles + ' empty files</div>' : '') +
        '</td><td class="r num">' + s.fit + ' / ' + s.measured + '</td></tr>';
    }).join('');
  }

  /* ---------------- line charts ---------------- */
  function lineChart(holder, pn, opts) {
    opts = opts || {};
    var W = Math.max(280, holder.clientWidth || 600), Hh = opts.h || (W < 520 ? 130 : 150);
    var m = { l: 50, r: 10, t: pn.unit ? 20 : 10, b: 26 };
    var svg = svgEl('svg', { width: W, height: Hh, viewBox: '0 0 ' + W + ' ' + Hh, role: 'img', 'aria-label': pn.title || '' });
    var xs = [], ys = [];
    pn.series.forEach(function (s) { xs = xs.concat(s.t); ys = ys.concat(s.y); });
    var x0 = opts.x0 !== undefined ? opts.x0 : Math.min.apply(null, xs), x1 = opts.x1 !== undefined ? opts.x1 : Math.max.apply(null, xs);
    var y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    if (y1 - y0 < 1e-9) { y0 -= 1; y1 += 1; }
    var pad = (y1 - y0) * 0.08; y0 -= pad; y1 += pad;
    var X = function (v) { return m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r); };
    var Y = function (v) { return Hh - m.b - (v - y0) / (y1 - y0) * (Hh - m.t - m.b); };
    (pn.bands || []).forEach(function (b) {
      var a = Math.max(x0, b.t0), z = Math.min(x1, b.t1);
      if (z < a) return;
      var col = b.kind === 'miss' ? 'rgba(138,90,158,.20)' : b.kind === 'gap' ? 'rgba(176,58,58,.55)' : b.kind === 'plant' ? 'rgba(180,118,10,.16)' : 'rgba(176,58,58,.13)';
      svgEl('rect', { x: X(a), y: m.t, width: Math.max(b.kind === 'gap' ? 1.5 : 2, X(z) - X(a)), height: Hh - m.t - m.b, fill: col }, svg);
    });
    var yt = niceTicks(y0, y1, 3);
    yt.forEach(function (v) {
      svgEl('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: '#ece9e4' }, svg);
      text(svg, m.l - 6, Y(v) + 4, tickLabel(v), { 'text-anchor': 'end', 'font-family': 'IBM Plex Mono, monospace', 'font-size': 10 });
    });
    var span = x1 - x0, ms = span < 0.5;
    niceTicks(ms ? x0 * 1000 : x0, ms ? x1 * 1000 : x1, W < 520 ? 3 : 5).forEach(function (v) {
      var xv = ms ? v / 1000 : v;
      var xp = X(xv), anchor = xp > W - 34 ? 'end' : xp < m.l + 20 ? 'start' : 'middle';
      text(svg, anchor === 'end' ? W - 2 : xp, Hh - 8, tickLabel(v) + (ms ? ' ms' : ' s'), { 'text-anchor': anchor, 'font-family': 'IBM Plex Mono, monospace', 'font-size': 10 });
    });
    svgEl('line', { x1: m.l, x2: W - m.r, y1: Hh - m.b, y2: Hh - m.b, stroke: '#c9c5be' }, svg);
    if (pn.unit) text(svg, m.l, 11, pn.unit, { 'font-family': 'IBM Plex Mono, monospace', 'font-size': 10, fill: '#808a96' });
    var order = pn.series.slice().sort(function (a, b) { return (a.role === 'main') - (b.role === 'main'); });
    order.forEach(function (s) {
      var d = '';
      for (var i = 0; i < s.t.length; i++) {
        if (s.t[i] < x0 || s.t[i] > x1) continue;
        var px = X(s.t[i]).toFixed(1), py = Y(s.y[i]).toFixed(1);
        if (pn.step && d) d += 'H' + px + 'V' + py; else d += (d ? 'L' : 'M') + px + ',' + py;
      }
      var st = s.role === 'main' ? { stroke: '#2c4a6b', 'stroke-width': 1.6 } : s.role === 'cmd' ? { stroke: '#b4760a', 'stroke-width': 1.6 } :
        s.role === 'orig' ? { stroke: '#b9bec4', 'stroke-width': 2.2 } : { stroke: '#9aa1a9', 'stroke-width': 1 };
      svgEl('path', Object.assign({ d: d, fill: 'none', 'stroke-linejoin': 'round' }, st), svg);
    });
    holder.innerHTML = '';
    holder.appendChild(svg);
  }

  /* ---------------- act one ---------------- */
  var showIdx = 0;
  function showcase() {
    var chips = $('#showchips');
    chips.innerHTML = D.showcase.map(function (s, i) { return '<button class="chip" aria-pressed="' + (i === showIdx) + '" data-i="' + i + '">' + esc(s.chip) + '</button>'; }).join('');
    chips.onclick = function (e) { var b = e.target.closest('.chip'); if (!b) return; showIdx = +b.dataset.i; showcase(); };
    var s = D.showcase[showIdx];
    $('#showlede').textContent = s.lede;
    var holder = $('#showpanels');
    holder.innerHTML = s.panels.map(function (p, i) {
      var names = p.series.map(function (q) { return q.role === 'twin' ? '<span class="small"> beside it, in grey: ' + esc(q.name) + '</span>' : ''; }).join('');
      return '<div class="panel"><h4>' + esc(p.title) + names + '</h4><div class="viz" id="sp' + i + '"></div></div>';
    }).join('');
    s.panels.forEach(function (p, i) { lineChart($('#sp' + i), p); });
    var rep = D.reports.filter(function (r) { return r.id === s.run; })[0];
    var fails = rep.rows.filter(function (r) { return r.status === 'FAIL'; });
    var missed = D.findings.filter(function (f) { return f.label === 'missed' && f.runs.indexOf(rep.label) >= 0; });
    $('#v1').innerHTML = '<p><span class="opener">The report for ' + esc(rep.label) + ' fails ' + fails.length + ' of its ' + rep.rows.length +
      ' sites.</span>' + (fails.length ? ' The failed lines:' : '') + '</p>' + (fails.length ? '<ul class="small" style="padding-left:18px;margin-bottom:8px">' +
      fails.map(function (r) { return '<li><b>' + esc(r.label) + '</b>: ' + esc(r.text) + '.</li>'; }).join('') + '</ul>' : '') +
      (missed.length ? '<p>Missed in this run: ' + missed.map(function (f) { return '<b>' + esc(f.siteLabel) + '</b>'; }).join(', ') + ', which act two explains.</p>' : '');
  }

  /* ---------------- act two ---------------- */
  var fFilter = 'real', fOpen = -1;
  function findings() {
    var F = D.findings, cnt = function (l) { return F.filter(function (f) { return l === 'all' || f.label === l; }).length; };
    var opts = [['real', 'Real problems'], ['missed', 'Missed by both'], ['false', 'False alarms'], ['all', 'Everything']];
    $('#fchips').innerHTML = opts.map(function (o) { return '<button class="chip" aria-pressed="' + (o[0] === fFilter) + '" data-f="' + o[0] + '">' + o[1] + ' (' + cnt(o[0]) + ')</button>'; }).join('');
    $('#fchips').onclick = function (e) { var b = e.target.closest('.chip'); if (!b) return; fFilter = b.dataset.f; fOpen = -1; findings(); };
    var t = $('#ftable');
    $('thead', t).innerHTML = '<tr><th>Finding</th><th>Checker</th><th>Range limit</th><th>My label</th></tr>';
    var rows = F.map(function (f, i) { return [f, i]; }).filter(function (x) { return fFilter === 'all' || x[0].label === fFilter; });
    var lab = { real: 'real problem', missed: 'missed', 'false': 'false alarm' };
    $('tbody', t).innerHTML = rows.map(function (x) {
      var f = x[0], i = x[1];
      var dateOf = function (l) { return l.slice(l.lastIndexOf(', ') + 2); };
      var sameDay = f.runs.every(function (l) { return dateOf(l) === dateOf(f.runs[0]); });
      var where = f.count > 1 ? f.count + ' runs' + (sameDay ? ' of ' + esc(dateOf(f.runs[0])) : '') : esc(f.runs[0]);
      var tr = '<tr class="frow' + (i === fOpen ? ' open' : '') + '" data-i="' + i + '"><td><b>' + esc(f.siteLabel) + '</b><div class="small">' + where +
        ' &middot; ' + esc(D.stands[f.stand].title) + '</div></td><td>' + (f.checker ? '<span class="yes">flagged</span>' : '<span class="no">passed</span>') +
        '</td><td>' + (f.range ? '<span class="yes">flagged</span>' : '<span class="no">passed</span>') + '</td><td><span class="pill ' + f.label + '">' + lab[f.label] + '</span></td></tr>';
      if (i === fOpen) {
        tr += '<tr class="reason"><td colspan="4">' + esc(f.reason) + (f.checkerText ? '<div class="note">Checker: ' + esc(f.checkerText) + '.</div>' : '') +
          (f.rangeText ? '<div class="note">Range limit: ' + esc(f.rangeText) + '.</div>' : '') + '</td></tr>';
      }
      return tr;
    }).join('');
    $('tbody', t).onclick = function (e) { var r = e.target.closest('tr.frow'); if (!r) return; var i = +r.dataset.i; fOpen = fOpen === i ? -1 : i; findings(); };
    var fc = F.filter(function (f) { return f.label === 'false' && f.checker; }).reduce(function (a, f) { return a + f.count; }, 0);
    var byCat = function (cat) { return F.filter(function (f) { return f.label === 'false' && f.checker && f.category === cat; }).reduce(function (a, f) { return a + f.count; }, 0); };
    $('#act2-h2').textContent = 'On ' + D.totals.runs + ' public runs it flags ' + H.realChecker + ' of ' + H.realTotal + ' real problems; a range limit flags ' + H.realRange;
    $('#v2').innerHTML = '<p><span class="opener">On the real logs the checker flags ' + H.realChecker + ' of the ' + H.realTotal + ' problems I found; the range limit flags ' + H.realRange + '.</span> ' +
      'The range limit finds the dead thermocouples, because their readings fall outside what other runs showed. It cannot see a sensor frozen at a normal value or a dead input with no other run to compare against, and it does not read timestamps at all.</p>' +
      '<p>The checker raised ' + fc + ' false alarms. ' + byCat('range') + ' come from the range rule it shares with the range limit, on new operating points; ' +
      byCat('timing') + ' blame dropped rows for what is really two sensors saturating while a third is frozen; and ' + byCat('valve') +
      ' is an igniter output that floats after firing. Both checks missed ' + H.realMissedBoth + ' real problems, listed under "Missed by both".</p>';
  }

  /* ---------------- act three ---------------- */
  var HF = D.hotfire.filter(function (r) { return r.split === 'fit'; })[0];
  var KN = { flat: 'Frozen flat', flat_noisy: 'Frozen, noise kept', rows_missing: 'Rows missing', rows_repeated: 'Rows repeated', valve_late: 'Valve late' };
  var plantState = { site: 'channel:pc', kind: 'flat' };
  function sizeOf(kind, pos) {
    if (kind === 'rows_missing' || kind === 'rows_repeated') return Math.max(1, Math.round(Math.pow(2, pos / 100 * 5)));
    if (kind === 'valve_late') return pos >= 98 ? 'never' : +(0.01 * Math.pow(300, pos / 98)).toPrecision(2);
    return +(0.01 * Math.pow(500, pos / 100)).toPrecision(2);
  }
  function sizeText(kind, v) {
    if (v === 'never') return 'never answers';
    if (kind === 'rows_missing' || kind === 'rows_repeated') return v + ' row' + (v === 1 ? '' : 's');
    return SC.fmtDur(v) + (kind === 'valve_late' ? ' late' : '');
  }
  function kindsFor(site) {
    var k = site.split(':')[0];
    return k === 'stream' ? ['rows_missing', 'rows_repeated'] : k === 'valve' ? ['valve_late'] : ['flat', 'flat_noisy'];
  }
  function plantSetup() {
    var sel = $('#psite'), opts = '<optgroup label="Channels">';
    Object.keys(HF.channels).forEach(function (c) { if (HF.channels[c].role === 'live') opts += '<option value="channel:' + esc(c) + '">' + esc(HF.channels[c].label) + '</option>'; });
    opts += '</optgroup><optgroup label="Valves">';
    HF.valves.forEach(function (v) { opts += '<option value="valve:' + esc(v.name) + '">' + esc(v.label) + '</option>'; });
    opts += '</optgroup><optgroup label="Record"><option value="stream:telemetry">The whole record (every channel)</option></optgroup>';
    sel.innerHTML = opts;
    sel.value = plantState.site;
    sel.onchange = function () { plantState.site = sel.value; plantState.kind = kindsFor(sel.value)[0]; $('#psize').value = 50; plantKinds(); plant(); };
    $('#pat').value = Math.round(100 * (2.0 - HF.active[0]) / (HF.active[1] - HF.active[0]));
    $('#psize').value = 77;
    $('#psize').oninput = plant; $('#pat').oninput = plant;
    plantKinds();
  }
  function plantKinds() {
    $('#pkinds').innerHTML = kindsFor(plantState.site).map(function (k) { return '<button class="chip" aria-pressed="' + (k === plantState.kind) + '" data-k="' + k + '">' + KN[k] + '</button>'; }).join('');
    $('#pkinds').onclick = function (e) { var b = e.target.closest('.chip'); if (!b) return; plantState.kind = b.dataset.k; plantKinds(); plant(); };
  }
  function verdictBox(title, s, sPub, which, key, run) {
    var fail, txt, pub;
    if (which === 'checker') {
      fail = s.score > 1; txt = SC.verdict(run, key, s); pub = sPub.score > 1;
    } else {
      var kind = key.split(':')[0];
      if (s.m === -1) { return '<div><div class="k">' + title + '</div><span class="pill">does not apply</span> ' +
        (kind === 'stream' ? 'A range limit reads values, not timestamps, so it never judges a record.' : 'This valve\'s feedback is a channel of its own; the range limit judges it there, not as a valve.') + '</div>'; }
      fail = s.m > SC.RANGE_MARGIN; pub = sPub.m > SC.RANGE_MARGIN;
      txt = kind === 'channel' ? (fail ? 'reads ' + SC.fmtVal(s.range.value) + ' at t = ' + s.range.t.toFixed(3) + ' s, outside its limits' : 'stays inside its limits')
        : (fail ? 'the output voltage leaves its range' : 'the output voltage stays inside its range');
    }
    return '<div><div class="k">' + title + '</div><span class="pill ' + (fail ? 'fail' : 'pass') + '">' + (fail ? 'fail' : 'pass') + '</span> ' + esc(txt) +
      '<div class="note">On the log as published: ' + (pub ? 'fail' : 'pass') + '.</div></div>';
  }
  function plant() {
    var key = plantState.site, kind = plantState.kind;
    var size = sizeOf(kind, +$('#psize').value);
    var at = HF.active[0] + (+$('#pat').value) / 100 * (HF.active[1] - HF.active[0]);
    $('#psizelab').textContent = sizeText(kind, size);
    $('#patlab').textContent = 't = ' + at.toFixed(2) + ' s' + (kind === 'valve_late' ? ' (the nearest command change is used)' : '');
    var res = SC.plant(HF, key, kind, size, at);
    var sNew = SC.siteScore(res.run, key), sPub = SC.siteScore(HF, key);
    var name = key.slice(key.indexOf(':') + 1);
    var chName = key.indexOf('channel:') === 0 ? name : key.indexOf('valve:') === 0 ? res.fb : 'pc';
    var w0 = Math.max(HF.t[0], res.t0 - 1.5), w1 = Math.min(HF.t[HF.t.length - 1], Math.max(res.t1, res.t0 + 0.05) + 1.5);
    var pick = function (run) {
      var tt = [], yy = [];
      for (var i = 0; i < run.t.length; i++) if (run.t[i] >= w0 && run.t[i] <= w1) { tt.push(run.t[i]); yy.push(run.channels[chName].x[i]); }
      return { t: tt, y: yy };
    };
    var a = pick(HF), b = pick(res.run);
    lineChart($('#plantviz'), { title: '', unit: HF.channels[chName].unit + '  ' + HF.channels[chName].label, series: [
      { name: 'published', t: a.t, y: a.y, role: 'orig' }, { name: 'with the fault', t: b.t, y: b.y, role: 'main' }],
      bands: [{ t0: res.t0, t1: Math.max(res.t1, res.t0 + 0.004), kind: 'plant' }] }, { x0: w0, x1: w1, h: 190 });
    $('#presult').innerHTML = verdictBox('Checker, with your fault', sNew, sPub, 'checker', key, res.run) + verdictBox('Range limit, with your fault', sNew, sPub, 'range', key, res.run);
  }

  function sizeCharts() {
    var holder = $('#sizeviz');
    var html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px 22px">';
    D.roc.kinds.forEach(function (k, ki) { html += '<div><h4 style="font-size:13px">' + esc(D.roc.kindNames[ki]) + '</h4><div class="viz" id="sz' + ki + '"></div></div>'; });
    holder.innerHTML = html + '</div><div class="legend"><span><i style="background:var(--accent)"></i>this checker</span><span><i style="background:var(--grey)"></i>range limit</span></div>';
    D.roc.kinds.forEach(function (k, ki) {
      var sizes = D.roc.sizes[ki], box = $('#sz' + ki), W = Math.max(250, box.clientWidth || 300), Hh = 150, m = { l: 36, r: 8, t: 8, b: 30 };
      var svg = svgEl('svg', { width: W, height: Hh, viewBox: '0 0 ' + W + ' ' + Hh });
      var X = function (i) { return m.l + (i + 0.5) / sizes.length * (W - m.l - m.r); }, Y = function (v) { return Hh - m.b - v * (Hh - m.t - m.b); };
      [0, 0.5, 1].forEach(function (v) { svgEl('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: '#ece9e4' }, svg); text(svg, m.l - 5, Y(v) + 4, (100 * v) + '%', { 'text-anchor': 'end', 'font-size': 10, 'font-family': 'IBM Plex Mono, monospace' }); });
      var pts = { c: [], r: [] };
      sizes.forEach(function (s, si) {
        var n = 0, c = 0, g = 0;
        D.roc.planted.forEach(function (p) { if (p[0] === ki && p[1] === si) { n++; if (p[3] > 1) c++; if (p[4] > SC.RANGE_MARGIN) g++; } });
        pts.c.push([X(si), Y(n ? c / n : 0)]); pts.r.push([X(si), Y(n ? g / n : 0)]);
        var lab = s === 'never' ? 'never' : (k.indexOf('rows') === 0 ? String(s) : (s < 1 ? (s * 1000) + 'ms' : s + 's'));
        text(svg, X(si), Hh - 14, lab, { 'text-anchor': 'middle', 'font-size': 9.5, 'font-family': 'IBM Plex Mono, monospace' });
      });
      text(svg, (m.l + W - m.r) / 2, Hh - 2, k.indexOf('rows') === 0 ? 'rows' : 'duration', { 'text-anchor': 'middle', 'font-size': 10 });
      ['r', 'c'].forEach(function (w) {
        var col = w === 'c' ? '#2c4a6b' : '#9aa1a9';
        svgEl('path', { d: 'M' + pts[w].map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join('L'), fill: 'none', stroke: col, 'stroke-width': 1.6 }, svg);
        pts[w].forEach(function (p) { svgEl('circle', { cx: p[0], cy: p[1], r: w === 'c' ? 3.2 : 2.6, fill: col }, svg); });
      });
      box.appendChild(svg);
    });
    // the sting below the panels, from the same counts
    var zeroUpTo = function (k) {
      var ki = D.roc.kinds.indexOf(k), sizes = D.roc.sizes[ki], last = null;
      for (var si = 0; si < sizes.length; si++) {
        var c = D.roc.planted.filter(function (p) { return p[0] === ki && p[1] === si && p[3] > 1; }).length;
        if (c === 0) last = sizes[si]; else break;
      }
      return last;
    };
    var nk = H.perKind.flat_noisy, fl = zeroUpTo('flat'), rr = zeroUpTo('rows_repeated'), vl = zeroUpTo('valve_late');
    $('#v3').innerHTML = '<p><span class="opener">Below its thresholds the checker catches nothing.</span> No single repeated row' +
      (rr && rr > 1 ? ' and nothing up to ' + rr + ' rows' : '') + ' is caught, no freeze of ' + SC.fmtDur(fl) + ' or less, and no valve late by ' + SC.fmtDur(vl) +
      ' or less, because each sits inside the allowance for normal behaviour. Freezes are caught from about the length of their channel\'s limit: ' +
      SC.fmtDur(D.thresholds.flat.p_fast) + ' for fast pressure, ' + SC.fmtDur(D.thresholds.flat.p_slow) + ' for slow pressure and load, ' + SC.fmtDur(D.thresholds.flat.temp) + ' for temperature.</p>' +
      '<p>A sensor frozen with its noise kept is caught ' + nk.checker + ' time in ' + nk.n + ', at every size. That is the blind spot the coda describes, with what would fix it.</p>';
  }

  /* ---------------- act four ---------------- */
  function reportSetup() {
    var sel = $('#rsel'), html = '';
    D.roc.stands.forEach(function (k) {
      html += '<optgroup label="' + esc(D.stands[k].title) + '">';
      D.reports.forEach(function (r) { if (r.stand === k) html += '<option value="' + r.id + '">' + esc(r.label) + ' (' + r.split + ', ' + r.verdict.toLowerCase() + ')</option>'; });
      html += '</optgroup>';
    });
    sel.innerHTML = html;
    sel.value = 'sterenberg-2018-03-17';
    sel.onchange = renderReport;
    $('#printbtn').onclick = function () {
      var pa = $('#printarea');
      pa.innerHTML = '<div class="wrap">' + $('#report').outerHTML.replace('id="report"', '') + '</div>';
      document.body.classList.add('printing');
      window.print();
      setTimeout(function () { document.body.classList.remove('printing'); }, 400);
    };
    renderReport();
  }
  function renderReport() {
    var r = D.reports.filter(function (x) { return x.id === $('#rsel').value; })[0], st = D.stands[r.stand];
    var src = r.source.file + (r.source.sha256 ? ', sha256 ' + r.source.sha256.slice(0, 16) : r.source.md5_archive ? ', archive md5 ' + r.source.md5_archive.slice(0, 16) : '');
    var nf = r.rows.filter(function (x) { return x.status === 'FAIL'; }).length;
    var h = '<div id="rephead"><div class="card-title">Post-test data check</div>' +
      '<div class="rep-head"><div><b>Stand</b>' + esc(st.title) + '</div><div><b>Run</b>' + esc(r.label) + '</div><div><b>Date</b>' + esc(r.date) + '</div>' +
      '<div><b>Source</b>' + esc(src) + '</div><div><b>Published by</b>' + esc(st.publisher) + ', ' + esc(st.licence) + '</div>' +
      '<div><b>Checked with</b>stand-check ' + esc(D.code || '') + ', thresholds as planned</div></div>' +
      '<div class="rep-verdict ' + r.verdict.toLowerCase() + '">' + (r.verdict === 'FAIL' ? 'Fail: ' + nf + ' of ' + r.rows.length + ' sites' : 'Pass: all ' + r.rows.length + ' sites') + '</div></div>';
    ['Records', 'Channels', 'Valves'].forEach(function (sec) {
      var rows = r.rows.filter(function (x) { return x.sec === sec; });
      h += '<div class="rep-sec">' + sec + '</div>';
      if (!rows.length) { h += '<p class="small">' + (sec === 'Valves' ? 'No valve with a command and a feedback is logged, so no valve check is possible.' : 'None.') + '</p>'; return; }
      rows.sort(function (a, b) { return (a.status === 'PASS') - (b.status === 'PASS'); });
      h += '<div class="tscroll"><table><tbody>' + rows.map(function (x) {
        return '<tr><td style="width:62px"><span class="pill ' + x.status.toLowerCase() + '">' + x.status.toLowerCase() + '</span></td><td style="width:36%"><b>' + esc(x.label) +
          '</b><div class="small mono">' + esc(x.name) + '</div></td><td class="small">' + esc(x.text) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    });
    if (r.spare.length) h += '<p class="note">Not checked, because the documentation does not name them: ' + esc(r.spare.join(', ')) + '.</p>';
    if (r.notes.length) h += '<div class="rep-sec">Notes</div><ul class="small" style="padding-left:18px">' + r.notes.map(function (n) { return '<li>' + esc(n) + '</li>'; }).join('') + '</ul>';
    h += '<div class="sign"><div>Checked by (name, date)</div><div>Approved by (name, date)</div></div>';
    $('#report').innerHTML = h;
  }

  /* ---------------- coda ---------------- */
  function coda() {
    var c = 0, g = 0, fc = 0, fr = 0;
    D.roc.planted.forEach(function (p) { if (p[3] > 1) c++; if (p[4] > SC.RANGE_MARGIN) g++; });
    D.roc.healthy.forEach(function (h) { if (h[1] > 1) fc++; if (h[2] > SC.RANGE_MARGIN) fr++; });
    var worst = 0, n = 0, bad = 0;
    D.hotfire.forEach(function (run) {
      SC.siteKeys(run).forEach(function (k) {
        var s = SC.siteScore(run, k), p = run.python[k]; n++;
        var d = Math.max(Math.abs(s.score - p[0]) / Math.max(1e-9, Math.abs(p[0])), Math.abs(s.m - p[1]) / Math.max(1e-9, Math.abs(p[1])));
        if (d > 1e-9) bad++;
        worst = Math.max(worst, d);
      });
    });
    var ok = c === H.caught && g === H.caughtRange && fc === H.falseChecker && fr === H.falseRange && bad === 0;
    $('#selfcheck').innerHTML = 'Counted here, in your browser, from the per-site scores: <b>' + c + '</b> of ' + D.roc.planted.length + ' planted faults caught by the checker (the build says ' + H.caught +
      '), <b>' + g + '</b> by the range limit (build: ' + H.caughtRange + '), and <b>' + fc + '</b> and <b>' + fr + '</b> false alarms on ' + D.roc.healthy.length + ' healthy sites (build: ' +
      H.falseChecker + ' and ' + H.falseRange + '). The JavaScript checker re-checked both hotfire logs: ' + (n - bad) + ' of ' + n + ' site scores match the Python build, the largest relative difference ' +
      (worst === 0 ? 'zero' : worst.toExponential(1)) + '. ' + (ok ? 'Everything agrees.' : '<b>Something disagrees; the numbers above should not be trusted until it is fixed.</b>');

    var S = D.stands, ms = S.dlr.measured + S.delft.measured + S.sterenberg.measured;
    $('#splittext').innerHTML = 'Thresholds were set by looking only at the <b>fit runs</b>: the 2019 hotfire log, the three DLR tests of 3 August 2020 and the ' + S.delft.fit +
      ' Delft runs of 20 March 2024. The <b>' + ms + ' measured runs</b> (the 2018 hotfire, the six DLR tests of 5 and 6 August, and the Delft runs of 3 April and 29 May 2024) were checked once with the thresholds frozen, and every count of planted faults and false alarms comes from them. ' +
      'The split is by date, so it was not chosen by looking at results. The plan was committed to the repository before the measured runs were checked; act two\'s table covers both halves and says which each finding is in.';

    var th = D.thresholds;
    var rows = [
      ['What it is', 'A set of fixed rules with thresholds, one score per site: how many times over its threshold the worst evidence is.'],
      ['What it judges', 'Whether each record, live channel and valve in a run behaved like a working data acquisition system.'],
      ['Thresholds', 'Flat for longer than ' + SC.fmtDur(th.flat.p_fast) + ' (fast pressure), ' + SC.fmtDur(th.flat.p_slow) + ' (slow pressure, load), ' + SC.fmtDur(th.flat.temp) + ' (temperature), ' + SC.fmtDur(th.flat.pos) +
        ' (position, flow); a driver output in the wrong state ' + SC.fmtDur(th.wElec) + ' after a command; a motorised valve more than ' + th.posTol + ' degrees off ' + SC.fmtDur(th.wPos) + ' after a setpoint change; a pressure answering a valve more than ' + SC.fmtDur(th.wResp) + ' from its command; gaps against each record\'s own jitter.'],
      ['Fitted on', D.totals.fit + ' fit runs, by reading each channel type\'s longest normal flat stretch, interval and response time.'],
      ['Scored on', D.totals.measured + ' measured runs: ' + H.healthy + ' healthy sites for false alarms, and ' + H.planted + ' faults planted into them.'],
      ['False alarms', H.falseChecker + ' of ' + H.healthy + ' healthy sites (' + pct(H.falseChecker, H.healthy, 1) + ' percent); the range limit, ' + H.falseRange + '.'],
      ['Against a range limit', H.caught + ' of ' + H.planted + ' planted faults caught, against ' + H.caughtRange + ' for the range limit at the same false-alarm count.'],
      ['Verdict', 'Useful for what a range limit cannot see, at no extra false alarms on this data; blind to a frozen sensor that keeps its noise, and to anything shorter than its limits.']
    ];
    $('#mcard').innerHTML = rows.map(function (r) { return '<tr><td>' + r[0] + '</td><td class="small">' + r[1] + '</td></tr>'; }).join('');

    $('#planttext').textContent = 'Five kinds of fault at six or seven sizes each, ' + D.nPer + ' times per size: ' + H.planted + ' in all. Each went into a copy of a random measured run, at a random site that neither check flags as published, and at a random time between one second before the first valve command and one second after the last. The stands take turns, so the many Delft runs do not drown out the single measured hotfire, and a fault too long for a run is drawn again elsewhere. The random seed is ' + D.seed + '.';

    var nk = H.perKind.flat_noisy, X = D.extra;
    $('#lim1').textContent = 'Of ' + nk.n + ' planted, it caught ' + nk.checker + '.';
    $('#lim-clip').textContent = X.clipMsMin + ' to ' + X.clipMsMax + ' ms';
    $('#lim-fast').textContent = SC.fmtDur(D.thresholds.flat.p_fast);
    $('#lim-drift').textContent = X.delftDriftPct;
    $('#lim-hot').textContent = 'Of the ' + D.totals.measured + ' measured runs, ' + D.stands.sterenberg.measured + ' is a hotfire; the rest are igniter and cold-flow runs.';

    $('#sources').innerHTML = D.roc.stands.map(function (k) {
      var s = D.stands[k];
      return '<li><b>' + esc(s.title) + '</b>, ' + esc(s.publisher) + ', <a href="' + s.url + '">' + esc(s.where) + '</a>, licence <a href="' + s.licence_url + '">' + esc(s.licence) + '</a>.' +
        (k === 'sterenberg' ? ' Copyright 2019 Nicholas Sterenberg; the notice and licence travel with the data in the repository.' : '') + '</li>';
    }).join('') + '<li>The advertisement: Rocket Lab, Junior Ground Systems Engineer, Instrumentation &amp; Control, Auckland, Greenhouse job 8034180003, read 19 October 2026.</li>';
  }

  /* ---------------- the walkthrough ---------------- */
  function tour() {
    var root = $('#tour'), hl = $('.tour-hl', root), card = $('.tour-card', root), idx = 0;
    var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    var STEPS = [
      { sel: 'header h1', k: 'Welcome · 1 of 8', html: 'This page asks one question about test-stand data: <b>did the logger record what actually happened?</b> It answers with a checker run on ' + D.totals.runs + ' public runs from three projects.' },
      { sel: '#bars', k: 'The answer · 2 of 8', html: 'Each bar is the share of faults planted into real runs that a check caught. Dark is the checker, grey a range limit, dashed is blind luck. <b>Drag the slider</b> to make both checks stricter or looser.' },
      { sel: '#domainsvg', k: 'The domain · 3 of 8', html: 'What a stand logs, and the three faults that leave every value in range: a missing row, a frozen sensor, a valve that ignores its command.' },
      { sel: '#sp0', k: 'One run · 4 of 8', html: 'Real runs, read by the checker. <b>Click a run in the row of buttons above</b>: red shading is what it flagged, purple what it missed.' },
      { sel: '#fchips', k: 'The real logs · 5 of 8', html: 'Every flag on the public logs, labelled by me as a real problem or a false alarm. <b>Click a button here</b> to see the misses or the false alarms, and click a row in the table below for the reason.' },
      { sel: '#plantviz', k: 'Your turn · 6 of 8', html: '<b>Pick a channel, a fault and a size in the controls above.</b> The checker runs again in your browser and both verdicts update.' },
      { sel: '#rephead', k: 'The report · 7 of 8', html: 'The output is a pass or fail per record, channel and valve, with the evidence, ready to sign. <b>Pick any run</b> above it.' },
      { sel: '#limits p', k: 'What it cannot do · 8 of 8', html: 'The first of the blind spots, with its number and what would close it. The rest follow below.' }
    ];
    function place() {
      var st = STEPS[idx], elm = document.querySelector(st.sel);
      if (!elm) { next(); return; }
      var r = elm.getBoundingClientRect(), sx = window.scrollX, sy = window.scrollY;
      var docTop = r.top + sy, docLeft = r.left + sx;
      root.style.height = document.documentElement.scrollHeight + 'px';
      var maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
      var target = Math.max(0, Math.min(docTop - 14, maxScroll)), vTop = docTop - target;
      var cw = Math.min(400, innerWidth - 32), ch = 250;
      var fitsRight = r.left + r.width + 18 + cw <= innerWidth - 16;
      var hh = fitsRight ? r.height : Math.max(120, Math.min(r.height, innerHeight - vTop - ch - 40));
      hl.style.left = (docLeft - 8) + 'px'; hl.style.top = (docTop - 8) + 'px';
      hl.style.width = (r.width + 16) + 'px'; hl.style.height = (hh + 16) + 'px';
      var dots = STEPS.map(function (_, i) { return '<i class="' + (i === idx ? 'on' : '') + '"></i>'; }).join('');
      card.innerHTML = '<div class="tk">' + st.k + '</div><p>' + st.html + '</p><div class="tour-nav"><div class="dots">' + dots + '</div>' +
        (idx > 0 ? '<button class="tour-btn" id="tprev">Back</button>' : '') +
        '<button class="tour-btn" id="tskip">Close</button><button class="tour-btn primary" id="tnext">' + (idx < STEPS.length - 1 ? 'Next' : 'Done') + '</button></div>';
      var cx, cy;
      if (fitsRight) { cx = docLeft + r.width + 18; cy = docTop; }
      else { cx = Math.min(docLeft, sx + innerWidth - 16 - cw); cy = docTop + hh + 22; }
      card.style.left = Math.max(sx + 16, cx) + 'px';
      card.style.top = Math.max(target + 16, cy) + 'px';
      $('#tnext').onclick = next; $('#tskip').onclick = stop;
      var pv = $('#tprev'); if (pv) pv.onclick = function () { idx = Math.max(0, idx - 1); place(); };
      window.scrollTo({ top: target, behavior: reduced ? 'auto' : 'smooth' });
    }
    function next() { if (idx >= STEPS.length - 1) { stop(); return; } idx++; place(); }
    function stop() { root.classList.remove('on'); try { localStorage.setItem('sc-tour', 'seen'); } catch (e) { } }
    function start() { idx = 0; root.classList.add('on'); place(); }
    $('#tourbtn').addEventListener('click', start);
    var replace = function () { if (root.classList.contains('on')) place(); };
    window.addEventListener('resize', replace);
    window.addEventListener('load', replace);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(replace);
    var seen = false; try { seen = localStorage.getItem('sc-tour') === 'seen'; } catch (e) { }
    if (!seen && !location.search.includes('tour=off')) setTimeout(start, 700);
    window.__tour = { start: start, next: next, stop: stop, steps: STEPS.length };
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (typeof D === 'undefined') return;
    header();
    bluf();
    standsTable();
    var dom = $('#domainsvg');
    dom.innerHTML = DOMAIN_SVG;
    showcase();
    findings();
    plantSetup();
    plant();
    sizeCharts();
    reportSetup();
    coda();
    var wasW = window.innerWidth, timer = null;
    window.addEventListener('resize', function () {
      if (Math.abs(window.innerWidth - wasW) < 40) return;
      wasW = window.innerWidth;
      clearTimeout(timer);
      timer = setTimeout(function () { showcase(); plant(); sizeCharts(); }, 150);
    });
    tour();
  });

  var DOMAIN_SVG = '<svg viewBox="0 0 360 250" role="img" aria-label="A simplified test stand: a tank, a valve with a command and a feedback, a line to the engine on a load cell, and the sensors wired to the data acquisition box" font-family="IBM Plex Sans, system-ui, sans-serif" font-size="11" fill="#1a1d21">' +
    '<rect x="14" y="36" width="54" height="96" rx="20" fill="#f3f1ed" stroke="#5b6470"/><text x="41" y="148" text-anchor="middle">tank</text>' +
    '<line x1="68" y1="84" x2="248" y2="84" stroke="#5b6470" stroke-width="3"/>' +
    '<path d="M118 72 L118 96 L142 72 L142 96 Z" fill="#fff" stroke="#2c4a6b" stroke-width="2"/><text x="112" y="66" text-anchor="end">valve</text>' +
    '<rect x="102" y="10" width="56" height="22" rx="3" fill="#fff" stroke="#b4760a"/><text x="130" y="25" text-anchor="middle" font-size="10">controller</text>' +
    '<line x1="124" y1="32" x2="124" y2="72" stroke="#b4760a" stroke-dasharray="3 2"/><text x="129" y="54" font-size="9.5" fill="#b4760a">command</text>' +
    '<line x1="136" y1="96" x2="136" y2="196" stroke="#2c4a6b" stroke-dasharray="3 2"/><text x="140" y="140" font-size="9.5" fill="#2c4a6b">feedback</text>' +
    '<path d="M248 66 L288 70 L300 84 L288 98 L248 102 Z" fill="#f3f1ed" stroke="#5b6470"/><text x="276" y="120" text-anchor="middle">engine</text>' +
    '<rect x="252" y="128" width="48" height="12" fill="#fff" stroke="#5b6470"/><text x="304" y="138" font-size="10">load cell</text>' +
    '<circle cx="41" cy="30" r="8" fill="#fff" stroke="#2c4a6b"/><text x="41" y="33" text-anchor="middle" font-size="8">P</text>' +
    '<circle cx="200" cy="72" r="8" fill="#fff" stroke="#2c4a6b"/><text x="200" y="75" text-anchor="middle" font-size="8">P</text>' +
    '<circle cx="222" cy="72" r="8" fill="#fff" stroke="#2c4a6b"/><text x="222" y="75" text-anchor="middle" font-size="8">T</text>' +
    '<line x1="41" y1="38" x2="41" y2="22" stroke="none"/>' +
    '<rect x="70" y="196" width="220" height="40" rx="4" fill="#2c4a6b"/><text x="180" y="214" text-anchor="middle" fill="#fff" font-size="11">data acquisition</text>' +
    '<text x="180" y="228" text-anchor="middle" fill="#dfe6ee" font-size="9.5">one row per sample, every channel</text>' +
    '<path d="M33 30 L 6 30 L 6 216 L 70 216" fill="none" stroke="#9aa1a9" stroke-width="1"/>' +
    '<path d="M200 80 L 200 196" fill="none" stroke="#9aa1a9" stroke-width="1"/><path d="M222 80 L 222 196" fill="none" stroke="#9aa1a9" stroke-width="1"/>' +
    '<path d="M276 140 L 276 196" fill="none" stroke="#9aa1a9" stroke-width="1"/>' +
    '</svg>';
})();
