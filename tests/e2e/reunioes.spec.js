const { test, expect } = require("@playwright/test");
const { carregarPagina, selecionarReuniao, fixtures } = require("./helpers");


async function esperarLista(page) {
  await page.waitForFunction(() => document.getElementById("transcricao").options.length > 0);
}


test("lista do assistente não mostra fala por padrão e não pede preview", async ({ page }) => {
  const ctx = await carregarPagina(page, "assistente");
  await esperarLista(page);
  const pedido = ctx.pedidos.find((p) => p.url.includes("/api/transcricoes"));
  expect(pedido.url).not.toContain("preview=1");
  await expect(page.locator("#transcricao")).not.toContainText("Bom dia a todos");
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(3);
  await expect(page.locator('#transcricao [role="option"]').first()).toContainText("22/09/2026 10:03");
  await expect(page.locator('#transcricao [role="option"]').nth(2)).toContainText("Protegida");
});


test("filtro preserva a seleção e sem resultado mostra estado próprio", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await esperarLista(page);
  await selecionarReuniao(page, "2026-09-18_15h30.txt");
  await page.fill("#busca-transcricao", "18/09");
  expect(await page.evaluate(() => document.getElementById("transcricao").value)).toBe("2026-09-18_15h30.txt");
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(1);
  await page.fill("#busca-transcricao", "zzz");
  await expect(page.locator("#transcricao .tk-listbox__estado")).toContainText("Nenhuma reunião combina");
  expect(await page.evaluate(() => document.getElementById("transcricao").value)).toBe("2026-09-18_15h30.txt");
  await page.fill("#busca-transcricao", "");
  await expect(page.locator('#transcricao [role="option"][aria-selected="true"]')).toHaveAttribute("data-id", "2026-09-18_15h30.txt");
});


test("teclado move o item ativo e Enter seleciona", async ({ page }) => {
  await carregarPagina(page, "assistente");
  await esperarLista(page);
  await page.locator("#transcricao").focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowDown");
  await expect(page.locator("#transcricao")).toHaveAttribute("aria-activedescendant", "transcricao-op-2");
  await page.keyboard.press("Enter");
  expect(await page.evaluate(() => document.getElementById("transcricao").value)).toBe("2026-09-11_09h00_diarizado.tkpt");
  await page.keyboard.press("Home");
  await expect(page.locator("#transcricao")).toHaveAttribute("aria-activedescendant", "transcricao-op-0");
  await expect(page.locator("#transcricao")).toBeFocused();
});


test("erro ao carregar mostra ação e não vira item da lista", async ({ page }) => {
  let falhar = true;
  await carregarPagina(page, "assistente", { api: (url) => (url.includes("/api/transcricoes") && falhar ? { status: 500, body: "{}" } : undefined) });
  await expect(page.locator("#transcricao .tk-listbox__estado")).toContainText("Não foi possível carregar");
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(0);
  falhar = false;
  await page.locator("#transcricao .tk-listbox__estado button").click();
  await esperarLista(page);
  await expect(page.locator('#transcricao [role="option"]')).toHaveCount(3);
});


test("lista vazia orienta o primeiro uso", async ({ page }) => {
  await carregarPagina(page, "assistente", { api: (url) => (url.includes("/api/transcricoes") ? [] : undefined) });
  await expect(page.locator("#transcricao .tk-listbox__estado")).toContainText("Nenhuma reunião ainda");
});


test("selecionar uma reunião pede detalhes só dela e troca o contexto do chat", async ({ page }) => {
  const ctx = await carregarPagina(page, "assistente");
  await esperarLista(page);
  await selecionarReuniao(page, "2026-09-22_10h03_diarizado.txt");
  await expect(page.locator("#context-file")).toHaveText("2026-09-22_10h03_diarizado.txt");
  await expect.poll(() => ctx.pedidos.some((p) => p.url.includes("detalhes=1") && p.url.includes("arquivo=2026-09-22_10h03_diarizado.txt"))).toBe(true);
  await expect(page.locator("#context-badge")).toContainText("com sua voz");
  expect(ctx.pedidos.filter((p) => p.url.includes("detalhes=1")).length).toBe(1);
});


test("página Reuniões consome o índice paginado e carregar mais anexa sem duplicar", async ({ page }) => {
  let chamadas = 0;
  const ctx = await carregarPagina(page, "reunioes", {
    api: (url) => {
      if (!url.includes("/api/reunioes-indice")) return undefined;
      chamadas++;
      const u = new URL(url);
      if (!u.searchParams.get("cursor")) return fixtures.indice(3, "c1");
      const pagina = fixtures.indice(3, null);
      pagina.reunioes = pagina.reunioes.map((r, i) => ({ ...r, meeting_id: r.meeting_id + "-p2" + i }));
      pagina.reunioes.push(fixtures.indice(1).reunioes[0]);
      return pagina;
    },
  });
  await expect(page.locator("#lista-reunioes .tk-row")).toHaveCount(3);
  await expect(page.locator("#lista-reunioes")).not.toContainText("Bom dia");
  await expect(page.locator("#carregar-mais")).toBeVisible();
  await page.click("#carregar-mais");
  await expect(page.locator("#lista-reunioes .tk-row")).toHaveCount(6);
  await expect(page.locator("#carregar-mais")).toBeHidden();
  expect(chamadas).toBe(2);
  expect(ctx.violacoes).toEqual([]);
  await expect(page.locator('#lista-reunioes .tk-row').first()).toContainText("Pronta");
});


test("página Reuniões: erro mostra ação e vazio orienta", async ({ page }) => {
  await carregarPagina(page, "reunioes", { api: (url) => (url.includes("/api/reunioes-indice") ? { status: 500, body: "{}" } : undefined) });
  await expect(page.locator("#lista-reunioes-estado")).toContainText("Não foi possível carregar");
  await expect(page.locator("#lista-reunioes-estado button")).toBeVisible();
  await page.goto("about:blank");
  await carregarPagina(page, "reunioes", { api: (url) => (url.includes("/api/reunioes-indice") ? { reunioes: [], proximo: null } : undefined) });
  await expect(page.locator("#lista-reunioes-estado")).toContainText("Nenhuma reunião ainda");
});


test("linha da reunião mostra título, início, duração e participantes", async ({ page }) => {
  const ctx = await carregarPagina(page, "reunioes", {
    api: (url) => {
      if (url.includes("/api/reunioes-indice")) {
        const dados = fixtures.indice(2);
        dados.reunioes[0].title = "Planejamento semanal";
        dados.reunioes[0].arquivo = "transcricao_2026-09-22_10h03_planejamento";
        return dados;
      }
      if (url.includes("/participantes")) {
        return url.includes(encodeURIComponent(fixtures.indice(2).reunioes[0].meeting_id))
          ? { participantes: ["Ana Fictícia", "Bruno Fictício"], sem_nome: 1 }
          : { participantes: [], sem_nome: 0 };
      }
      return undefined;
    },
  });
  const primeira = page.locator("#lista-reunioes .tk-row").first();
  await expect(primeira).toContainText("Planejamento semanal");
  await expect(primeira).toContainText("22/09/2026 · 10:03");
  await expect(primeira).toContainText("30 min");
  await expect(primeira.locator(".tk-row__participantes")).toHaveText("Ana Fictícia, Bruno Fictício + 1 sem nome");
  const segunda = page.locator("#lista-reunioes .tk-row").nth(1);
  await expect(segunda).toContainText("Reunião sem título");
  await expect(segunda.locator(".tk-row__participantes")).toHaveText("Participantes não identificados");
  await expect(primeira.locator("a.tk-row__abrir")).toHaveAttribute("href", "/participantes?reuniao=" + fixtures.indice(2).reunioes[0].meeting_id);
  await expect(primeira.locator("a.tk-row__assistente")).toHaveAttribute("href", "/?reuniao=transcricao_2026-09-22_10h03_planejamento");
  expect(ctx.violacoes).toEqual([]);
});


test("clicar na linha abre a transcrição daquela reunião com nomes e tempos", async ({ page }) => {
  await carregarPagina(page, "reunioes", {
    api: (url) => {
      if (url.includes("/api/reunioes-indice")) {
        const dados = fixtures.indice(1);
        dados.reunioes[0].meeting_id = "reuniao-b";
        return dados;
      }
      if (url.endsWith("/api/reunioes")) return ["reuniao-a", "reuniao-b"];
      return undefined;
    },
  });
  await page.locator("#lista-reunioes .tk-row").first().click({ position: { x: 20, y: 10 } });
  await expect(page).toHaveURL(/\/participantes\?reuniao=reuniao-b$/);
  await expect(page.locator("#reuniao-participantes")).toHaveValue("reuniao-b");
  await expect(page.locator("#participantes-drawer")).toContainText("00:0");
});


test("passar o mouse no nome da reunião mostra o resumo da IA local", async ({ page }) => {
  let pronto = false;
  await carregarPagina(page, "reunioes", {
    api: (url) => {
      if (url.includes("/api/reunioes-indice")) return fixtures.indice(2);
      if (url.includes("/resumo")) {
        if (url.includes(encodeURIComponent(fixtures.indice(2).reunioes[1].meeting_id))) return { estado: "indisponivel", motivo: "IA local indisponível" };
        return pronto ? { estado: "pronto", resumo: "Equipe fechou o cronograma; Ana entrega sexta." } : { estado: "gerando" };
      }
      return undefined;
    },
  });
  const primeira = page.locator("#lista-reunioes .tk-row").first();
  const titulo = primeira.locator("a.tk-row__abrir");
  const dica = primeira.locator(".tk-row__resumo");
  await expect(dica).toHaveText(/Gerando resumo/);
  await expect(dica).toBeHidden();
  await expect(page.locator("#lista-reunioes .tk-row").nth(1).locator(".tk-row__resumo")).toHaveText("Resumo indisponível: IA local indisponível");
  pronto = true;
  await page.evaluate(() => document.dispatchEvent(new Event("tk-resumos-atualizar")));
  await expect(dica).toHaveText("Equipe fechou o cronograma; Ana entrega sexta.");
  await expect(titulo).not.toHaveAttribute("title", /./);
  expect(await titulo.getAttribute("aria-describedby")).toBe(await dica.getAttribute("id"));
  await titulo.hover();
  await expect(dica).toBeVisible();
  await page.mouse.move(0, 0);
  await expect(dica).toBeHidden();
  await titulo.focus();
  await expect(dica).toBeVisible();
});
