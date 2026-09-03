# Concept — Transkriptor v1.6 — Refinamento Operacional & UX Premium

## Incidente observado (dívida de UX da v1.5)

A v1.5 estabilizou captura, fila e consentimento, mas deixou débito de UX visível na auditoria 2026-09-03 (19/40 no Nielsen, 1 warning `bounce` no `detect.mjs`):

- **Bandeja:** 19 itens flat em `app_bandeja_menu.py:369` com 5 separators. Viola Miller 4±1; “Abrir assistente” perdido entre toggles de voz.
- **Retranscrever:** `simpledialog.askstring` com `"\n".join(f"{i+1}. {it['rotulo']}" ...)` (`transkriptor_menu_flows.py:62`) obriga contar linhas e digitar número.
- **Renomear:** 2× `askstring` sem validação live; `FALANTE_XX` sem `Combobox`.
- **Assistente:** `sidebar 340px` rouba conteúdo em 1366px; sem busca, sem `context-bar`; 6 `action-card` mesmo peso; streaming só `textContent` sem markdown; sem copiar por mensagem; drawer só em `375px`; `animation: bounce` proibido.
- **Consentimento:** Win32 500×235 `COLOR_WINDOW` cinza sistema, botões 210/100 mesmo peso, sem countdown visível dos 30s.
- **Diagnóstico:** só `.txt` no Notepad, sem semáforo visual.

Nenhum débito impedia gravação, mas todos aumentam erro humano, tempo de tarefa e abandono.

## Causas-raiz

1. **Menu flat sem IA** — crescimento orgânico sem reagrupar após F10.H4.
2. **Diálogos Tk primitivos** — `simpledialog` reaproveitado do protótipo F10.E2.
3. **Assistente sem tokens explícitos** — vars OK mas `sidebar 340px` e ausência de `context-bar` fora do `select`.
4. **Sem busca/filtro** — `buildSelectOptions` só renderizava `select` sem `input[type=search]`.
5. **Streaming sem markdown** — `aiEl.textContent = txt` direto em `assistente.js:184`.
6. **Consentimento sem feedback temporal** — timeout `30s` invisível.
7. **Sem gate visual** — `detect.mjs` nunca no CI da janela.
8. **Breakpoint fixo** — `375px` herdado de mobile first genérico, inútil em 860px.

## Decisão de arquitetura

**Modo Operate** (Impeccable): visitante completa tarefa, não é persuadido. Marca vive em detalhes precisos, não em expressão.

- Durante a reunião, nada muda no ciclo `AGUARDANDO -> PEDINDO_CONSENTIMENTO -> GRAVANDO -> EM_FILA -> PROCESSANDO -> PRONTA` da v1.5.
- Refinamento é **puro front + Chrome UI da bandeja**: tokens, layout, a11y, micro-interações. `captura_leve.py`, `fila_processamento.py`, `processador_reuniao.py` não são tocados.
- Tokens centralizados em `:root` (`--bg-base`, `--panel-solid`, `--violet`, `--gold`, `--shadow-*`, `--radius-*`, `--focus`). Nenhum hex fora de `:root`.
- `easing` permitido: `ease / ease-in-out / cubic-bezier(0.32,0.72,0,1)` + `prefers-reduced-motion`.
- Assistente: `sidebar 312px` + `search-wrap` + `context-bar` desacoplada + `renderMarkdown()` seguro + `msg-copy` por balão.
- Bandeja: `≤9` itens raiz, 3 sub-menus (`Transcrições ▸`, `Minha voz ▸`, `Google Meet ▸`).
- Diálogos: `Toplevel` 560×420 / 420×220 com `Listbox/Combobox` + fallback `simpledialog`.
- Consentimento: Win32 520×272, `Segoe UI` via `WM_SETFONT`, countdown via `SetWindowTextW` a cada `WM_TIMER`.
- Gate visual: `node .agents/skills/impeccable/scripts/detect.mjs --json templates static` deve ser `[]` em toda fase.

```
AGUARDANDO -> PEDINDO_CONSENTIMENTO[520×272 + countdown] -> GRAVANDO -> FINALIZANDO
     ^                    | Não/timeout                                   |
     +--------------------+                              v
     +-------------- PRONTA <- PROCESSANDO <- EM_FILA ----+
                (context-bar mostra .txt ativo em todo ciclo)
```

## Resultado do usuário

- Em laptop 1366 ou mobile 375, achar transcrição <3s via `Ctrl+K` + contador `N de M`.
- Saber sempre qual `.txt` está ativo (`context-bar` + `header-meta`).
- Copiar qualquer resposta IA por balão; limpar conversa sem reload.
- Consentimento com countdown legível; `Não/X/timeout` = fail-closed.
- Bandeja escaneável em 2s; erros visíveis só em tooltip/ícone, nunca toast por bloco (UX-10.B1 mantido).

## Critérios visuais (Operate)

- Densidade média, não landing page. Uma ação primária (`Resumir` `is-primary`), 2 secundárias, resto em sub-menu.
- Tipografia: `Segoe UI` / `Georgia` display só em `brand-name`; `ui-monospace` só em `code`.
- Cor: `violet` para ação, `gold` para foco/“VOCÊ”, `green` pulsing para `ollama ok`, `red` só para `stop/erro`.
- Motion: `fadeIn 0.32s`, `progressIndeterminate 1.15s ease-in-out`, `pulse 2.2s` — nunca `bounce/elastic`.
- A11y: `color-scheme:dark`, `focus-visible 2px gold`, `aria-live`, `keyboard` completo, `forced-colors` fallback.

## Recuperação e compatibilidade

- Nenhum `.wav`/`job` existente é migrado; `transkriptor_menu_flows.py` fallback garante `simpledialog` se `Toplevel` falhar.
- `config.VERSAO` só é bumpada de `1.5.0` → `1.6.0` em `T-11.H1` após auditoria verde.
- `AGENTS.md` continua apontando `docs/sdd/v1.5/` até `T-11.H1`; `docs/sdd/v1.6/` é preview.
