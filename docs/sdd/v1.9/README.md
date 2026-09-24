# Transkriptor — diagnóstico UI/UX e proposta SDD v1.9 (plataforma visual e Central)

Elaborado em 24/09/2026. Base examinada: `5566f074011948457571cf934c8fb02c8855a6e8`, produto `config.VERSAO = 1.7.0`.

**Status: aprovada em 24/09/2026 (todas as DP-14 na recomendação padrão; DP-14-12 revisada para iniciar já) e em execução na branch `sdd-v1.9-design`, a partir de T-14.A1. A v1.8 continua sendo a especificação ativa da remediação** (`docs/sdd/README.md`); as duas execuções não compartilham branch. Este SDD foi produzido sem as skills Superpowers, a pedido do usuário; a execução futura segue o ciclo de `AGENTS.md`.

## Documentos

1. [Diagnóstico UI/UX](diagnostico-ux.md): inventário das onze superfícies, 22 achados com severidade e evidência, avaliação heurística, o que preservar e a direção recomendada.
2. [Concept](concept.md): conceito "sala de controle silenciosa", escopo, arquitetura de interface e decisões de design.
3. [Design system](design-system.md): tokens de cor (dois temas), tipografia, espaço, elevação, movimento, ícones, componentes com estados, layout da Central, ícone da bandeja, microcopy e glossário.
4. [Spec](spec.md): 21 requisitos verificáveis (`UX-14.*`, `SEC-14.*`, `FR-14.*`, `NFR-14.*`) com rastreabilidade para tarefas, limites e metas.
5. [Plan](plan.md): sete fases F14.A–F14.G, ordem, ciclo por task, gates automatizados e gate visual, migração e rollback, estimativa.
6. [Tasks](tasks.md): 21 tarefas `T-14.*` com arquivos, implementação, RED, migração de testes legados, teste final e aceite.
7. [Decisões do usuário](decisoes-usuario.md): 12 decisões pendentes com recomendação e padrão, autorizações e condição de nova consulta.
8. [Interfaces congeladas](interfaces.md): contrato de tokens, arquivos, IDs de DOM, API da Central, bandeja, consentimento, extensão e fixtures.
9. [Protocolo para LLM executora](executor-llm.md): escopo, leitura obrigatória, regras de front-end, algoritmo por task, paradas e formato de evidência.
10. [Evidências](evidencias/README.md): capturas sintéticas e scripts do diagnóstico; evidências futuras por task.

## Conclusão principal

A engenharia do produto é séria; a apresentação não a acompanha. Existem cinco linguagens visuais (assistente escuro com dourado e serifa, diálogos Tk claros, janela Win32 cinza, extensão sem estilo, ícone desenhado por código), a bandeja é a única "home" com 24 itens, o drawer de participantes não tem design, e a CSP de produção quebra o próprio assistente (botão Parar sempre visível, ícones ausentes). A média heurística é 2,6/5.

A proposta unifica tudo com tokens em fonte única, transforma o assistente em uma Central local (Início, Reuniões, Assistente, Participantes, Configurações, Diagnóstico), redesenha os momentos nativos (ícone, menu, consentimento) e fixa gates de acessibilidade e orçamento como testes. Nada muda em captura, contratos de dados ou privacidade.

## Como auditar este SDD

```powershell
python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v1.9
```

O verificador da v1.8 confere que todo requisito aponta para uma task existente, que toda task tem requisito e seletor de teste final, e que o índice liga os documentos obrigatórios.

## Como usar

Ler `diagnostico-ux.md` → `concept.md` → `design-system.md` → `spec.md` → `plan.md` → `tasks.md` → `decisoes-usuario.md` → `interfaces.md` → `executor-llm.md`. As decisões DP-14-* estão respondidas. Executar uma task por vez conforme `executor-llm.md`, registrando evidência em `evidencias/T-14.Xn.md`.
