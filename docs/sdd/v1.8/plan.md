# Transkriptor: confiabilidade e nomes no Meet — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Revisão independente pode usar subagentes quando autorizada pelas instruções aplicáveis; não executar tarefas dependentes em paralelo.

**Goal:** produzir transcrições locais completas, com participantes identificados quando houver evidência, privacidade explícita e recuperação verificável.

**Architecture:** manter `Transcritor`, separar sessão/eventos/identidade/resultado, tornar jobs seguros entre processos e usar extensão local autenticada. Google REST é complemento opcional; Media API é experimento isolado.

**Tech Stack:** Python 3.12+, Windows/COM, soundcard, faster-whisper, SpeechBrain, Flask/Ollama, extensão Chromium Manifest V3, pytest, Vitest, Playwright e PyNaCl/Libsodium SecretStream para áudio longo protegido. Versões concretas serão fixadas a partir da matriz validada em G1.

## Global Constraints

Aplicam-se integralmente os invariantes de `spec.md` e as decisões DU-01–DU-16 de `decisoes-usuario.md`: UTF-8/PT-BR; constantes em `config.py`; `Transcritor` único; nenhum callback sob lock do ciclo; serviços em `127.0.0.1`; processamento local; consentimento antes de captura; dados reais isolados dos testes; sem exclusão de original antes de cópia equivalente validada.

Este plano está em execução na tarefa corrente registrada em `tasks.md`. Não
bump de versão, instalação de extensão, OAuth, publicação ou migração sem a
autorização específica exigida por `decisoes-usuario.md`.

## Checkpoint de execução — 19/09/2026

Este é o estado factual para retomada por outra LLM. Ele não substitui a
definição de pronto nem altera a ordem obrigatória das tarefas.

| Tarefa | Estado | Evidência/commit |
|---|---|---|
| T-13.A1 | DONE | `0b7a11d`, `2d7a521`; evidência `T-13.A1.md` |
| T-13.A2 | DONE | `604c935`, `a1149f2`; evidência `T-13.A2.md` |
| T-13.B1 | DONE | `e0ad07f`, `8850e92`; evidência `T-13.B1.md` |
| T-13.B2 | DONE | `7d971a3`, `86979bd`; evidência `T-13.B2.md` |
| T-13.B3 | DONE | `c9a7255`, `8ca0f8e`, `0a175fb`; evidência `T-13.B3.md` |
| T-13.C1 | DONE | `8a65132` (C1) + commit de fechamento; evidência `T-13.C1.md` (gates 25 s e 600 s APROVADOS) |
| T-13.C2 | DONE | `846d52a` (automatizada) + commit de fechamento; evidência `T-13.C2.md` (gate mic humano APROVADO) |
| T-13.C3 | DONE | commit de fechamento; evidência `T-13.C3.md` (F13.C encerrada) |
| T-13.D1 | DONE | commit de fechamento; evidência `T-13.D1.md` |
| T-13.D2 | BLOCKED | implementação commitada (`765ef1d`); evidência `T-13.D2.md`; demo Chrome+Edge pendente de autorização |
| T-13.D3 | DONE | commit de fechamento; evidência `T-13.D3.md` (exceção: iniciado com D2 BLOCKED, só fixtures/JS) |
| T-13.D4 | PRÓXIMA | depende de D3 DONE; sem coleta real sem autorização |

### Base e árvore de trabalho

- Base de C1: `0a175fba7ba737862b44aa965e764848425a8b56`; commit C1: `8a651328f9994016af5326ce16281010c095fca9`.
- Fechamento de C1 nesta sessão: correção do validador do gate em `scripts/gate_reuniao_real.py` (aceita `transkriptor|transcriptor|transcritor`; Whisper grafou “Transcriptor” nas execuções reais), evidência promovida a DONE, `tasks.md` com C1 marcada.
- `transcricao_core.py` tem 497 linhas, respeitando o limite de 500. Pastas temporárias do gate (`--manter` para diagnóstico) foram removidas após a análise.

### Implementação local de C1 a preservar e revisar

- Métricas por `loopback` e `microfone`: frames, último frame monotônico,
  erros consecutivos, lacunas e estado de espaço em disco; o conteúdo de áudio
  não entra nas métricas nem nos logs.
- O watchdog distingue silêncio (frames avançam) de fonte viva sem frames,
  supervisiona/reinicia o microfone sem gerar alarme quando ele está desligado e
  sinaliza disco sem espaço uma única vez por ocorrência.
- Falha/reconexão da fonte registra marcador técnico de lacuna no resultado e
  fecha a lacuna quando os frames retornam.
- `gravar_audio_microfone()` usa `com_inicializada()`; `stop()` não fecha,
  move, diariza ou descarta WAV enquanto houver thread escritora viva e deixa
  a finalização pendente e visível.

### Verificação já observada

- Baseline anterior ao RED de C1: 37 testes passaram.
- RED→GREEN de C1: 11 testes em `tests/test_captura_progresso.py` passaram.
- Teste final exigido por C1, depois da última alteração: 48 testes passaram:
  `python -m pytest tests/test_captura_progresso.py tests/test_diagnostico.py tests/test_com_audio.py tests/test_watchdog.py tests/test_lock_sem_callback.py tests/test_dubles_fieis.py -v --tb=short`.
- Limite de linhas, compilação e C1: 21 testes passaram:
  `python -m pytest tests/test_limite_linhas.py tests/test_v16_g_qualidade.py tests/test_captura_progresso.py -v --tb=short`.
- Suíte completa refeita: `python -m pytest tests/ -qq --tb=short` → exit code 0, **566 passed** em 144.30 s.
- Gates físicos autorizados (DU-12) em 19/09/2026, ambos **APROVADOS — 11 etapas**: 25 s (384.000 frames, 0 falhas) e 600 s (9.600.000 frames, 0 falhas; WAV 601 s; 19/20 termos).

### Próximos passos (C2 em diante)

1. C1 está DONE. Próxima tarefa elegível: T-13.C2, uma por vez, com RED→GREEN, teste final, evidência e commit local; push autorizado pelo usuário.
2. C3 encerra F13.C com o gate longo já validado aqui mais o streaming em blocos.
3. F13.D–G exigem gates reais próprios (Chrome/Edge, corpus, instalação); cada um pede autorização específica na hora, por DU-12.

Antes de implementar, a LLM executora deve ler integralmente `interfaces.md` e `executor-llm.md`. Esses documentos fecham assinaturas, escolhas técnicas, escopo autorizado, formato de evidência e condições de parada. Não substituir uma decisão fechada por preferência do agente. Se uma decisão se provar inviável, propor emenda documental e parar a task antes de alterar consumidores.

O usuário aprovou todas as decisões de produto necessárias para A–G. Não interromper A–G para perguntar novamente sobre navegador, Zoom, formato de saída, thresholds, biometria, modos de proteção, retenção, CPU/CUDA ou política de falha. Gates reais continuam exigindo autorização por execução. H permanece bloqueada até tipo/edição da conta Google e autorização específica.

### Definição objetiva de pronto

Uma task está pronta somente quando seu requisito, RED comportamental, GREEN, teste final, revisão do diff, evidência e commit local apontam para o mesmo código. Uma fase está pronta somente quando todas as tasks obrigatórias da fase e o gate da fase estão verdes. “Código escrito”, “suíte geral verde” ou “mock passou” isoladamente não significam conclusão.

## Ordem de implantação

| Fase | Objetivo | Dependência / saída |
|---|---|---|
| F13.A | Reconciliar SDD e consertar instrumentos de verificação | Base para qualquer alteração funcional |
| F13.B | Garantir integridade de jobs, retenção e worker | Sem perda/duplicação de trabalho nos ensaios de crash |
| F13.C | Garantir áudio e fala local/remota | Gate físico e regressões COM/lock |
| F13.D | Entregar nomes de ponta a ponta | Sessão → transporte → extração → storage → worker → atribuição → revisão |
| F13.E | Fechar política de proteção, temporários e API | Nenhuma degradação silenciosa; testes negativos de fronteira |
| F13.F | Corrigir contexto, respostas longas e UX | Conversas isoladas e interface comportamentalmente verificada |
| F13.G | Reproduzir instalação e validar qualidade/release | Release local pronta só com gates humanos e artefatos |
| F13.H | Complemento Google e experimento de mídia | Opcional; H1→H2; H3 é decisão experimental, não gate do núcleo |

Para não persistir eventos sensíveis sem cifra, D4 já implementa a exigência de chave para seu armazenamento. E1 unifica depois essa política com os caminhos legados; a dependência não autoriza fallback plaintext em D4.

## Ciclo obrigatório de cada tarefa

- [ ] Ler requisito, contratos e casos negativos específicos da task.
- [ ] Invocar `superpowers:test-driven-development` antes de código de feature/fix.
- [ ] Escrever teste de comportamento com entrada/saída descritas em `tasks.md`; rodar seletor do teste e confirmar RED pelo comportamento esperado. Criar interfaces mínimas se necessário: erro de import não comprova a regressão.
- [ ] Implementar a menor alteração coesa nos arquivos definidos; preservar alterações do usuário.
- [ ] Rodar **o teste específico ao final da task** e a regressão indicada; ambos GREEN.
- [ ] Registrar comando, data, ambiente, exit code e resultado em `evidencias/T-13.Xn.md`, sem dados pessoais.
- [ ] Revisar segurança/compatibilidade; invocar `verification-before-completion` antes de marcar concluída.
- [ ] Criar commit em português, imperativo, somente com arquivos da task; registrar SHA. Ex.: `fix: preserva eventos Meet no processamento posterior`.

Se um teste falhar: `systematic-debugging`, investigar causa, corrigir e repetir o mesmo gate. Não atualizar expected para esconder o defeito. Última task da fase exige também o gate da fase e revisão de código prevista no AGENTS.

## Gates por fase

Os comandos de testes novos abaixo só existirão após as respectivas tasks; não são evidências da análise atual.

| Fase | Gate automatizado | Evidência adicional |
|---|---|---|
| A | `python -m pytest tests/test_sdd_rastreabilidade.py tests/test_gate_reuniao_qualidade.py -v`; `npm run test:unit` | Provar que cabeçalho e marcador sem fala reprovam; JS real é executado |
| B | `python -m pytest tests/test_fila_concorrencia.py tests/test_retencao_resultado.py tests/test_worker_liveness.py -v` | Dois subprocessos, crash durante gravação de job e retomada sem duplicar |
| C | `python -m pytest tests/test_diagnostico.py tests/test_com_audio.py tests/test_lock_sem_callback.py tests/test_dubles_fieis.py tests/test_captura_progresso.py tests/test_audio_duas_fontes.py tests/test_audio_streaming.py -v` | Gates de 25 s/600 s e teste de mic com frase exclusiva |
| D | `python -m pytest tests/test_sessao_meet.py tests/test_eventos_meet_store.py tests/test_nomes_meet_worker.py tests/test_identidade_reuniao.py tests/test_resultado_reuniao.py tests/test_meet_bridge_seguranca.py -v`; `npm run test:unit`; `npm run test:e2e` | Chrome/Edge reais: três participantes, duas abas, reconexão, legenda desligada, homônimos |
| E | `python -m pytest tests/test_politica_privacidade.py tests/test_crypto_stream.py tests/test_recuperacao_sessao.py tests/test_assistente_seguranca.py tests/test_privacidade_eventos.py -v`; `npm run test:e2e` | Falha DPAPI, corrupção/truncamento TKAS e crash antes/depois da cifra; inventário seguro de resíduos |
| F | `python -m pytest tests/test_assistente_ollama.py tests/test_resumo_orcamento.py tests/test_indice_transcricoes.py -v`; `npm run test:e2e` | Sessões A/B isoladas, cancelamento no servidor, teclado/Narrador, 375/860/1366 |
| G | `python -m pytest tests/ -q --tb=short`; `python scripts/verificar_fase.py --fase all`; `npm ci`; `npm run test:unit`; `npm run test:e2e`; `python -m pip check`; `git diff --check` | Instalação limpa Windows CPU/CUDA, corpus de qualidade e relatório físico |
| H | `python -m pytest tests/test_google_capabilities.py tests/test_google_meet_import.py -v` | Conta autorizada; expiração/403/429; H3 requer piloto separado e elegibilidade |

## Gate físico de captura e de identificação

Antes de mexer em captura: `python -m pytest tests/test_diagnostico.py -v`.
Após alterações: `python scripts/gate_reuniao_real.py --segundos 25` e `python scripts/gate_reuniao_real.py --segundos 600`.

Esses gates serão reforçados em A2. Continuam sendo ensaios do caminho de áudio com fala de teste; não provam detecção espontânea nem nomes no Google Meet. O gate de identificação adicional, implementado em G3, precisa:

1. Reunião consentida em Chrome e depois Edge, versões registradas, três pessoas com falas alternadas e frases exclusivas do mic.
2. Legendas PT-BR, câmera ligada/desligada, troca de aba, minimização, perda/reconexão da extensão e retorno do aplicativo.
3. Duas abas de reuniões diferentes; uma encerra enquanto a outra continua. Não unir eventos/nomes entre elas.
4. Homônimos, convidado, alteração de nome, telefone/dispositivo compartilhado quando disponível, sobreposição e ruído.
5. Encerrar captura, reiniciar worker, abrir resultado e verificar que texto, nomes, tempos e proveniência sobrevivem.
6. Corrigir um nome, reexportar e desfazer. Nenhum perfil de voz novo é criado sem ação separada.
7. Recusar gravação ou revogar nomes: nenhum áudio/conteúdo não autorizado persistido; heartbeat mínimo permitido para detecção.
8. Registrar métricas e amostra de referência consentida fora do repositório; evidência pública só contém agregados e IDs sintéticos.

Sem pessoas/contas/hardware disponíveis, marcar **gate pendente**. Não substituir por mock, `--sem-audio` ou screenshot e declarar sucesso real.

## Migração e rollback

- Jobs v1 continuam legíveis. Importar para schema v2 somente com backup e migração idempotente; job em execução pertence ao lease existente.
- Eventos históricos ausentes não podem ser reconstruídos por adivinhação. Preservar `FALANTE_XX` e permitir revisão; áudio pode ser reprocessado sem prometer recuperar nomes passados.
- Adicionar resultados estruturados ao lado dos arquivos antigos. Não sobrescrever texto corrigido manualmente; exportações têm versão/hash e política de colisão.
- Instalação existente preserva a preferência compatível até escolha explícita; instalação nova começa protegida. A interface mostra as consequências para abertura/exportação fora do aplicativo.
- Reverter código com `git revert` por task. Não reverter ou remover dados em bloco. Se uma versão anterior não entende schema v2, usar exportação compatível e desabilitar o worker antigo para esses jobs; nunca consumir silenciosamente formato desconhecido.
- Antes de trocar versão em uso: confirmar ausência de gravação, parar de aceitar novos jobs, aguardar/preservar lease e reiniciar apenas o aplicativo do projeto. Não interromper outros programas.
- Release bloqueada por perda de áudio, vazamento entre reuniões, nome automático incorreto recorrente, cifra falhando silenciosamente, teste obrigatório vermelho ou gate real sem evidência.

## Estimativa de esforço

Faixas para planejamento, não promessa: A–C, 8–14 dias úteis de engenharia; D, 10–18; E–F, 8–14; G, 4–8. Núcleo: aproximadamente 30–54 dias úteis de uma pessoa, incluindo testes e revisão. H1–H2: 4–8 adicionais; H3: 2–4 para estudo/piloto se elegível. Esperas por participantes, políticas Google, hardware e validação institucional não estão incluídas. Reestimar após A2 e o primeiro ensaio D2.

## Critério de entrega da implementação

Todas A–G GREEN, fontes/testes/artefatos no mesmo commit, evidências disponíveis, documentação atualizada, `config.VERSAO` alterada apenas no fechamento G3. H pode permanecer explicitamente não contratado/indisponível sem comprometer o núcleo. Commit/push/publicação só no fluxo de implantação autorizado; a presente solicitação entrega diagnóstico e plano.
