# Roteiro — reunião de teste real (gate F15.A/B/C e insumo da T-15.F1)

- **Objetivo:** medir, numa chamada de verdade, o que a simulação não mede, e destravar as tarefas que dependem do protocolo real.
  - **Medições:** relógio, atraso da legenda, idioma, dispositivo próprio, nomes automáticos e saúde do canal.
  - **Tarefas destravadas:** B1W (idioma), B3 (canal legado) e B5 (chat).
- **Duração:** 20 a 30 min.
- **Participantes:** você e mais 2 pessoas, idealmente com vozes e ritmos diferentes.

## 1. Consentimento (obrigatório, antes de gravar)

Envie aos participantes, e só siga com o "sim" de todos:

> Vou gravar uma reunião de teste do Transkriptor, um app que transcreve no meu computador. O áudio e a transcrição ficam só na minha máquina e serão usados para medir a precisão dos nomes. Posso apagar tudo quando o teste terminar. Você concorda?

Registre a data e a concordância. **Não** use reuniões de trabalho com assuntos sensíveis.

## 2. Preparação (10 min)

1. **Bandeja:** confirme que ela está aberta e atualizada (reiniciada hoje com a versão da branch `sdd-v2.0-nomes-ia-instalador`).
2. **Extensão:**
   - Em `chrome://extensions`, **recarregue** a Transkriptor Meet Bridge: o ID mudou para `mkcfobdlgdaeplnklpfcioojjgjjoojo`.
   - Registre o pareamento automático **uma vez**: `python -m instalador.registrar_host`.
   - Confira em **Diagnóstico** que a extensão aparece pareada, ou pareie à mão por `pairing.html`.
3. **Tactiq:** desative-a nesta aba. Numa segunda rodada curta, reative-a para testar a coexistência.
4. **Legenda do Meet:** deixe em **inglês** nos primeiros 5 min (para ver o aviso de idioma e o alinhamento só por tempo) e depois troque para **português**.
5. **Fones:** você **com fone de ouvido**, para evitar que o som dos outros volte pelo seu microfone.

## 3. O que falar (roteiro)

| Tempo | Quem | O quê | Mede |
|---|---|---|---|
| 0–2 min | Cada um | Apresenta-se com nome e sobrenome | Nome do Meet × voz; dispositivo próprio ("você") |
| 2–7 min | Livre | Conversa com a legenda em **inglês** | Aviso de idioma no Diagnóstico; nomes só pelo tempo |
| 7–15 min | Livre | Conversa com a legenda em **português**, com respostas curtas ("sim", "ok", "exato") | Frases curtas; atraso da legenda; corte na troca de falante |
| 15–18 min | Dois ao mesmo tempo | Interrupções propositais e falas sobrepostas | Marcação de sobreposição; ausência de nome errado |
| 18–20 min | Um participante | Fica 60 s em silêncio e depois volta a falar | Vigia do canal mudo |
| 20 min | Alguém | Escreve 2 mensagens no **chat** do Meet | Formato do chat (insumo da B5) |
| 20–25 min | Opcional | Reativa a Tactiq e fala mais 3 min | Coexistência (aviso no Diagnóstico) |

## 4. Depois da reunião (me chame para estes passos)

1. **Diagnóstico da Central:** conferir relógio, idioma, "Canal de legendas do Meet" (lidos/brutos, recriações), dispositivo próprio e Tactiq.
2. **Resultado:** abrir a reunião na Central e conferir os nomes (origem "Meet", "Meet (automático) · %"), a aba "Transcrição do Meet" e as lacunas `[legenda do Meet]`.
3. **Log** (só números): linha `[meet_alinhamento]` com o atraso estimado, a concordância e os cortes.
4. **Gabarito** (para a T-15.F1): marcar, trecho a trecho, quem realmente falou. Eu preparo a planilha a partir da reunião, **sem copiar texto para fora da sua máquina**.

## 5. O que esta reunião ainda **não** destrava sozinha

- **B1W** (pedir o idioma ao Meet), **B3** (canal legado) e **B5** (chat) precisam de um **modo de captura de estrutura**:
  - ele registra só números de campo e tamanhos dos canais `media-session`, `captions` e `meet_messages`, sem conteúdo;
  - ele ainda **não existe**: é uma tarefa nova, a ser escrita e aprovada antes.
  - A reunião de teste pode ser repetida depois com esse modo ligado.
- **Limites dos nomes automáticos:** são recalibrados só com 3 reuniões desse tipo (T-15.F1).
