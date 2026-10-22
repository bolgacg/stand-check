"""Print the planted-fault and false-alarm counts from data/results.json."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths  # noqa
import json, collections
import numpy as np
import inject

r = json.load(open(os.path.join(_paths.ROOT, 'data', 'results.json')))
H, C = r['healthy'], r['cases']
print('healthy sites', len(H), dict(collections.Counter(h['kind'] for h in H)), dict(collections.Counter(h['stand'] for h in H)))
for kind in ['stream', 'channel', 'valve']:
    hs = np.array([h['score'] for h in H if h['kind'] == kind]); hm = np.array([h['m'] for h in H if h['kind'] == kind])
    print(' %s: checker false alarms %d/%d, range %d/%d' % (kind, (hs > 1).sum(), len(hs), (hm > 0.1).sum(), len(hm)))
    for h in H:
        if h['kind'] == kind and (h['score'] > 1 or h['m'] > 0.1):
            print('    ', h['run'], h['site'], round(h['score'], 2), round(h['m'], 3))
for k, sz in inject.KINDS.items():
    row = []
    for i, s in enumerate(sz):
        cs = [c for c in C if c['kind'] == k and c['size'] == i]
        row.append('%s: %d/%d|%d' % (s, sum(c['score'] > 1 for c in cs), len(cs), sum(c['m'] > 0.1 for c in cs)))
    print(k, ' '.join(row))
    for st in ['sterenberg', 'dlr', 'delft']:
        cs = [c for c in C if c['kind'] == k and c['stand'] == st]
        if cs:
            print('    %s %d/%d' % (st, sum(c['score'] > 1 for c in cs), len(cs)))
allc = np.array([c['score'] for c in C]); allm = np.array([c['m'] for c in C])
print('ALL planted: checker %d/%d = %.3f ; range %d/%d = %.3f' % ((allc > 1).sum(), len(allc), (allc > 1).mean(), (allm > 0.1).sum(), len(allm), (allm > 0.1).mean()))
hs = np.array([h['score'] for h in H]); hm = np.array([h['m'] for h in H])
print('ALL healthy: checker false alarms %.4f, range %.4f' % ((hs > 1).mean(), (hm > 0.1).mean()))
