# Evidências — SDD v1.9 (design)

## Diagnóstico (24/09/2026)

Pasta `diagnostico/`. Todas as capturas usam **dados sintéticos** injetados por `fetch` falso; nenhum arquivo de `transcricoes/`, `_modelo_voz/` ou `config_user.json` foi lido.

| Arquivo | O que mostra |
|---|---|
| `render.js` | Renderiza `templates/assistente.html` + `static/*` com API simulada e captura 1366/375/860 px |
| `csp.js` | Serve a mesma página com o cabeçalho `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'` de `assistente.py` e registra violações |
| `01-desktop-vazio.png` | Estado vazio em 1366×800; sexto card de ação cortado |
| `02-desktop-chat.png` | Resposta renderizada; bolha de ~700 px e espaço vazio |
| `03-desktop-participantes.png` | Drawer de participantes sem estilo sobre o chat; "Carregando…" preso |
| `04-mobile.png` | Sidebar em 375 px |
| `05-mobile-drawer.png` | Drawer mobile (captura durante a transição; não usada como evidência) |
| `06-mobile-participantes.png` | Drawer de participantes em 375 px, texto na borda |
| `07-860.png` | 860 px: marca duplicada e drawer sem estilo |
| `08-csp-producao.png` | Sob a CSP real: botão Parar visível ao carregar, ícones `data:` ausentes |

Comandos executados (Git Bash, raiz do repositório, Node do projeto):

```bash
node docs/sdd/v1.9/evidencias/diagnostico/render.js <pasta-de-saida>
node docs/sdd/v1.9/evidencias/diagnostico/csp.js <pasta-de-saida>
```

Saída relevante de `csp.js`:

```
{"stopVisivel":"flex","timerVisivel":"block","glifo":"block"}
Applying inline style violates the following Content Security Policy directive 'default-src 'self''. (3×)
Loading the image 'data:image/svg+xml,…' violates the following Content Security Policy directive: "default-src 'self'". (2×)
```

## Evidências por task (execução em 24/09/2026)

| Task | Evidência | Capturas / anexos |
|---|---|---|
| T-14.A1 | `T-14.A1.md` | tokens gerados, pares de contraste |
| T-14.A2 | `T-14.A2.md` | CSP normativa, sprite |
| T-14.A3 | `T-14.A3.md` | `T-14.A3/` galeria e assistente (dark/light) |
| T-14.B1 | `T-14.B1.md` | `T-14.B1/` shell em 900/1366/1920 |
| T-14.B2 | `T-14.B2.md` | `T-14.B2/` lista de reuniões |
| T-14.B3 | `T-14.B3.md` | chat com markdown |
| T-14.B4 | `T-14.B4.md` | `T-14.B4/` estados (Ollama offline) |
| T-14.C1 | `T-14.C1.md` | `T-14.C1/` painel de participantes |
| T-14.C2 | `T-14.C2.md` | `T-14.C2/` revisão e desfazer |
| T-14.C3 | `T-14.C3.md` | `T-14.C3/` aprender voz e exportar |
| T-14.D1 | `T-14.D1.md` | `T-14.D1/` Início por estado |
| T-14.D2 | `T-14.D2.md` | `T-14.D2/` Configurações e confirmação |
| T-14.D3 | `T-14.D3.md` | `T-14.D3/` Diagnóstico |
| T-14.E1 | `T-14.E1.md` | `T-14.E1/` ícone em barra clara/escura |
| T-14.E2 | `T-14.E2.md` | `T-14.E2/menu-arvore.txt` |
| T-14.E3 | `T-14.E3.md` | `T-14.E3/` consentimento 100/150/200 % (janela real) |
| T-14.E4 | `T-14.E4.md` | `T-14.E4/` MessageBox real e diálogo da Central |
| T-14.E5 | `T-14.E5.md` | `T-14.E5/` pareamento nos três estados |
| T-14.F1 | `T-14.F1.md` | `T-14.F1/axe-relatorio.json`, `aria/*.yaml`, `roteiro-narrador.md` |
| T-14.F2 | `T-14.F2.md` | `T-14.F2/` medição de primeira renderização |
| T-14.G1 | `T-14.G1.md` | `T-14.G1/` capturas finais das seis páginas + galeria; `GATE-FINAL.md` |

Formato de cada evidência: `../../v1.8/evidencias/` (comando, data, ambiente, exit code, resultado, testes migrados, capturas, gate, limitações). Nenhuma captura contém dados reais.
