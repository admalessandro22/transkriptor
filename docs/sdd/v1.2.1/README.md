# SDD v1.2.1 — Estabilidade da bandeja e detecção do Meet

Hotfix de confiabilidade do Transkriptor para Windows 10/11.

## Documento canônico

**[PLANO-FINAL.md](PLANO-FINAL.md)** — decisão fechada, ordem F0–F4, gates e critérios de aceite.

## Artefatos

| Arquivo | Propósito |
|---------|-----------|
| [concept.md](concept.md) | Problema, evidências, objetivo e limites |
| [spec.md](spec.md) | Requisitos `FR-*`, `NFR-*`, `SEC-*` e `UX-*` |
| [plan.md](plan.md) | Fases, dependências, gates e rollback |
| [tasks.md](tasks.md) | Tarefas executáveis, uma por vez |
| [PLANO-FINAL.md](PLANO-FINAL.md) | Fonte de verdade do hotfix |
| [plano TDD detalhado](../../superpowers/plans/2026-07-18-transkriptor-v1.2.1-tray-stability.md) | Passos RED → GREEN → verificação |

## Status

**Executado e validado em 2026-07-18.** Correções de produção, testes e evidências estão registrados neste pacote; a instância local está ativa pelo atalho da Área de Trabalho.

## Ordem obrigatória

```text
F0 contrato e baseline
  └─► F1 ciclo de vida da bandeja
        └─► F2 detecção real do Meet
              └─► F3 atalho da Área de Trabalho
                    └─► F4 validação integrada e entrega
```

Cada tarefa de [tasks.md](tasks.md) deve ser executada isoladamente com TDD. Uma tarefa verde corresponde a um commit pequeno e relacionado.
