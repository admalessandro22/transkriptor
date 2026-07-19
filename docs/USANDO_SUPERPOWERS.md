# Usando Superpowers no Transkriptor

## Instalação (concluída)

Skills copiadas para:

```
.grok/skills/superpowers/     # 14 skills do plugin oficial
.grok/skills/Transkriptor-sdd/ # skill SDD específica do projeto
```

`AGENTS.md` na raiz referencia o fluxo completo.

## Fluxo de trabalho v1.2

```
1. Ler docs/sdd/v1.2/concept.md
2. Ler docs/sdd/v1.2/spec.md (requisito FR-* que vai implementar)
3. Abrir docs/sdd/v1.2/tasks.md → pegar próxima T-F* pendente
4. Invocar: superpowers:test-driven-development
5. Seguir: docs/superpowers/plans/2026-07-08-Transkriptor-v1.2-audit-remediation.md
6. Rodar gate: python scripts/verificar_fase.py --fase N
7. Se falhar → superpowers:systematic-debugging
8. Se passar → marcar [x] em tasks.md
9. Ao fechar fase → superpowers:verification-before-completion
```

## Skills por situação

| Situação | Skill |
|----------|-------|
| Início de sessão | `using-superpowers` |
| Implementar tarefa | `test-driven-development` |
| Plano multi-etapa | `writing-plans` |
| Executar plano | `executing-plans` ou `subagent-driven-development` |
| Gate falhou | `systematic-debugging` |
| Antes de marcar done | `verification-before-completion` |
| Fase completa | `requesting-code-review` |
| SDD deste projeto | `Transkriptor-sdd` |

## Comandos rápidos

```bash
# Instalar deps de teste
python -m pip install -r requirements-dev.txt

# Gate fase atual
python scripts/verificar_fase.py --fase 0

# Todos os testes (gate final v1.2)
python scripts/verificar_fase.py --fase all
```

## Atualizar skills Superpowers

```powershell
$src = "$env:USERPROFILE\.claude\plugins\cache\claude-plugins-official\superpowers\6.1.1\skills"
$dst = ".\.grok\skills\superpowers"
Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force
```