# Decisões aprovadas pelo usuário — SDD v1.8

Confirmação recebida em 19/09/2026. Estas decisões são normativas para concept, spec, plano, tasks e execução. A LLM não deve perguntar novamente nem alterar estes valores, salvo se o usuário revogar expressamente uma decisão.

| ID | Decisão aprovada | Aplicação obrigatória |
|---|---|---|
| DU-01 | F13.A–F13.G formam o núcleo obrigatório. H1–H2 são opcionais; H3 não integra a execução normal. | Release do núcleo não depende do Google. H só começa com autorização posterior. |
| DU-02 | Processamento continua local. Áudio, transcrição e biometria não são enviados ao Google ou a outro serviço. | Conector Google, quando autorizado, acessa somente participantes e transcrições nativas permitidas. |
| DU-03 | Chrome e Edge no Windows são navegadores oficialmente suportados. | Gate D2/D3/D7 e gate final precisam dos dois navegadores. |
| DU-04 | Zoom permanece apenas no suporte atual de detecção/captura; nomes automáticos de Zoom estão fora da v1.8. | Não ampliar parser, transporte ou identidade para Zoom. |
| DU-05 | JSON estruturado é canônico. TXT é exportação no formato `[HH:MM:SS] Nome: texto`. | D7 testa equivalência de texto, tempo e nome entre JSON e TXT. |
| DU-06 | Nome automático exige precisão seletiva ≥98% e cobertura ≥80% nos turnos com evidência utilizável. | Abaixo da meta, usar sugestão ou `Identificação pendente`; nunca adivinhar. |
| DU-07 | Correção manual prevalece, pode ser desfeita e vale para a reunião selecionada. | Renomear nunca cadastra biometria automaticamente. |
| DU-08 | Perfil de voz é opcional, desligado por padrão, requer consentimento separado e pode ser removido com verificação. | E4 implementa opt-in, revogação e prova de remoção. |
| DU-09 | Instalação existente sem política explícita permanece `compatible`; instalação nova inicia `protected`. | UI mostra estado efetivo. Exportação TXT em modo protegido exige ação explícita. |
| DU-10 | Áudio expira após 7 dias somente com resultado validado e sem trabalho dependente. Eventos Meet brutos expiram 7 dias após resultado válido. Transcrições/resultados permanecem até exclusão manual. Perfil de voz permanece até revogação. | B2/E2/E4 implementam relógios separados e bloqueios de retenção. |
| DU-11 | Migração começa em inventário/dry-run. Nenhum dado real é removido sem confirmação específica com lista exata de alvos. | Migração e recuperação não recebem autorização destrutiva implícita. |
| DU-12 | Testes começam sintéticos. Cada gate com reunião real, reprodução/captura de áudio, extensão em perfil pessoal ou OAuth exige aviso e autorização específica. | Gate não autorizado fica `PENDENTE`, nunca `PASS`. |
| DU-13 | Depois de autorização explícita para implementar, a LLM pode criar um commit local por task. | Push, tag, release, instalação real, OAuth e publicação continuam proibidos sem autorização própria. |
| DU-14 | A release suporta CPU e GPU CUDA compatível. | G1/G3 testam e documentam as duas rotas; otimização exclusiva da máquina atual não encerra a fase. |
| DU-15 | Falha parcial preserva dados íntegros e informa a etapa afetada. | Erro, ausência de permissão ou ausência de dados nunca é apresentado como sucesso. |
| DU-16 | Tipo e edição da conta Google não foram informados. | H1–H3 ficam `BLOCKED_EXTERNAL_INFO` até o usuário informar conta pessoal/Workspace e edição, além de autorizar OAuth/piloto. A–G prosseguem normalmente. |

## Rastreabilidade para implementação

| Decisão | Tarefas/gates que a aplicam |
|---|---|
| DU-01 | A1, G3, H1–H3 |
| DU-02 | D4, E1, E4, H1–H2 |
| DU-03 | D2, D3, D7, G3 |
| DU-04 | A1, G3 (verificação de não expansão) |
| DU-05 | B2, D7 |
| DU-06 | D6, G3 |
| DU-07 | D7, E4 |
| DU-08 | E1, E4 |
| DU-09 | E1, G2 |
| DU-10 | B2, D4, E2, E4 |
| DU-11 | E1, E2, G2 |
| DU-12 | A2, C1–C3, D2–D3, D7, G3, H1–H3 |
| DU-13 | Protocolo de todas as tasks; fechamento G3 |
| DU-14 | G1, G3 |
| DU-15 | B3, D7, E1, E3, F2 |
| DU-16 | H1–H3 |

## Autorizações vigentes

- Autorizado agora: produzir e refinar diagnóstico/plano documental.
- Não autorizado agora: implementar A–H, criar commits de implementação, executar reunião real, OAuth, instalar extensão, migrar/excluir dados, push, tag, release ou publicação.
- Uma futura ordem explícita para “executar o plano v1.8” autoriza código/testes e commits locais de A–G, uma task por vez, respeitando DU-12 e DU-13. Não autoriza automaticamente H nem ações externas.

## Condição para nova consulta ao usuário

A–G não têm decisão de produto pendente. Consultar o usuário apenas se surgir mudança material não coberta pela spec, ação externa/destrutiva, conflito com trabalho local ou gate real. Para H, solicitar primeiro o tipo/edição da conta e a autorização específica; não pedir nem registrar credenciais.
