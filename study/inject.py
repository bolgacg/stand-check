"""Planting faults into copies of real runs (PLAN.md, "Planted faults").

Each function returns (new_run, site_key, info) or None when the chosen site cannot take a fault
of that size. The original run is never changed: arrays that are touched are copied.
"""
import numpy as np

from checker import live_channels

KINDS = {
    'rows_missing': [1, 2, 4, 8, 16, 32],
    'rows_repeated': [1, 2, 4, 8, 16, 32],
    'flat': [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
    'flat_noisy': [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
    'valve_late': [0.03, 0.1, 0.3, 1.0, 3.0, 'never'],
}
KIND_SITE = {'rows_missing': 'stream', 'rows_repeated': 'stream', 'flat': 'channel',
             'flat_noisy': 'channel', 'valve_late': 'valve'}


def eligible(run, key, kind):
    k, name = key.split(':', 1)
    if k != KIND_SITE[kind]:
        return False
    if kind == 'rows_missing':
        return run['streams'][name]['timing'] != 'untimed'
    if kind == 'rows_repeated':
        return sum(1 for ch in live_channels(run).values() if ch['stream'] == name) >= 3
    return True


def shallow(run):
    new = dict(run)
    new['streams'] = {k: dict(v) for k, v in run['streams'].items()}
    new['channels'] = {k: dict(v) for k, v in run['channels'].items()}
    new['valves'] = [dict(v) for v in run['valves']]
    return new


def stream_arrays(run, sname):
    """Every array that shares the stream's rows: channels, and valve commands and battery."""
    out = [('channel', c) for c, ch in run['channels'].items() if ch['stream'] == sname]
    for i, v in enumerate(run['valves']):
        if v['stream'] == sname:
            out.append(('valve_cmd', i))
            if 'batt' in v:
                out.append(('valve_batt', i))
    return out


def get_arr(run, ref):
    kind, k = ref
    if kind == 'channel':
        return run['channels'][k]['x']
    return run['valves'][k]['cmd' if kind == 'valve_cmd' else 'batt']


def set_arr(run, ref, arr):
    kind, k = ref
    if kind == 'channel':
        run['channels'][k]['x'] = arr
    else:
        run['valves'][k]['cmd' if kind == 'valve_cmd' else 'batt'] = arr


def pick_start(t, a0, a1, rng, need=0.0, need_rows=0):
    """A random index whose time lies in [a0, a1] with room for the fault after it."""
    lo = int(np.searchsorted(t, a0))
    hi = int(np.searchsorted(t, min(a1, t[-1] - need), side='right')) - 1 - need_rows
    lo = max(lo, 1)
    if hi < lo:
        return None
    return int(rng.integers(lo, hi + 1))


def residual_noise(x, n, avoid, rng):
    """n samples of the channel's own noise (value minus a 21-sample running median), taken from
    another part of the same record."""
    from numpy.lib.stride_tricks import sliding_window_view
    k = 21
    if len(x) < k + n + 2:
        return np.zeros(n)
    pad = np.r_[np.full(k // 2, x[0]), x, np.full(k // 2, x[-1])]
    med = np.median(sliding_window_view(pad, k), axis=1)
    res = x - med
    for _ in range(50):
        s = int(rng.integers(0, len(x) - n))
        if s + n <= avoid[0] or s >= avoid[1]:
            return res[s:s + n]
    return res[:n]


def quantum(x):
    d = np.abs(np.diff(x))
    d = d[d > 0]
    if not len(d):
        return 0.0
    q = float(np.min(d))
    if q > 0 and np.all(np.abs(d / q - np.round(d / q)) < 1e-6):
        return q
    return 0.0


def plant(run, key, kind, size, rng):
    kind_site, name = key.split(':', 1)
    a0, a1 = run['active']
    new = shallow(run)
    if kind in ('rows_missing', 'rows_repeated'):
        st = run['streams'][name]
        t = st['t']
        i = pick_start(t, a0, a1, rng, need_rows=size + 1)
        if i is None:
            return None
        refs = stream_arrays(run, name)
        if kind == 'rows_missing':
            keep = np.r_[0:i, i + size:len(t)]
            new['streams'][name]['t'] = t[keep]
            for ref in refs:
                set_arr(new, ref, get_arr(run, ref)[keep])
        else:
            for ref in refs:
                x = get_arr(run, ref).copy()
                x[i:i + size] = x[i - 1]
                set_arr(new, ref, x)
        return new, key, dict(t=float(t[i]), rows=size)

    if kind in ('flat', 'flat_noisy'):
        ch = run['channels'][name]
        t = run['streams'][ch['stream']]['t']
        i = pick_start(t, max(a0, t[0]), a1, rng, need=size)
        if i is None:
            return None
        j = int(np.searchsorted(t, t[i - 1] + size, side='right'))
        j = max(j, i + 1)
        x = ch['x'].copy()
        hold = np.full(j - i, x[i - 1])
        if kind == 'flat_noisy':
            hold = hold + residual_noise(ch['x'], j - i, (i, j), rng)
            q = quantum(ch['x'])
            if q:
                hold = np.round(hold / q) * q
        x[i:j] = hold
        new['channels'][name]['x'] = x
        return new, key, dict(t=float(t[i - 1]), seconds=float(t[j - 1] - t[i - 1]))

    # valve_late: the feedback (output voltage, position or pressure) answers late, or never
    vi = next(k for k, v in enumerate(run['valves']) if v['name'] == name)
    v = run['valves'][vi]
    tc = run['streams'][v['stream']]['t']
    edges = np.flatnonzero(np.diff(v['cmd']) != 0) + 1
    if not len(edges):
        return None
    e = int(rng.choice(edges))
    te = tc[e]
    nxt = edges[edges > e]
    fb = run['channels'][v['fb']]
    tf = run['streams'][fb['stream']]['t']
    s0 = int(np.searchsorted(tf, te))
    s1 = int(np.searchsorted(tf, tc[nxt[0]])) if len(nxt) else len(tf)
    if s0 < 2 or s1 - s0 < 2:
        return None
    x = fb['x'].copy()
    pre = x[s0 - 1]
    seg_t = tf[s0:s1]
    if size == 'never':
        late = np.full(s1 - s0, pre)
    else:
        src = seg_t - size
        late = np.interp(src, tf[s0:s1], fb['x'][s0:s1])
        late[src < te] = pre
    held = late == pre
    noise = residual_noise(fb['x'], s1 - s0, (s0, s1), rng)
    late = np.where(held, pre + noise, late)
    q = quantum(fb['x'])
    if q:
        late = np.where(held, np.round(late / q) * q, late)
    x[s0:s1] = late
    new['channels'][v['fb']]['x'] = x
    return new, key, dict(t=float(te), seconds=None if size == 'never' else float(size))
