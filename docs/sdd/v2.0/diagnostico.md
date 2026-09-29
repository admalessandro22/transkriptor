# Diagnóstico — como a Tactiq nomeia falantes no Meet e o que falta ao Transkriptor

Elaborado em 29/09/2026. Base examinada: `master` em `f292d81` (v1.8 remediada + v1.9 integrada), `config.VERSAO = 1.7.0`. Extensão de referência: Tactiq `fggkaccpbmombhnjkjokndojfgagejfb` versão `3.1.7049`, instalada no perfil `Default` do Chrome desta máquina.

Método: leitura do `manifest.json` e dos scripts empacotados (`rtcinjector.js`, `googlemeet.inline.js`, `content.js`), formatados com `jsbeautifier` numa pasta temporária fora do repositório. Nenhum código da Tactiq foi copiado para o repositório. O produto reimplementa a **técnica**, com código próprio. O código da Tactiq é proprietário: não se reutilizam trechos, nomes internos nem esquemas `.proto` deles.

## 1. Como a Tactiq funciona

### 1.1 Injeção antes da página

- O `manifest.json` declara dois content scripts em `*://meet.google.com/*-*-*`. `rtcinjector.js` roda em `document_start`. `content.js` roda depois e desenha a interface.
- `rtcinjector.js` insere `<script src="googlemeet.inline.js">` como **primeiro filho** do `<head>`. O arquivo está em `web_accessible_resources`. Assim o código roda no mundo da página antes do JavaScript do Meet criar qualquer `RTCPeerConnection`.
- Ela marca a presença com `<meta id="tactiq-rtc" name="tactiq-rtc" version="…">`. A versão vem do build do Meet (`boq_meetingsuiserver_*` em `WIZ_global_data`). Esse marcador permite detectar a Tactiq ativa na mesma aba.

### 1.2 Três fontes interceptadas

| Fonte | O que a Tactiq faz | O que obtém |
|---|---|---|
| `window.RTCPeerConnection` (substituído por um wrapper) | Escuta `datachannel` remoto. `collections`: guarda a conexão principal e decodifica `deviceId → nome`. `media-session`: guarda o canal para comandos de idioma. `captions`/`captions_v2` remotos: consome, se existirem. | Mapa de dispositivos, a conexão certa e o canal de controle |
| `RTCPeerConnection.prototype.createDataChannel` (patch) | Observa os canais que **o próprio Meet** cria (`captions`, `captions_v2`, `meet_messages`, `media-session`). | Legendas do CC nativo quando ligado, chat e a sequência do `media-session` |
| `RTCDataChannel.prototype.send` (patch) | Lê o que o Meet envia pelo `media-session`: número da operação, ack e **idioma da legenda**. Com a "guarda de idioma" ligada, reescreve o pedido de idioma do Meet para o idioma escolhido pelo usuário. | Idioma efetivo das legendas |
| `window.fetch` (patch, sem alterar a resposta) | `SyncMeetingSpaceCollections`: lê o request (extrai `spaces/…/devices/…` do próprio usuário) e a resposta (roster em base64/protobuf). `CreateMeetingDevice`: extrai o id do dispositivo e da sessão de mídia. `GetMediaSession`/`UpdateMediaSession`: extrai o id da sessão e o código do idioma. `CreateMeetingMessage`: lê o chat enviado. `CreateMeetingRecording`: sabe que a gravação nativa começou. | Roster pré-chamada, **dispositivo próprio**, idioma, chat e gravação |
| `XMLHttpRequest.open/send` (patch) | Endpoints legados `media_sessions/modify` e `/query`: idioma da tradução/transcrição e id da sessão. | Compatibilidade com versões antigas do Meet |

### 1.3 Abertura dos canais de legenda

- O `content.js` avisa (`type:"con"`) quando a reunião começa. O script da página espera até 5 s pela conexão principal e cria **dois** canais: `captions` (legado) e `captions_v2`. Os dois usam `ordered:true`, `maxRetransmits:10` e ids a partir de 50001.
- O servidor passa a mandar as legendas de todos os participantes, **com o CC desligado na tela**. Cada pacote `captions_v2` traz `utteranceId`, `version` e `{texto, deviceId, idioma}`. A Tactiq responde a cada pacote com um ack `{utteranceId, version, 1}`. Sem o ack, o servidor reenvia.
- Pacotes gzip são detectados pelos bytes `1f 8b 08` no início ou após 3 bytes e descompactados.
- O pacote legado (`captions`) é decodificado por varredura de marcadores de bytes, com fallback para o decodificador tipado.

### 1.4 Idioma da legenda

- A Tactiq escolhe o idioma nesta ordem: o último usado, o idioma da interface do Meet, o do navegador.
- Ela envia pelo `media-session` um comando `captionUpdate` com `lang_1 = lang_2 = código` e a máscara `client_config.caption_config`, seguido de dois acks de sequência. Depois espera confirmação por até 5 s: `success`, `rejected`, `timeout` ou `superseded`.
- Se o envio falhar, ela troca o idioma pela interface do Meet (listbox de idioma).
- **Esse é o ponto que mais afeta a qualidade.** A legenda chega no idioma configurado. Se o Meet legenda em inglês uma reunião em português, o texto vira ruído.

### 1.5 Horário, nome e deduplicação

- O horário de cada fala é `Date.now()` no **primeiro** pacote daquele `messageId = utteranceId/deviceId`. As versões seguintes só substituem o texto (`messageVersion` maior ou igual) e **não mudam o horário**.
- Mensagens são agrupadas e entregues ao `content.js` a cada 500 ms, substituindo versões antigas do mesmo `messageId` no buffer.
- A deduplicação entre canais compara a chave `deviceId|version|texto`. Se ela se repete em até 700 ms com outro `messageId`, a segunda é mapeada para a primeira (memória de 30 s, até 512 entradas). Isso evita fala duplicada quando `captions` e `captions_v2` entregam a mesma coisa.
- O nome é resolvido no momento da inserção: `devices[deviceId]` → `deviceName` → `"Speaker"`. O primeiro nome visto para um `deviceId` é preservado.
- O **dispositivo próprio** vem do `SyncMeetingSpaceCollections`/`CreateMeetingDevice` e é divulgado como `self-device`. O chat enviado pelo usuário leva esse id e esse nome.
- Na exibição, blocos consecutivos do mesmo falante são agrupados quando o intervalo fica abaixo de um limite (curto, médio ou longo), quando o texto não passou de N frases, e quando destaques e marcadores coincidem.

### 1.6 Saúde e recuperação

- Um vigia (a cada 10 s) detecta **60 s sem pacote de legenda enquanto há alguém falando**. A fala é detectada à parte por atividade de áudio recente, com janela de 30 s. Nesse caso o vigia recria `captions` e `captions_v2`, até 3 tentativas. Depois escala: liga e desliga o CC pela interface.
- Um canal que fecha é reaberto na mesma conexão. Se a conexão mudou, ela tenta na conexão nova a cada 5 s, até 5 vezes.
- A Tactiq registra contadores por canal (`raw/parsed/control/rejected`), motivos de rejeição, "lacuna de parsing" (50 rejeições seguidas, com o esqueleto protobuf **sem conteúdo**), recriações, quedas, conflitos (outro canal de legenda aberto) e trocas de conexão. O resumo é enviado ao fim da reunião.
- Após 5 s em chamada, `checkCaptions` confirma que o canal existe. Se não existir, marca a reunião como "legendas falharam".

### 1.7 Instalação

- Ela é instalada pela Chrome Web Store: um clique, ID fixo e atualização automática.
- Não tem componente nativo nem pareamento. Tudo é enviado à nuvem da Tactiq (`externally_connectable` para `app.tactiq.io`).
- O Transkriptor mantém processamento local. A simplicidade de instalação precisa vir do instalador Windows mais pareamento automático, não de uma nuvem.

## 2. Estado atual do Transkriptor

O `extension/meet/rtc.js` **já reimplementa o núcleo**: wrapper de `RTCPeerConnection`, canal `captions_v2` próprio com ack, gzip, nomes pelo `collections` e pelo `SyncMeetingSpaceCollections`. O problema é o que acontece **depois** da captura.

### 2.1 Lacunas que impedem o nome exato

| ID | Lacuna | Evidência | Efeito |
|---|---|---|---|
| G-01 | O horário da fala é sobrescrito a cada revisão | `extension/meet/content.js:162-171` grava `visto: Date.now()` em toda versão nova | O início da fala some; sobra o horário da última revisão |
| G-02 | O horário enviado é o do flush e do envelope, não o da chegada | `content.js` agenda o descarregamento com `RTC_FLUSH_MS` (`:221`); `background.js` gera `client_wall_ms` ao montar o envelope | Erro adicional de até ~1 s por fala |
| G-03 | Não há conversão do relógio do navegador para o tempo do áudio | `sessao_reuniao.anotar_handshake` (`sessao_reuniao.py:115`) sem chamada fora de testes; `processador_reuniao.py:169` usa `clock_uncertainty_ms=5000` | O relógio é tratado como incerto |
| G-04 | Com o relógio incerto, a atribuição ignora o tempo e compara só texto | `identidade_reuniao.py:190-199`: com `absoluto`/`relogio_ok` falsos a janela é pulada; `IDENTIDADE_LIMIAR_LEGENDA = 0.5` (`config.py:204`) | Qualquer legenda da reunião pode "casar" com qualquer segmento; frases curtas ("sim", "ok") nunca atingem o limiar |
| G-05 | O idioma da legenda não é controlado | `rtc.js:15` declara que não altera idioma | Legenda em idioma diferente do falado derruba a similaridade para ~0 |
| G-06 | O resultado nunca passa de sugestão | `MODO_AUTO_NOMES = False` (`config.py:209`); `correlacionador.py:176` só aplica com CONFIRMED | O arquivo final sai com `FALANTE_XX` até o usuário confirmar |
| G-07 | O Whisper roda sem tempos por palavra | `audio_fontes.py:75` chama `transcribe` sem `word_timestamps` | Um segmento com duas vozes não pode ser cortado na troca |
| G-08 | Eventos anteriores à sessão, ou durante uma reconexão, são descartados | `background.js:269-276` retorna sem enfileirar; a reconexão zera a sessão (`:210-213`) | Início da reunião e trechos após queda sem legenda |
| G-09 | Cada revisão parcial vira um evento persistido e um lacre durável | `meet_bridge.py:237` força `descarregar` por evento; `content.js` reenvia cada versão | Muitos arquivos cifrados por reunião; pressão no limite de 20 eventos/s (excesso descartado em silêncio, `meet_bridge.py:384-396`) |
| G-10 | O dispositivo do próprio usuário não é identificado | nenhuma referência a *self device* em `extension/meet/` | "VOCÊ" depende só do perfil de voz ou da energia do mic |
| G-11 | Só o canal `captions_v2` é usado; os canais criados pelo Meet não são observados | `rtc.js:219, 265-268` | Sem reserva quando o v2 falha; conflito com o CC nativo |
| G-12 | A recuperação cobre apenas o fechamento do canal | `rtc.js:236-242` (5 tentativas de 1 s); `content.js:197` cai para o DOM após 10 s | Um canal aberto porém mudo passa despercebido |
| G-13 | Não há telemetria local da captura | nenhum contador por canal | O Diagnóstico não sabe dizer por que não houve nomes |
| G-14 | O aviso legado "Nenhum nome recebido do Meet" lê uma fila vazia em produção | `app_ciclo_reuniao.py:46-68, 259`: a ponte é criada com `Pareador` (`transkriptor.pyw:146`) | Provável falso alarme em toda reunião (inferido do código; confirmar em T-15.A2) |
| G-15 | O chat não é capturado | nenhuma referência a `meet_messages` | Perguntas e links do chat ficam fora da ata |

### 2.2 Lacunas de instalação e de configuração de IA

| ID | Lacuna | Evidência |
|---|---|---|
| G-16 | A extensão é "carregada sem compactação" com modo desenvolvedor | `extension/meet/README.md` |
| G-17 | O manifest não tem `key`: o ID muda por máquina, e a ponte aceita **qualquer** extensão | `meet_bridge.py:37-42, 95-110` aceita `chrome-extension://[a-p]{16,32}` |
| G-18 | O pareamento é manual: copiar `pair-…` do Diagnóstico para `pairing.html` | `meet_pareamento.py:91-103` |
| G-19 | A instalação exige Python 3.12 no PATH e roda um `.bat` | `instalar.bat`, `instalar_helper.py:20-25` |
| G-20 | A detecção do Ollama é só `ollama list` e só avisa | `instalar_helper.py:36-50` |
| G-21 | O endereço do Ollama está fixo | `config.py:109` (`OLLAMA_URL`) |
| G-22 | O modelo de resumo é automático e sem configuração | `resumo_reuniao.py:26, 86-91` (`MODELOS_PREFERIDOS`) |
| G-23 | O modelo do chat é escolhido a cada acesso e não é salvo | `static/js/chat.js:164-176` |
| G-24 | Três cópias da listagem `/api/tags` e duas do `/api/chat` | `assistente.py:372-385, 422-429`; `central_resumos.py:31-38, 63-78`; `assistente_ollama.py:66-120` |
| G-25 | Não há provedor remoto; as decisões vigentes proíbem envio de transcrição | DU-02 (`v1.8/decisoes-usuario.md:8`), `v1.9/spec.md:9-10` |
| G-26 | Dispositivo e precisão do Whisper não são configuráveis | `config.py:39-40` |

### 2.3 Verificação do Ollama nesta máquina (referência para a detecção)

- `ollama.exe` está em `%LOCALAPPDATA%\Programs\Ollama\` e no PATH.
- A chave de desinstalação em `HKCU\…\Uninstall` informa `Ollama version 0.34.4`.
- `GET http://127.0.0.1:11434/api/version` respondeu `0.34.4`.
- `GET /api/tags` listou `granite4.1:3b`, `ornith:latest` e `gemma4:latest`. `OLLAMA_HOST` não está definido.
- As quatro formas de detecção (API, PATH, pasta padrão e registro) funcionam e precisam de ordem definida (`interfaces.md` §6).

## 3. Riscos da técnica

- **Protocolo não documentado.** Canais, campos protobuf e RPCs do Meet podem mudar sem aviso. A Tactiq mitiga com telemetria de parsing e diversas reservas. O produto deve fazer o mesmo, localmente: contadores, esqueleto sem conteúdo, reserva por DOM, fixtures versionadas por build do Meet (`boq_meetingsuiserver_*`).
- **Alterar o idioma da legenda** é escrita no protocolo, não só leitura. Afeta apenas a sessão de mídia do próprio usuário (o idioma das legendas que **ele** recebe), mas exige decisão explícita (DP-15-01).
- **Coexistência com a Tactiq.** As duas extensões abrem canais de legenda na mesma conexão. Os ids não colidem (Tactiq a partir de 50001, Transkriptor a partir de 61001), mas o Meet pode marcar o CC como indisponível. Detectar `meta#tactiq-rtc` e avisar no Diagnóstico.
- **Publicar na Chrome Web Store** exige conta de desenvolvedor, política de privacidade e revisão. Extensões com a mesma técnica estão publicadas, mas a aprovação não é garantida.
- **OpenRouter** tira texto da máquina. Isso contraria DU-02 e exige emenda consciente (DP-15-04), consentimento e indicação visível.
