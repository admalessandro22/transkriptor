# Spec — Transkriptor v1.6

Referencia `config.VERSAO` (1.5.0 até T-11.H1, depois 1.6.0). Nenhum arquivo fora de `config.py` hardcoda versão.

## F11.A — Fundamentos visuais e design system

- **UX-11.A1** Tokens em `:root` de `static/assistente.css:1` (`--bg-base`, `--bg-deep`, `--panel`, `--panel-solid`, `--border`, `--text`, `--violet`, `--gold`, `--grad-accent`, `--shadow-*`, `--radius-*`, `--focus`, `--font-sans`) são únicos; nenhum hex fora de `:root` exceto `*::before` glows.
- **UX-11.A2** Nenhum `animation: bounce` / `elastic` / `ease` com bounce; permitido: `ease`, `ease-in-out`, `cubic-bezier(0.32,0.72,0,1)`; `prefers-reduced-motion` zera `animation-duration`.
- **NFR-11.A1** `node .agents/skills/impeccable/scripts/detect.mjs --json templates static` retorna `[]`.

## F11.B — Assistente: layout e conteúdo (Operate)

- **FR-11.B1** `context-bar` (`#context-file`, `#context-kb`, `#context-badge`, `#header-meta`) reflete `selTrans.value` após `loadList()` e `change`; `contextBadge` usa classes `tipo-diarizado` / `tipo-transcricao` + `· com sua voz` quando `com_sua_voz`.
- **FR-11.B2** Busca `#busca-transcricao` (`type=search`) filtra `transcricoesLista` live via `filtrarTranscricoes()`; `renderTranscricoesSelect` preserva `prev` se ainda no filtro; `#transcricao-count` mostra `N` ou `N de M`; `Ctrl+K` foca busca e abre drawer em mobile.
- **FR-11.B3** `renderMarkdown(text)` escapa HTML (`escapeHtml`) e converte ` ```code``` / `code` / **bold** / listas `-`/`1.` / `http*` / `## heading` para HTML seguro; streaming usa `textContent` até `done` e troca para `innerHTML` com markdown; `pergunta()` adiciona `msg-copy` por balão IA + `#copiar-resposta` para última.
- **UX-11.B1** `action-grid` 6 cards com hierarquia: primeiro `is-primary` (“Resumir”) com `background: linear-gradient(violet)`; cada card tem `action-icon` SVG `stroke`, `action-label` + `action-desc` + `action-kbd`; clique preenche `textarea` editável + `showToast()`; `dblclick` envia direto; `Empty` com 3 `tip` kbd.
- **UX-11.B2** Estados vazios/erro: `(nenhuma transcrição)` vs `(nenhum resultado para o filtro)` vs `erro ao carregar` (`#tamanho-kb` limpa); `showToastInline` + `showToast(error)` em `!transc` ou `!modelo`; `progress-bar` visível só em `busy`; `timer` com `longo` após 15s (`iniciarTimer`).

## F11.C — Assistente: a11y e responsivo

- **UX-11.C1** `color-scheme:dark`, `focus-visible: 2px solid --gold-bright` em todos interativos (`action-card`, `select`, `#busca-transcricao`, `#send`, `#stop`, `#limpar`, `#menu-toggle`, `.msg-copy`); `aria-label`/`aria-expanded`/`aria-controls` em `#menu-toggle`; `aria-live` em `#context-bar`, `#transcricao-count`, `#timer`, `#chat role=log`; `avatar` com `aria-hidden`.
- **UX-11.C2** Drawer: `sidebar` `translateX(-100%)` em `max-width:860px`, `drawer-open` em `translateX(0)` com `cubic-bezier(0.32,0.72,0,1)`; `drawer-overlay` blur; `Esc` fecha drawer; `ArrowUp/Down` navega `action-card` pulando `TEXTAREA/INPUT/SELECT`; `header` visível só em `860px`.
- **NFR-11.C1** Breakpoints `980/860/420/375` testados; `375px` preserva `width:100vw` sem overflow; `input` max-height 140px; `msg-row.user` max 88% (92% em 860).
- **UX-11.C3** Compat: `forced-colors` borda `CanvasText`; `scrollbar-gutter:stable`.

## F11.D — Bandeja: hierarquia e estados

- **FR-11.D1** `app_bandeja_menu.py:369` `_menu()` nível raiz ≤9 itens + `SEPARATOR`; 3 sub-menus `pystray.Menu`: `Transcrições ▸` (Abrir pasta/Assistente/Retranscrever/Vozes), `Minha voz ▸` (Cadastrar/Identificar/Apagar), `Google Meet ▸` (Nomes/Legendas/Extensão/Renomear); todos os 14 itens legados permanecem alcançáveis em `≤2` cliques.
- **UX-11.D1** Rótulos com verbo + contexto: “Abrir pasta de transcrições”, “Abrir assistente (IA local)”, “Diagnóstico (por que não está gravando?)”; disabled hint “✓ Confirmar antes de gravar (obrigatório)” preservado; status disabled no topo via `_texto_status`.
- **FR-11.D2** `_texto_status`/`resolver_estado_icone` continuam refletindo `transcrevendo/diarizando/processando/pausado/erro` sem logar conteúdo (`status_seguro`).

## F11.E — Diálogos nativos: retranscrever e renomear

- **FR-11.E1** `transkriptor_menu_flows.py:51` `iniciar_retranscricao_ui` chama `_escolher_audio_dialog(items)`: `Toplevel` 560×420 `ttk` `vista/clam`, header “Áudios retidos” + contador, `Entry` filtro, `Listbox` + `Scrollbar`, preview `caminho · dur · mtime`, seleção preservada, `Double-Button-1` confirma, `Esc/Return/WM_DELETE_WINDOW`; em `Exception` cai para `simpledialog.askstring` legado com `int(escolha)-1` validado.
- **FR-11.E2** `_renomear_dialog(rotulos)` (`transkriptor_menu_flows.py:112`): `Toplevel` 420×220, `Combobox readonly` só com `FALANTE_XX`, `Entry` novo nome com validação live (`<2` → `erro_var`), hint “Maria Silva”, `Esc` cancela, `Return` foca `Entry` → confirma; fallback idem; `persistir_renomeacao_falante` levanta `ValueError` para nome vazio.
- **SEC-11.E1** Diálogos são `topmost` + `transient` + `grab_set`; `iconbitmap` tenta `transkriptor.ico` mas não falha se ausente; thread `daemon` não bloqueia bandeja.

## F11.F — Consentimento: polimento visual e countdown

- **FR-11.F1** `consentimento_gravacao.py:273` janela 520×272, `Segoe UI` via `CreateFontW(-15/-12)` + `WM_SETFONT` (`0x0030`), countdown `STATIC` (`_ID_COUNTDOWN`) atualizado em cada `WM_TIMER` (`_ID_TIMER_CANCELAR` 50ms) via `SetWindowTextW` (“fecha em Xs (Não gravar)”), dica “Nada é gravado antes do Sim…”, botões 224×36 (`● Sim, gravar`) / 132×36 (`Não gravar`), `WS_EX_TOPMOST|TOOLWINDOW`, sem owner modal, `X` = `IDNO`, timeout = `MB_TIMEDOUT` fail-closed.
- **UX-11.F1** `_configurar_user32` expõe `SetWindowTextW`/`SendMessageW`; `inicio = time.monotonic()` + `restante = max(0, timeout - int(now-inicio))`.
- **SEC-11.F1** `pedir_consentimento` só retorna `True` para `IDYES`; qualquer `Exception` loga e retorna `False`.

## F11.G — Qualidade técnica e performance

- **NFR-11.G1** Nenhum `*.py`/`*.pyw` >500 linhas (gate `test_limite_linhas.py:24`); `transkriptor_menu_flows.py` ≤460, `consentimento_gravacao.py` ≤435. `python -m py_compile` nos 3 editados sem erro.
- **NFR-11.G2** `pyproject.toml` `version` == `config.VERSAO`; `transkriptor.pyw` e `instalar.bat` não hardcodam versão (só `config.VERSAO`).
- **SEC-11.G1** Testes usam `tmp_path`/`monkeypatch`; `front_assistente.HTML` é concatenação de 3 arquivos, não `file://`.
- **NFR-11.G3** Gate visual Windows 10min (NFR-10.C2) mantido: 1 processo, 1 ícone, <100MB, <10% CPU.

## F11.H — Auditoria final

- **NFR-11.H1** Cada `T-11.*` termina com teste GREEN + commit imperativo português; `Bumped` só em `T-11.H1`.
- **NFR-11.H2** Suíte `pytest -q` 474+ verde; `detect` `[]`; `compileall` 0.
- **NFR-11.H3** Auditoria cruza cada `FR-11.*` com código (`file:line`), teste e evidência Windows (screenshots 860/375, `diagnostico_*`); revisa bounce, a11y, privacidade (nenhum conteúdo em log/job).
- **NFR-11.H4** Conclusões comportamentais exigem evidência real, não só `HTML` contains.
