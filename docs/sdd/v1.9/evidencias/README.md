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

Testes futuros das tarefas T-14.* registram evidência em `T-14.Xn.md` nesta pasta, seguindo o formato de `../../v1.8/evidencias/`.
