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

O journal de rollback foi removido após validar o resultado; não há backup persistente independente deste reparo. Os áudios originais e as falas permaneceram preservados. As Tasks 1, 2 e 3 estão nos commits `d62189d`, `cd5184a` e `8e9ad13`. O fechamento deste incidente não altera o status de release dos gates físicos v1.8; o gate físico de uma nova reunião com áudio real não foi executado neste incidente.

## Continuação — 25/09/2026: aprender voz da reunião selecionada

**Sintoma:** ao confirmar “Aprender voz” em Participantes, a Central mostrou “Nenhuma separação de vozes recente para aprender”, apesar de haver resultado e áudio íntegros da última reunião.

**Causa confirmada:** `participantes.js` envia apenas rótulo e nome; `central_api.py` consulta os centroides em `app.transcritor._centroides_por_rotulo_ultima`. O worker de diarização usa outro `Transcritor`, não entrega esses centroides à bandeja, e um reinício também apaga esse campo. Além de falhar, um centroide global poderia pertencer a outra reunião com o mesmo rótulo. O diagnóstico histórico D08 em `docs/sdd/v1.8/diagnostico.md` já descrevia essa lacuna.

### Task 4 — aprender voz vinculada a uma reunião

**Files:** criar `aprendizado_voz_reuniao.py` e `tests/test_aprendizado_voz_reuniao.py`; modificar `central_api.py`, `static/js/participantes.js`, testes da rota/interface e este plano.

**Interfaces:** `POST /api/acoes/aprender-voz` recebe `meeting_id`, `expected_revision`, `rotulo`, `nome`. O serviço carrega somente o job `ready` escolhido, confere manifesto, hashes das fontes, revisão e rótulo; extrai embeddings ECAPA de trechos suficientes da mesma fonte, sem guardar biometria intermediária. Só a confirmação explícita existente salva a voz conhecida, com a cifra/política atual.

- [x] RED: reproduzir 404 com provedor vazio mesmo para uma reunião válida; impedir que um rótulo igual em outra reunião ou revisão obsoleta resulte em cadastro; recusar áudio ausente, adulterado ou insuficiente sem gravar biometria.
- [x] GREEN: enviar ID e revisão do resultado selecionado; calcular o embedding sob demanda a partir de trechos sem sobreposição marcados para o rótulo nessa reunião e preservar a confirmação separada; retornar erro específico se a amostra não for segura. Nunca usar centroides globais de outra reunião.
- [x] Gate: testes dirigidos RED→GREEN, suíte Python, E2E de Participantes/Aprender voz, `git diff --check`, inspeção real não mutante do áudio da reunião de 24/09 e reinício da bandeja. Cadastro de um nome real depende da identificação do falante/nome pretendido pelo usuário; nenhum nome será inferido da transcrição.

### Task 5 — usar a fonte correta ao separar vozes e reavaliar a reunião

**Causa adicional confirmada no código:** `retranscritor.py` e o reparo anterior entregavam o trecho do loopback ao ECAPA mesmo quando o segmento STT era do microfone. Na reunião de 24/09, 655 de 726 segmentos eram do microfone. Em uma amostra não mutante, os trechos dos rótulos mais frequentes não produziram embeddings coerentes para cadastro; isso não prova por si só quem falou, mas impede aprender uma identidade segura do resultado atual.

**Files:** modificar `audio_trechos.py`, `diarizador.py`, `diarizacao_final.py`, `retranscritor.py`, `scripts/reparar_diarizacao_reuniao.py`, `tests/test_audio_duas_fontes.py`, `tests/test_reparo_diarizacao_reuniao.py` e este plano.

**Interfaces:** selecionar `trechos_lb[i]` ou `trechos_mic[i]` conforme `audio_source` do segmento fundido, com erro explícito para cardinalidade/origem inválida. A guarda anti-eco continua recebendo o loopback original por segmento, distinto do áudio escolhido para o embedding. O reparo de uma reunião já `complete` requer opção específica para refazer somente rótulos a partir das fontes corretas, preservando fala, tempos e áudios.

- [x] RED: duas falas simultâneas, uma de cada fonte, fizeram os dois modos de `retranscrever_resultado` entregar sinal de loopback ao diarizador (2 failed, exit 1).
- [x] GREEN: fonte correta no fluxo protegido, compatível e reparo; nenhuma inferência de voz por uma fonte diferente da que gerou o segmento. O RMS anti-eco continua sendo calculado com o loopback original.
- [ ] Gate de dados: primeiro executar reavaliação sem escrita na reunião real e aferir cardinalidade, alinhamento e distribuição; só aplicar reparo limitado ao ID confirmado se a saída for íntegra. Depois regenerar/verificar o resumo da revisão nova e conferir o painel.
- [ ] Gate de código/operacional: testes dirigidos, suíte completa, E2E, manifesto/índice/resumo, `git diff --check`, reinício seguro da bandeja. O gate de nova reunião com áudio real continua distinto.

**Checkpoint operacional:** às 17h18 de 25/09 uma nova gravação começou na bandeja (PID 50144). O recálculo exploratório, iniciado antes disso, foi interrompido pelo PID exato 3736 para não disputar CPU; era leitura apenas e não alterou a reunião de 24/09. O monitor confirmou `gravando=True` às 17h24. Testes executados durante a gravação produziram erros de teardown no guard de estado real porque a bandeja atualizava legitimamente `transcricoes/sessoes`; repetir os gates com a bandeja ociosa, sem desativar o guard. Não reiniciar a bandeja, não aplicar reparo e não rodar ECAPA completo enquanto houver gravação/processamento.

Às 18h21 a gravação foi encerrada normalmente e o worker `101124` assumiu o job `5e0bbfa92ec644ceb634299b8fa7f805`. Aguardar o worker chegar a estado terminal e o monitor confirmar ociosidade antes dos gates pendentes.

**Retomada em 26/09:** os jobs `5e0bbfa92ec644ceb634299b8fa7f805` e `04e27a3d587446c3a475e4e711d9673d` terminaram `ready`, ambos com STT/diarização `complete`, zero warnings e arquivos cifrados de resumo gravados em 25/09 após os workers. A reunião de 24/09 permanece `ready`, 726 segmentos, revisão `rev-reparo-832840d3059b`, sem warnings e com arquivo de resumo. A sessão de comandos roda como `codexsandboxoffline` e não consegue abrir a chave DPAPI da conta do aplicativo; por isso não verificou o conteúdo nem a revisão interna dos resumos nem aplicou a rediarização real. A Central não estava aberta no navegador; a inspeção de interface não produziu evidência adicional.

**Gates de código desta continuação:** `test_aprendizado_voz_reuniao.py`, `test_central_api.py`, `test_audio_duas_fontes.py`, `test_diarizacao_voce.py` e `test_reparo_diarizacao_reuniao.py` → 41 passed; `test_retranscritor.py` → 5 passed; `test_resultado_pipeline.py` + `test_resumo_reuniao.py` → 30 passed; bloco inicial de API/estado/voz → 29 passed; E2E `exportar.spec.js` → 3 passed. `compileall`, `node --check` e `git diff --check` passaram. A suíte integral foi interrompida com `-1073741510` durante a coleta/primeiros testes; uma execução em segundo plano deu `PermissionError` no temporário do pytest devido ao sandbox, não um resultado de código. Suíte integral, rediarização real, verificação da revisão do resumo após reparo e reinício da bandeja permanecem pendentes.

**Retomada em 27/09:** o monitor registrou `reunião=False` e `gravando=False` às 22h11; a fila não tinha jobs `pending` nem `processing`. Um teste novo reproduziu HTTP 500 quando a leitura de áudio protegido lança `ErroDescriptografia`; após tratamento na rota, o mesmo teste passou com HTTP 503 e sem cadastro de biometria. A rodada dirigida atual (`test_aprendizado_voz_reuniao.py`, `test_central_api.py`, `test_audio_duas_fontes.py`, `test_diarizacao_voce.py`, `test_reparo_diarizacao_reuniao.py`, `test_retranscritor.py`, `test_resultado_pipeline.py`, `test_resumo_reuniao.py`) terminou com **77 passed**; `exportar.spec.js` terminou com **3 passed**. A conta de comandos ainda é `codexsandboxoffline`: `git add` foi recusado por `.git/index.lock: Permission denied`, e a chave DPAPI da conta do aplicativo segue indisponível. O controle do Chrome foi recusado pela revisão automática de acesso. A bandeja não foi reiniciada e o reparo real não foi aplicado; esses gates continuam abertos.

**Gate automatizado final em 27/09:** `python -m pytest tests/ -v --tb=short -x` → **998 passed, 8 warnings**, exit 0, em 40m55s. Os warnings são de `Image.Image.getdata` nos testes de ícones, fora do incidente. `npm run test:e2e -- exportar.spec.js` → 3 passed; `npm run test:e2e -- reunioes.spec.js` → 16 passed, incluindo dica e diálogo de resumo. `compileall` dos módulos alterados, `node --check static/js/participantes.js` e `git diff --check` → exit 0. Isso fecha o gate de código; o gate dos dados reais, o commit e a ativação da nova versão na bandeja continuam pendentes pela identidade/permissões da sessão.

**Retomada em 28/09:** comandos fora do sandbox confirmaram a conta Windows do usuário e abriram a chave DPAPI dedicada. Os três jobs de 24–25/09 permaneceram `ready`, sem jobs `pending`/`processing`; os manifestos validaram os hashes das duas fontes de cada reunião. Os seis áudios legados `.wav.enc` foram abertos e autenticados sem gravar plaintext. Os três resumos cifrados abriram, e cada revisão interna correspondeu à revisão do resultado (475, 499 e 494 caracteres). A bandeja antiga ociosa (PID 50144) foi encerrada e a atual (PID 61940) registrou `Bandeja pronta`, uma única instância e ponte em `127.0.0.1:5051`. Uma Central temporária em `127.0.0.1:5050` mostrou as três reuniões `Pronta`, os resumos em diálogo e a ação separada `Aprender voz` na reunião de 24/09; o diálogo foi cancelado sem cadastrar biometria. Essa Central mostrou `Central sem bandeja`, portanto o painel vinculado à instância da bandeja não foi validado. A instância temporária foi encerrada; a bandeja permaneceu ativa. Testes dirigidos: 77 passed, exit 0; E2E `exportar.spec.js`: 3 passed, exit 0; `git diff --check`: exit 0. Inspeção sem escrita com `--refazer-origens`: 726 segmentos, revisão `rev-reparo-832840d3059b`. Continuam pendentes a reavaliação real dos rótulos, a validação após eventual nova revisão e o gate de nova reunião; nenhum nome foi inferido ou cadastrado.

**Central da bandeja validada em 28/09:** após o usuário abrir “Abrir Transkriptor”, a porta `127.0.0.1:5050` passou a pertencer ao próprio PID 61940 da bandeja. No Edge, a página Início mostrou `Aguardando reunião` e as três reuniões alvo de 24–25/09 como `Pronta`. A página Participantes da reunião de 24/09 mostrou a revisão `rev-reparo-832840d3059b` e os botões `Aprender voz` por rótulo. Nenhum cadastro foi confirmado. Isso valida a Central conectada à instância real da bandeja, sem afirmar que os rótulos antigos já foram recalculados com a correção da fonte.
