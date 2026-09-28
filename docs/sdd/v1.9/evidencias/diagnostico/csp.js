const { chromium } = require(require('node:path').resolve(__dirname, '../../../../..', 'node_modules/@playwright/test'));
const { readFileSync } = require('node:fs');
const raiz = require('node:path').resolve(__dirname, '../../../../..');
const out = process.argv[2];
const html = readFileSync(raiz + '/templates/assistente.html', 'utf8')
  .replace("{{ url_for('static', filename='assistente.css') }}", '/static/assistente.css')
  .replace("{{ url_for('static', filename='assistente.js') }}", '/static/assistente.js');
const CSP = "default-src 'self'; frame-ancestors 'none'";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 800 } });
  const console_ = [];
  page.on('console', m => console_.push(m.text()));
  await page.route('http://127.0.0.1:5050/**', async (route) => {
    const u = route.request().url();
    if (u.endsWith('/static/assistente.css')) return route.fulfill({ status: 200, contentType: 'text/css', body: readFileSync(raiz + '/static/assistente.css', 'utf8'), headers: { 'Content-Security-Policy': CSP } });
    if (u.endsWith('/static/assistente.js')) return route.fulfill({ status: 200, contentType: 'application/javascript', body: readFileSync(raiz + '/static/assistente.js', 'utf8'), headers: { 'Content-Security-Policy': CSP } });
    if (u.endsWith('/api/transcricoes')) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ arquivo: 'a.txt', data: '01/01', tipo: 'transcricao', tamanho_kb: 1, preview: 'x', com_sua_voz: false }]), headers: { 'Content-Security-Policy': CSP } });
    if (u.endsWith('/api/modelos')) return route.fulfill({ status: 200, contentType: 'application/json', body: '["llama3"]', headers: { 'Content-Security-Policy': CSP } });
    return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html, headers: { 'Content-Security-Policy': CSP } });
  });
  await page.goto('http://127.0.0.1:5050/');
  await page.waitForTimeout(800);
  const stopVisivel = await page.evaluate(() => getComputedStyle(document.getElementById('stop')).display);
  const timerVisivel = await page.evaluate(() => getComputedStyle(document.getElementById('timer')).display);
  const glifo = await page.evaluate(() => getComputedStyle(document.querySelector('#menu-toggle span')).display);
  console.log(JSON.stringify({ stopVisivel, timerVisivel, glifo }));
  console.log(console_.filter(t => /Refused|CSP|Content Security/i.test(t)).slice(0, 5).join('\n'));
  await page.screenshot({ path: out + '/08-csp-producao.png' });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
