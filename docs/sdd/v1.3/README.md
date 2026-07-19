# SDD v1.3 — Nomes, Ollama e Atalho Global

Pacote de melhorias pós-auditoria de 2026-07-19. Pronto para execução por agente LLM.

## Artefatos

| Arquivo | Propósito |
|---------|-----------|
| [concept.md](concept.md) | Auditoria completa (achados A/B/C), objetivo e limites |
| [spec.md](spec.md) | Requisitos `FR-*`, `NFR-*`, `SEC-*`, `UX-*` por fase |
| [plan.md](plan.md) | Ordem F1–F7, gates, rollback e riscos |
| [tasks.md](tasks.md) | Tarefas executáveis com TDD, uma por vez |

## Status

**Planejado em 2026-07-19 (revisado com decisões do usuário). Não iniciado.**
Baseline: 170 testes verdes.

Decisões incorporadas: gravação local garantida de toda reunião (áudio retido 7 dias,
criptografado), pausa com confirmação e aviso, transcrições criptografadas por padrão,
Whisper `auto` por hardware (GTX 1650 → `medium`/CUDA).

**Revisão pós-entrega (2026-07-19):** por decisão do usuário, a **Fase 3 (atalho global
Ctrl+Espaço) foi removida** — o app abre por dois cliques no atalho/arquivo e fica na
bandeja até ser fechado, **sem atalho de teclado**. O `.lnk` continua sem `Hotkey`
(FR-3.6 mantida). `hotkey_global.py` e seus testes foram excluídos; a transcrição manual
opera apenas pelo menu da bandeja.

## Ordem obrigatória

```text
F1 higiene + git ─► F2 gravação garantida ─► F3 Ctrl+Espaço ─► F4 Ollama
  ─► F5 nomes das vozes ─► F6 robustez + Whisper auto ─► F7 instalador ─► F8 refatoração
```

Regras do método: ver `AGENTS.md` (TDD com skills Superpowers, um commit por tarefa,
gate verde antes de avançar de fase).
