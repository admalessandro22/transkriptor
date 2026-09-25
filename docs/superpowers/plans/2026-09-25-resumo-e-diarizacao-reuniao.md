# Resumo automático e diarização da última reunião — plano de correção

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task, with `superpowers:test-driven-development` before code and `superpowers:verification-before-completion` before closure. Do not parallelize dependent tasks.

**Goal:** gerar o resumo local quando uma reunião nova termina de processar, exibi-lo na Central e corrigir o estado parcial da reunião de 24/09/2026 sem inventar identificação.

**Architecture:** a bandeja agenda o resumo depois de um job `ready`, e a fila serial existente gera e cifra o texto com Ollama quando o app está ocioso. A diarização conserva os tempos originais no resultado, mesmo quando usa intervalos normalizados internamente. O reparo de um único resultado reexecuta somente a diarização, mantém um journal de rollback até a validação e atualiza resultado, exportação, manifesto e índice.

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

**Files:** `scripts/reparar_diarizacao_reuniao.py`, `tests/test_reparo_diarizacao_reuniao.py`, `resumo_reuniao.py`, `config.py`, `tests/test_resumo_reuniao.py`, `tests/conftest.py`, evidência deste plano.

**Interfaces:** CLI `--meeting-id ID` faz inspeção sem escrita; `--aplicar` limita a alteração a esse ID. Consumir `ResultadoStorage`, `carregar_manifesto`, `validar_manifesto`, `extrair_trechos`, `diarizar` e `criar_segmentos`.

- [x] RED: fixture com duas falas sobrepostas reproduziu o desalinhamento; os testes exigiram inspeção sem escrita, recusa de manifesto inválido, rollback após falha sintética e leitura das duas fontes de áudio. Antes da implementação, `tests/test_reparo_diarizacao_reuniao.py` falhou (exit 1).
- [x] GREEN: validar o manifesto e hashes das fontes antes da execução; recalcular os rótulos sem refazer STT; exigir cardinalidade, IDs, texto e tempos idênticos; manter cópia byte a byte no journal durante a transação; atualizar JSON, TXT, manifesto e índice com nova revisão. O journal é removido só depois da validação; se o alinhamento não fechar, o resultado anterior permanece `partial`.
- [x] Gate de dados: execução limitada ao ID `d34375d6363f4020871fc861f5716329` após confirmação de bandeja e worker ociosos. Resultado `ready`, 726 segmentos, STT e diarização `complete`, zero warnings; `validar_manifesto` e `validar_manifesto_para_job` passaram; índice `pronto`. Revisão do resumo cifrado = revisão do resultado (`rev-reparo-832840d3059b`), modelo `granite4.1:3b`, 475 caracteres; API devolve HTTP 200 e `pronto`.
- [x] Gate de código: `python -m pytest tests/ -q --tb=short` → 985 passed, exit 0; `npm run test:e2e -- reunioes.spec.js` → 16 passed, exit 0; `compileall` dos módulos alterados e `git diff --check` → exit 0.
- [x] Gate operacional: a bandeja ociosa foi reiniciada com o código novo; um único `pythonw.exe transkriptor.pyw` (PID 50144) ficou ativo, registrou `Bandeja pronta` e abriu a ponte em `127.0.0.1:5051`. Em um servidor local temporário da mesma Central, o navegador carregou a reunião real como primeira linha, exibiu `Pronta` e mostrou o resumo de 475 caracteres tanto na dica quanto no diálogo; o servidor de verificação foi encerrado. A rota real já havia devolvido HTTP 200 e `pronto` para a revisão atual.

## Fechamento

Na primeira execução da suíte inteira, um teste de rota deixou uma thread aguardando o estado global de um app falso; a fixture passou a restaurar o provedor de estado, o teste passou a sempre parar o serviço e a espera do serviço passou a aceitar cancelamento. A execução integral seguinte passou (985 testes). A primeira tentativa real de regeneração do resumo teve falha transitória do Ollama; uma repetição manual completa funcionou, então o serviço passou a tentar mais uma vez, com intervalo de 10 s, quando a chamada local falhar. O resumo real foi regenerado depois desse ajuste. A causa exata da falha transitória não foi identificada.

O journal de rollback foi removido após validar o resultado; não há backup persistente independente deste reparo. Os áudios originais e as falas permaneceram preservados. As Tasks 1 e 2 estão nos commits `d62189d` e `cd5184a`. O SHA da Task 3 será informado no retorno, após o commit. O fechamento deste incidente não altera o status de release dos gates físicos v1.8; o gate físico de uma nova reunião com áudio real não foi executado neste incidente.
