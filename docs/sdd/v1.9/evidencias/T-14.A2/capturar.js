// Captura o assistente servido sob a CSP normativa (helpers E2E), tema escuro e claro.
const path = require('node:path');
const raiz = path.resolve(__dirname, '../../../../..');
const { chromium } = require(path.join(raiz, 'node_modules/@playwright/test'));
const { carregarPagina } = require(path.join(raiz, 'tests/e2e/helpers.js'));
(async () => {
  const browser = await chromium.launch();
  for (const tema of ['dark', 'light']) {
    const page = await browser.newPage({ viewport: { width: 1366, height: 800 }, colorScheme: tema });
    const ctx = await carregarPagina(page, 'assistente');
    await page.waitForFunction(() => document.getElementById('modelo').options.length > 0);
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, `csp-${tema}-vazio.png`) });
    console.log(tema, 'violacoes:', ctx.violacoes.length);
    await page.close();
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
