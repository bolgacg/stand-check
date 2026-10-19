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


def flagged(site):
    return site['score'] > 1.0 or site['m'] > checker.RANGE_MARGIN


def real_pass(runs, env):
    out = {}
    for run in runs:
        out[run['run_id']] = checker.check_run(run, env)
    return out


def list_flags(runs, real):
    for run in runs:
        for key, site in real[run['run_id']].items():
            if flagged(site):
                print('%s|%s  [%s]  checker %.2f%s  range m %.3f%s  :: %s' % (
                    run['run_id'], key, run['split'], site['score'], ' FLAG' if site['score'] > 1 else '',
                    site['m'], ' FLAG' if site['m'] > checker.RANGE_MARGIN else '',
                    checker.verdict_text(run, key, site)))


def rescore(run, key, env):
    kind, name = key.split(':', 1)
    if kind == 'stream':
        sc, ev = checker.score_stream(run, name)
        live = checker.live_channels(run)
        ms = [checker.range_mstar(run['streams'][name]['t'], ch['x'], *env.get(run['stand'], c, run['run_id']))[0]
              for c, ch in live.items() if ch['stream'] == name]
        return sc, (max(ms) if ms else -1.0)
    if kind == 'channel':
        s1, _, m, _ = checker.score_channel(run, name, env)
        return max(s1, max(0.0, m) / checker.RANGE_MARGIN), m
    v = next(v for v in run['valves'] if v['name'] == name)
    sc, _ = checker.score_valve(run, v)
    fb = run['channels'][v['fb']]
    m = checker.range_mstar(run['streams'][fb['stream']]['t'], fb['x'], *env.get(run['stand'], v['fb'], run['run_id']))[0]
    return sc, m


def planted_pass(measured, healthy, env):
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
                st = stands_here[n % len(stands_here)]
                rid, key = pool[st][int(rng.integers(len(pool[st])))]
                res = inject.plant(by_id[rid], key, kind, size, rng)
                if res is None:
                    continue
                new, key, info = res
                sc, m = rescore(new, key, env)
                cases.append(dict(kind=kind, size=si, stand=st, run=rid, site=key, score=float(sc), m=float(m), info=info))
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
    missing = [(r['run_id'], k) for r in runs for k, s in real[r['run_id']].items()
               if flagged(s) and '%s|%s' % (r['run_id'], k) not in labels]
    if missing:
        print('unlabelled flagged sites:', len(missing))
        for m in missing[:40]:
            print('  ', '|'.join(m))
        sys.exit(2)
    realkeys = {k for k, v in labels.items() if v['label'] == 'real'}
    for m in adj.get('missed', []):
        realkeys.add('%s|%s' % (m['run'], m['site']))

    measured = [r for r in runs if r['split'] == 'measured']
    healthy = [(r['run_id'], k) for r in measured for k in real[r['run_id']] if '%s|%s' % (r['run_id'], k) not in realkeys]
    cases = planted_pass(measured, healthy, env)
    results = dict(seed=SEED, n_per=N_PER, cases=cases,
                   healthy=[dict(run=rid, site=k, kind=k.split(':')[0], stand=rid.split('-')[0],
                                 score=real[rid][k]['score'], m=real[rid][k]['m']) for rid, k in healthy])
    json.dump(results, open(OUT_JSON, 'w'), default=float)
    import build_page_data
    build_page_data.build(runs, env, real, adj, results, git_sha())


if __name__ == '__main__':
    main()
