# Transkriptor v2.0: nomes exatos, IA escolhível e instalação em um clique — plano de implementação

> **Para agentes executores:** use obrigatoriamente `superpowers:executing-plans`. Uma task por vez, com ciclo RED → GREEN → regressão → evidência → commit. Antes de declarar uma task concluída, rode `superpowers:verification-before-completion`. Se um gate falhar, rode `superpowers:systematic-debugging`.

**Objetivo:** cada fala da transcrição com o nome do Meet e o horário, tão fiel quanto a Tactiq. Instalação sem terminal. Escolha do modelo de transcrição e do provedor/modelo de resumo e chat.

**Arquitetura:** a extensão captura como a Tactiq e preserva o tempo da fala. A ponte mede o relógio. O worker alinha as legendas às palavras do Whisper. A camada `provedores_ia` unifica Ollama e OpenRouter. Um setup por usuário com Native Messaging faz o pareamento automático. Detalhes em `concept.md` e `interfaces.md`.

**Tech stack:** Python 3.12, faster-whisper 1.1.1 (`word_timestamps`), SpeechBrain ECAPA, Flask, extensão MV3 (`world: MAIN`), Vitest, Playwright, Inno Setup 6, `uv` (runtime a partir dos lockfiles), Windows Sandbox para o gate de instalação.

## Restrições globais

- Valem `AGENTS.md`, `v2.0/spec.md` (invariantes) e as decisões aprovadas em `v2.0/decisoes-usuario.md`.
- Enquanto uma DP não for respondida, a task dependente fica `BLOCKED`, sem implementação especulativa.
- Sem bump de `config.VERSAO`, push, publicação na loja, OAuth, chave real, instalação em perfil real ou reunião real sem autorização específica.
- Pré-condição: a remediação v1.8 tem gates físicos pendentes (D2/G1–G3). A v2.0 não os declara concluídos. T-15.F1 cobre os gates de nomes e instalação, que absorvem G3 somente se o usuário aprovar (DP-15-10).

## Trilhas e ordem

Duas trilhas independentes em arquivos. Podem ser executadas em sequência, ou em paralelo em worktrees separadas, com integração ao fim de cada fase.

```
Trilha 1 — nomes         A1 → A2 → C1 → C2 → B1 → B2 → A3 → B3 → B4 → B5 → C3 → C4   (ordem DP-15-12)
Trilha 2 — IA/instalação D1 → D2* → D3 → E1* → E2 → E3 → E4* → E5*
Fechamento               F1 (depende das duas trilhas)
(* = dependia de decisão do usuário; todas respondidas em 29/09/2026)
```

Recomendação para o maior ganho no menor tempo:

1. **Primeiro lote (resolve a maior parte da imprecisão):** A1, A2, C1, C2. Com o horário preservado, o relógio medido e o alinhamento por palavra, o nome passa a vir do tempo, e não da comparação de texto que falha hoje.
2. **Segundo lote:** B1 (idioma) e B2 (você). São as duas causas restantes de erro sistemático.
3. **Em paralelo:** D1 e D3 (configurações de IA), que não tocam na captura.
4. **Depois:** A3, B3, B4 (robustez), C3, C4, e então a Trilha 2 de instalação (E1–E5), que depende de decisões de publicação.

## Fases, gates e critério de saída

| Fase | Tasks | Gate de fase (além do teste final de cada task) |
|---|---|---|
| F15.A relógio | A1–A3 | `python -m pytest tests/ -v --tb=short -x`; `npx vitest run`; `python scripts/gate_reuniao_real.py --segundos 25`; em reunião de teste autorizada, o Diagnóstico mostra incerteza de relógio < `RELOGIO_INCERTEZA_MAX_MS` |
| F15.B captura | B1–B5 | suíte completa; `npx vitest run`; `npm run test:e2e`; reunião de teste com CC desligado: contadores `parsed > 0` nos dois canais, idioma confirmado, dispositivo próprio identificado, zero duplicatas |
| F15.C atribuição | C1–C4 | suíte completa; fixtures de alinhamento ≥ 98%; `gate_reuniao_real.py --segundos 600`; reunião de teste com 3 pessoas mostra nomes e horários na Central e no TXT |
| F15.D IA | D1–D3 | suíte completa; `npm run test:e2e`; troca real de modelo Ollama para resumo sintético; OpenRouter só com chave de teste autorizada |
| F15.E instalação | E1–E5 | `gate_instalacao.py --setup` em Windows Sandbox; pareamento nativo em perfil de teste; extensão da loja (quando publicada) conecta à ponte |
| F15.F fechamento | F1 | métricas do concept; `evidencias/GATE-FINAL.md`; decisão de versão |

Uma fase só fecha com todas as tasks `DONE` e o gate registrado em `evidencias/F15.X-gate.md` com o SHA.

## Ciclo por task

1. Ler o bloco da task, os requisitos citados e as seções de `interfaces.md`.
2. `python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v2.0 --tarefa T-15.Xn`.
3. Escrever os testes RED e mostrar que falham pelo motivo certo.
4. Implementar o mínimo, até GREEN.
5. Rodar o teste final da task e a regressão da fase.
6. Registrar a evidência em `evidencias/T-15.Xn.md` (comandos, contagens, SHA, capturas sintéticas, limites).
7. Fazer um commit em português no imperativo, por exemplo `feat: preserva horário de início da legenda do Meet`.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Meet muda o protocolo (campos, canais, RPCs) | Decodificadores tolerantes com fixtures por build do Meet (`boq_meetingsuiserver_*`); contadores e esqueleto (B4); reserva DOM; C4 funciona só com o que chegar |
| Pedido de idioma rejeitado ou mudança de sequência | Resultado registrado; sem retry agressivo; `nao_alterar` como escape; peso textual zerado quando diverge |
| `word_timestamps` deixa a transcrição mais lenta em CPU | Medido em C1; se passar de 15%, adotar como padrão só com GPU e usar alinhamento por segmento em CPU (emenda) |
| Conflito com a Tactiq na mesma aba | Detecção e aviso (B3); faixa de ids distinta; gate F1 com as duas ligadas |
| Tamanho do instalador com torch/CUDA | Runtime baixado na instalação a partir do lock (DP-15-06); rota CUDA só com NVIDIA |
| SmartScreen bloqueando o setup | Assinatura de código (DP-15-07); sem ela, instrução "Mais informações → Executar assim mesmo" no manual |
| Loja recusa a extensão | Canal "não listada"; reserva por modo desenvolvedor e política corporativa `ExtensionInstallForcelist` documentada |
| Texto sai da máquina pelo OpenRouter | Opt-in por função, consentimento datado, marca em cada saída, sem fallback silencioso, áudio e voz nunca enviados |

## Migração e rollback

- Envelope v1 continua aceito; resultados sem `words`/`alinhamento` continuam legíveis. Reprocessar uma reunião antiga não inventa horário: sem `caption_started_ms`, ela usa o fluxo atual.
- Configurações novas têm padrão em `config.py`; apagar a chave de `config_user.json` volta ao comportamento anterior.
- **Rollback de captura:** a opção `meet_idioma_legenda = nao_alterar` e a desativação de canais extras (constante) voltam ao `rtc.js` só leitura atual.
- **Rollback do instalador:** `instalar.bat` permanece para desenvolvimento até F1 fechar.

## Estimativa relativa

P ≈ meio dia; M ≈ 1–2 dias; G ≈ 3–4 dias de execução assistida, sem contar a revisão da loja e as reuniões reais.

- Trilha 1: 3 P + 7 M + 2 G.
- Trilha 2: 2 P + 5 M + 1 G.
- F1: G.
