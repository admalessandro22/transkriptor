# Identificação de participantes no Google Meet

Documento de referência para **Fase 7** (você = `VOCÊ`) e **Fase 8** (outros participantes com nome).

---

## Caso Tactiq (sem bot visível)

O Tactiq **não é** app de bandeja nem bot na reunião. É **extensão Chrome/Edge** que roda **dentro** da aba `meet.google.com`.

### Stack técnica (documentação oficial + marketing)

| Camada | Tecnologia |
|--------|------------|
| Presença no Meet | **Chrome Extension** (Manifest V3), content script em `meet.google.com` |
| Texto da fala | **Legendas ao vivo do próprio Google Meet** (Closed Captions) — a FAQ diz: *"ative Closed Captions para o Tactiq começar a transcrever"* |
| Quem falou | Nome vem do **Meet** (atribuição nas legendas + tile/participante ativo na UI que a extensão lê no DOM) |
| IA / resumos | Nuvem Tactiq → **OpenAI GPT-4** (API); transcrições salvas no dashboard deles |
| Áudio | Marketing: *"transcreve em tempo real sem gravar áudio"* no Meet — ou seja, **não faz STT local**; reaproveita o pipeline de captions do Google |
| Widget | Overlay na lateral direita da página (não aparece na lista de participantes) |

### Por que parece “mágica”

1. Não entra como participante → ninguém vê “Tactiq bot”.
2. O trabalho pesado de STT + speaker diarization no Meet é feito pelo **Google** (quando CC está ligado).
3. A extensão **captura o texto já rotulado** e enriquece com IA na nuvem.

### Limitações do modelo Tactiq

- Meet no **navegador** (não app Android/iOS puro sem extensão).
- **Legendas ativadas** — sem CC, o Tactiq muitas vezes não inicia.
- Conta **Google Workspace** tende a ter melhor atribuição de nomes nas legendas.
- Dados passam pelos servidores Tactiq/OpenAI (não é 100% local).

### Equivalente local no Transkriptor (Fase 8 revisada)

Duas sub-opções alinhadas ao Tactiq:

**8A — Modo “legendas Meet” (igual Tactiq)**  
Extensão lê nós DOM das legendas (`[data-caption]`, etc.) + nome do falante → WebSocket → `127.0.0.1` → salva `.txt` local. **Sem Whisper** para esse trecho; Whisper/loopback continua como fallback se CC desligado.

**8B — Modo “áudio local” (atual Fase 7+8)**  
Loopback + mic + diarização ECAPA — funciona sem extensão, mas nomes só com correlação UI ou cadastro de voz.

---

## Como apps comerciais fazem

| Abordagem | Quem usa | Nomes reais? | Privacidade local |
|-----------|----------|--------------|-------------------|
| **Bot na reunião** | Fireflies, Otter (modo notetaker) | Sim — áudio/metadata por participante | Áudio vai ao servidor deles |
| **Integração Zoom/Meet SDK** | Fireflies enterprise | Sim | Depende do vendor |
| **Extensão Chrome no Meet** | Tactiq, extensões Otter | Sim — lê DOM + eventos de “quem fala” | Pode ser local (WebSocket → app) |
| **Só áudio do sistema (loopback)** | Fireflies desktop sem bot | **Não** — só Speaker 1, 2… | Local |
| **Diarização + cadastro de voz** | Otter pós-reunião | Parcial — você etiqueta Speaker 1 → “João” | Local |
| **Legendas Workspace do Meet** | Google nativo | Sim (contas Google) | Google |

**Conclusão:** gravar como o Transkriptor (bandeja + loopback, sem bot) é o mesmo modo em que a Fireflies admite **não ter speaker labels** — só diarização anônima, a menos que você acrescente outra fonte de nomes.

---

## O que o Transkriptor pode implementar (sem nuvem)

### Nível 1 — Fase 7 (já no plano): identificar **você**

- Cadastro de voz pelo microfone
- Gravação mic + loopback
- Rótulo `VOCÊ` no `*_diarizado.txt`

### Nível 2 — Fase 8 (proposta): nomes dos **outros** no Meet

**Opção A — Extensão Chrome (recomendada)**

1. Extensão em `meet.google.com` lê lista de participantes e evento “falante ativo” (tile destacado / nome na UI).
2. Envia `{nome, timestamp}` para `ws://127.0.0.1:5051` (servidor leve no Transkriptor).
3. No pós-processamento, correlaciona timestamp do segmento Whisper com nome ativo ±1,5s.
4. Saída: `[Maria Silva 02:10-02:18] texto...`

Prós: confiável, nomes iguais aos do Meet.  
Contras: usuário instala extensão; Google pode mudar DOM (testes de regressão).

**Opção B — UI Automation Windows (fallback)**

- `uiautomation` / `pywinauto` na janela Chrome/Edge do Meet.
- Lê elemento “está falando” quando Meet destaca participante.
- Mais frágil que extensão; quebra em updates do Meet.

**Opção C — Banco de vozes local (estilo Otter)**

- Após reunião, usuário renomeia `FALANTE_01` → “Carlos”.
- Salva embedding em `vozes_conhecidas/`; próximas reuniões fazem match automático.
- Não precisa extensão; não dá nome na 1ª reunião de alguém.

**Opção D — Bot no Meet**

- Fora do escopo do Transkriptor (privacidade, complexidade, ToS).

---

## Matriz de decisão

| Objetivo | Solução mínima |
|----------|----------------|
| Saber o que **eu** falei | Fase 7 |
| Nomear **colegas fixos** ao longo do tempo | Fase 7 + Opção C |
| Nome **na hora** igual ao Meet | Fase 8 Opção A (extensão) |

---

## Riscos Fase 8

- DOM do Meet muda → extensão precisa versão e testes
- Latência UI vs áudio (~0,5–2s) → janela de correlação configurável
- Participante sem câmera/nome genérico → fallback `FALANTE_XX`