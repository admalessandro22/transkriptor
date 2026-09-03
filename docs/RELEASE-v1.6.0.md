# Release v1.6.0 — Refinamento UX Premium

**Data:** 2026-09-03
**Tag:** `v1.6.0` @ `a95a369`
**Branch:** `master` (merge de `v1.4-deteccao-e-captura`)
**Versão:** `config.VERSAO = "1.6.0"` / `pyproject.toml 1.6.0`
**SDD:** `docs/sdd/v1.6/` (fonte de verdade, promovido de v1.5)

## Resumo

v1.6 resolve integralmente o débito de UX mapeado na auditoria 2026-09-03 (Nielsen 19/40, 1 warning `bounce` no `detect.mjs`). Nenhuma alteração no ciclo de captura/fila/processamento da v1.5 — refinamento é puro front + bandeja + diálogos, mantendo `NFR-10.C2` e `SEC-10.F*`.

**Resultado:** busca de transcrição <3s (`Ctrl+K` + contador `N de M`), context-bar sempre visível, markdown seguro com copiar por balão, bandeja escaneável em 2s (19→9 itens raiz), diálogos premium com filtro/validação live, consentimento 520×272 com countdown legível.

## Commits (7 + 1 evidências)

```
ea53e1b docs: cria SDD v1.6 refinamento UX premium (F11.A-H)
657369a feat: redesenha assistente com busca, context-bar, markdown e a11y (F11.B-C)
e3761bf feat: agrupa menu da bandeja em 3 submenus Transcrições/Minha voz/Google Meet (F11.D)
dbd6526 feat: moderniza diálogos de retranscrever e renomear com Listbox/Combobox premium (F11.E)
ec8d572 fix: polimento do diálogo de consentimento com Segoe UI e countdown 520x272 (F11.F)
34e6fea test: adiciona suíte v1.6 F11.A-G com gates de tokens, a11y, bandeja e diálogos
0722ba7 chore: bump versão para 1.6.0 e promove SDD v1.6 como fonte (F11.H)
ea0079e docs: marca T-11.A1-H1 como ✅ com SHAs das evidências
af24dd1 docs: adiciona evidências F11.A-H (detect [], 39 passed, v1.6-estatico 47 passed, 513 passed)
a95a369 merge: promove SDD v1.6 refinamento UX premium (1.5.0 → 1.6.0) para master
```

## Mudanças por área

### Assistente (`templates/assistente.html`, `static/assistente.css`, `static/assistente.js`)
- **Tokens:** `:root` centralizado, `color-scheme:dark` em `assistente.css:7`, sem `bounce`/`elastic`, `prefers-reduced-motion` e `forced-colors` (UX-11.A1/A2)
- **Layout:** sidebar 312px (era 340), `search-wrap` com `#busca-transcricao` + `Ctrl+K`, `context-bar` (`#context-file/kb/badge` + `#header-meta` mobile), contador `#transcricao-count`
- **Conteúdo:** `renderMarkdown()` com `escapeHtml` (code/bold/listas/links), streaming `textContent`→`innerHTML`, `msg-meta`/`msg-copy` por balão + `#copiar-resposta`, `timer` com `longo` 15s, `progress-bar` `ease-in-out`, `toast-region`
- **A11y/Resp:** `focus-visible gold`, `aria-*` drawer, drawer 860px (`cubic-bezier(0.32,0.72,0,1)`) + compat 375px, `Esc`/`ArrowUp/Down`/`Ctrl+K`, `breakpoints 980/860/420/375`

### Bandeja (`app_bandeja_menu.py:369`)
- 19 flat → ≤9 raiz + 3 `pystray.Menu` aninhados: `Transcrições ▸`, `Minha voz ▸`, `Google Meet ▸`
- Todos 14 itens legados preservados em ≤2 cliques; `test_fluxo_reuniao_v15.py:129` e `test_notificador.py:67` verdes

### Diálogos (`transkriptor_menu_flows.py:51,112`)
- `_escolher_audio_dialog`: `Toplevel` 560×420 `ttk vista/clam`, `Listbox+Scrollbar`, filtro live, preview `caminho·dur·mtime`, `Double-Button-1`, fallback `simpledialog`
- `_renomear_dialog`: `Toplevel` 420×220 `Combobox readonly` `FALANTE_XX` + `Entry` validado `<2` → `erro_var`, fallback idem
- Ambos `topmost`+`transient`+`grab_set`

### Consentimento (`consentimento_gravacao.py:17,162,273`)
- 500×235 → 520×272, `Segoe UI` via `CreateFontW` + `WM_SETFONT` `0x0030`
- Countdown `STATIC _ID_COUNTDOWN` via `SetWindowTextW` a cada `WM_TIMER` 50ms
- Botões 224×36 (`● Sim`) /132×36, dica “Nada é gravado antes do Sim…”, `TOPMOST|TOOLWINDOW`, `X`=`IDNO`, timeout `MB_TIMEDOUT`

## Testes

- **Suíte total:** `pytest -q` → **513 passed** (474 v1.5 + 39 v1.6)
- **Gate estático v1.6:** `scripts/verificar_fase.py --fase v1.6-estatico` → **47 passed**
- **Detect:** `detect.mjs --json templates static` → `[]` / `[]`
- **Novos testes T-11:** `tests/test_v16_{a..g}_*.py` (39 testes) cobrindo tokens, busca/markdown, a11y, bandeja, diálogos, consentimento, qualidade
- **Isolamento:** `tmp_path`, sem write em `transkriptor.log`, `python -m py_compile` e `compileall` OK, `≤500` linhas (`transkriptor_menu_flows.py 460`)

## Evidências

Salvas em `docs/sdd/v1.6/evidencias/`:
- `F11.A-detect-*.json`
- `F11.A-G-pytest_q.txt` (39)
- `F11.G-verify_v1.6-estatico.txt` (47)
- `F11.H-pytest_q_tail.txt` (513 tail)

## Checklist de auditoria (plan.md:44)

- [x] 9 passos v1.5 (PID único, áudio fora Meet 0 jobs, `Meet: …` 1 pergunta, `Não` 0 `.wav` / `Sim` `.txt`, troca aba, `faster_whisper` não importado, job `ready`, 1 ícone, retomada `pending`)
- [x] +3 novos v1.6: filtro `30 → 3 de 30`, markdown+copiar+abort `Esc`, resize 860/375 sem overflow
- [x] `AGENTS.md:18` aponta `v1.6`, `config.VERSAO`/`pyproject` `1.6.0`

## Próximos passos

- `git remote add origin <url>` + `git push --follow-tags` quando houver remoto
- Gate de reunião real 25s/600s (`scripts/gate_reuniao_real.py`) se houver alteração futura em captura
