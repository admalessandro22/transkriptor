# AGENTS.md — Transkriptor

Guia universal para agentes de IA (Cursor, Grok, Claude Code, Codex) neste repositório.

## Produto

**Transkriptor** — app de bandeja Windows que detecta Google Meet, transcreve offline (Whisper),
diariza falantes e oferece assistente local via Ollama.

## Método de trabalho

Este projeto usa **Spec-Driven Development (SDD)** + **Superpowers**.

### Ordem obrigatória

1. Ler `docs/sdd/v1.2/PLANO-FINAL.md` → **plano fechado**, ordem F0–F9, menu de opções.
2. Ler `docs/sdd/v1.2/concept.md` → visão e escopo.
3. Ler `docs/sdd/v1.2/spec.md` → requisitos `FR-*`, `SEC-*`, `UX-*`.
4. Ler `docs/sdd/v1.2/tasks.md` → tarefa atual.
4. Executar **uma tarefa por vez** de `docs/sdd/v1.2/tasks.md`.
5. Para implementação detalhada com TDD: `docs/superpowers/plans/2026-07-08-Transkriptor-v1.2-audit-remediation.md`.
6. **Antes de codar:** invocar skill `superpowers:test-driven-development`.
7. **Antes de declarar fase concluída:** invocar skill `superpowers:verification-before-completion`.
8. **Se testes falharem:** invocar skill `superpowers:systematic-debugging` → corrigir → re-rodar gate.

### Skills Superpowers (projeto)

Instaladas em `.grok/skills/superpowers/`. Principais:

| Skill | Quando usar |
|-------|-------------|
| `using-superpowers` | Início de toda sessão |
| `writing-plans` | Antes de planos multi-etapa |
| `test-driven-development` | Antes de qualquer código de feature/fix |
| `executing-plans` | Executar plano fase a fase |
| `subagent-driven-development` | Tarefas independentes em paralelo |
| `verification-before-completion` | Antes de marcar tarefa/fase como done |
| `systematic-debugging` | Quando gate de fase falha |
| `requesting-code-review` | Ao fechar uma fase |

### Regras de código

- Python 3.12+, UTF-8, `config.py` para constantes.
- Não duplicar lógica — `transcricao_core.Transcritor` é o núcleo.
- Flask do assistente: **sempre** `host="127.0.0.1"`.
- Transcrições são dados sensíveis — validar paths, escapar HTML, não logar conteúdo.
- Commits em português, imperativo: `fix: corrige ordem de startup do assistente`.
- Uma tarefa (`T-*`) = um commit (ou stack pequeno relacionado).

### Testes

```bash
python -m pytest tests/ -v
python -m pytest tests/ -v --tb=short -x   # parar no primeiro erro
```

Gate de fase: ver `docs/sdd/v1.2/plan.md` § "Gates de verificação".

### Fase 7 — Identificação de voz (`VOCÊ`)

Loopback sozinho **não** captura sua voz na maioria dos Meets. Fase 7 usa:
cadastro de perfil (mic 20s) + gravação paralela do mic + matching ECAPA na diarização.
Ver `docs/sdd/v1.2/concept.md` § "Identificação da sua voz".

### Versões SDD

| Versão | Pasta | Status |
|--------|-------|--------|
| 1.1 | `docs/sdd/` (raiz legado) | Implementado |
| 1.2 | `docs/sdd/v1.2/` | Em execução (auditoria sênior) |