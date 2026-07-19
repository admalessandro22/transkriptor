# Tasks — Transkriptor v1.2

> **Ordem canônica e tarefas de criptografia/menu:** ver **[PLANO-FINAL.md](PLANO-FINAL.md)**.  
> Numeração abaixo será alinhada na execução (F0–F9). Use o plano final como fonte de verdade.

Tarefas acionáveis com rastreabilidade spec → implementação → teste.

**Status:** `[ ]` pendente · `[~]` em andamento · `[x]` concluído  
**Skills:** TDD antes de codar · `verification-before-completion` antes de `[x]`

---

## Fase 0 — Fundação QA

### T-F0-01 — Configurar pytest
- **Spec:** FR-0.1, FR-0.2
- **Arquivos:** `pyproject.toml`, `requirements-dev.txt`
- **AC-F0-01:** `python -m pytest --version` OK
- **Status:** [x]

### T-F0-02 — Fixtures conftest
- **Spec:** FR-0.2
- **Arquivos:** `tests/conftest.py`, `tests/test_fixtures.py`
- **AC-F0-02:** fixture `tmp_transcricoes` cria .txt isolado
- **Status:** [x]

### T-F0-03 — Testes baseline detector_meet
- **Spec:** NFR-1
- **Arquivos:** `tests/test_detector_meet.py`
- **AC-F0-03:** 8+ casos: positivo Meet, falso positivo pesquisa, debounce início/fim
- **Status:** [x]

### T-F0-04 — Script verificar_fase
- **Spec:** FR-0.3
- **Arquivos:** `scripts/verificar_fase.py`
- **AC-F0-04:** `--fase 0` roda subset correto, exit 0
- **Status:** [x]

**GATE F0:** `python scripts/verificar_fase.py --fase 0`

---

## Fase 1 — P0 Crítico

### T-F1-01 — caminho_transcricao_seguro
- **Spec:** FR-1.3, FR-1.4, SEC-1
- **Arquivos:** `assistente.py`, `tests/test_assistente_seguranca.py`
- **AC-F1-01:** `../x` → None; `transcricao.txt` → path válido
- **Status:** [x]

### T-F1-02 — Aplicar validação nas rotas API
- **Spec:** FR-1.4
- **Arquivos:** `assistente.py`
- **AC-F1-02:** GET chat com path inválido → 403 JSON
- **Status:** [x]

### T-F1-03 — Refatorar startup assistente (thread first)
- **Spec:** FR-1.1, FR-1.2
- **Arquivos:** `Transkriptor.pyw`, `assistente.py` (helper `iniciar_servidor`)
- **AC-F1-03:** Servidor responde antes de `webbrowser.open`
- **Status:** [x]

### T-F1-04 — Anti-XSS no select de transcrições
- **Spec:** FR-1.5, SEC-2
- **Arquivos:** `assistente.py` (JS: função `buildSelectOptions`)
- **AC-F1-04:** Entrada `<script>alert(1)</script>` renderiza como texto
- **Status:** [x]

**GATE F1:** `python scripts/verificar_fase.py --fase 1` + teste manual 3× assistente

---

## Fase 2 — Engenharia P1

### T-F2-01 — Ícone erro + auto-revert
- **Spec:** FR-2.1
- **Arquivos:** `Transkriptor.pyw`, `tests/test_Transkriptor_estado.py`
- **AC-F2-01:** `_erro_critico` → `estado_icone=="erro"`
- **Status:** [x]

### T-F2-02 — Ícone estado pausado
- **Spec:** FR-2.2
- **Arquivos:** `Transkriptor.pyw`
- **AC-F2-02:** `deteccao_ativa=False` → cor `#64748b`
- **Status:** [x]

### T-F2-03 — DEVICE_WHISPER auto
- **Spec:** FR-2.3, FR-2.4
- **Arquivos:** `config.py`, `transcricao_core.py`, `tests/test_config_device.py`
- **AC-F2-03:** auto → cpu quando CUDA indisponível
- **Status:** [x]

### T-F2-04 — instalar.bat pythonw dinâmico
- **Spec:** FR-2.5, SEC-5
- **Arquivos:** `instalar.bat`, `scripts/resolver_pythonw.py`
- **AC-F2-04:** Script imprime path válido em qualquer instalação Python 3.12+
- **Status:** [x]

### T-F2-05 — Mutex instância única
- **Spec:** FR-2.6
- **Arquivos:** `Transkriptor.pyw`, `tests/test_mutex.py`
- **AC-F2-05:** Segundo lock falha
- **Status:** [x]

### T-F2-06 — Log rotation
- **Spec:** FR-2.7
- **Arquivos:** `Transkriptor.pyw`
- **AC-F2-06:** Handler `RotatingFileHandler` configurado
- **Status:** [x]

### T-F2-07 — Limpeza código morto + default modelo
- **Spec:** FR-2.8, FR-2.9
- **Arquivos:** `Transkriptor.pyw`, `assistente.py`, `config.py`
- **AC-F2-07:** Sem `import winreg`; sem `gemma4:latest` hardcoded
- **Status:** [x]

**GATE F2:** `python scripts/verificar_fase.py --fase 2`

---

## Fase 3 — Criptografia em repouso

> Alinhado a `spec.md` FR-3.* e `PLANO-FINAL.md` § F3. Gate: `test_crypto_storage.py`, `test_transcricao_crypto.py`.

### T-F3-01 — Módulo crypto_storage (AES-GCM + DPAPI)
- **Spec:** FR-3.1, SEC-8
- **Arquivos:** `crypto_storage.py`, `tests/test_crypto_storage.py`
- **AC-F3-01:** Round-trip bytes; header `TKPT1`; chave em `config_user.json`
- **Status:** [x]

### T-F3-02 — Gravação .tkpt sem plaintext em disco
- **Spec:** FR-3.2, FR-3.3
- **Arquivos:** `transcricao_core.py`, `tests/test_transcricao_crypto.py`
- **AC-F3-02:** `Transcritor` grava `.tkpt`; frase-teste ausente no binário
- **Status:** [x]

### T-F3-03 — Leitura única no assistente
- **Spec:** FR-3.4
- **Arquivos:** `assistente.py`, `crypto_storage.py`
- **AC-F3-03:** API lista e chat leem via `ler_transcricao` / `ler_conteudo_transcricao`
- **Status:** [x]

### T-F3-04 — Toggle menu criptografia
- **Spec:** FR-3.5
- **Arquivos:** `transkriptor.pyw`, `config_user.json`
- **AC-F3-04:** Item menu persiste `criptografar_transcricoes` (default `true`)
- **Status:** [x]

### T-F3-05 — Migração .txt → .tkpt
- **Spec:** FR-3.6
- **Arquivos:** `crypto_storage.py`, `transkriptor.pyw`
- **AC-F3-05:** Remove plaintext; backup `.bak` só com `backup_txt_na_migracao`; sem sobrescrever `.tkpt` válido
- **Status:** [x]

### T-F3-06 — Perfil e vozes em .enc
- **Spec:** FR-3.8
- **Arquivos:** `identificador_voz.py`, `crypto_storage.py` (`migrar_vozes_legacy`)
- **AC-F3-06:** `perfil_usuario` e `vozes_conhecidas` migrados e gravados criptografados
- **Status:** [x]

### T-F3-07 — DPAPI fail-closed
- **Spec:** SEC-8, SEC-9
- **Arquivos:** `crypto_storage.py`
- **AC-F3-07:** Chave DPAPI inválida → `False`; blob antigo preservado
- **Status:** [x]

**GATE F3:** `python scripts/verificar_fase.py --fase 3`

---

## Fase 4 — UX Bandeja e Assistente

### T-F4-01 — Toast ao vivo
- **Spec:** FR-4.1, UX-1.3
- **Arquivos:** `transkriptor.pyw`, `notificador.py`
- **AC-F4-01:** Bloco transcrito + Meet não focado → toast 60 chars
- **Status:** [x]

### T-F4-02 — Menu: abrir log
- **Spec:** FR-4.2
- **Arquivos:** `transkriptor.pyw`
- **AC-F4-02:** Item menu existe e chama `LOG_FILE`
- **Status:** [x]

### T-F4-03 — Menu: transcrição manual
- **Spec:** FR-4.2
- **Arquivos:** `transkriptor.pyw`
- **AC-F4-03:** Inicia/para transcritor sem detector Meet
- **Status:** [x]

### T-F4-04 — Confirmar saída se gravando
- **Spec:** FR-4.3
- **Arquivos:** `transkriptor.pyw`
- **AC-F4-04:** `sair()` com `rodando` → não encerra imediato sem confirmação
- **Status:** [x]

### T-F4-05 — Progresso diarização
- **Spec:** FR-4.4
- **Arquivos:** `diarizador.py`, `tests/test_diarizador_progresso.py`
- **AC-F4-05:** Callback a cada 10 segmentos com `N/total`
- **Status:** [x]

### T-F4-06 — Mensagem timer 15s

- **Spec:** FR-5.1, UX-2.2
- **Arquivos:** `assistente.py`
- **AC-F4-06:** Após 15s sem token → texto "O modelo está pensando..."
- **Status:** [x]

### T-F4-07 — Barra progresso indeterminada
- **Spec:** FR-5.2
- **Arquivos:** `assistente.py`
- **AC-F4-07:** Elemento `.progress-bar` visível durante `busy`
- **Status:** [x]

### T-F4-08 — Drawer mobile sidebar
- **Spec:** FR-5.4, UX-2.5
- **Arquivos:** `assistente.py`
- **AC-F4-08:** 375px: botão ☰ abre sidebar
- **Status:** [x]

### T-F4-09 — Navegação teclado action-cards
- **Spec:** FR-5.3, UX-2.4
- **Arquivos:** `assistente.py`
- **AC-F4-09:** ↑↓ move foco entre cards
- **Status:** [x]

### T-F4-10 — Copiar resposta + tamanho_kb
- **Spec:** FR-5.5, FR-5.6
- **Arquivos:** `assistente.py`
- **AC-F4-10:** Botão copiar + label "12.5 KB" ao selecionar
- **Status:** [x]

### T-F4-11 — Testes API metadados
- **Spec:** NFR-1
- **Arquivos:** `tests/test_assistente_api.py`
- **AC-F4-11:** `/api/transcricoes` retorna campos obrigatórios
- **Status:** [x]

**GATE F4:** `python scripts/verificar_fase.py --fase 4` + checklist browser/bandeja

---

## Fase 5 — Segurança Avançada

### T-F5-01 — Token de sessão
- **Spec:** FR-5.1, SEC-4
- **Arquivos:** `assistente.py`, `Transkriptor.pyw`, `tests/test_token_sessao.py`
- **AC-F5-01:** Sem header `X-Transkriptor-Token` → 403
- **Status:** [x]

### T-F5-02 — Meet requer janela visível (opcional)
- **Spec:** FR-5.2
- **Arquivos:** `detector_meet.py`, `config.py`, `tests/test_detector_meet_visivel.py`
- **AC-F5-02:** Com flag `exigir_janela_visivel=True`, título em janela minimizada → False
- **Status:** [x]

### T-F5-03 — Truncar contexto Ollama
- **Spec:** FR-5.3
- **Arquivos:** `assistente.py`, `config.py`
- **AC-F5-03:** Transcrição 100k chars → truncada + aviso no stream
- **Status:** [x]

**GATE F5:** `python scripts/verificar_fase.py --fase 5`

---

## Fase 6 — Manutenção

### T-F6-01 — .gitignore
- **Spec:** FR-6.1
- **Arquivos:** `.gitignore`
- **AC-F6-01:** `git check-ignore` cobre `__pycache__`, `transcricoes/`
- **Status:** [x]

### T-F6-02 — docs/VERIFICACAO.md
- **Spec:** FR-6.3
- **Arquivos:** `docs/VERIFICACAO.md`
- **AC-F6-02:** Documenta gates F0–F7 com comandos copy-paste
- **Status:** [x]

### T-F6-03 — CHANGELOG v1.2
- **Spec:** FR-6.3
- **Arquivos:** `docs/sdd/v1.2/CHANGELOG.md`
- **AC-F6-03:** Lista todas as fases e requisitos entregues
- **Status:** [x]

**GATE F6:** `python scripts/verificar_fase.py --fase 6`

---

## Fase 7 — Identificação da Voz do Usuário

### T-F7-01 — Módulo identificador_voz
- **Spec:** FR-7.1, FR-7.2, SEC-7
- **Arquivos:** `identificador_voz.py`, `config.py`, `tests/test_identificador_voz.py`
- **AC-F7-01:** `salvar_perfil`/`carregar_perfil` round-trip; arquivo em `_modelo_voz/perfil_usuario.npz`
- **Status:** [x]

### T-F7-02 — Constantes e config_user
- **Spec:** FR-7.3, FR-7.9
- **Arquivos:** `config.py`, `config_user.json` (schema)
- **AC-F7-02:** `identificar_minha_voz`, `rotulo_usuario` persistidos
- **Status:** [x]

### T-F7-03 — Captura paralela do microfone
- **Spec:** FR-7.5, NFR-7
- **Arquivos:** `transcricao_core.py`, `tests/test_captura_mic.py`
- **AC-F7-03:** `_mic.wav` criado sincronizado com `_audio.wav`; thread para com `stop()`
- **Status:** [x]

### T-F7-04 — Integrar matching na diarização
- **Spec:** FR-7.6, FR-7.7, FR-7.8
- **Arquivos:** `diarizador.py`, `tests/test_diarizacao_voce.py`
- **AC-F7-04:** Cluster com embedding similar → `VOCÊ`; reforço RMS mic em overlap
- **Status:** [x]

### T-F7-05 — Wizard cadastro na bandeja
- **Spec:** FR-7.4, UX-3.1
- **Arquivos:** `Transkriptor.pyw`, `identificador_voz.py`
- **AC-F7-05:** Menu grava 20s, toast "Perfil de voz salvo"
- **Status:** [x]

### T-F7-06 — Menus toggle e apagar perfil
- **Spec:** FR-7.9, FR-7.10
- **Arquivos:** `Transkriptor.pyw`
- **AC-F7-06:** Toggle desativa identificação; apagar remove `.npz`
- **Status:** [x]

### T-F7-07 — Badge assistente
- **Spec:** FR-7.11
- **Arquivos:** `assistente.py`, `tests/test_assistente_badge_voce.py`
- **AC-F7-07:** Dropdown e meta marcam transcrições diarizadas com `VOCÊ` como "com sua voz"
- **Status:** [x]

**GATE F7:** `python scripts/verificar_fase.py --fase 7` + teste manual Meet

**GATE FINAL v1.2:** `python scripts/verificar_fase.py --fase all`

---

## Fase 8 — Nomes dos participantes no Meet (opcional)

> Só iniciar após GATE F7. Requer extensão Chrome instalada pelo usuário.

### T-F8-01 — Servidor WebSocket local
- **Spec:** FR-8.2
- **Arquivos:** `meet_bridge.py`, `config.py`
- **AC-F8-01:** Cliente teste envia evento → fila thread-safe no Transkriptor
- **Status:** [x]

### T-F8-02 — Extensão Chrome Transkriptor-meet
- **Spec:** FR-8.1
- **Arquivos:** `extension/meet/` (manifest v3, content script)
- **AC-F8-02:** Ao falar, envia nome do tile ativo para ws://127.0.0.1:5051
- **Status:** [x]

### T-F8-03 — correlacionador.py
- **Spec:** FR-8.3, FR-8.4
- **Arquivos:** `correlacionador.py`, `diarizador.py`, `tests/test_correlacionador.py`
- **AC-F8-03:** Segmento 10.0–12.0s + evento "Ana" em 10.5s → rótulo `Ana Silva`
- **Status:** [x]

### T-F8-04 — Banco vozes conhecidas (renomear falante)
- **Spec:** FR-8.5
- **Arquivos:** `identificador_voz.py`, UI mínima no assistente ou bandeja
- **AC-F8-04:** Renomear FALANTE_01 → Carlos persiste embedding para próxima reunião
- **Status:** [x]

**GATE F8:** testes `test_correlacionador.py` + teste manual Meet com 2 participantes

---

## Resumo

| Fase | Tarefas | Gate |
|------|---------|------|
| 0 | 4 | AC-F0 |
| 1 | 4 | AC-F1 |
| 2 | 7 | AC-F2 |
| 3 | 7 | AC-F3 |
| 4 | 11 | AC-F4 |
| 5 | 3 | AC-F5 |
| 6 | 3 | AC-F6 |
| 7 | 7 | AC-F7 |
| 8 (opc.) | 4 | AC-F8 |
| **Total** | **46** (+4 opc.) | |

## Ordem de execução

```
T-F0-01 → T-F0-02 → T-F0-03 → T-F0-04 → [GATE F0]
→ T-F1-01 → T-F1-02 → T-F1-03 → T-F1-04 → [GATE F1]
→ T-F2-01 … T-F2-07 → [GATE F2]
→ T-F3-01 … T-F3-07 → [GATE F3]
→ T-F4-01 … T-F4-11 → [GATE F4]
→ T-F5-01 … T-F5-03 → [GATE F5]
→ (T-F7-* após F2, ∥ F3–F5) → [GATE F7]
→ T-F6-01 … T-F6-03 → [GATE F6]
→ [GATE FINAL all]
```