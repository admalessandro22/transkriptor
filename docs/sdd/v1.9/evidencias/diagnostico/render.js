const { chromium } = require(require('node:path').resolve(__dirname, '../../../../..', 'node_modules/@playwright/test'));
const { readFileSync } = require('node:fs');
const raiz = require('node:path').resolve(__dirname, '../../../../..');
const out = process.argv[2];
const modelo = readFileSync(raiz + '/templates/assistente.html', 'utf8').replace(/\{\{[^}]*\}\}/g, '#');
const css = readFileSync(raiz + '/static/assistente.css', 'utf8');
const js = readFileSync(raiz + '/static/assistente.js', 'utf8');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(modelo.replace('<link rel="stylesheet" href="#">', '<style>' + css + '</style>'));
  await page.evaluate(() => {
    window.fetch = async (url) => {
      const u = String(url);
      if (u.endsWith('/api/transcricoes')) return { ok: true, json: async () => [
        { arquivo: '2026-09-22_10h03_diarizado.txt', data: '22/09/2026 10:03', tipo: 'diarizado', tamanho_kb: 96.4, preview: 'Bom dia a todos, vamos começar pela pauta', com_sua_voz: true },
        { arquivo: '2026-09-18_15h30.txt', data: '18/09/2026 15:30', tipo: 'transcricao', tamanho_kb: 41.2, preview: 'Reunião de alinhamento do projeto', com_sua_voz: false },
        { arquivo: '2026-09-11_09h00_diarizado.tkpt', data: '11/09/2026 09:00', tipo: 'diarizado', tamanho_kb: 12.8, preview: 'Revisão do sprint', com_sua_voz: false },
      ] };
      if (u.endsWith('/api/modelos')) return { ok: true, json: async () => ['llama3.1:8b', 'qwen2.5:7b'] };
      if (u.endsWith('/api/reunioes')) return { ok: true, json: async () => ['reuniao-2026-09-22'] };
      if (u.endsWith('/resultado')) return { ok: true, json: async () => ({ schema_version: 1, revision: 'rev-3', segmentos: [
        { segment_id: 's1', start_ms: 0, end_ms: 4000, audio_source: 'loopback', text: 'Bom dia a todos, vamos começar pela pauta do dia.', speaker_cluster_id: 'FALANTE_00', overlap: false, assignment: { status: 'suggested', participant_id: 'p1', display_name: 'Ana Souza', source: 'caption', confidence: 0.91 } },
        { segment_id: 's2', start_ms: 4000, end_ms: 9000, audio_source: 'microfone', text: 'Perfeito. Eu fico com a parte de integração.', speaker_cluster_id: 'FALANTE_01', overlap: false },
        { segment_id: 's3', start_ms: 9000, end_ms: 14000, audio_source: 'loopback', text: 'Então fechamos o prazo para sexta.', speaker_cluster_id: 'FALANTE_00', overlap: false, assignment: { status: 'suggested', participant_id: 'p1', display_name: 'Ana Souza', source: 'caption', confidence: 0.88 } },
      ], mapeamento: { FALANTE_01: { display_name: 'VOCÊ', origem: 'voz' } }, historico: [] }) };
      if (u.endsWith('/api/chat')) { const bytes = new TextEncoder().encode('## Resumo executivo\n\nA reunião tratou do **planejamento do sprint**.\n\n1. Integração fica com VOCÊ\n2. Prazo: sexta-feira\n\n- Risco: dependência externa'); return { ok: true, body: { getReader: () => { let f = false; return { read: async () => { if (f) return { done: true }; f = true; return { done: false, value: bytes }; } }; } } }; }
      return { ok: true, json: async () => ({}) };
    };
  });
  await page.addScriptTag({ content: js });
  await page.waitForFunction(() => document.getElementById('transcricao').options.length === 3);
  await page.setViewportSize({ width: 1366, height: 800 });
  await page.screenshot({ path: out + '/01-desktop-vazio.png' });
  await page.selectOption('#transcricao', '2026-09-22_10h03_diarizado.txt');
  await page.fill('#input', 'Resuma a reunião');
  await page.click('#send');
  await page.waitForFunction(() => !document.getElementById('copiar-resposta').disabled);
  await page.screenshot({ path: out + '/02-desktop-chat.png' });
  await page.click('#abrir-participantes');
  await page.waitForSelector('#lista-participantes .participante-seg');
  await page.screenshot({ path: out + '/03-desktop-participantes.png' });
  await page.click('#fechar-participantes');
  await page.setViewportSize({ width: 375, height: 760 });
  await page.screenshot({ path: out + '/04-mobile.png' });
  await page.click('#menu-toggle');
  await page.screenshot({ path: out + '/05-mobile-drawer.png' });
  await page.click('#sidebar-close');
  await page.click('#abrir-participantes');
  await page.screenshot({ path: out + '/06-mobile-participantes.png' });
  await page.setViewportSize({ width: 860, height: 760 });
  await page.screenshot({ path: out + '/07-860.png' });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
