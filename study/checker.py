"""The checks. Every function returns a score: how many times over its threshold the worst
evidence is. A site is flagged at sensitivity s when its score is above s; s = 1 is the setting
fixed in PLAN.md. Scores of 1000 mean "flagged at any setting" (time running backwards), 100
means "the expected response never came".
"""
import math

import numpy as np

from stands import FLAT_LIMIT, CLASS_WORDS

ALWAYS, NEVER_CAME = 1000.0, 100.0
NO_RANGE = -1.0       # the range limit's margin score where it does not apply
MIN_FLAT = 5          # a flat stretch must be at least this many samples
RANGE_MARGIN = 0.10   # the range limit's own setting: 10 percent of the envelope's span
PERSIST = 3           # samples in a row for a range or valve flag
W_ELEC, W_POS, W_RESP = 0.1, 1.5, 1.0
POS_TOL = 10.0


def longest_true(mask):
    """Length and start index of the longest run of True."""
    if not len(mask) or not mask.any():
        return 0, 0
    m = np.r_[False, mask, False].astype(np.int8)
    d = np.diff(m)
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    k = int(np.argmax(ends - starts))
    return int(ends[k] - starts[k]), int(starts[k])


def flat(t, x):
    """Longest stretch of identical consecutive values: (samples, start index, seconds)."""
    if len(x) < 2:
        return 0, 0, 0.0
    run, i = longest_true(x[1:] == x[:-1])
    if not run:
        return 1, 0, 0.0
    n = run + 1
    return n, i, float(t[i + n - 1] - t[i])


def stuck(t, x, cls):
    n, i, dur = flat(t, x)
    limit = FLAT_LIMIT[cls]
    score = dur / limit if n >= MIN_FLAT else 0.0
    whole = n >= len(x) - 1
    if whole:
        ev = 'never changed: %s for the whole record' % fmt_val(x[0])
    else:
        ev = 'flat at %s for %s from t = %s (limit %s)' % (fmt_val(x[i]), fmt_dur(dur), fmt_t(t[i]), fmt_dur(limit))
    return score, dict(rule='stuck', samples=n, start=float(t[i]), seconds=dur, limit=limit, whole=bool(whole),
                       value=float(x[i]), text=ev)


def range_mstar(t, x, lo, hi):
    """Largest margin (in envelope spans) at which PERSIST samples in a row still sit outside."""
    span = max(hi - lo, 1e-9 * max(1.0, abs(hi)))
    e = np.maximum((lo - x) / span, (x - hi) / span)
    if len(e) >= PERSIST:
        w = np.minimum.reduce([e[k:len(e) - PERSIST + 1 + k] for k in range(PERSIST)])
    else:
        w = e
    j = int(np.argmax(w))
    return float(w[j]), dict(rule='range', t=float(t[j]), value=float(x[j]), lo=lo, hi=hi, span=span)


def range_text(ev, margin=RANGE_MARGIN):
    lo, hi = ev['lo'] - margin * ev['span'], ev['hi'] + margin * ev['span']
    return 'reads %s at t = %s; limits %s to %s' % (fmt_val(ev['value']), fmt_t(ev['t']), fmt_val(lo), fmt_val(hi))


def chance_repeat_rows(xs):
    """Longest run of whole-row repeats that chance alone would give about once in 100 records,
    from how often each channel repeats its previous value on its own."""
    n = len(xs[0])
    p = 1.0
    for x in xs:
        p *= max(float(np.mean(x[1:] == x[:-1])), 1e-12)
    if p >= 1.0:
        return float('inf')
    return max(1.0, math.log(100.0 * n) / math.log(1.0 / p))


def integrity(st, live, ref_duration):
    """Score for one stream. live is the list of live analog channel arrays in it."""
    t, n, parts, ev = st['t'], len(st['t']), {}, {}
    if st['timing'] == 'untimed':
        dur = n / st['rate']
        if ref_duration:
            rel = abs(dur - ref_duration) / ref_duration
            parts['length'] = rel / 0.10
            ev['length'] = 'record spans %s at %g a second; the reference record spans %s (%.0f percent apart, limit 10)' % (
                fmt_dur(dur), st['rate'], fmt_dur(ref_duration), 100 * rel)
    else:
        dt = np.diff(t)
        back = int((dt <= 0).sum())
        if back:
            parts['order'] = ALWAYS
            ev['order'] = '%d timestamp%s repeat or run backwards' % (back, '' if back == 1 else 's')
        pos = dt[dt > 0]
        med = float(np.median(pos))
        j = int(np.argmax(dt))
        if st['timing'] == 'irregular':
            parts['gap'] = float(dt[j]) / st['max_interval']
            ev['gap'] = 'longest wait between readings %s at t = %s (limit %s)' % (fmt_dur(dt[j]), fmt_t(t[j]), fmt_dur(st['max_interval']))
        else:
            jit = 1.4826 * float(np.median(np.abs(pos - med))) / med
            a0 = max(0.5, 4 * jit)
            parts['gap'] = max(0.0, (float(dt[j]) / med - 1) / a0)
            ev['gap'] = 'longest interval %s at t = %s against a normal %s (limit %s)' % (
                fmt_dur(dt[j]), fmt_t(t[j]), fmt_dur(med), fmt_dur(med * (1 + a0)))
            ev['missing'] = int(np.sum(np.maximum(0, np.round(dt[dt > med * (1 + a0)] / med) - 1)))
            if st.get('declared_rate'):
                expected = (t[-1] - t[0]) * st['declared_rate'] + 1
                short = 1 - n / expected
                parts['short'] = max(0.0, short) / 0.02
                ev['short'] = '%d rows where %g a second gives %d (%.1f percent short, limit 2)' % (
                    n, st['declared_rate'], round(expected), 100 * short)
    if len(live) >= 3:
        same = np.logical_and.reduce([x[1:] == x[:-1] for x in live])
        run, i = longest_true(same)
        lim = chance_repeat_rows(live)
        parts['repeat'] = run / lim if math.isfinite(lim) else 0.0
        if run:
            ev['repeat'] = '%d row%s in a row repeat the previous row in all %d live channels at t = %s (chance allows %.1f)' % (
                run, '' if run == 1 else 's', len(live), fmt_t(t[i + 1]), lim)
    score = max(parts.values()) if parts else 0.0
    worst = max(parts, key=parts.get) if parts else None
    return score, dict(rule='integrity', parts=parts, text=ev, worst=worst)


def ages(t, cmd):
    """Seconds since the last change of the command; before the first change, a large number."""
    edges = np.flatnonzero(np.diff(cmd) != 0) + 1
    last = np.full(len(t), -np.inf)
    last[edges] = t[edges]
    last = np.maximum.accumulate(last)
    a = t - last
    a[~np.isfinite(a)] = 1e3
    return a, edges


def windows_min(a):
    if len(a) < PERSIST:
        return a
    return np.minimum.reduce([a[k:len(a) - PERSIST + 1 + k] for k in range(PERSIST)])


def valve_electrical(t, cmd, v, batt):
    on, off = v >= 0.75 * batt, v <= 0.5 * batt
    mism = ((cmd > 0.5) & ~on) | ((cmd < 0.5) & ~off)
    age, edges = ages(t, cmd)
    w = windows_min(np.where(mism, age, 0.0)) / W_ELEC
    j = int(np.argmax(w)) if len(w) else 0
    score = float(w[j]) if len(w) else 0.0
    if score > 0:
        txt = 'commanded %s, output %s V (battery %s V) at t = %s, %s after the last command (limit %s)' % (
            'on' if cmd[j] > 0.5 else 'off', fmt_val(v[j]), fmt_val(batt[j]), fmt_t(t[j]), fmt_dur(age[j]), fmt_dur(W_ELEC))
    else:
        txt = 'output followed %s within %s' % (changes(len(edges), 'command change'), fmt_dur(W_ELEC))
    return score, dict(rule='valve', text=txt, edges=len(edges), t=float(t[j]))


def valve_position(t, sp, p):
    err = np.abs(p - sp)
    age, edges = ages(t, sp)
    w = windows_min(np.minimum(age / W_POS, err / POS_TOL))
    j = int(np.argmax(w)) if len(w) else 0
    score = float(w[j]) if len(w) else 0.0
    if score > 1:
        txt = 'position %s against setpoint %s at t = %s, %s after the last change (limits %g degrees, %s)' % (
            fmt_val(p[j]), fmt_val(sp[j]), fmt_t(t[j]), fmt_dur(age[j]), POS_TOL, fmt_dur(W_POS))
    else:
        txt = 'within %g degrees of its setpoint by %s after %s' % (POS_TOL, fmt_dur(W_POS), changes(len(edges), 'change', each=True))
    return score, dict(rule='valve', text=txt, edges=len(edges), t=float(t[j]))


def valve_response(t_c, cmd, t_r, r, sign, step):
    edges = np.flatnonzero(np.diff(cmd) != 0) + 1
    k = max(1, int(round(0.01 / (t_r[1] - t_r[0]))))
    rs = np.convolve(r, np.ones(k) / k, mode='same')
    scores, worst, taus = [], None, []
    for n_e, i in enumerate(edges):
        te = t_c[i]
        prev = t_c[edges[n_e - 1]] if n_e else -np.inf
        nxt = t_c[edges[n_e + 1]] if n_e + 1 < len(edges) else t_r[-1]
        a, b = max(prev, te - 1.5), te - 0.5
        if b <= a:
            a, b = max(prev, te - 0.5), te
        sel = (t_r >= a) & (t_r < b)
        pre = float(np.median(r[sel])) if sel.any() else float(rs[np.searchsorted(t_r, te)])
        d = sign if cmd[i] > 0.5 else -sign
        win = (t_r >= te - 1.0) & (t_r < nxt)
        hit = np.flatnonzero(win & (d * (rs - pre) >= step / 2))
        if len(hit):
            tau = float(t_r[hit[0]] - te)
            sc = abs(tau) / W_RESP
        else:
            tau, sc = None, NEVER_CAME
        taus.append(tau)
        scores.append(sc)
        if worst is None or sc > scores[worst]:
            worst = n_e
    score = max(scores) if scores else 0.0
    if not len(edges):
        txt = 'never commanded'
    elif taus[worst] is None:
        txt = 'commanded %s at t = %s; the pressure never moved by %s bar before the next command' % (
            'open' if cmd[edges[worst]] > 0.5 else 'shut', fmt_t(t_c[edges[worst]]), fmt_val(step / 2))
    else:
        txt = 'pressure answered the %s command at t = %s after %s (limit %s); %d commands checked' % (
            'open' if cmd[edges[worst]] > 0.5 else 'shut', fmt_t(t_c[edges[worst]]),
            ('%s early' % fmt_dur(-taus[worst])) if taus[worst] < 0 else fmt_dur(taus[worst]), fmt_dur(W_RESP), len(edges))
    return score, dict(rule='valve', text=txt, edges=int(len(edges)), lags=taus)


# ------------------------------------------------------------------ one run

def live_channels(run):
    return {c: ch for c, ch in run['channels'].items() if ch['role'] == 'live'}


def ref_duration(run, sname):
    st = run['streams'][sname]
    ref = st.get('ref')
    if not ref:
        return None
    r = run['streams'][ref]
    return len(r['t']) / r['rate']


def score_stream(run, sname):
    st = run['streams'][sname]
    live = [ch['x'] for ch in live_channels(run).values() if ch['stream'] == sname]
    return integrity(st, live, ref_duration(run, sname))


def score_channel(run, c, env):
    ch = run['channels'][c]
    t = run['streams'][ch['stream']]['t']
    s1, e1 = stuck(t, ch['x'], ch['cls'])
    lo, hi = env.get(run['stand'], c, run['run_id'])
    m, e2 = range_mstar(t, ch['x'], lo, hi)
    return s1, e1, m, e2


def score_valve(run, v):
    t = run['streams'][v['stream']]['t']
    fb = run['channels'][v['fb']]
    if v['kind'] == 'electrical':
        return valve_electrical(t, v['cmd'], fb['x'], v['batt'])
    if v['kind'] == 'position':
        return valve_position(t, v['cmd'], fb['x'])
    tr = run['streams'][fb['stream']]['t']
    return valve_response(t, v['cmd'], tr, fb['x'], v['sign'], v['step'])


def check_run(run, env):
    """Every site of one run: its checker score and the range limit's margin score (m*)."""
    sites = {}
    live = live_channels(run)
    # The range limit reads values, not timestamps, so it never marks a record (m = NO_RANGE). It
    # marks a valve only through a driver-output voltage, which has no channel site of its own;
    # a position or pressure feedback channel is judged once, at its own channel site.
    for sname in run['streams']:
        sc, ev = score_stream(run, sname)
        sites['stream:' + sname] = dict(kind='stream', name=sname, score=sc, m=NO_RANGE, ev=ev)
    for c in live:
        s1, e1, m, e2 = score_channel(run, c, env)
        sites['channel:' + c] = dict(kind='channel', name=c, score=max(s1, max(0.0, m) / RANGE_MARGIN),
                                     stuck=s1, m=m, ev=dict(stuck=e1, range=e2))
    for v in run['valves']:
        sc, ev = score_valve(run, v)
        sites['valve:' + v['name']] = dict(kind='valve', name=v['name'], score=sc, m=valve_range(run, v, env), ev=ev)
    return sites


def valve_range(run, v, env):
    fbc = v['fb']
    if run['channels'][fbc]['role'] != 'valve':
        return NO_RANGE
    t_fb = run['streams'][run['channels'][fbc]['stream']]['t']
    return range_mstar(t_fb, run['channels'][fbc]['x'], *env.get(run['stand'], fbc, run['run_id']))[0]


def envelopes(runs):
    """Each channel's minimum and maximum in every untouched run, for a range limit set from the
    stand's other runs. A channel that appears in only one run is limited by that run itself."""
    mm = {}
    for run in runs:
        for c, ch in run['channels'].items():
            if ch['role'] in ('live', 'valve'):
                mm.setdefault((run['stand'], c), {})[run['run_id']] = (float(np.min(ch['x'])), float(np.max(ch['x'])))
    return Envelopes(mm)


class Envelopes:
    def __init__(self, mm):
        self.mm = mm

    def get(self, stand, c, run_id):
        per = self.mm[(stand, c)]
        # A limit is set only from runs where the channel moved; a dead channel sets no range.
        others = [v for k, v in per.items() if k != run_id and v[1] > v[0]] or [per[run_id]]
        return min(v[0] for v in others), max(v[1] for v in others)

    def own_only(self, stand, c, run_id):
        return all(k == run_id for k in self.mm[(stand, c)])


# ------------------------------------------------------------------ wording

def changes(n, noun, each=False):
    if n == 1:
        return 'its one ' + noun
    return ('each of %d %ss' if each else 'all %d %ss') % (n, noun)


def fmt_val(v):
    v = float(v)
    if v == 0:
        return '0'
    a = abs(v)
    if a >= 1000:
        return '{:,.0f}'.format(v)
    if a >= 100:
        return '%.0f' % v
    if a >= 10:
        return '%.1f' % v
    if a >= 1:
        return '%.2f' % v
    return '%.3g' % v


def fmt_dur(s):
    s = float(s)
    if s >= 1:
        return '%.2f s' % s
    if s >= 0.001:
        return '%.0f ms' % (s * 1000) if s >= 0.01 else '%.1f ms' % (s * 1000)
    return '%.0f microseconds' % (s * 1e6)


def fmt_t(s):
    return '%.3f s' % float(s)


def site_label(run, key):
    kind, name = key.split(':', 1)
    if kind == 'stream':
        return '%s record' % name.capitalize()
    if kind == 'channel':
        ch = run['channels'][name]
        return ch['label']
    v = next(v for v in run['valves'] if v['name'] == name)
    return v['label']


def verdict_text(run, key, site, s=1.0):
    """One sentence of evidence for a site at sensitivity s."""
    if site['kind'] == 'stream':
        ev = site['ev']
        w = ev.get('worst')
        if site['score'] <= s or w is None:
            bits = [v for k, v in ev['text'].items() if k in ('gap', 'length', 'short')]
            return 'complete: ' + '; '.join(bits) if bits else 'complete'
        return ev['text'].get(w, '')
    if site['kind'] == 'channel':
        ev = site['ev']
        if site['stuck'] > s:
            return ev['stuck']['text']
        if max(0.0, site['m']) / RANGE_MARGIN > s:
            return range_text(ev['range'])
        return 'moving and inside its range'
    return site['ev']['text']
