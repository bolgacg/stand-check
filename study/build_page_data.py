"""Write docs/data.js from the study's results. Every number on the page comes from here."""
import json, os, time

import numpy as np

import _paths
import checker, inject, stands

KIND_NAMES = {'rows_missing': 'Rows missing', 'rows_repeated': 'Rows repeated by the logger',
              'flat': 'Sensor frozen flat', 'flat_noisy': 'Sensor frozen, noise kept',
              'valve_late': 'Valve late or silent'}
SITE_KINDS = ['stream', 'channel', 'valve']
STAND_ORDER = ['sterenberg', 'dlr', 'delft']


def r4(x):
    return float('%.4g' % x)


def f10(x):
    return float('%.10g' % x)


def decimate(t, y, n=900):
    """Keep the shape for plotting: the min and max of each bucket, in time order."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    if len(t) <= 2 * n:
        return [r4(v) for v in t], [r4(v) for v in y]
    edges = np.linspace(0, len(t), n + 1).astype(int)
    tt, yy = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        seg = y[a:b]
        i, j = a + int(np.argmin(seg)), a + int(np.argmax(seg))
        for k in sorted({i, j}):
            tt.append(t[k]); yy.append(y[k])
    return [r4(v) for v in tt], [r4(v) for v in yy]


def window(run, c, t0, t1):
    ch = run['channels'][c]
    t = run['streams'][ch['stream']]['t']
    sel = (t >= t0) & (t <= t1)
    return t[sel], ch['x'][sel]


# ------------------------------------------------------------------ the curves

def curves(results):
    H, C = results['healthy'], results['cases']
    kinds = list(inject.KINDS)
    healthy = [[SITE_KINDS.index(h['kind']), f10(h['score']), f10(h['m'])] for h in H]
    planted = [[kinds.index(c['kind']), c['size'], STAND_ORDER.index(c['stand']), f10(c['score']), f10(c['m'])] for c in C]
    return dict(kinds=kinds, kindNames=[KIND_NAMES[k] for k in kinds], kindSite=[SITE_KINDS.index(inject.KIND_SITE[k]) for k in kinds],
                sizes=[[('never' if s == 'never' else s) for s in inject.KINDS[k]] for k in kinds],
                siteKinds=SITE_KINDS, stands=STAND_ORDER, healthy=healthy, planted=planted)


def headline(results, real_rows):
    H, C = results['healthy'], results['cases']
    hs = np.array([h['score'] for h in H]); hm = np.array([h['m'] for h in H])
    cs = np.array([c['score'] for c in C]); cm = np.array([c['m'] for c in C])
    per = {}
    for k in inject.KINDS:
        sel = [c for c in C if c['kind'] == k]
        per[k] = dict(n=len(sel), checker=int(sum(c['score'] > 1 for c in sel)), range=int(sum(c['m'] > checker.RANGE_MARGIN for c in sel)))
    visible = [c for c in C if c['kind'] != 'flat_noisy']
    out = dict(
        planted=len(C), caught=int((cs > 1).sum()), caughtRange=int((cm > checker.RANGE_MARGIN).sum()),
        plantedVisible=len(visible), caughtVisible=int(sum(c['score'] > 1 for c in visible)),
        healthy=len(H), falseChecker=int((hs > 1).sum()), falseRange=int((hm > checker.RANGE_MARGIN).sum()),
        falseCheckerOwn=int(sum(1 for h in H if h['score'] > 1 and not (h['kind'] == 'channel' and h['m'] > checker.RANGE_MARGIN))),
        perKind=per)
    real = [r for r in real_rows if r['label'] in ('real', 'missed')]
    out.update(realTotal=len(real), realChecker=sum(1 for r in real if r['checker']), realRange=sum(1 for r in real if r['range']),
               realMissedBoth=sum(1 for r in real if not r['checker'] and not r['range']),
               realOnlyChecker=sum(1 for r in real if r['checker'] and not r['range']),
               falseAllChecker=sum(1 for r in real_rows if r['label'] == 'false' and r['checker']),
               falseAllRange=sum(1 for r in real_rows if r['label'] == 'false' and r['range']))
    return out


# ------------------------------------------------------------------ the real data

def findings(runs, real, adj):
    by = {r['run_id']: r for r in runs}
    rows = []
    for key, lab in adj['sites'].items():
        rid, site = key.split('|', 1)
        run = by[rid]
        s = real[rid][site]
        rows.append(dict(run=rid, runLabel=run['label'], stand=run['stand'], split=run['split'], site=site,
                         siteLabel=checker.site_label(run, site),
                         checker=bool(s['score'] > 1), range=bool(s['m'] > checker.RANGE_MARGIN),
                         checkerText=checker.verdict_text(run, site, s) if s['score'] > 1 else '',
                         rangeText=range_site_text(run, site, s), label=lab['label'], category=lab['category'], reason=lab['reason']))
    for m in adj['missed']:
        run = by[m['run']]
        s = real[m['run']][m['site']]
        rows.append(dict(run=m['run'], runLabel=run['label'], stand=run['stand'], split=run['split'], site=m['site'],
                         siteLabel=checker.site_label(run, m['site']), checker=bool(s['score'] > 1), range=bool(s['m'] > checker.RANGE_MARGIN),
                         checkerText='', rangeText='', label='missed', category=m['category'], reason=m['reason']))
    return rows


def range_site_text(run, site, s):
    if s['m'] <= checker.RANGE_MARGIN:
        return ''
    if site.startswith('channel:'):
        return checker.range_text(s['ev']['range'])
    return 'a channel in it leaves its range'


def group_findings(rows):
    """Rows that say the same thing about the same channel in many runs become one row."""
    groups, order = {}, []
    for r in rows:
        k = (r['stand'], r['site'], r['label'], r['reason'])
        if k not in groups:
            groups[k] = dict(r, runs=[], count=0)
            order.append(k)
        g = groups[k]
        g['runs'].append(r['runLabel'])
        g['count'] += 1
    out = [groups[k] for k in order]
    rank = {'real': 0, 'missed': 1, 'false': 2, 'echo': 3}
    out.sort(key=lambda g: (rank[g['label']], STAND_ORDER.index(g['stand']), -g['count']))
    return out


# ------------------------------------------------------------------ reports

def report(run, sites):
    rows = []
    for key, s in sites.items():
        kind = s['kind']
        sec = {'stream': 'Records', 'channel': 'Channels', 'valve': 'Valves'}[kind]
        rows.append(dict(sec=sec, label=checker.site_label(run, key), name=key.split(':', 1)[1],
                         status='FAIL' if s['score'] > 1 else 'PASS', score=r4(s['score']),
                         text=checker.verdict_text(run, key, s)))
    spare = [c for c, ch in run['channels'].items() if ch['role'] == 'spare']
    return dict(id=run['run_id'], label=run['label'], stand=run['stand'], date=run['date'], split=run['split'],
                source=run['source'], notes=run.get('notes', []), rows=rows, spare=spare,
                verdict='FAIL' if any(r['status'] == 'FAIL' for r in rows) else 'PASS',
                n=dict(records=sum(1 for r in rows if r['sec'] == 'Records'), channels=sum(1 for r in rows if r['sec'] == 'Channels'),
                       valves=sum(1 for r in rows if r['sec'] == 'Valves')))


# ------------------------------------------------------------------ showcase plots

def showcase(runs, real):
    by = {r['run_id']: r for r in runs}
    out = []

    def panel(run, c, t0, t1, title, extra=None, bands=None, n=900):
        t, x = window(run, c, t0, t1)
        tt, yy = decimate(t, x, n)
        series = [dict(name=run['channels'][c]['label'], t=tt, y=yy, role='main')]
        for e in extra or []:
            te, xe = window(run, e, t0, t1)
            a, b = decimate(te, xe, n)
            series.append(dict(name=run['channels'][e]['label'], t=a, y=b, role='twin'))
        return dict(title=title, unit=run['channels'][c]['unit'], series=series, bands=bands or [])

    def cmd_panel(run, vname, t0, t1, title):
        v = next(v for v in run['valves'] if v['name'] == vname)
        t = run['streams'][v['stream']]['t']
        sel = (t >= t0) & (t <= t1)
        tt, yy = decimate(t[sel], v['cmd'][sel], 900)
        return dict(title=title, unit='', series=[dict(name='command', t=tt, y=yy, role='cmd')], bands=[], step=True)

    fv, fd = checker.fmt_val, checker.fmt_dur

    def lags(rid, vname):
        return [x for x in real[rid]['valve:' + vname]['ev']['lags']]

    def edge_times(run, vname):
        v = next(v for v in run['valves'] if v['name'] == vname)
        t = run['streams'][v['stream']]['t']
        return [float(t[i]) for i in np.flatnonzero(np.diff(v['cmd']) != 0) + 1]

    # 1. the 2018 hotfire
    r = by['sterenberg-2018-03-17']
    t = r['streams']['telemetry']['t']
    dt = np.diff(t)
    gaps = [[r4(t[i]), r4(t[i + 1])] for i in np.flatnonzero(dt > 3 * np.median(dt))]
    p14, tc2 = r['channels']['pressure[14] (psi)']['x'][0], r['channels']['thermocouple[2] (degC)']['x'][0]
    burn = edge_times(r, 'motorised valve 0')
    out.append(dict(id='hotfire', chip='2018 hotfire', run=r['run_id'], runLabel=r['label'],
                    lede='The first motorised main valve is commanded open for %s. Thrust and two pressure inputs move as they should; next to them, '
                         'a pressure input sits at %s psi and a thermocouple at %s C on every row, and the red line on the '
                         'thrust chart marks the longest gap between rows.' % (fd(burn[1] - burn[0]), fv(p14), fv(tc2)),
                    panels=[panel(r, 'thrust_load (lbs)', t[0], t[-1], 'Thrust, moving: passes',
                                  bands=[dict(t0=a, t1=b, kind='gap') for a, b in gaps]),
                            panel(r, 'pressure[4] (psi)', t[0], t[-1], 'Pressure input 4, moving: passes', extra=['pressure[5] (psi)']),
                            panel(r, 'pressure[14] (psi)', t[0], t[-1], 'Pressure input 14: never changes, fails',
                                  bands=[dict(t0=r4(t[0]), t1=r4(t[-1]), kind='flag')]),
                            panel(r, 'thermocouple[2] (degC)', t[0], t[-1], 'Thermocouple input 2: never changes, fails',
                                  bands=[dict(t0=r4(t[0]), t1=r4(t[-1]), kind='flag')])]))
    # 2. DLR test 9: frozen PD403, saturated PD409
    r = by['dlr-20200805_9']
    td = r['streams']['dynamic pressure']['t']
    n9, i9, d9 = checker.flat(td, r['channels']['PD409']['x'])
    pd403 = r['channels']['PD403']['x'][0]
    out.append(dict(id='dlr9', chip='DLR test 9', run=r['run_id'], runLabel=r['label'],
                    lede='The valve shuts at time zero and a pressure wave runs up and down the line. At station S3 the '
                         'static sensor records it; the dynamic sensor beside it reads %s bar the whole time. At station '
                         'S1 the dynamic sensor sits flat at its top for %s while the static one beside it keeps rising.' % (fv(pd403), fd(d9)),
                    panels=[panel(r, 'PD403', 0.0, 0.3, 'Station S3: dynamic PD403 frozen, static PS402 moving: fails',
                                  extra=['PS402'], bands=[dict(t0=0.0, t1=0.3, kind='flag')], n=1200),
                            panel(r, 'PD409', 0.0, 0.06, 'Station S1: dynamic PD409 flat at its top for %s: missed' % fd(d9),
                                  extra=['PS408'], bands=[dict(t0=r4(td[i9]), t1=r4(td[i9 + n9 - 1]), kind='miss')], n=1500)]))
    # 3. Delft combustion run: valves answer, TC0 dead
    rid = 'delft-240529_084127'
    r = by[rid]
    e1, e2 = edge_times(r, 'main valve 1'), edge_times(r, 'main valve 2')
    worst = max(abs(x) for x in lags(rid, 'main valve 1') + lags(rid, 'main valve 2'))
    a0, a1 = e1[0] - 4, e1[-1] + 6
    out.append(dict(id='delft', chip='Delft combustion run', run=r['run_id'], runLabel=r['label'],
                    lede='Oxygen flows from %s, methane joins at %s and both shut at %s. Each valve command is followed by '
                         'its line pressure within %s. The thermocouple the README calls ambient reads %s C throughout.' % (
                             fd(e1[0]), fd(e2[0]), fd(e1[-1]), fd(worst), fv(r['channels']['TC0']['x'][0])),
                    panels=[cmd_panel(r, 'main valve 1', a0, a1, 'Main valve 1 command'),
                            panel(r, 'PS0', a0, a1, 'Oxygen line pressure answers main valve 1: passes'),
                            cmd_panel(r, 'main valve 2', a0, a1, 'Main valve 2 command'),
                            panel(r, 'PS2', a0, a1, 'Methane line pressure answers main valve 2: passes'),
                            panel(r, 'TC0', a0, a1, 'Ambient thermocouple TC0 reads %s C: fails' % fv(r['channels']['TC0']['x'][0]),
                                  bands=[dict(t0=a0, t1=a1, kind='flag')])]))
    # 4. Delft run whose valve log drifts
    rid = 'delft-240320_093730'
    r = by[rid]
    lg, ed = lags(rid, 'main valve 1'), edge_times(r, 'main valve 1')
    k = int(np.argmax([abs(x) for x in lg]))
    out.append(dict(id='drift', chip='Delft valve log drift', run=r['run_id'], runLabel=r['label'],
                    lede='The same valve opens twice. The first time, the pressure rises %s after the logged command. The second '
                         'time it rises %s after it: the valve log has no timestamps and lost time between the two cycles.' % (fd(lg[0]), fd(lg[2])),
                    panels=[cmd_panel(r, 'main valve 1', ed[0] - 5, ed[-1] + 5, 'Main valve 1 command, as logged'),
                            panel(r, 'PS0', ed[0] - 5, ed[-1] + 5, 'Oxygen line pressure: answers %s late the second time, fails' % fd(max(lg[2], lg[3])),
                                  bands=[dict(t0=r4(ed[k]), t1=r4(ed[k] + lg[k]), kind='flag')])]))
    return out


# ------------------------------------------------------------------ the hotfire logs for the browser

def hotfire(runs, env, real):
    out = []
    for run in runs:
        if run['stand'] != 'sterenberg':
            continue
        st = run['streams']['telemetry']
        chans = {}
        for c, ch in run['channels'].items():
            if ch['role'] not in ('live', 'valve'):
                continue
            lo, hi = env.get(run['stand'], c, run['run_id'])
            chans[c] = dict(x=[f10(v) for v in ch['x']], cls=ch['cls'], unit=ch['unit'], label=ch['label'], role=ch['role'],
                            lo=lo, hi=hi)
        valves = [dict(name=v['name'], kind=v['kind'], fb=v['fb'], label=v['label'], cmd=[f10(x) for x in v['cmd']],
                       batt=[f10(x) for x in v['batt']] if 'batt' in v else None) for v in run['valves']]
        py = {k: [s['score'], s['m']] for k, s in real[run['run_id']].items()}
        out.append(dict(id=run['run_id'], label=run['label'], split=run['split'], t=[f10(v) for v in st['t']],
                        declaredRate=st['declared_rate'], channels=chans, valves=valves, active=list(run['active']), python=py))
    return out


def build(runs, env, real, adj, results, sha):
    rows = findings(runs, real, adj)
    empty = [r for r in stands.load_delft(include_empty=True) if r.get('empty')]
    counts = {}
    for s in STAND_ORDER:
        rs = [r for r in runs if r['stand'] == s]
        counts[s] = dict(runs=len(rs), fit=sum(r['split'] == 'fit' for r in rs), measured=sum(r['split'] == 'measured' for r in rs),
                         sites=sum(len(real[r['run_id']]) for r in rs),
                         sitesMeasured=sum(len(real[r['run_id']]) for r in rs if r['split'] == 'measured'))
    counts['delft']['emptyFiles'] = len(empty)
    by = {r['run_id']: r for r in runs}
    clip = []
    for m in adj['missed']:
        if m['category'] == 'clipped':
            run = by[m['run']]
            ch = run['channels'][m['site'].split(':', 1)[1]]
            clip.append(checker.flat(run['streams'][ch['stream']]['t'], ch['x'])[2] * 1000)
    drift = 0.0
    for r in runs:
        if r['stand'] == 'delft':
            st = r['streams']['valve state']
            ref = len(r['streams']['thermocouple']['t']) / 100.0
            drift = max(drift, abs(len(st['t']) / st['rate'] - ref) / ref)
    extra = dict(clipMsMin=round(min(clip)), clipMsMax=round(max(clip)), clipRuns=len({m['run'] for m in adj['missed'] if m['category'] == 'clipped'}),
                 delftDriftPct=round(100 * drift))
    D = dict(
        built=time.strftime('%d %B %Y'), code=sha, seed=results['seed'], nPer=results['n_per'], extra=extra,
        stands={k: dict(v, **counts[k]) for k, v in stands.STANDS.items()},
        totals=dict(runs=len(runs), fit=sum(r['split'] == 'fit' for r in runs), measured=sum(r['split'] == 'measured' for r in runs),
                    sites=sum(len(v) for v in real.values()), emptyFiles=len(empty)),
        thresholds=dict(flat=stands.FLAT_LIMIT, rangeMargin=checker.RANGE_MARGIN, persist=checker.PERSIST, minFlat=checker.MIN_FLAT,
                        wElec=checker.W_ELEC, wPos=checker.W_POS, posTol=checker.POS_TOL, wResp=checker.W_RESP),
        roc=curves(results), headline=headline(results, rows),
        findings=group_findings(rows),
        reports=[report(r, real[r['run_id']]) for r in runs],
        emptyFiles=[r['run_id'] for r in empty],
        showcase=showcase(runs, real),
        hotfire=hotfire(runs, env, real),
    )
    js = '/* generated by study/build_page_data.py from the study results; do not edit */\nconst D = ' + \
        json.dumps(D, separators=(',', ':'), ensure_ascii=False) + ';\n'
    open(os.path.join(_paths.DOCS, 'data.js'), 'w').write(js)
    print('wrote docs/data.js', len(js) // 1000, 'kB')
    print(json.dumps(D['headline'], indent=1))
