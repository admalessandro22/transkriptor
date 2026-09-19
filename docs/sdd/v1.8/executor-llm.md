# Protocolo de execução para LLM — SDD v1.8

Este documento é normativo para qualquer LLM que implemente a proposta v1.8. Ele reduz escolhas implícitas, mas não substitui leitura de código, testes nem revisão humana. Se houver conflito, vale esta ordem: instruções de sistema/usuário → `AGENTS.md` → `decisoes-usuario.md` → `plan.md` → `concept.md` → `spec.md` → `interfaces.md` → `tasks.md` → este protocolo. O executor deve registrar o conflito e parar antes de alterar comportamento.

## 1. Escopo autorizado e não autorizado

Uma autorização para “executar o plano v1.8” permite alterar código, testes e documentação apenas na tarefa corrente, executar testes locais e criar o commit local previsto. Não permite, sem autorização separada:

- `push`, publicação, deploy, release, tag ou alteração de repositório remoto;
- OAuth com conta real, instalação de extensão em perfil pessoal ou acesso a Google Meet real;
- abrir transcrições, áudios, embeddings, tokens, chaves ou `config_user.json` reais;
- apagar, mover ou migrar dados reais; encerrar processos do usuário; modificar atalhos/registro reais;
- instalar dependência global ou “consertar” o Python do sistema;
- executar gate físico que reproduza/capture áudio sem avisar o usuário e obter autorização para aquele ensaio.

Fixtures sintéticas e diretórios temporários são permitidos. Commits locais só começam após autorização explícita para implementar; este documento, sozinho, não concede essa autorização.

## 2. Leitura obrigatória e pré-checagem

Em toda sessão nova, executar exatamente nesta ordem:

```powershell
git status --short --branch
git rev-parse HEAD
python -c "import config; print(config.VERSAO)"
Get-Content AGENTS.md
Get-Content docs/sdd/v1.8/plan.md
Get-Content docs/sdd/v1.8/concept.md
Get-Content docs/sdd/v1.8/spec.md
Get-Content docs/sdd/v1.8/tasks.md
Get-Content docs/sdd/v1.8/decisoes-usuario.md
Get-Content docs/sdd/v1.8/interfaces.md
Get-Content docs/sdd/v1.8/executor-llm.md
```

Depois:

1. Identificar a primeira tarefa sem evidência concluída cujas dependências estejam concluídas.
2. Conferir `git log -10 --oneline`, `git diff --name-only` e `git diff --cached --name-only`.
3. Se houver mudança do usuário em arquivo da tarefa, não sobrescrever: registrar paths e pedir direção.
4. Se `HEAD` diferir da base registrada na última evidência, fazer delta somente nos arquivos da tarefa e registrar a nova base. Não reaplicar alterações já presentes.
5. Rodar o baseline específico listado na tarefa antes de escrever o RED. Baseline vermelho é bloqueio; não confundir falha preexistente com RED novo.

## 3. Estado: uma tarefa por vez

Estados permitidos: `PENDING`, `IN_PROGRESS`, `BLOCKED`, `DONE`. O estado não é inferido da intenção.

- `PENDING`: sem commit/evidência.
- `IN_PROGRESS`: RED registrado, ainda sem todos os gates verdes.
- `BLOCKED`: depende de decisão/autorização/ambiente externo; código parcial deve permanecer identificável e sem checkbox concluída.
- `DONE`: código + testes específicos + regressões + evidência + commit local existem e correspondem ao mesmo `HEAD`.

Nunca iniciar a próxima tarefa se a atual estiver `IN_PROGRESS`. Nunca marcar fase concluída se uma tarefa obrigatória estiver `PENDING/BLOCKED`. F13.H é opcional; A–G são obrigatórias para a release proposta.

DU-01–DU-15 estão decididas e não devem gerar nova pergunta. DU-16 é informação externa ausente e bloqueia somente H. Uma autorização futura para executar A–G não autoriza reunião real/OAuth; pedir autorização no momento exato de cada gate, conforme DU-12.

## 4. Algoritmo fechado para cada tarefa

Aplicar estes passos, sem reordenar:

1. **READY:** verificar dependências, paths permitidos, working tree e baseline.
2. **CONTRATO:** copiar para a evidência o requisito, interfaces consumidas/produzidas e invariantes.
3. **RED:** escrever primeiro os casos nomeados em `tasks.md`. O teste deve importar interface existente ou o esqueleto mínimo da interface planejada; erro de importação não conta como prova comportamental.
4. **PROVAR RED:** executar cada seletor novo isoladamente. Registrar comando, exit code e trecho que mostra a falha esperada. Se falhar por outro motivo, corrigir o teste/harness antes de seguir.
5. **GREEN MÍNIMO:** implementar somente o comportamento necessário para os casos e contratos da tarefa. Não antecipar tarefa posterior.
6. **PROVAR GREEN:** repetir os seletores RED e o arquivo de teste completo.
7. **REGRESSÃO:** executar exatamente o “Teste final” da tarefa e os gates adicionais indicados.
8. **REVISÃO:** inspecionar `git diff --check`, `git diff --stat`, `git diff -- <paths da tarefa>` e procurar segredo/dado pessoal.
9. **EVIDÊNCIA:** criar `docs/sdd/v1.8/evidencias/T-13.Xn.md` no formato da seção 8.
10. **VERIFICAÇÃO:** invocar `verification-before-completion`; resultados antigos não valem.
11. **COMMIT:** adicionar somente os paths da tarefa e a evidência. Mensagem em português, imperativa. Não usar `git add .`.
12. **PÓS-COMMIT:** registrar SHA, confirmar `git status --short --branch` e que arquivos alheios continuam intactos.

Se a LLM não tiver as skills Superpowers, deve seguir literalmente o ciclo acima. A ausência da skill não autoriza pular RED, diagnóstico ou verificação.

## 5. Regras de interpretação

- “Criar” significa novo módulo focado, UTF-8, sem duplicar lógica existente.
- “Modificar” não autoriza refatoração não relacionada.
- “Aceite” é cumulativo: todos os itens precisam de evidência.
- “Gate real” não pode ser substituído por mock; se indisponível, a tarefa/fase fica bloqueada ou com gate pendente conforme `tasks.md`.
- “Nome” é `display_name` observado/confirmado, não identidade civil.
- Roster não atribui fala. Tile visível não prova fala. Tempo sozinho não nomeia se a incerteza exceder 1,5 s.
- Falta de evidência produz `unknown`/`conflict`, nunca o nome mais frequente.
- Resultado parcial preserva dados válidos e declara a etapa faltante; não fabrica sucesso global.
- Erro de criptografia preserva a única cópia e marca `protection_pending`; nunca apaga para esconder plaintext.
- Todo serviço permanece em `127.0.0.1`. Não abrir listener para LAN.
- Não enfraquecer token, contenção de path, consentimento, COM, locks ou sanitização para fazer teste passar.

Quando surgir uma escolha não fechada:

1. Pesquisar primeiro código, testes, histórico e documentos locais.
2. Se for compatível com interfaces e invariantes, escolher a menor mudança e registrar em “Decisões locais”.
3. Se alterar contrato, segurança, dados, dependência, UX pública ou escopo, parar e propor emenda à spec. Não decidir silenciosamente.

## 6. Decisões arquiteturais já fechadas

| Tema | Decisão obrigatória | Não fazer |
|---|---|---|
| Núcleo | Reusar `transcricao_core.Transcritor`; composição por módulos focados | Criar segundo pipeline de captura/transcrição |
| JS | Vitest para unidade e Playwright para E2E da extensão/UI | Usar parser Python espelhado como prova do JS |
| Lock de job | `msvcrt.locking` em lockfile por job; identidade de processo via Win32 `GetProcessTimes`, encapsulados em `fila_lock.py` | Adicionar Redis/DB ou confiar apenas em `threading.Lock` |
| Resultado | JSON estruturado é canônico; TXT é exportação derivada e versionada | Editar apenas TXT e perder proveniência |
| Transporte Meet | Manifest V3: content script → service worker → WebSocket local autenticado/pareado | Implementar Native Messaging nesta versão ou pôr segredo no content script |
| Eventos Meet | Segmentos JSONL ≤1 MiB ou ≤1 s, cifrados individualmente com primitives existentes; índice sem conteúdo | Manter tudo em RAM ou registrar legenda/nome em job/log |
| Identidade | IDs e evidências primeiro; nome automático somente após calibração | Usar `display_name` como chave única ou fallback por frequência |
| Áudio | STT separado por mic/loopback e fusão temporal; sobreposição preservada | Tratar energia RMS como transcrição ou remover fala simultânea como “eco” |
| Cifra longa | C3 faz streaming de WAV plaintext e ADR; E1 implementa exatamente TKAS/1 + PyNaCl SecretStream descrito em `interfaces.md` | Inventar outra primitiva/framing ou implementá-lo antes de E1 |
| Privacidade | Modos `compatible` e `protected`, com estado efetivo por artefato | Chamar fallback plaintext de “criptografado” |
| Google | REST é opcional; escopo inicial `meetings.space.readonly`; H só com autorização | Exigir Google para o núcleo ou usar roster para inferir autoria |
| Media API | Apenas estudo/piloto isolado em H3 | Adicionar ao startup normal |
| Release | Bump de `config.VERSAO` somente em G3 após todos os gates | Hardcodar versão em outros arquivos |
| Navegadores | Chrome e Edge Windows são obrigatórios | Encerrar D/G validando somente um navegador |
| Zoom | Manter detecção/captura atual; nomes fora da v1.8 | Ampliar identidade para Zoom |
| Saída | JSON canônico; TXT `[HH:MM:SS] Nome: texto` | Tratar TXT como fonte canônica |
| Retenção | Áudio/eventos: 7 dias após resultado válido; resultados: exclusão manual; perfil: revogação | Contar prazo antes de resultado válido |
| Hardware | CPU e CUDA suportados | Declarar release com uma única rota |

## 7. Ordem exata e saídas mínimas

Executar: `A1 → A2 → B1 → B2 → B3 → C1 → C2 → C3 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → E1 → E2 → E3 → E4 → F1 → F2 → F3 → G1 → G2 → G3`. H1 → H2 → H3 somente por decisão explícita.

| Tarefa | Saída que deve existir ao final | Proibição específica |
|---|---|---|
| A1 | índice SDD e verificador requisito→task→teste | reescrever evidência histórica |
| A2 | gate lexical + Vitest/Playwright reais | tocar hardware em teste unitário |
| B1 | claim/lease interprocesso atômico | recuperar PID vivo só por timeout |
| B2 | `ResultManifest` mínimo validado por hash | retenção baseada só em TXT existente |
| B3 | heartbeat, timeout, retry e cancelamento | matar PID sem lease validado |
| C1 | contadores por fonte + watchdog de progresso + COM | callback sob lock |
| C2 | segmentos STT de mic e loopback com origem | `wave.open` em ciphertext |
| C3 | leitor em blocos e rejeição explícita de formato | ler áudio de 2 h inteiro |
| D1 | sessão/aba/conexão/relógio isolados | estado global entre reuniões |
| D2 | pareamento e transporte MV3 autenticado | aceitar prefixo de Origin |
| D3 | parser JS versionado e capability state | primeiro tile visível = falante |
| D4 | spool cifrado durável, ACK após persistência | descarte silencioso no overflow |
| D5 | job v2 leva refs/hash até o worker | embutir eventos sensíveis no job |
| D6 | resolver conservador com abstinência | nome automático não calibrado |
| D7 | resultado canônico + correção/undo | treinar biometria ao renomear |
| E1 | política/estado de proteção tipados | fallback silencioso |
| E2 | inventário e recuperação por sessão | varrer TEMP inteiro |
| E3 | payload tipado, limites e cancelamento | aceitar JSON escalar/lista |
| E4 | logs tipados e ciclo de biometria | conteúdo/tokens/nomes em log |
| F1 | histórico por `meeting_id`/`generation_id` | resposta tardia cruzar reunião |
| F2 | orçamento total e evidências por segmento | tratar fala como instrução confiável |
| F3 | índice paginado e E2E acessível | decifrar todos os textos para listar |
| G1 | locks/constraints, SBOM e CI Windows | corrigir ambiente global |
| G2 | instalação/startup em paths difíceis | alterar atalho/registro real em teste |
| G3 | relatório de métricas e gates físicos | release com gate pendente |
| H1 | OAuth/capability opcional | conta real sem autorização |
| H2 | import idempotente e fonte distinta | lista vazia fingir “completa” |
| H3 | ADR go/no-go ou piloto isolado | dependência experimental no núcleo |

## 8. Evidência obrigatória

Cada `docs/sdd/v1.8/evidencias/T-13.Xn.md` deve conter:

```markdown
# T-13.Xn — título

- Estado: DONE | BLOCKED
- Base: <SHA antes>
- Resultado: <SHA do commit ou "sem commit — bloqueado">
- Requisito: <ID>
- Ambiente: Windows, Python, Node/navegador quando aplicável
- Arquivos alterados: lista exata
- Decisões locais: nenhuma | lista com justificativa

## Baseline
Comando, exit code e resumo.

## RED
Caso, comando, exit code e motivo comportamental esperado.

## GREEN
Comando, exit code e contagem.

## Regressão e gate
Todos os comandos exigidos, exit codes e resultado. Gate não executado = PENDENTE, nunca PASS.

## Segurança e dados
Confirmar ausência de segredo/dado real; listar resíduos temporários criados/removidos.

## Limitações
Lacunas restantes e próxima tarefa autorizada.
```

Não colar fala, nome real, token, path pessoal, embedding ou conteúdo de transcrição na evidência.

## 9. Condições de parada

Parar sem improvisar quando houver: mudança alheia sobreposta; risco de perda da única cópia; necessidade de conta/reunião/pessoa real; contrato incompatível; nova dependência não prevista; teste baseline vermelho; gate físico sem ambiente; vulnerabilidade crítica; ou necessidade de ação externa não autorizada.

O relatório de bloqueio deve dizer: tarefa, evidência, impacto, tentativas seguras já feitas e a única decisão necessária do usuário. Dificuldade técnica, demora ou preferência pessoal não são bloqueio.

## 10. Prompt de retomada recomendado

```text
Execute somente a próxima tarefa elegível do SDD v1.8 do Transkriptor.
Leia AGENTS.md e docs/sdd/v1.8/{decisoes-usuario,plan,concept,spec,tasks,interfaces,executor-llm}.md.
Siga RED→GREEN, teste final, evidência e um commit local. Não faça push,
OAuth, reunião real, migração/exclusão de dados ou mudanças fora da tarefa.
Ao final, informe tarefa, SHA, comandos/exit codes, gates pendentes e working tree.
```
