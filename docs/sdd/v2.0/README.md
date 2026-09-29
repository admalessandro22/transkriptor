# Transkriptor — SDD v2.0: nomes exatos no Meet, IA escolhível e instalação em um clique

Elaborado em 29/09/2026. Base: `master` `f292d81`, `config.VERSAO = 1.7.0`.

**Status: decisões respondidas em 29/09/2026; implementação autorizada task a task a partir de T-15.A1 (branch `sdd-v2.0-nomes-ia-instalador`).** A v1.8 continua sendo a fonte ativa da remediação. A v2.0 não altera seus gates.

## Documentos

1. [Diagnóstico](diagnostico.md): como a Tactiq 3.1.7049 captura legendas, nomes, horários e idioma no Meet, e as 26 lacunas do Transkriptor, com evidência em `arquivo:linha`.
2. [Concept](concept.md): visão, princípios, escopo, arquitetura e métricas de sucesso.
3. [Spec](spec.md): 21 requisitos `FR/SEC/UX/NFR-15.*` com rastreabilidade para as tasks.
4. [Plan](plan.md): duas trilhas (nomes; IA e instalação), ordem recomendada, gates, riscos e rollback.
5. [Tasks](tasks.md): 21 tarefas `T-15.*` com arquivos, RED, teste final e aceite.
6. [Decisões do usuário](decisoes-usuario.md): 12 decisões respondidas e autorizações.
7. [Interfaces congeladas](interfaces.md): mensagens da extensão, envelope v2, handshake de relógio, alinhamento, provedores de IA, detecção do Ollama, configurações, Native Messaging.
8. [Protocolo para LLM executora](executor-llm.md): escopo, leitura, regras e paradas.
9. [Evidências](evidencias/README.md).

## Conclusão principal

- A Tactiq não lê a tela. Ela intercepta o `RTCPeerConnection` do Meet, abre os próprios canais de legenda (`captions` e `captions_v2`) e recebe do servidor do Google cada frase com o dispositivo de quem falou. O nome vem do canal `collections` e da RPC `SyncMeetingSpaceCollections`. O horário é o do primeiro pacote da frase. Ela ainda fixa o idioma da legenda, identifica o dispositivo do próprio usuário, deduplica os canais e recupera o canal mudo.
- O Transkriptor **já captura do mesmo jeito** (`extension/meet/rtc.js`), mas descarta o que torna o nome exato:
  - o horário de início da fala é sobrescrito;
  - o relógio nunca é convertido para o tempo do áudio;
  - a atribuição cai numa comparação de texto (Jaccard ≥ 0,5) sem janela de tempo e sem controle de idioma;
  - o resultado final para em "sugestão".
- O plano corrige isso em quatro tasks de maior retorno (A1, A2, C1, C2). Depois fecha a paridade com a Tactiq (B1–B5) e adiciona a transcrição do Meet como segunda saída (C4).
- Em paralelo:
  - unifica Ollama e OpenRouter numa camada de provedores, com seleção separada para resumo e chat e modelo, dispositivo e precisão do Whisper (D1–D3);
  - troca "Python + .bat + modo desenvolvedor + código colado" por setup por usuário, extensão da loja e pareamento automático via Native Messaging, com detecção do Ollama e modelos no seletor (E1–E5).

## Como auditar

```powershell
python scripts/verificar_fase.py --fase v1.8-sdd --sdd-root docs/sdd/v2.0
```
