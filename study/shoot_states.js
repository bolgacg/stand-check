/* Screenshot the interactive states of the page: every act-one run, every act-two filter, and a few planted faults. */
const { chromium } = (() => { try { return require('playwright'); } catch (e) { return require('/home/bolgac/projects/minimalist-workout-app/node_modules/playwright'); } })();
const path = require('path');
const OUT = process.argv[2];
const PAGE = 'file://' + path.resolve(__dirname, '..', 'docs', 'index.html') + '?tour=off';
(async () => {
  const browser = await chromium.launch();
  for (const [name, w] of [['d', 1280], ['p', 375]]) {
    const page = await (await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1.5 })).newPage();
    page.on('pageerror', e => console.log('pageerror', e.message));
    await page.goto(PAGE, { waitUntil: 'networkidle' }); await page.waitForTimeout(700);
    for (let i = 0; i < 4; i++) {
      await page.click(`#showchips .chip[data-i="${i}"]`); await page.waitForTimeout(300);
      await (await page.$('#act1')).screenshot({ path: path.join(OUT, `${name}-act1-${i}.png`) });
    }
    for (const f of ['real', 'missed', 'false']) {
      await page.click(`#fchips .chip[data-f="${f}"]`); await page.waitForTimeout(200);
      await page.click('#ftable tbody tr.frow'); await page.waitForTimeout(200);
      await (await page.$('#act2')).screenshot({ path: path.join(OUT, `${name}-act2-${f}.png`) });
    }
    const plants = [['channel:pc', 'flat', 77], ['channel:pc', 'flat_noisy', 77], ['valve:ox main valve', 'valve_late', 80], ['stream:telemetry', 'rows_missing', 60]];
    for (const [k, site, kind, size] of plants.map((p, i) => [i, ...p])) {
      await page.selectOption('#psite', site); await page.waitForTimeout(150);
      await page.click(`#pkinds .chip[data-k="${kind}"]`);
      await page.$eval('#psize', (e, v) => { e.value = v; e.dispatchEvent(new Event('input')); }, size);
      await page.waitForTimeout(250);
      await (await page.$('#plantcard')).screenshot({ path: path.join(OUT, `${name}-plant-${k}.png`) });
      console.log(name, site, kind, (await page.$eval('#presult', e => e.innerText)).replace(/\n/g, ' | '));
    }
    await (await page.$('#sizecard')).screenshot({ path: path.join(OUT, `${name}-sizes.png`) });
    await (await page.$('#act4')).screenshot({ path: path.join(OUT, `${name}-act4.png`) });
  }
  await browser.close();
})();
