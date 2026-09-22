# Remediação da auditoria v1.8 — índice de execução

- Base auditada: `64b415bdc1ae26100b533cbd3c94abafa2dcb0e8`
- Branch local: `remediacao-auditoria-v18`
- Fonte: `docs/superpowers/plans/2026-09-22-remediacao-auditoria-v18.md`
- Estado global: EM EXECUÇÃO; o produto ainda não atende à definição de pronto.

| Task | Estado | Commit de implementação | Evidência | Gate externo |
|---|---|---|---|---|
| 1 — reconciliação SDD | DONE | `c456714e8124e3d8caf95ab511068ed0d7528ed6` | Este índice; RED exit 1, GREEN 10 passed | Não aplicável |
| 2 — cliente Meet | DONE (automação) | `95045e456100ffa9cf1a5d816ce43b6d86eb4a87` | RED/GREEN abaixo | Demo Chrome/Edge real na Task 12: PENDENTE |
| 3–11 — correções sequenciais | PENDING | — | — | Conforme tarefa |
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
