# Remediação da auditoria v1.8 — índice de execução

- Base auditada: `64b415bdc1ae26100b533cbd3c94abafa2dcb0e8`
- Branch local: `remediacao-auditoria-v18`
- Fonte: `docs/superpowers/plans/2026-09-22-remediacao-auditoria-v18.md`
- Estado global: EM EXECUÇÃO; o produto ainda não atende à definição de pronto.

| Task | Estado | Commit de implementação | Evidência | Gate externo |
|---|---|---|---|---|
| 1 — reconciliação SDD | DONE | `c456714e8124e3d8caf95ab511068ed0d7528ed6` | Este índice; RED exit 1, GREEN 10 passed | Não aplicável |
| 2 — cliente Meet | DONE (automação) | `95045e456100ffa9cf1a5d816ce43b6d86eb4a87` | RED/GREEN abaixo | Demo Chrome/Edge real na Task 12: PENDENTE |
| 3 — bridge/sessão/store | DONE (automação) | `362c63d2fc2b4c3ab4b7dd92e19833d907a843a7` | RED/GREEN e 714 testes abaixo | Navegador real na Task 12: PENDENTE |
| 4 — refs Meet no job | DONE (automação) | `d9e2e7f3a2d4b858077be877a247136d0eedf1c9` | RED/GREEN abaixo | Não aplicável |
| 5 — resultado estruturado | DONE (automação) | `3f505e736a98df4f268ec461d30044876186261b` | RED/GREEN e 720 testes abaixo | Não aplicável |
| 6 — sugestão e revisão UI | DONE (automação) | `ab330cf1a3ffa2bd48d909b72cbbb2cc0559af5c` | RED/GREEN abaixo | Não aplicável |
| 7 — TKAS/1 incremental | DONE (automação) | `f6f11b9af2939c0bed660654482588057decff6f` | RED/GREEN e 726 testes abaixo | Não aplicável |
| 8–11 — correções sequenciais | PENDING | — | — | Conforme tarefa |
| 12 — gates e release | BLOCKED | — | — | CI, áudio real, Chrome/Edge, três pessoas, CPU/CUDA e autorização de release pendentes |

As evidências históricas `T-13.*.md` permanecem intactas; seus antigos estados DONE não comprovam os contratos reabertos pela auditoria. Cada linha deste índice deve ser detalhada após a respectiva task, com comandos, exit codes, ambiente e SHA real. Gate não executado permanece PENDENTE.

## Task 2 — cliente da extensão Meet

- Estado: DONE para implementação automatizável; demo Chrome/Edge real continua PENDENTE na Task 12.
- Base: `b401848a2e353fea7609dcbb24db72fa68fb1035`
- Resultado: `95045e456100ffa9cf1a5d816ce43b6d86eb4a87`
- Requisito: SEC-13.D2, FR-13.D1 (porção cliente do envelope).
- Ambiente: Windows, Node/Vitest, Playwright Chromium em página sintética; nenhum perfil ou reunião pessoal.
- Arquivos: `extension/meet/background.js`, `content.js`, `parser.js`, `tests/js/background.test.js`, `background-pairing.test.js`, `tests/e2e/meet-transport.spec.js`.
- Baseline: `npm run test:unit -- tests/js/background.test.js` exit 0, 4 testes.
- RED: `npm run test:unit -- tests/js/background-pairing.test.js` exit 1, 6 falhas pelo listener não exportado; `npm run test:unit -- tests/js/background.test.js` exit 1, 3 falhas por ausência de hello/sessão/envelope; `npm run test:e2e -- meet-transport.spec.js` exit 1 para metadados do parser; teste de troca de reunião na mesma aba exit 1 por vazamento de sessão.
- GREEN/regressão em 22/09/2026: `npm run test:unit` exit 0, 21 testes; `npm run test:e2e -- meet-transport.spec.js` exit 0, 6 testes; `git diff --check` exit 0.
- Segurança/dados: somente identificadores e nomes sintéticos em fixtures; token não entra no envelope, e o relógio de recebimento fica para o bridge. Nenhum processo, perfil, áudio ou dado real foi alterado.
- Limitação: o bridge ainda não aceita `hello`/envelope v1. Essa integração pertence à Task 3; a prova de navegador real pertence à Task 12.

## Task 3 — bridge, sessão e EventStore

- Base: `1df93087fd4f1fed6a20975f5633e185133ba08d`.
- Baseline: `python -m pytest tests/test_sessao_meet.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_eventos_meet_store.py -q --tb=short` exit 0, 38 testes.
- RED observado: `test_duas_abas_no_mesmo_socket_mantem_estado_independente` exit 1 por ausência de `vincular`; `test_seal_impede_append_posterior` exit 1 por append aceito após seal; `test_envelope_v1_sem_sessao_nao_cai_na_fila_legada` exit 1 por fallback à fila legada.
- Emenda do contrato: a ordem de continuar autorizou o vínculo em memória do código observado no `hello` à chave opaca, somente com uma sala ativa única. `plan.md`, `spec.md`, `tasks.md`, `interfaces.md` e `executor-llm.md` registram a regra; sem código ou com ambiguidade, o bridge não entrega nomes.
- RED adicional: conexão lógica sem vínculo, fallback v1 para fila legada, `append` após `seal`, falta de `schema_version`, hello sem estado ativo e falta de vínculo no início real do mixin. A suíte completa inicialmente falhou no limite de 500 linhas (`meet_bridge.py`: 543); o pareamento foi extraído para `meet_pareamento.py` e os testes de limite passaram.
- GREEN em 22/09/2026, Windows/Python 3.12/Node: `python -m pytest tests/test_sessao_meet.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_eventos_meet_store.py -v` exit 0, 46 passed; `npm run test:unit` exit 0, 22 passed; `python -m pytest tests/ -q --tb=short` exit 0, 714 passed; `git diff --check` exit 0.
- O teste WebSocket usa duas conexões lógicas no mesmo socket e reabre o segmento cifrado para provar persistência antes do ACK. O relógio de recebimento vem do servidor; nome/texto não entram em log. Não foram usados Meet real, perfil pessoal ou captura de áudio.
- Commit de implementação: `362c63d2fc2b4c3ab4b7dd92e19833d907a843a7`.

## Task 4 — referências Meet até o worker

- Base: `d44e2d2093ad0bc43f1ff667c171e81f2b060e2b`.
- RED: `python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py::test_parar_sela_e_entrega_refs_ao_job -v` exit 1; a parada real criou job com `eventos_refs=()` apesar de `EventStore.seal()` produzir um segmento.
- GREEN: mesmo teste exit 0; `python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py tests/test_nomes_meet_worker.py tests/test_fila_processamento.py tests/test_processador_reuniao.py -v` exit 0, 21 passed; regressão do ciclo/bandeja exit 0, 16 passed; teste do limite de 500 linhas exit 0; `git diff --check` exit 0.
- Fluxo verificado: `_parar_transcricao()` e `_enfileirar_reuniao()` reais criam job v2 com refs; uma nova `FilaProcessamento` lê o job; `processar_job()` carrega o evento; hash adulterado resulta em `evento_hash_invalido_recusado` e nenhum nome. O teste legado v1 passa sem nome inventado. Dados, áudio e nomes usados são sintéticos.
- Commit de implementação: `d9e2e7f3a2d4b858077be877a247136d0eedf1c9`.

## Task 5 — resultado estruturado canônico

- Base: `76ddfcfba7715ed27e9f8eb9b433ea8dd0439b05`.
- RED: `test_worker_materializa_resultado_estruturado` exit 1 porque `segments_ref` apontava para `reuniao.txt`; `test_manifesto_com_json_malformado_nao_libera_retencao` exit 1 porque um hash válido bastava mesmo com campos de segmento ausentes.
- GREEN em 22/09/2026: `python -m pytest tests/test_resultado_pipeline.py tests/test_resultado_reuniao.py tests/test_processador_reuniao.py tests/test_retencao_resultado.py -v` exit 0, 25 passed; `python -m pytest tests/ -q --tb=short` exit 0, 720 passed; limite de 500 linhas e `git diff --check` exit 0.
- O worker grava `resultados/{job.id}.json`, deriva TXT do JSON, cria as refs e valida o manifesto antes de concluir. O alinhamento usa intervalo e texto, preserva origem e sinaliza `segment_alignment_failed` sem atribuir nome por índice. Saída existente é preservada e o job falha sem apagar o áudio. A API pública `retranscrever()` mantém retorno `str`.
- Commit de implementação: `3f505e736a98df4f268ec461d30044876186261b`.

## Task 6 — sugestões, proveniência e revisão

- Base: `9c4ddef2d2b634790a655524adb442cdbd0fb4c1`.
- RED: `serializar_atribuicao` ausente; worker gravava `assignment: null`; Playwright não mostrava sugestão nem atualizava revisão após 409; TXT editado fora do app permitia avançar revisão JSON antes de falhar. Todos reproduzidos por testes específicos.
- GREEN em 22/09/2026: `python -m pytest tests/test_identidade_reuniao.py tests/test_correlacionador.py tests/test_resultado_reuniao.py tests/test_resultado_pipeline.py tests/test_nomes_meet_worker.py -v` exit 0, 40 passed; `npm run test:e2e -- participants.spec.js` exit 0, 4 passed; limite de 500 linhas e `git diff --check` exit 0.
- Sugestões persistem com status, fonte, confiança, IDs de evidência e versão da calibração. TXT permanece pendente até confirmação manual. O drawer escapa texto/nome, exige escolha manual se o mesmo cluster tiver sugestões divergentes, recarrega a revisão em 409; confirmação e undo atualizam TXT e hashes do manifesto. Não há criação de perfil biométrico nesse fluxo.
- Commit de implementação: `ab330cf1a3ffa2bd48d909b72cbbb2cc0559af5c`.

## Task 7 — autenticação TKAS/1 e leitura incremental

- Base: `02bb011078fb13e7c1d969d06d5f0c1dd2e05802`.
- RED: `test_tkas_rejeita_sufixo_apos_chunk_final_cheio` aceitou bytes não autenticados depois de `TAG_FINAL`; `test_validacao_de_cifra_nao_acumula_chunks` mediu 100 objetos vivos no `list(...)`; inspeção de WAV cifrado com sufixo no segundo chunk retornou sucesso sem consumir o final.
- GREEN em 22/09/2026: `python -m pytest tests/test_crypto_stream.py tests/test_audio_streaming.py tests/test_audio_utils.py -v` exit 0, 20 passed; após remover parser RIFF não usado, gate dirigido exit 0, 20 passed; `python -m pytest tests/ -q --tb=short` exit 0, 726 passed; `git diff --check` exit 0.
- TKAS/1 exige chunk size fixo e EOF após a tag final. A validação de `encrypt_file` itera sem agregar plaintext; falha remove o temporário. `IteratorReader` mantém apenas o chunk atual; `wave.open` e inspeção consomem o stream cifrado inteiro sem tempfile plaintext. A suíte de áudio longo existente exercita 60 segundos sintéticos em blocos; gate físico de duração maior permanece na Task 12.
- Commit de implementação: `f6f11b9af2939c0bed660654482588057decff6f`.
