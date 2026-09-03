# Plan — Transkriptor v1.6

Ordem fechada. Uma fase só começa com a anterior verde e commitada. Até `T-11.H1`, `AGENTS.md` continua apontando `docs/sdd/v1.5/` como fonte; `v1.6` é preview.

```text
F11.A tokens/detect
  -> F11.B assistente layout+conteúdo
    -> F11.C assistente a11y+responsivo
      -> F11.D bandeja hierarquia
        -> F11.E diálogos retranscrever/renomear
          -> F11.F consentimento countdown
            -> F11.G qualidade/perf
              -> F11.H auditoria final
```

## Regra por tarefa (TDD estrito)

1. Escrever teste **RED** citando o ID da spec (`FR-11.B2`, `UX-11.A2`...).
2. Rodar `pytest <arquivo>::<teste> -v` e confirmar falha pelo **motivo esperado** (não por import).
3. Implementar a menor mudança coerente (sem duplicar `Transcritor`/`config`, `127.0.0.1` fixo no Flask).
4. Rodar o **teste específico ao final da tarefa** → GREEN.
5. Se última tarefa da fase, rodar **gate da fase** (tabela abaixo).
6. Commit em português, imperativo, só arquivos da tarefa: `feat: agrupa menu da bandeja em 3 submenus` / `fix: remove bounce do typing`.

Falha de teste → invocar `superpowers:systematic-debugging`, corrigir causa, re-rodar **mesmo gate** antes de avançar.

Antes de codar: `superpowers:test-driven-development`.
Antes de fechar fase: `superpowers:verification-before-completion`.

## Gates

| Fase | Gate automatizado (obrigatório ao fechar) | Gate real (evidência Windows) |
|------|--------------------------------------------|--------------------------------|
| **F11.A** | `python -m pytest tests/test_limite_linhas.py -v` **e** `node .agents/skills/impeccable/scripts/detect.mjs --json templates static` deve ser `[]` | Abrir `http://127.0.0.1:<porta>` com `?token=`, inspecionar `:root` vars, confirmar 0 hex fora de `:root`, `animation` sem `bounce` |
| **F11.B** | `python -m pytest tests/test_assistente_api.py tests/test_assistente_badge_voce.py tests/test_assistente_ollama.py -v` | Com 3+ transcrições, filtrar com `Ctrl+K`, ver `N de M` + `context-bar`; clicar action-card → `textarea` preenchida + toast; double-click → envia e renderiza markdown + `msg-copy` |
| **F11.C** | `python -m pytest tests/test_assistente_api.py::test_html_drawer_mobile_375px tests/test_assistente_api.py::test_html_navegacao_teclado_action_cards tests/test_assistente_api.py::test_html_timer_mensagem_15s -v` | Redimensionar para 860 e 375: drawer `translateX`, overlay blur, `Esc` fecha; `ArrowUp/Down` navega cards pulando `TEXTAREA`; `prefers-reduced-motion` zera animações |
| **F11.D** | `python -m pytest tests/test_fluxo_reuniao_v15.py::test_menu_nao_oferece_captura_generica tests/test_notificador.py::test_menu_contem_itens_fase3 tests/test_modelo_whisper_auto.py::test_menu_persiste_modelo_whisper -v` | Abrir bandeja: contar ≤9 raiz, expandir `Transcrições ▸`/`Minha voz ▸`/`Google Meet ▸`, confirmar 14 itens legados em ≤2 cliques |
| **F11.E** | `python -m pytest tests/test_retranscritor.py tests/test_renomear_falante_flow.py -v` + novo `test_dialog_premium_listbox` / `test_dialog_renomear_combobox` | Retranscrever: filtrar, double-click, `Esc`; Renomear: `Combobox` só `FALANTE_XX`, nome vazio → erro inline, `Esc` cancela |
| **F11.F** | `python -m pytest tests/test_aviso_gravacao.py -v` + `Select-String SetWindowTextW consentimento_gravacao.py` e `Select-String _ID_COUNTDOWN` | `detector.verificar()=="iniciou"` → janela 520×272, countdown decrescente, `Não/X/timeout` não cria `.wav` |
| **F11.G** | `python -m pytest tests/test_limite_linhas.py tests/test_log_isolado.py tests/test_worker_observabilidade.py -v` + `python -m py_compile app_bandeja_menu.py transkriptor_menu_flows.py consentimento_gravacao.py` + `python -m compileall .` | `git diff --stat` sem `plyer`, sem `transkriptor.log` em testes, `pyproject version == config.VERSAO` |
| **F11.H** | `python scripts/verificar_fase.py --fase all` e `python -m pytest -q` (≥474) e `detect --json` (`[]`) | Checklist 9 passos v1.5 + 3 novos v1.6 (busca, markdown, countdown) em isolamento 10min; screenshots 860/375 |

## Gate final Windows v1.6 (estende 9 passos v1.5)

1. `python -c "import config; print(config.VERSAO)"` e `tasklist` → 1 PID `1.6.0`.
2. Áudio fora de Meet 2min → 0 jobs.
3. `Meet: ...` → pergunta 520×272 com countdown, 1 vez, sem som/ícone extra.
4. `Não` → 0 `.wav`; nova sessão `Sim` → `transcricao_*.txt` + `context-bar` atualizada.
5. Trocar aba com extensão → continua; matar extensão → para em `CONFIRMACAO_FIM_SEM_SINAL_FORTE` ciclos.
6. Durante gravação, `ImportError` `faster_whisper` não importado.
7. Após fim, job `ready` + `.txt` UTF-8 + diarizado opcional; log sem conteúdo.
8. Reiniciar Explorer → 1 ícone; reiniciar app → `pending` retoma.
9. Auditoria `retencao_audio` + lacuna 285s se aplicável.
10. **Novo:** com 30 transcrições, filtrar `Ctrl+K` → `3 de 30`, limpar → `30`.
11. **Novo:** enviar via card, `Esc` aborta streaming, `Copiar` por balão funciona.
12. **Novo:** 860 e 375 sem overflow, `forced-colors` borda `CanvasText`.

## Rollback

Cada `T-11.*` é 1 commit. `git revert <sha>` nunca apaga `transcricoes/audio` nem `transcricoes/*.txt`. Jobs `processing` órfãos voltam a `pending` no próximo `AppTranskriptor._preparar_processamento()`.

## Evidências por fase

Salvar em `docs/sdd/v1.6/evidencias/`:
- `F11.A-detect.json`, `F11.B-screenshot-860.png`, `F11.B-screenshot-375.png`, `F11.D-menu.png`, `F11.F-countdown.png`, `F11.H-verificar_all.txt`, `F11.H-pytest_q.txt`.
