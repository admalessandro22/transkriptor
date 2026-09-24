// NFR-14.F1 — gate axe: nenhuma violação serious/critical em todas as páginas da
// Central e na galeria, nos dois temas e com forced-colors/reduced-motion emulados.
// O relatório completo (inclusive minor/moderate) vai para a evidência da F1.
"use strict";
const { test, expect } = require("@playwright/test");
const { AxeBuilder } = require("@axe-core/playwright");
const { mkdirSync, writeFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { carregarPagina } = require("./helpers");

const PAGINAS = ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"];
const SERIAS = new Set(["serious", "critical"]);
const relatorio = [];

async function analisar(page, rotulo) {
  const resultado = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
  const violacoes = resultado.violations.map((v) => ({
    id: v.id, impact: v.impact, help: v.help, nos: v.nodes.length,
    alvos: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
  }));
  relatorio.push({ rotulo, passes: resultado.passes.length, incompletas: resultado.incomplete.length, violacoes });
  return violacoes;
}

for (const tema of ["dark", "light"]) {
  test.describe(`tema ${tema}`, () => {
    test.use({ colorScheme: tema, viewport: { width: 1366, height: 900 } });

    for (const pagina of PAGINAS) {
      test(`sem violacoes serias em cada pagina e tema: ${pagina}`, async ({ page }) => {
        const ctx = await carregarPagina(page, pagina);
        await page.waitForTimeout(500);
        const violacoes = await analisar(page, `${pagina} · ${tema}`);
        expect(violacoes.filter((v) => SERIAS.has(v.impact))).toEqual([]);
        expect(ctx.violacoes).toEqual([]);
      });
    }
  });
}

test.describe("forced-colors e reduced-motion", () => {
  test.use({ colorScheme: "dark", viewport: { width: 1366, height: 900 } });

  for (const pagina of PAGINAS) {
    test(`sem violacoes serias com forced-colors ativo: ${pagina}`, async ({ page }) => {
      await page.emulateMedia({ forcedColors: "active", reducedMotion: "reduce" });
      await carregarPagina(page, pagina);
      await page.waitForTimeout(500);
      const violacoes = await analisar(page, `${pagina} · forced-colors + reduced-motion`);
      expect(violacoes.filter((v) => SERIAS.has(v.impact))).toEqual([]);
      const animadas = await page.evaluate(() =>
        [...document.querySelectorAll("*")].filter((el) => {
          const cs = getComputedStyle(el);
          return cs.animationName !== "none" && parseFloat(cs.animationDuration) > 0.01; // base.css: 0.01ms
        }).map((el) => `${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]} ${getComputedStyle(el).animationName} ${getComputedStyle(el).animationDuration}`),
      );
      expect(animadas, "reduced-motion deve zerar animações").toEqual([]);
    });
  }
});

test.afterAll(() => {
  const destino = resolve(__dirname, "../../docs/sdd/v1.9/evidencias/T-14.F1");
  mkdirSync(destino, { recursive: true });
  // um arquivo por worker; docs/sdd/v1.9/evidencias/T-14.F1/juntar_axe.js consolida
  const worker = process.env.TEST_WORKER_INDEX || "0";
  writeFileSync(resolve(destino, `axe-relatorio.w${worker}.json`), JSON.stringify({ gerado_em: new Date().toISOString(), analises: relatorio }, null, 2));
});
