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
| 4–11 — correções sequenciais | PENDING | — | — | Conforme tarefa |
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
- Commit de implementação: `362c63d2fc2b4c3ab4b7dd92e19833d907a843a7`. Task 4 ainda não iniciada.
