# Índice SDD — Transkriptor

## Fonte ativa

A especificação ativa é a [v1.8](v1.8/README.md). A execução deve começar por
seus documentos normativos, nesta ordem:

1. [Plano](v1.8/plan.md)
2. [Concept](v1.8/concept.md)
3. [Spec](v1.8/spec.md)
4. [Tasks](v1.8/tasks.md)
5. [Decisões aprovadas](v1.8/decisoes-usuario.md)
6. [Interfaces congeladas](v1.8/interfaces.md)
7. [Protocolo para LLM executora](v1.8/executor-llm.md)

Verifique a integridade do mapa requisito → tarefa com:

```powershell
python scripts/verificar_fase.py --fase v1.8-sdd
```

`config.VERSAO` continua sendo a única versão do executável. A versão SDD não
autoriza bump de produto, release, push, OAuth ou qualquer gate físico.

## Proposta em revisão

A [v1.9](v1.9/README.md) (diagnóstico UI/UX, design system e Central) foi
aprovada em 24/09/2026 e é executada na branch `sdd-v1.9-design`, separada da
remediação v1.8. Não autoriza bump ou release. Auditar com
`python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9`.

## Histórico preservado

As pastas v1.1–v1.6 e [VERIFICACAO.md](../VERIFICACAO.md) são registros
históricos. Seus comandos e resultados devem ser lidos no contexto da release
em que foram produzidos; eles não certificam os requisitos v1.8.
