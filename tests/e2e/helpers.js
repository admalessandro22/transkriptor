// Helpers E2E (SDD v1.9): serve templates e estáticos reais sob a CSP normativa
// e simula a API com fixtures sintéticas. Nenhum servidor Flask é iniciado.
"use strict";
const { readFileSync, existsSync } = require("node:fs");
const { resolve, extname } = require("node:path");
const fx = require("./fixtures/central.js");

const raiz = resolve(__dirname, "../..");
const ORIGEM = "http://127.0.0.1:5050";
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'";
const TIPOS = { ".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".png": "image/png", ".html": "text/html; charset=utf-8" };

function lerTemplate(nome) {
  return readFileSync(resolve(raiz, "templates", nome + ".html"), "utf8");
}

// Subconjunto de Jinja suficiente para os templates da Central: extends + blocks.
function renderJinja(fonte, blocosFilho = {}) {
  const ext = fonte.match(/\{%\s*extends\s+"([^"]+)"\s*%\}/);
  const blocos = { ...blocosFilho };
  const re = /\{%\s*block\s+(\w+)\s*%\}([\s\S]*?)\{%\s*endblock\s*%\}/g;
  let m;
  while ((m = re.exec(fonte)) !== null) if (!(m[1] in blocos)) blocos[m[1]] = m[2];
  if (ext) return renderJinja(lerTemplate(ext[1].replace(/\.html$/, "")), blocos);
  let saida = fonte.replace(re, (_, nome, padrao) => (nome in blocos ? blocos[nome] : padrao));
  saida = saida.replace(/\{\{\s*self\.(\w+)\(\)\s*\}\}/g, (_, nome) => blocos[nome] || "");
  return saida;
}

function template(nome) {
  return renderJinja(lerTemplate(nome))
    .replace(/\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}/g, "/static/$1")
    .replace(/\{\{[^}]*\}\}/g, "")
    .replace(/\{%[^%]*%\}/g, "");
}

function apiPadrao(url, opc) {
  const u = new URL(url);
  const p = u.pathname;
  if (p === "/api/transcricoes") {
    const lista = fx.reunioes(3).map((r) => ({ ...r, protegida: /\.tkpt$/.test(r.arquivo), com_sua_voz: null }));
    if (u.searchParams.get("detalhes") !== "1") return lista;
    const nome = u.searchParams.get("arquivo");
    const base = fx.reunioes(3);
    return (nome ? base.filter((r) => r.arquivo === nome) : base).map((r) => ({ ...r, preview: "Bom dia a todos, vamos começar pela pauta" }));
  }
  if (p === "/api/reunioes-indice") return fx.indice(3);
  if (p === "/api/modelos") return fx.modelos();
  if (p === "/api/reunioes") return ["reuniao-2026-09-22"];
  if (/^\/api\/reunioes\/[^/]+\/resultado$/.test(p)) return fx.resultado();
  if (p === "/api/estado") return fx.estado();
  if (p === "/api/config") return fx.config();
  if (p === "/api/saude") return { ollama: true, modelos: fx.modelos(), versao: "1.7.0" };
  return {};
}

/**
 * Carrega `templates/<nome>.html` em `page` com CSS/JS reais servidos sob CSP.
 * `opc.api(url, request)` pode devolver um objeto (JSON), uma string (texto puro)
 * ou `{ status, body, contentType }`; `opc.chat` devolve o texto do stream.
 * Retorna `{ violacoes, console, pedidos }` preenchidos durante o teste.
 */
async function carregarPagina(page, nome = "assistente", opc = {}) {
  const ctx = { violacoes: [], console: [], pedidos: [] };
  page.on("console", (m) => {
    const t = m.text();
    ctx.console.push(t);
    if (/Content Security Policy|Refused to/i.test(t)) ctx.violacoes.push(t);
  });
  const csp = opc.csp === false ? null : CSP;
  await page.route(ORIGEM + "/**", async (route) => {
    try { await responder(route); } catch (e) { /* requisição abortada pelo cliente (stop/troca de reunião) */ }
  });
  async function responder(route) {
    const req = route.request();
    const u = new URL(req.url());
    const headers = csp ? { "Content-Security-Policy": csp } : {};
    if (u.pathname.startsWith("/static/")) {
      const arquivo = resolve(raiz, "static", u.pathname.slice("/static/".length));
      if (!existsSync(arquivo)) return route.fulfill({ status: 404, body: "", headers });
      return route.fulfill({ status: 200, body: readFileSync(arquivo), contentType: TIPOS[extname(arquivo)] || "application/octet-stream", headers });
    }
    if (u.pathname.startsWith("/api/")) {
      ctx.pedidos.push({ url: req.url(), metodo: req.method(), corpo: req.postData() });
      if (u.pathname === "/api/chat") {
        const texto = await (typeof opc.chat === "function" ? opc.chat(req) : (opc.chat || fx.resposta()));
        if (texto && typeof texto === "object" && "status" in texto) {
          return route.fulfill({ status: texto.status, body: texto.body, contentType: texto.contentType || "application/json", headers });
        }
        return route.fulfill({ status: 200, body: texto, contentType: "text/plain; charset=utf-8", headers });
      }
      let dados = opc.api ? await opc.api(req.url(), req) : undefined;
      if (dados === undefined) dados = apiPadrao(req.url(), req);
      if (dados && typeof dados === "object" && "status" in dados && "body" in dados) {
        return route.fulfill({ status: dados.status, body: dados.body, contentType: dados.contentType || "application/json", headers });
      }
      if (typeof dados === "string") return route.fulfill({ status: 200, body: dados, contentType: "text/plain; charset=utf-8", headers });
      return route.fulfill({ status: 200, body: JSON.stringify(dados), contentType: "application/json", headers });
    }
    const pagina = u.pathname === "/" ? nome : u.pathname.replace(/^\//, "").replace(/\.html$/, "");
    const caminho = resolve(raiz, "templates", pagina + ".html");
    if (!existsSync(caminho)) return route.fulfill({ status: 404, body: "", headers });
    return route.fulfill({ status: 200, body: template(pagina), contentType: TIPOS[".html"], headers });
  }
  await page.goto(ORIGEM + (nome === "assistente" ? "/" : "/" + nome));
  return ctx;
}

/** Seleciona uma reunião na listbox `#transcricao` (substitui page.selectOption do <select> antigo). */
async function selecionarReuniao(page, id) {
  await page.locator(`#transcricao [role="option"][data-id="${id}"]`).click();
}

module.exports = { carregarPagina, template, selecionarReuniao, CSP, ORIGEM, fixtures: fx };
