/* Render the page headless, capture any script error, screenshot it at phone and desktop width,
   probe for horizontal overflow, read back what it printed, and walk every walkthrough step.

   node study/verify_page.js [outdir] [url] */
const { chromium } = (() => { try { return require('playwright'); } catch (e) { return require('/home/bolgac/projects/minimalist-workout-app/node_modules/playwright'); } })();
const path = require('path');
const fs = require('fs');

const OUT = process.argv[2] || path.resolve(__dirname, '..', 'data', 'shots');
const PAGE = process.argv[3] || 'file://' + path.resolve(__dirname, '..', 'docs', 'index.html');

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const errors = [];
  let fail = false;

  for (const [name, w, h] of [['phone375', 375, 812], ['phone390', 390, 844], ['desktop1280', 1280, 800]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.setDefaultTimeout(240000);
    page.on('pageerror', e => errors.push(`[${name}] pageerror: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') errors.push(`[${name}] console: ${m.text()}`); });
    await page.goto(PAGE + (PAGE.includes('?') ? '&' : '?') + 'tour=off', { waitUntil: 'networkidle' });
    await page.waitForTimeout(900);
    const overflow = await page.evaluate(() => {
      const de = document.documentElement, bad = [];
      if (de.scrollWidth > de.clientWidth + 1) {
        document.querySelectorAll('body *').forEach(el => {
          const r = el.getBoundingClientRect();
          if (r.right > de.clientWidth + 1 && r.width > 0) {
            let ok = el;
            while (ok && ok !== document.body) { const st = getComputedStyle(ok); if (st.overflowX === 'auto' || st.overflowX === 'scroll') return; ok = ok.parentElement; }
            bad.push(el.tagName + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '') + ' right=' + Math.round(r.right));
          }
        });
      }
      return { sw: de.scrollWidth, cw: de.clientWidth, bad: bad.slice(0, 10) };
    });
    if (overflow.sw > overflow.cw + 1) { console.log(`OVERFLOW at ${name}: ${overflow.sw} > ${overflow.cw}`); overflow.bad.forEach(b => console.log('   ' + b)); fail = true; }
    else console.log(`no horizontal overflow at ${name}`);
    await page.screenshot({ path: path.join(OUT, `${name}-first.png`) });
    await page.screenshot({ path: path.join(OUT, `${name}-full.png`), fullPage: true, timeout: 180000 });
    for (const id of ['bluf', 'primer', 'act1', 'act2', 'act3', 'act4', 'coda']) {
      const el = await page.$('#' + id);
      if (el) await el.screenshot({ path: path.join(OUT, `${name}-${id}.png`) });
    }
    const printed = await page.evaluate(() => ({
      dek: document.querySelector('#dek').innerText,
      qgrid: document.querySelector('#qgrid').innerText,
      h2: document.querySelector('#bluf-h2').innerText,
      bars: document.querySelector('#bars').innerText,
      stat: document.querySelector('#blufstat').innerText,
      verdicts: Array.from(document.querySelectorAll('.verdict')).map(v => v.innerText),
      selfcheck: document.querySelector('#selfcheck').innerText,
      findings: document.querySelectorAll('#ftable tbody tr.frow').length,
      reportRows: document.querySelectorAll('#report tr').length,
      text: document.body.innerText
    }));
    fs.writeFileSync(path.join(OUT, `${name}-printed.json`), JSON.stringify(printed, null, 1));
    if (name === 'desktop1280') {
      console.log('\nDEK: ' + printed.dek + '\nQUESTIONS:\n' + printed.qgrid + '\nH2: ' + printed.h2 + '\nSTAT: ' + printed.stat.replace(/\n/g, ' | '));
      printed.verdicts.forEach((v, i) => console.log(`VERDICT ${i + 1}: ${v}`));
      console.log('SELF-CHECK: ' + printed.selfcheck);
      console.log(`rows: findings ${printed.findings}, report ${printed.reportRows}`);
    }
    await ctx.close();
  }

  for (const [name, w, h] of [['desktop1536', 1536, 960], ['phone390', 390, 844]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    page.setDefaultTimeout(240000);
    page.on('pageerror', e => errors.push(`[tour ${name}] pageerror: ${e.message}`));
    await page.goto(PAGE, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
    let step = 0;
    while (true) {
      const info = await page.evaluate(() => {
        const root = document.querySelector('#tour');
        if (!root || !root.classList.contains('on')) return null;
        const hl = document.querySelector('.tour-hl').getBoundingClientRect();
        const card = document.querySelector('.tour-card').getBoundingClientRect();
        const k = document.querySelector('.tour-card .tk');
        return { k: k ? k.textContent : '', hlTop: Math.round(hl.top), hlH: Math.round(hl.height), cardTop: Math.round(card.top),
          cardBottom: Math.round(card.bottom), vh: innerHeight,
          overlaps: !(card.right < hl.left || card.left > hl.right || card.bottom < hl.top || card.top > hl.bottom) };
      });
      if (!info) break;
      step++;
      const bad = info.hlH < 40 || info.overlaps || info.hlTop < -4;
      if (bad) fail = true;
      console.log(`tour ${name} step ${step}: ${info.k} highlight top=${info.hlTop} h=${info.hlH} card top=${info.cardTop} bottom=${info.cardBottom}/${info.vh}` +
        (info.overlaps ? '  CARD COVERS THE HIGHLIGHT' : '') + (info.hlH < 40 ? '  HIGHLIGHT COLLAPSED' : ''));
      await page.screenshot({ path: path.join(OUT, `tour-${name}-step${step}.png`) });
      const next = await page.$('#tnext');
      if (!next) break;
      await next.click();
      await page.waitForTimeout(700);
      if (step > 12) break;
    }
    await ctx.close();
  }

  await browser.close();
  if (errors.length) { console.log('\nSCRIPT ERRORS:'); errors.forEach(e => console.log('  ' + e)); fail = true; }
  else console.log('\nno script errors');
  console.log('shots in ' + OUT);
  process.exit(fail ? 1 : 0);
})();
