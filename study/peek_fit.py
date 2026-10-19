"""Run the checker on the fit runs only and print every site's score. Used to set thresholds."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths  # noqa
import stands, checker

runs = stands.load_all()
env = checker.envelopes(runs)
for run in runs:
    if run['split'] != 'fit':
        continue
    sites = checker.check_run(run, env)
    flagged = {k: v for k, v in sites.items() if v['score'] > 1 or v['m'] > checker.RANGE_MARGIN}
    print('==', run['run_id'], run.get('title', ''), '| sites', len(sites), '| flagged', len(flagged))
    for k, v in sorted(sites.items(), key=lambda kv: -kv[1]['score']):
        if v['score'] > 0.5 or v['m'] > 0.05 or '-v' in sys.argv:
            print('   %-34s score %8.2f  m %7.3f  %s' % (k, v['score'], v['m'], checker.verdict_text(run, k, v)[:150]))
