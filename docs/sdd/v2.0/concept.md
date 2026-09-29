# Concept — nomes exatos, IA escolhível e instalação em um clique (SDD v2.0)

## Problema

O usuário quer a mesma experiência da Tactiq: cada fala com o nome da pessoa e o horário, como aparece no Google Meet. Quer também instalar em outro computador sem esforço e escolher qual IA transcreve e qual resume, local ou por chave OpenRouter.

O Transkriptor já captura a matéria-prima do mesmo jeito que a Tactiq (canal `captions_v2` + `collections`). A perda acontece depois, em três pontos:

- o horário da fala é descartado;
- o relógio do navegador nunca é convertido para o tempo do áudio;
- a atribuição recai numa comparação de texto que falha em frases curtas e em legendas no idioma errado.

A instalação exige Python, `.bat`, modo desenvolvedor no Chrome e código de pareamento copiado à mão.

## Visão

> "Abro o instalador, clico em Avançar, adiciono a extensão como qualquer outra e entro no Meet. No fim da reunião, a transcrição do Whisper mostra `Ana Silva`, `Bruno Costa` e `Alessandro (você)` com horário em cada fala. Nas configurações escolho o modelo do Whisper, e para os resumos escolho entre os modelos do meu Ollama ou colo minha chave do OpenRouter."

## Princípios

1. **A legenda do Meet diz quem; o Whisper diz o quê.** O servidor do Google sabe de qual dispositivo veio cada frase, e essa é a prova de autoria. O texto final continua vindo do Whisper local, mais completo e com pontuação. A legenda entra como linha do tempo de falantes e como reserva.
2. **Tempo antes de texto.** A atribuição usa primeiro o intervalo de cada fala, convertido para o relógio do áudio com incerteza medida. O texto só serve para estimar o atraso residual e para desempatar.
3. **Mesma técnica, código próprio.** Reimplementar os comportamentos observados na Tactiq (§1 do diagnóstico) sem copiar código, nomes ou esquemas.
4. **Local por padrão, remoto por escolha consciente.** A transcrição é sempre local. Resumo e chat podem usar OpenRouter apenas com chave informada pelo usuário, consentimento explícito e indicação visível em cada saída. Áudio e biometria nunca saem da máquina.
5. **Falha visível.** Sem canal de legenda, com idioma divergente ou relógio incerto, o Diagnóstico e o resultado dizem o motivo. Nenhum nome é inventado.
6. **Instalar como um app comum.** Um `Setup.exe` por usuário, sem administrador e sem Python pré-instalado. A extensão é adicionada pela loja e pareada sozinha. Ollama detectado e modelos listados no primeiro uso.

## Escopo

### Dentro

- **Captura (paridade com a Tactiq):**
  - horário no primeiro pacote da fala e fim na última revisão;
  - idioma da legenda alinhado ao da transcrição;
  - dispositivo próprio identificado;
  - canal legado `captions` e canais do próprio Meet observados, com deduplicação;
  - vigia de silêncio e recuperação;
  - contadores locais sem conteúdo;
  - chat opcional;
  - detecção de coexistência com a Tactiq.
- **Transporte:** fila antes da sessão e durante reconexão; revisões consolidadas; persistência em lotes.
- **Relógio:** handshake de ida e volta entre extensão e app; conversão para o tempo do primeiro quadro de áudio; incerteza calculada.
- **Atribuição:**
  - tempos por palavra no Whisper;
  - estimativa de atraso legenda↔áudio;
  - atribuição palavra a palavra e corte de segmentos na troca de falante;
  - votação por cluster;
  - nomes automáticos acima de um limiar calibrado;
  - "você" pelo dispositivo próprio e pelo mic.
- **Saídas:** transcrição Whisper nomeada (principal) e "transcrição do Meet" (legendas agrupadas por falante, como a Tactiq), usada também para preencher lacunas.
- **IA:**
  - provedores unificados (Ollama com URL configurável, OpenRouter com chave protegida por DPAPI);
  - seleção separada para resumo e para chat;
  - modelo, dispositivo e precisão do Whisper.
- **Instalação:**
  - ID fixo da extensão e Origin fixado;
  - pareamento automático via Native Messaging;
  - assistente de primeiro uso (hardware, Whisper, Ollama/OpenRouter, extensão);
  - instalador empacotado;
  - publicação da extensão na loja.

### Fora

- Transcrição por API remota. O Whisper continua local; OpenRouter não é caminho de áudio.
- Entrar na reunião como bot, gravar vídeo, enviar mensagem no chat ou alterar qualquer coisa visível aos outros participantes.
- Zoom e Teams nesta versão (a Tactiq cobre, e a arquitetura permite depois).
- Nuvem própria, conta de usuário, sincronização.
- Meet REST/Media API (continuam em `v1.8` F13.H).

## Arquitetura

```
Meet (página) ─ rtc.js (MAIN, document_start)
   │  canais captions/captions_v2 próprios + do Meet, collections, media-session
   │  fetch: SyncMeetingSpaceCollections, CreateMeetingDevice, UpdateMediaSession, CreateMeetingMessage
   │  → evento {tipo, utterance, versao, dispositivo, texto, t_inicio_ms, t_ultimo_ms, idioma}
   ▼
content.js ─ consolida por utterance/dispositivo, mantém t_inicio, fila até sessão
   ▼
background.js ─ ws://127.0.0.1:5051 + ping/pong de relógio + credencial automática
   │                 ▲
   │     Native Messaging host (com.transkriptor.ponte) → entrega código de pareamento
   ▼
meet_bridge.py ─ valida, estima offset (RTT), persiste lote cifrado por sessão
   ▼
worker ─ Whisper (word_timestamps) → linha do tempo de falas no tempo do áudio
       → estimativa de atraso → atribuição por palavra → corte → votação por cluster
       → ResultManifest com assignment {nome, origem, confiança}
   ▼
Central ─ resultado nomeado, "transcrição do Meet", Configurações de IA, assistente de primeiro uso
          provedores_ia: Ollama (local) | OpenRouter (chave, consentimento)
```

## Métrica de sucesso

Medida em corpus consentido (T-15.F1). Os limiares começam provisórios (DP-15-02) e são recalibrados com esse corpus.

- **Palavras com nome correto** ≥ 95% quando o canal de legendas esteve ativo.
- **Palavras com nome errado** (não apenas desconhecido) ≤ 1%.
- **Cobertura:** ≥ 90% das palavras com nome.
- **Instalação:** de um Windows limpo até a primeira reunião nomeada em ≤ 10 minutos, sem terminal e sem modo desenvolvedor, excluídos os downloads de modelos.
