# Remediação da auditoria v1.8 — índice de execução

- Base auditada: `64b415bdc1ae26100b533cbd3c94abafa2dcb0e8`
- Branch local: `remediacao-auditoria-v18`
- Fonte: `docs/superpowers/plans/2026-09-22-remediacao-auditoria-v18.md`
- Estado global: EM EXECUÇÃO; o produto ainda não atende à definição de pronto.

| Task | Estado | Commit de implementação | Evidência | Gate externo |
|---|---|---|---|---|
| 1 — reconciliação SDD | DONE | `c456714e8124e3d8caf95ab511068ed0d7528ed6` | Este índice; RED exit 1, GREEN 10 passed | Não aplicável |
| 2–11 — correções sequenciais | PENDING | — | — | Conforme tarefa |
| 12 — gates e release | BLOCKED | — | — | CI, áudio real, Chrome/Edge, três pessoas, CPU/CUDA e autorização de release pendentes |

As evidências históricas `T-13.*.md` permanecem intactas; seus antigos estados DONE não comprovam os contratos reabertos pela auditoria. Cada linha deste índice deve ser detalhada após a respectiva task, com comandos, exit codes, ambiente e SHA real. Gate não executado permanece PENDENTE.
