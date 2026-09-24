// Mede a primeira renderização de cada página contra o Flask REAL em 127.0.0.1
// (NFR-14.F2: < 300 ms). Sobe servidor_medicao.py e navega com o cookie de sessão.
// Duas colunas por página, 5 amostras cada, mediana:
//   - frio: contexto novo do Chromium (inclui ~200 ms de arranque do renderer, que
//     não é código da Central e não muda com o front);
//   - morno: segunda navegação no mesmo contexto com o cache HTTP desligado (CDP
//     Network.setCacheDisabled), ou seja, todo o HTML/CSS/JS baixado de novo.
// O orçamento é cobrado na coluna morna; a fria fica registrada.
// Uso: node docs/sdd/v1.9/evidencias/T-14.F2/medir_render_servidor.js
"use strict";
const { spawn } = require("node:child_process");
const path = require("node:path");
const { chromium } = require("@playwright/test");

const PORTA = 5077;
const TOKEN = "medicao-sintetica-" + Date.now();
const ORIGEM = `http://127.0.0.1:${PORTA}`;
const PAGINAS = ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"];
const AMOSTRAS = 5;
const ORCAMENTO_MS = 300;
const mediana = (v) => { const s = [...v].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const rota = (pagina) => `${ORIGEM}/${pagina === "assistente" ? "" : pagina}`;

async function esperarServidor() {
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(ORIGEM + "/inicio", { headers: { "X-Transkriptor-Token": TOKEN } }); if (r.status < 500) return; } catch (e) { /* ainda subindo */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("servidor não subiu");
}

async function medir(page, url) {
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(120);
  return page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    const paint = performance.getEntriesByType("paint").find((p) => p.name === "first-contentful-paint");
    return { fcp: paint ? paint.startTime : NaN, dcl: nav.domContentLoadedEventEnd, pedidos: performance.getEntriesByType("resource").length + 1 };
  });
}

(async () => {
  const servidor = spawn("python", [path.join(__dirname, "servidor_medicao.py"), String(PORTA)], {
    cwd: path.resolve(__dirname, "../../../../.."), env: { ...process.env, TRANSKRIPTOR_TOKEN: TOKEN, PYTHONUTF8: "1" }, stdio: "ignore",
  });
  try {
    await esperarServidor();
    const browser = await chromium.launch();
    const linhas = ["| Página | requisições | FCP frio (ms) | FCP morno sem cache (ms) | DCL morno (ms) |", "|---|---|---|---|---|"];
    let pior = 0;
    for (const pagina of PAGINAS) {
      const frio = [], morno = [], dcl = [];
      let pedidos = 0;
      for (let i = 0; i < AMOSTRAS; i++) {
        const contexto = await browser.newContext({ viewport: { width: 1366, height: 900 } });
        await contexto.addCookies([{ name: "tkpt_token", value: TOKEN, url: ORIGEM }]);
        const page = await contexto.newPage();
        const cdp = await contexto.newCDPSession(page);
        await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
        const a = await medir(page, rota(pagina));
        await page.goto(`${ORIGEM}/indisponivel-medicao`).catch(() => {});
        const b = await medir(page, rota(pagina));
        frio.push(a.fcp); morno.push(b.fcp); dcl.push(b.dcl); pedidos = b.pedidos;
        await contexto.close();
      }
      const m = mediana(morno);
      pior = Math.max(pior, m);
      linhas.push(`| ${pagina} | ${pedidos} | ${mediana(frio).toFixed(0)} | ${m.toFixed(0)} | ${mediana(dcl).toFixed(0)} |`);
    }
    await browser.close();
    console.log(linhas.join("\n"));
    console.log(`\npior FCP morno: ${pior.toFixed(0)} ms (${pior < ORCAMENTO_MS ? "dentro" : "FORA"} do orçamento de ${ORCAMENTO_MS} ms)`);
    process.exitCode = pior < ORCAMENTO_MS ? 0 : 1;
  } finally {
    servidor.kill();
  }
})().catch((e) => { console.error(e); process.exit(1); });
