---
name: transkiptor-sdd
description: Fluxo SDD do Transkiptor v1.2. Use ao implementar correções da auditoria, executar fases do plano, ou quando o usuário mencionar SDD, spec, tasks, ou v1.2.
---

# Transkiptor SDD v1.2

## Artefatos (ordem de leitura)

1. `docs/sdd/v1.2/concept.md`
2. `docs/sdd/v1.2/spec.md`
3. `docs/sdd/v1.2/plan.md`
4. `docs/sdd/v1.2/tasks.md`
5. `docs/superpowers/plans/2026-07-08-transkiptor-v1.2-audit-remediation.md`

## Fluxo por tarefa

1. Identificar tarefa `T-*` pendente em `tasks.md`.
2. Invocar `superpowers:test-driven-development`.
3. Escrever teste que falha.
4. Implementar mínimo para passar.
5. Rodar gate da fase (`plan.md`).
6. Se falhar → `superpowers:systematic-debugging` → corrigir → repetir gate.
7. Marcar `[x]` na tarefa e no critério de aceite `AC-*`.
8. Invocar `superpowers:verification-before-completion` antes de declarar done.

## Proibições

- Não pular fases (dependências em `plan.md`).
- Não implementar requisito sem ID (`FR-*`, etc.) rastreável na spec.
- Não declarar fase concluída sem evidência do gate (output de pytest).