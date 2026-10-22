/* CI check without the raw data: the JavaScript checker in docs/ must reproduce every hotfire
   site score the Python build wrote into docs/data.js, and the page's headline counts must
   follow from the per-site scores it ships. */
const fs = require('fs'), path = require('path');
const docs = path.resolve(__dirname, '..', 'docs');
eval(fs.readFileSync(path.join(docs, 'checker.js'), 'utf8'));
eval(fs.readFileSync(path.join(docs, 'data.js'), 'utf8').replace('const D', 'globalThis.D'));
let bad = 0, n = 0;
for (const run of D.hotfire) for (const k of SC.siteKeys(run)) {
  const s = SC.siteScore(run, k), p = run.python[k]; n++;
  const d = Math.max(Math.abs(s.score - p[0]) / Math.max(1e-9, Math.abs(p[0])), Math.abs(s.m - p[1]) / Math.max(1e-9, Math.abs(p[1])));
  if (d > 1e-9) { bad++; console.log('MISMATCH', run.id, k, s.score, p[0], s.m, p[1]); }
}
const H = D.headline, cnt = (a, f) => a.filter(f).length;
const checks = [
  [cnt(D.roc.planted, p => p[3] > 1), H.caught], [cnt(D.roc.planted, p => p[4] > 0.1), H.caughtRange],
  [cnt(D.roc.healthy, h => h[1] > 1), H.falseChecker], [cnt(D.roc.healthy, h => h[2] > 0.1), H.falseRange]];
checks.forEach(([a, b], i) => { if (a !== b) { bad++; console.log('HEADLINE MISMATCH', i, a, b); } });
console.log(`${n} hotfire site scores and ${checks.length} headline counts checked, ${bad} mismatches`);
process.exit(bad ? 1 : 0);
