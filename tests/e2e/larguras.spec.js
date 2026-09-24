// NFR-14.F1 — 375/900/1366/1920 sem overflow horizontal e sem elemento visível
// saindo da viewport (texto cortado), em todas as páginas da Central e na galeria.
"use strict";
const { test, expect } = require("@playwright/test");
const { carregarPagina } = require("./helpers");

const PAGINAS = ["inicio", "reunioes", "assistente", "participantes", "configuracoes", "diagnostico", "galeria"];
const LARGURAS = [375, 900, 1366, 1920];

for (const largura of LARGURAS) {
  test.describe(`largura ${largura}`, () => {
    test.use({ viewport: { width: largura, height: largura < 900 ? 760 : 900 } });

    for (const pagina of PAGINAS) {
      test(`sem overflow: ${pagina}`, async ({ page }) => {
        await carregarPagina(page, pagina);
        await page.waitForTimeout(400);
        const medidas = await page.evaluate(() => {
          const doc = document.documentElement;
          const estouro = doc.scrollWidth - doc.clientWidth;
          const fora = [];
          for (const el of document.querySelectorAll("body *")) {
            const cs = getComputedStyle(el);
            if (cs.display === "none" || cs.visibility === "hidden" || el.closest("[hidden]")) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            // nav em drawer fica fora à esquerda de propósito (translateX(-100%)); só o lado direito conta
            if (r.right > window.innerWidth + 1 && r.left >= 0) {
              fora.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : ""} right=${Math.round(r.right)}`);
            }
          }
          const cortados = [];
          for (const el of document.querySelectorAll("h1, h2, h3, p, label, button, a, span, li, td, th, dt, dd")) {
            const cs = getComputedStyle(el);
            if (cs.display === "none" || el.closest("[hidden]")) continue;
            if (el.clientWidth <= 1) continue; // padrão visually-hidden (1px + overflow hidden)
            if (el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== "visible" && cs.textOverflow !== "ellipsis") {
              cortados.push(`${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""} ${el.scrollWidth}>${el.clientWidth}`);
            }
          }
          return { estouro, fora: fora.slice(0, 10), cortados: cortados.slice(0, 10) };
        });
        expect(medidas.estouro, "scrollWidth > clientWidth").toBeLessThanOrEqual(1);
        expect(medidas.fora, "elementos além da borda direita").toEqual([]);
        expect(medidas.cortados, "texto cortado sem reticências").toEqual([]);
      });
    }
  });
}
