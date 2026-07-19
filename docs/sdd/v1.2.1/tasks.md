# Tasks — Transkriptor v1.2.1

Tarefas acionáveis do hotfix de estabilidade. Executar **uma tarefa por vez**.

**Status:** `[ ]` pendente · `[~]` em andamento · `[x]` concluída  
**Regra:** teste RED observado → implementação mínima → gate verde → commit em português.

## Fase 0 — Contrato

### T-F0-01 — Confirmar baseline e registrar diagnóstico

- **Spec:** FR-0.3
- **Arquivos:** nenhum código de produção
- **AC:** `python -m pytest tests/ -v --tb=short -x` retorna `152 passed` antes do hotfix
- **Status:** [x]

**GATE F0:** baseline registrado no log de execução da tarefa.

## Fase 1 — Bandeja

### T-F1-01 — Corrigir ordem de registro do ícone

- **Spec:** FR-0.1, FR-1.1, FR-1.2, FR-1.4, UX-1–3
- **Arquivos:** `tests/test_bandeja_lifecycle.py`, `transkriptor.pyw`
- **AC:** o teste prova que `visible=True` ocorre somente dentro do setup após prontidão
- **Commit:** `fix: corrige ciclo de inicialização do ícone da bandeja`
- **Status:** [x]

### T-F1-02 — Tornar setup idempotente e iniciar monitor uma vez

- **Spec:** FR-1.3, FR-1.5, FR-1.6, FR-1.7, NFR-6, UX-6
- **Arquivos:** `tests/test_bandeja_lifecycle.py`, `transkriptor.pyw`
- **AC:** duas chamadas controladas do setup não criam duas threads; falha de setup chega ao handler fatal
- **Commit:** `fix: estabiliza prontidão da bandeja e thread do monitor`
- **Status:** [x]

### T-F1-03 — Remover lock de processo já terminado

- **Spec:** FR-1.7, FR-1.8
- **Arquivos:** `tests/test_mutex.py`, `transkriptor_lock.py`
- **AC:** processo terminado com handle Win32 ainda consultável não bloqueia nova aquisição
- **Commit:** `fix: remove lock de processo já encerrado`
- **Status:** [x]

### T-F1-04 — Adiar carregamento do Whisper até a transcrição

- **Spec:** FR-1.9, NFR-2, NFR-5
- **Arquivos:** `tests/test_bandeja_lifecycle.py`, `transkriptor.pyw`
- **AC:** importar o app de bandeja não carrega `transcricao_core`; a classe `Transcritor` é carregada somente ao iniciar uma transcrição
- **Commit:** `perf: adia carregamento do Whisper até iniciar transcrição`
- **Status:** [x]

**GATE F1:**

```powershell
python -m pytest tests/test_bandeja_lifecycle.py tests/test_mutex.py -v --tb=short
```

## Fase 2 — Meet

### T-F2-01 — Reconhecer títulos reais de Chrome e Edge

- **Spec:** FR-0.2, FR-2.1–FR-2.5
- **Arquivos:** `tests/test_detector_meet.py`, `detector_meet.py`
- **AC:** matriz positiva/negativa verde com sufixos reais e debounce inalterado
- **Commit:** `fix: reconhece títulos reais do Google Meet nos navegadores`
- **Status:** [x]

### T-F2-02 — Testar integração detector → transcrição

- **Spec:** FR-2.6–FR-2.8, NFR-4
- **Arquivos:** `tests/test_integracao_monitor_meet.py`, `transkriptor.pyw`
- **AC:** evento `iniciou` chama `_iniciar_transcricao` uma vez; `encerrou` chama parada; modo manual preservado
- **Commit:** `test: cobre início automático da transcrição pelo detector`
- **Status:** [x]

**GATE F2:**

```powershell
python -m pytest tests/test_detector_meet.py tests/test_detector_meet_visivel.py tests/test_integracao_monitor_meet.py -v --tb=short
```

## Fase 3 — Atalho

### T-F3-01 — Criar script parametrizado do atalho

- **Spec:** FR-3.1–FR-3.5, FR-3.7, SEC-3, SEC-4, UX-4
- **Arquivos:** `scripts/criar_atalho_desktop.ps1`, `tests/test_atalho_desktop.py`
- **AC:** `.lnk` temporário contém metadados corretos e funciona com caminhos contendo espaços
- **Commit:** `feat: adiciona criação confiável do atalho do Transkriptor`
- **Status:** [x]

### T-F3-02 — Integrar atalho ao instalador

- **Spec:** FR-3.6, FR-3.7
- **Arquivos:** `instalar.bat`, `tests/test_atalho_desktop.py`
- **AC:** instalador chama o script único, verifica `%ERRORLEVEL%` e não cria atalho duplicado
- **Commit:** `fix: integra atalho único ao instalador`
- **Status:** [x]

**GATE F3:**

```powershell
python -m pytest tests/test_atalho_desktop.py -v --tb=short
```

## Fase 4 — Gate e documentação

### T-F4-01 — Adicionar gate de estabilidade

- **Spec:** FR-0.4, FR-4.1, FR-4.3
- **Arquivos:** `scripts/verificar_fase.py`, `tests/test_gitignore_docs.py`
- **AC:** `python scripts/verificar_fase.py --fase estabilidade` retorna 0 e executa os quatro módulos novos/relevantes
- **Commit:** `test: adiciona gate de estabilidade da bandeja e Meet`
- **Status:** [x]

### T-F4-02 — Executar validação manual e documentar

- **Spec:** FR-4.2, FR-4.4, NFR-1–NFR-7
- **Arquivos:** `docs/VERIFICACAO.md`, `docs/sdd/v1.2/CHANGELOG.md` ou changelog corrente
- **AC:** checklist Windows preenchido; suíte completa e gate all verdes
- **Commit:** `docs: registra verificação do hotfix de estabilidade`
- **Status:** [x]

**GATE FINAL v1.2.1:**

```powershell
python scripts/verificar_fase.py --fase estabilidade
python -m pytest tests/ -v --tb=short
python scripts/verificar_fase.py --fase all
```

## Rastreabilidade

| Tarefa | Requisitos principais |
|--------|------------------------|
| T-F0-01 | FR-0.3 |
| T-F1-01 | FR-0.1, FR-1.1, FR-1.2, FR-1.4, UX-1–3 |
| T-F1-02 | FR-1.3, FR-1.5–1.7, NFR-6, UX-6 |
| T-F1-03 | FR-1.7–1.8 |
| T-F1-04 | FR-1.9, NFR-2, NFR-5 |
| T-F2-01 | FR-0.2, FR-2.1–2.5 |
| T-F2-02 | FR-2.6–2.8, NFR-4 |
| T-F3-01 | FR-3.1–3.5, FR-3.7, SEC-3–4, UX-4 |
| T-F3-02 | FR-3.6–3.7 |
| T-F4-01 | FR-0.4, FR-4.1, FR-4.3 |
| T-F4-02 | FR-4.2, FR-4.4, NFR-1–7 |

Nenhuma tarefa está autorizada a alterar Whisper, diarização, criptografia, Flask ou extensão Meet fora do necessário para manter os testes existentes verdes.
