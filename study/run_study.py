"""Run the whole study and write docs/data.js.

    python3 -I study/run_study.py --list     print every site flagged on the real data, for labelling
    python3 -I study/run_study.py            the full study (needs every flagged site labelled)

Labels live in data/adjudication.json, written by hand: for each flagged site, whether it is a
real problem in the published data or a false alarm, and why.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths  # noqa: E402
import json, subprocess  # noqa: E402

import numpy as np  # noqa: E402

import stands, checker, inject  # noqa: E402

SEED = 20261019
N_PER = 30
ADJ = os.path.join(_paths.ROOT, 'data', 'adjudication.json')
OUT_JSON = os.path.join(_paths.ROOT, 'data', 'results.json')
S_GRID = sorted(set(np.round(np.logspace(-3, 4, 281), 6).tolist() + [1.0]))
M_GRID = sorted(set(np.round(np.linspace(-0.5, 2.0, 251), 6).tolist() + [checker.RANGE_MARGIN]))


def is_healthy(run, key, realkeys):
    """A site with no real problem. A record counts only if none of its channels has one either,
    so a range limit is not charged a false alarm for pointing at a real fault."""
    rid = run['run_id']
    if '%s|%s' % (rid, key) in realkeys:
        return False
    kind, name = key.split(':', 1)
    if kind == 'stream':
        return not any('%s|channel:%s' % (rid, c) in realkeys
                       for c, ch in run['channels'].items() if ch['stream'] == name)
    if kind == 'valve':
        v = next(v for v in run['valves'] if v['name'] == name)
        return '%s|channel:%s' % (rid, v['fb']) not in realkeys
    return True


def flagged(site):
    """Flagged by the planned checker or the range limit at their marked settings (the preregistered pair)."""
    return site['score'] > 1.0 or site['m'] > checker.RANGE_MARGIN


def flagged_any(site):
    """Flagged by any method on the page, including the two added after the measured runs."""
    return flagged(site) or site['simple'] > 1.0 or site['rail'] > 1.0


def real_pass(runs, env):
    out = {}
    for run in runs:
        out[run['run_id']] = checker.check_run(run, env)
    return out


def list_flags(runs, real):
    for run in runs:
        for key, site in real[run['run_id']].items():
            if flagged_any(site):
                print('%s|%s  [%s]  checker %.2f%s  range m %.3f%s  simple %.2f%s  rail %.2f%s :: %s' % (
                    run['run_id'], key, run['split'], site['score'], ' FLAG' if site['score'] > 1 else '',
                    site['m'], ' FLAG' if site['m'] > checker.RANGE_MARGIN else '',
                    site['simple'], ' FLAG' if site['simple'] > 1 else '', site['rail'], ' FLAG' if site['rail'] > 1 else '',
                    checker.verdict_text(run, key, site)))


def rescore(run, key, env):
    """(checker, range margin, simple baseline, rail check) for one site of a changed run."""
    kind, name = key.split(':', 1)
    NR = checker.NO_RANGE
    if kind == 'stream':
        sc, ev = checker.score_stream(run, name)
        return sc, NR, checker.simple_gap(run['streams'][name]), NR
    if kind == 'channel':
        s1, _, m, _ = checker.score_channel(run, name, env)
        ch = run['channels'][name]
        t = run['streams'][ch['stream']]['t']
        return max(s1, max(0.0, m) / checker.RANGE_MARGIN), m, checker.simple_flat(t, ch['x']), checker.rail(t, ch['x'], ch['cls'])[0]
    v = next(v for v in run['valves'] if v['name'] == name)
    sc, _ = checker.score_valve(run, v)
    return sc, checker.valve_range(run, v, env), NR, NR


def planted_pass(measured, healthy, env, before):
    rng = np.random.default_rng(SEED)
    stand_order = ['sterenberg', 'dlr', 'delft']
    by_id = {r['run_id']: r for r in measured}
    cases = []
    for kind, sizes in inject.KINDS.items():
        pool = {s: [(rid, key) for rid, key in healthy if by_id[rid]['stand'] == s and inject.eligible(by_id[rid], key, kind)]
                for s in stand_order}
        stands_here = [s for s in stand_order if pool[s]]
        for si, size in enumerate(sizes):
            n = 0
            tries = 0
            while n < N_PER and tries < N_PER * 40:
                tries += 1
                st = stands_here[tries % len(stands_here)]
                rid, key = pool[st][int(rng.integers(len(pool[st])))]
                res = inject.plant(by_id[rid], key, kind, size, rng)
                if res is None:
                    continue
                new, key, info = res
                sc, m, sp, ra = rescore(new, key, env)
                b = before[(rid, key)]
                cases.append(dict(kind=kind, size=si, stand=st, run=rid, site=key, score=float(sc), m=float(m),
                                  simple=float(sp), rail=float(ra), before=[b['score'], b['m'], b['simple'], b['rail']], info=info))
                n += 1
            print('planted %-14s %-6s %d cases' % (kind, size, n), flush=True)
    return cases


def curve(h_sc, p_sc, grid):
    h, p = np.asarray(h_sc), np.asarray(p_sc)
    return [[float(np.mean(h > g)) if len(h) else 0.0, float(np.mean(p > g)) if len(p) else 0.0] for g in grid]


def git_sha():
    try:
        return subprocess.run(['git', '-C', _paths.ROOT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ''


def main():
    runs = stands.load_all()
    env = checker.envelopes(runs)
    real = real_pass(runs, env)
    if '--list' in sys.argv:
        list_flags(runs, real)
        return
    adj = json.load(open(ADJ))
    labels = adj['sites']
    missed_keys = {'%s|%s' % (m['run'], m['site']) for m in adj.get('missed', [])}
    missing = [(r['run_id'], k) for r in runs for k, s in real[r['run_id']].items()
               if flagged_any(s) and '%s|%s' % (r['run_id'], k) not in labels and '%s|%s' % (r['run_id'], k) not in missed_keys]
    if missing:
        print('unlabelled flagged sites:', len(missing))
        for m in missing[:40]:
            print('  ', '|'.join(m))
        sys.exit(2)
    realkeys = {k for k, v in labels.items() if v['label'] == 'real'}
    for m in adj.get('missed', []):
        realkeys.add('%s|%s' % (m['run'], m['site']))

    measured = [r for r in runs if r['split'] == 'measured']
    healthy = [(r['run_id'], k) for r in measured for k in real[r['run_id']] if is_healthy(r, k, realkeys)]
    # Faults are planted only where neither method flags anything at its marked setting, so a site
    # that is already flagged cannot be credited with catching what is planted there.
    quiet = [(rid, k) for rid, k in healthy if not flagged(real[rid][k])]
    before = {(rid, k): real[rid][k] for rid, k in quiet}
    cases = planted_pass(measured, quiet, env, before)
    results = dict(seed=SEED, n_per=N_PER, cases=cases,
                   healthy=[dict(run=rid, site=k, kind=k.split(':')[0], stand=rid.split('-')[0],
                                 score=real[rid][k]['score'], m=real[rid][k]['m'], simple=real[rid][k]['simple'],
                                 rail=real[rid][k]['rail']) for rid, k in healthy])
    json.dump(results, open(OUT_JSON, 'w'), default=float)
    if '--no-page' in sys.argv:
        return
    import build_page_data
    build_page_data.build(runs, env, real, adj, results, git_sha())


if __name__ == '__main__':
    main()
