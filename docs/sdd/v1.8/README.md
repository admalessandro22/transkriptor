# Transkriptor — diagnóstico e proposta SDD v1.8

Elaborado em 19/09/2026, com inspeção e testes iniciados em 18/09/2026.
Base examinada: `eff83a61f3ee2291e48a80a00da3f70f1475ccbc`, produto `config.VERSAO = 1.7.0`.

**Status: plano aprovado e em execução na `master`. A conclusão de cada tarefa
fica registrada separadamente em `evidencias/`; `config.VERSAO` permanece
`1.7.0` até o gate G3.**
“MIT” foi interpretado como Google Meet. O tipo de conta Google não foi informado; o núcleo proposto funciona sem depender de uma edição Workspace, condicionado à compatibilidade da extensão e à disponibilidade dos sinais na página.

## Documentos

1. [Diagnóstico da plataforma](diagnostico.md): achados, evidências, prioridades, controles existentes e limites da auditoria.
2. [Pesquisa sobre identificação no Meet](pesquisa-meet.md): fontes oficiais, alternativas, requisitos e recomendação.
3. [Concept](concept.md): resultado esperado, arquitetura e decisões.
4. [Spec](spec.md): requisitos verificáveis e contratos de dados.
5. [Plan](plan.md): sequência, dependências, gates, migração e rollback.
6. [Tasks](tasks.md): 28 tarefas, arquivos, critérios e testes ao final de cada item.
7. [Decisões aprovadas pelo usuário](decisoes-usuario.md): escopo, privacidade, retenção, qualidade, autorizações e único dado externo ainda ausente.
8. [Interfaces congeladas](interfaces.md): assinaturas, tipos, formatos e ownership que agentes executores não podem reinventar.
9. [Protocolo para LLM executora](executor-llm.md): autorização, ordem, algoritmo RED→GREEN, decisões fechadas, evidências e condições de parada.
10. [Evidências desta análise](evidencias.md): comandos executados e resultados; testes futuros não são apresentados como executados.
11. [Relatório técnico de segurança](seguranca/report.md): dois achados de severidade baixa, modelo de ameaças e cobertura parcial; acompanha os artefatos canônicos gerados pela auditoria.

## Conclusão principal

A base tem proteções úteis e **520 testes passando**, mas a identificação de participantes não atravessa o fluxo real de captura → fila → worker → diarização. Além disso, a fala do microfone não é transcrita pelo caminho principal, os eventos do Meet podem saturar e a correlação pode substituir `VOCÊ` por um nome remoto sem correspondência textual.

A proposta prioriza integridade de gravação/fila, identificação local com evidência e privacidade. A integração oficial Google é complementar e opcional. Meet Media API fica em avaliação experimental, por suas restrições atuais.

## Como usar

Ler `plan.md` → `concept.md` → `spec.md` → `tasks.md` → `decisoes-usuario.md` → `interfaces.md` → `executor-llm.md`. Executar uma tarefa por vez depois da autorização de implantação. Cada tarefa tem ciclo RED → GREEN, regressão, evidência e commit próprio; cada fase tem gate adicional. A reconciliação dos documentos vigentes e `AGENTS.md` é a T-13.A1, sem reescrever evidências históricas.

Esta entrega é um diagnóstico amplo das superfícies principais, não uma certificação de ausência de vulnerabilidades. A cobertura de segurança tem lacunas explícitas em `diagnostico.md` e `evidencias.md`.
