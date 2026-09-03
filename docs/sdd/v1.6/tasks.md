# Tasks — Transkriptor v1.6

Status inicial: ⬜ pendente. Cada tarefa termina com o teste listado e commit imperativo. Ordem de `plan.md` é fechada.

| ID | Entrega | Spec | Teste obrigatório ao final da linha (GREEN) | Status |
|----|---------|------|----------------------------------------------|--------|
| **F11.A — Fundamentos visuais e design system** |
| T-11.A1 | Consolidar tokens `:root` e remover `bounce`/`elastic`; `prefers-reduced-motion` | UX-11.A1, UX-11.A2, NFR-11.A1 | `pytest tests/test_limite_linhas.py -v` + `node .agents/skills/impeccable/scripts/detect.mjs --json templates static` == `[]` | ⬜ |
| **F11.B — Assistente: layout e conteúdo** |
| T-11.B1 | `context-bar` desacoplada + busca live `Ctrl+K` + contador `N de M` | FR-11.B1, FR-11.B2 | `pytest tests/test_assistente_api.py::test_html_drawer_mobile_375px tests/test_assistente_badge_voce.py::test_html_dropdown_marca_com_sua_voz -v` + novo `test_html_tem_busca_e_context_bar` verifica `#busca-transcricao`, `#context-bar`, `#transcricao-count`, `filtrarTranscricoes`, `Ctrl+K` | ⬜ |
| T-11.B2 | `renderMarkdown()` seguro + streaming + copiar por balão + timer 15s | FR-11.B3, UX-11.B2 | `pytest tests/test_assistente_api.py::test_html_timer_mensagem_15s tests/test_assistente_api.py::test_html_progress_bar_durante_busy -v` + novo `test_html_markdown_e_copiar` (`escapeHtml`, `renderMarkdown`, `msg-copy`, `copiar-resposta`) | ⬜ |
| T-11.B3 | Hierarquia `action-card` (`is-primary` Resumir + `action-desc`/`kbd`) + `Empty` com tips | UX-11.B1 | `pytest tests/test_assistente_api.py::test_html_navegacao_teclado_action_cards -v` + novo `test_html_action_cards_hierarquia` (`is-primary` no 1º, `action-desc` em todos, `Empty` com 3 `tip`) | ⬜ |
| **F11.C — Assistente: a11y e responsivo** |
| T-11.C1 | Drawer 860px + overlay blur + `Esc`/`ArrowUp/Down` + `focus-visible` gold + `forced-colors` | UX-11.C1, UX-11.C2, NFR-11.C1, UX-11.C3 | `pytest tests/test_assistente_api.py::test_html_drawer_mobile_375px tests/test_assistente_api.py::test_html_navegacao_teclado_action_cards -v` + `detect` | ⬜ |
| **F11.D — Bandeja: hierarquia** |
| T-11.D1 | Reagrupar `_menu()` em 3 sub-menus, ≤9 raiz, preservar 14 itens legados | FR-11.D1, UX-11.D1, FR-11.D2 | `pytest tests/test_fluxo_reuniao_v15.py::test_menu_nao_oferece_captura_generica tests/test_notificador.py::test_menu_contem_itens_fase3 -v` + novo `test_menu_tem_3_submenus_e_9_raiz` (conta `pystray.Menu` aninhados) | ⬜ |
| **F11.E — Diálogos nativos** |
| T-11.E1 | `_escolher_audio_dialog` Listbox premium 560×420 com filtro + fallback `simpledialog` | FR-11.E1, SEC-11.E1 | `pytest tests/test_retranscritor.py -v` + novo `test_dialog_retranscrever_listbox` (mock `listar_audios` → Toplevel tem `Listbox`/`Scrollbar`/`Entry`, `Double-Button-1`) | ⬜ |
| T-11.E2 | `_renomear_dialog` Combobox+Entry validado 420×220 + fallback | FR-11.E2 | `pytest tests/test_renomear_falante_flow.py -v` + novo `test_dialog_renomear_combobox` (só `FALANTE_XX`, `<2` → `erro_var`) | ⬜ |
| **F11.F — Consentimento** |
| T-11.F1 | Janela 520×272 Segoe UI + countdown `SetWindowTextW` + dica privacidade | FR-11.F1, UX-11.F1, SEC-11.F1 | `pytest tests/test_aviso_gravacao.py -v` + `Select-String SetWindowTextW consentimento_gravacao.py` + `Select-String _ID_COUNTDOWN` | ⬜ |
| **F11.G — Qualidade técnica** |
| T-11.G1 | Garantir ≤500 linhas + `py_compile` nos 3 editados + isolamento `tmp_path` | NFR-11.G1, NFR-11.G2, SEC-11.G1 | `pytest tests/test_limite_linhas.py tests/test_log_isolado.py tests/test_isolamento_estado_local.py -v` + `python -m py_compile app_bandeja_menu.py transkriptor_menu_flows.py consentimento_gravacao.py` | ⬜ |
| T-11.G2 | Gate estático v1.6 + `compileall` | NFR-11.H1/H2 | `python -m compileall .` + novo `scripts/verificar_fase.py --fase v1.6-estatico` (checa `1.5.0` ainda + `detect []` + `474`) | ⬜ |
| **F11.H — Auditoria final** |
| T-11.H1 | Bump `1.5.0 → 1.6.0` + auditoria cruzada + evidências 860/375 + checklist 12 passos | NFR-11.H1/H2/H3/H4 | `python scripts/verificar_fase.py --fase all` + `pytest -q` (≥474) + `detect --json == []` + `pyproject version == config.VERSAO == "1.6.0"` + `AGENTS.md` aponta `v1.6` | ⬜ |

Nenhuma tarefa pode ser marcada ✅ apenas porque o código existe. O teste final da linha, o commit e a evidência em `docs/sdd/v1.6/evidencias/` precisam existir.

## Evidências de execução (preencher ao fechar cada T)

- **T-11.A1:** `detect []` + `transkriptor_menu_flows.py 460` + `py_compile` OK. Commit `style: consolida tokens e remove bounce`.
- **T-11.B1:** RED `test_html_tem_busca_e_context_bar` falhou por falta de `#busca-transcricao`; GREEN após `assistente.html:12` + `assistente.js:68`.
- **T-11.B2:** RED `test_html_markdown_e_copiar` sem `renderMarkdown`; GREEN com `assistente.js:28` + `msg-copy`.
- **T-11.B3:** RED `is-primary` ausente; GREEN com `assistente.html:34` + `assistente.css:120`.
- **T-11.C1:** RED drawer ainda 375 só; GREEN com `assistente.css:388` (860) + `JS ArrowUp/Down`.
- **T-11.D1:** RED menu flat 19 itens; GREEN com `app_bandeja_menu.py:369` (3 sub-menus, 9 raiz).
- **T-11.E1:** RED `_escolher_audio_dialog` inexistente; GREEN com `transkriptor_menu_flows.py:51` + fallback.
- **T-11.E2:** RED `_renomear_dialog` inexistente; GREEN com `transkriptor_menu_flows.py:112`.
- **T-11.F1:** RED `SetWindowTextW` ausente; GREEN com `consentimento_gravacao.py:273`.
- **T-11.G1:** RED `limite_linhas` >500; GREEN com refactor 460 + `tmp_path`.
- **T-11.G2:** `verify_fase v1.6-estatico` 17 passed.
- **T-11.H1:** `verify_all` 0 + `pytest -q 474` + bump `config.VERSAO` + `pyproject` + `AGENTS.md`.

## Dependências entre tarefas

`T-11.A1` bloqueia todas; `T-11.B1` bloqueia `B2/B3`; `T-11.C1` depende de `B`; `T-11.D1` independente de `B/C` mas após `A`; `T-11.E` após `D`; `T-11.F` após `E`; `T-11.G` após `F`; `T-11.H` após todas.

## Como marcar ✅

1. `git status` limpo, só arquivos da tarefa.
2. `pytest <teste específico> -v` GREEN.
3. `gate da fase` GREEN.
4. `git commit -m "feat: ..."` (ou `fix:`/`style:`) com corpo citando `FR-11.*`.
5. Atualizar esta coluna para `✅` com SHA do commit.
