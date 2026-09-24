// Dump de bounding boxes dos elementos principais para comparar layout antes/depois (T-14.A1).
const path = require('node:path');
const raiz = process.argv[2]; const out = process.argv[3];
const { chromium } = require(path.join(raiz, 'node_modules/@playwright/test'));
const { readFileSync, writeFileSync } = require('node:fs');
const modelo = readFileSync(path.join(raiz, 'templates/assistente.html'), 'utf8').replace(/\{\{[^}]*\}\}/g, '#');
let css = readFileSync(path.join(raiz, 'static/assistente.css'), 'utf8');
try { css = readFileSync(path.join(raiz, 'static/css/tokens.css'), 'utf8') + '\n' + css.replace(/@import[^;]+;/g, ''); } catch (e) {}
const js = readFileSync(path.join(raiz, 'static/assistente.js'), 'utf8');
const SEL = ['.sidebar', '.brand', '.sidebar-body', '.action-grid', '.action-card', '.sidebar-footer', '.main', '.context-bar', '#chat', '.empty-state', '.input-area', '.input-wrap', '#input', '#send', '.input-hint', '#busca-transcricao', '#transcricao', '#modelo', '.msg-row.ai .bubble', '.msg-row.user .bubble', '#abrir-participantes'];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1366, height: 800 }, colorScheme: process.env.COLOR_SCHEME === 'dark' ? 'dark' : 'light' });
  await page.setContent(modelo.replace('<link rel="stylesheet" href="#">', '<style>' + css + '</style>'));
  await page.evaluate(() => { window.fetch = async (url) => { const u = String(url);
    if (u.endsWith('/api/transcricoes')) return { ok: true, json: async () => [{ arquivo: 'a.txt', data: '01/01/2026 10:00', tipo: 'diarizado', tamanho_kb: 96.4, preview: 'Bom dia a todos', com_sua_voz: true }] };
    if (u.endsWith('/api/modelos')) return { ok: true, json: async () => ['llama3.1:8b'] };
    if (u.endsWith('/api/chat')) { const b = new TextEncoder().encode('## Resumo\n\nTexto **forte**.\n\n1. um\n2. dois'); return { ok: true, body: { getReader: () => { let f = false; return { read: async () => { if (f) return { done: true }; f = true; return { done: false, value: b }; } }; } } }; }
    return { ok: true, json: async () => ({}) }; }; });
  await page.addScriptTag({ content: js });
  await page.waitForFunction(() => document.getElementById('transcricao').options.length === 1);
  await page.waitForTimeout(500); await page.screenshot({ path: out + '-vazio.png' });
  await page.selectOption('#transcricao', 'a.txt'); await page.fill('#input', 'Resuma'); await page.click('#send');
  await page.waitForFunction(() => !document.getElementById('copiar-resposta').disabled);
  await page.waitForTimeout(500); await page.screenshot({ path: out + '-chat.png' });
  const rects = await page.evaluate((sel) => { const o = {}; for (const s of sel) { const el = document.querySelector(s); if (!el) { o[s] = null; continue; } const r = el.getBoundingClientRect(); o[s] = [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; } return o; }, SEL);
  writeFileSync(out + '-rects.json', JSON.stringify(rects, null, 1));
  console.log(JSON.stringify(rects));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
