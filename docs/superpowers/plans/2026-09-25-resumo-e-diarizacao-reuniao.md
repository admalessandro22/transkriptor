# Resumo automático e diarização da última reunião — plano de correção

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task, with `superpowers:test-driven-development` before code and `superpowers:verification-before-completion` before closure. Do not parallelize dependent tasks.

**Goal:** gerar o resumo local quando uma reunião nova termina de processar, exibi-lo na Central e corrigir o estado parcial da reunião de 24/09/2026 sem inventar identificação.

**Architecture:** a bandeja agenda o resumo depois de um job `ready`, e a fila serial existente gera e cifra o texto com Ollama quando o app está ocioso. A diarização conserva os tempos originais no resultado, mesmo quando usa intervalos normalizados internamente. O reparo de um único resultado reexecuta somente a diarização, preserva cópias byte a byte e atualiza resultado, exportação, manifesto e índice sob validação.

**Tech Stack:** Python 3.12, pytest, Ollama local, Flask, ECAPA, JSON canônico e TXT derivado.

## Restrições globais

- Seguir os contratos de `docs/sdd/v1.8/` e a política de dados locais; não transmitir fala para serviços externos.
- Não trocar `config.VERSAO`, abrir reunião nova, executar gate físico ou apagar originais.
- Escopo de dados reais: somente a última reunião indicada pelo usuário, identificada por ID a partir do índice. Não escrever fala, nomes, áudio nem resumo na evidência.
- `Parcial` descreve `stage_status` do manifesto; resumo pronto é estado separado. Só marcar `Pronta` quando todas as etapas requeridas estiverem completas e o manifesto íntegro.

## Evidência inicial — 25/09/2026

- Job da última reunião: `ready`; 726 segmentos; STT `complete`; diarização `partial` com `segment_alignment_failed`.
- 142 segmentos sobrepostos tiveram início/fim alterados por `diarizador._normalizar_segmentos`; os mesmos 142 ficaram com o rótulo de fallback no alinhamento por tempo e texto. Há mais três ocorrências do rótulo como cluster legítimo; elas não são prova de falha.
- A reunião começou depois do corte dos resumos automáticos. O índice armazena data ISO válida; o PowerShell apenas a exibiu em formato brasileiro.
- Um resumo cifrado da revisão `rev-1` já existe, criado em 25/09 às 10h17. A leitura local retorna `pronto`. O fluxo atual o agenda apenas quando a página consulta a API.
- Baseline dirigido: `python -m pytest tests/test_resumo_reuniao.py tests/test_resultado_pipeline.py tests/test_diarizador_progresso.py tests/test_worker_observabilidade.py -q --tb=short` → 32 passed.

### Task 1 — agendar resumos no ciclo do job

**Files:** `central_resumos.py`, `app_processamento.py`, `tests/test_resumo_reuniao.py`, `tests/test_worker_observabilidade.py`.

**Interfaces:** consumir `job.id`, `job.metadados["inicio_iso"]` e `ServicoResumos.obter(meeting_id, gerar=True)`. Produzir `agendar_concluida(job)`, sem bloquear a thread da bandeja em uma chamada ao modelo.

- [x] RED: os dois testes do ciclo do worker falharam com `Expected 'mock' to be called once. Called 0 times` (exit 1); o teste da elegibilidade do job falhou pelo mesmo comportamento (exit 1).
- [x] GREEN: a bandeja chama `agendar_concluida` fora do lock quando o job fica `ready`; no startup, reexamina jobs prontos. A rotina usa a data do job, preserva o corte de 24/09 às 18h40 e põe a reunião na fila existente sem chamar Ollama de forma síncrona. O estado da bandeja fica disponível ao serviço mesmo sem abrir a Central.
- [x] Gate: `python -m pytest tests/test_resumo_reuniao.py tests/test_worker_observabilidade.py tests/test_worker_liveness.py -q --tb=short` → 36 passed, exit 0. Resumo já salvo é reaproveitado pelo serviço; reunião anterior ao corte permanece fora da fila. RED adicional: sem abrir a Central, o worker ativo era visto como ocioso; GREEN confirmou a espera.

### Task 2 — conservar tempos na diarização

**Files:** `diarizador.py`, `tests/test_resultado_pipeline.py`, `tests/test_diarizador_progresso.py`.

**Interfaces:** `diarizar(trechos_audio, segmentos, ...) -> [(rotulo, start, end, texto)]` deve devolver `start/end` de cada segmento de entrada; `criar_segmentos` continua exigindo chave temporal e textual para vincular rótulo.

- [x] RED: duas falas simultâneas passaram por `diarizar` e `criar_segmentos`; o código anterior devolveu `segment_alignment_failed` (exit 1).
- [x] GREEN: o clamp continua por segmento, sem deslocar uma fala para depois da outra. Os horários reais e a ordem são preservados; o alinhamento por tempo e texto continua conservador e não usa só o índice.
- [x] Gate: `python -m pytest tests/test_resultado_pipeline.py tests/test_diarizador_progresso.py tests/test_audio_duas_fontes.py tests/test_diarizacao_voce.py -q --tb=short` → 22 passed, exit 0.

### Task 3 — reparar e verificar a reunião de 24/09

**Files:** `scripts/reparar_diarizacao_reuniao.py`, `tests/test_reparo_diarizacao_reuniao.py`, evidência deste plano.

**Interfaces:** CLI `--meeting-id ID` faz inspeção sem escrita; `--aplicar` limita a alteração a esse ID. Consumir `ResultadoStorage`, `carregar_manifesto`, `validar_manifesto`, `extrair_trechos`, `diarizar` e `criar_segmentos`.

- [ ] RED: fixture sintética reproduz os 142 deslocamentos em miniatura; teste exige nenhuma escrita no modo inspeção, recusa de manifesto inválido e preservação de backup no modo aplicado.
- [ ] GREEN: verificar hashes do áudio e das refs antes da execução; gerar novos rótulos sem refazer STT; conferir cardinalidade, IDs, texto e tempos idênticos; guardar cópias integrais dos artefatos alterados; atualizar JSON, TXT, manifesto e índice com nova revisão e rollback recuperável. Se algum vínculo continuar falhando, preservar `partial` e registrar a causa.
- [ ] Gate local: teste dirigido, `validar_manifesto`, qualidade do índice, revisão do resumo, `git diff --check`; executar somente no ID da última reunião depois de confirmar bandeja e worker ociosos. Reiniciar somente a bandeja do Transkriptor para carregar o código e verificar API/painel ao vivo.

## Fechamento

Registrar aqui RED, GREEN, comandos/exit codes, hashes de backup sem dados de conteúdo, estado do job/manifesto/resumo, processo em uso, SHA e gates ainda pendentes. O fechamento deste incidente não altera o status de release dos gates físicos v1.8.
