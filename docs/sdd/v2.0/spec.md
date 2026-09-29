# Spec — nomes exatos, IA escolhível e instalação em um clique (SDD v2.0)

A versão do produto está em `config.VERSAO`. Os IDs novos usam a série 15 (v1.8 usa a 13, v1.9 a 14). Aprovar esta spec não autoriza implementação, instalação de extensão em perfil real, publicação na loja, uso de chave OpenRouter real nem bump de versão; ver `decisoes-usuario.md`.

Contratos detalhados estão em `interfaces.md`. Se a implementação divergir de um contrato, emendar os documentos antes de escrever código incompatível.

## Invariantes globais

- Continuam valendo os invariantes da v1.8 e da v1.9:
  - Python 3.12+, UTF-8/PT-BR, constantes em `config.py`, `Transcritor` único;
  - nenhum callback sob `self._lock`;
  - toda thread de `soundcard` dentro de `com_audio.com_inicializada()`;
  - serviços em `127.0.0.1`, consentimento antes de captura, CSP da Central inalterada (`connect-src 'self'`);
  - arquivos Python ≤ 500 linhas;
  - a suíte não escreve em `transkriptor.log`.
- A extensão **lê** o protocolo do Meet. A única escrita permitida é o pedido de idioma da legenda da própria sessão (FR-15.B1), condicionado a DP-15-01. É proibido enviar chat, reações, alterar mídia ou qualquer coisa visível a outros participantes.
- Nenhum código, nome interno ou esquema da Tactiq entra no repositório. Fixtures de protocolo são geradas por nós, sintéticas e anonimizadas.
- Texto de legenda, nome, chat, chave e token nunca aparecem em log, em `/api/estado`, em telemetria ou em evidência. Contadores e esqueletos protobuf levam apenas números de campo, tipos e tamanhos.
- Áudio, embeddings e biometria nunca saem da máquina. Texto de transcrição só sai para o OpenRouter quando o usuário escolheu esse provedor para a função em uso e consentiu (SEC-15.D2).
- Requisições de rede fora de `127.0.0.1` partem somente do processo Python, nunca do front. São permitidas apenas para:
  - `openrouter.ai` (provedor escolhido);
  - download de modelos Whisper/ECAPA;
  - `/api/pull` do Ollama local.
- Todo nome atribuído carrega `origem` (`meet_legenda`, `meet_proprio`, `voz_cadastrada`, `mic_local`, `manual`) e `confianca`. Sem evidência suficiente, o rótulo continua `FALANTE_XX — identificação pendente`.
- **Suíte verde não substitui o gate de reunião real** (NFR-10.C2). Tasks que mexem em captura rodam `scripts/gate_reuniao_real.py`.

## Requisitos e rastreabilidade

| Requisito | Comportamento verificável | Tarefa |
|---|---|---|
| FR-15.A1 | A extensão marca `t_inicio_ms` no primeiro pacote de cada `utterance/dispositivo` e `t_ultimo_ms` na última revisão, com relógio monotônico da página convertido para época (`performance.timeOrigin + performance.now()`). Revisões atualizam texto e `t_ultimo_ms`, nunca `t_inicio_ms`. Os dois campos chegam ao envelope sem serem substituídos pelo horário do flush ou do background. | T-15.A1 |
| FR-15.A2 | A ponte faz handshake de relógio com cada aba vinculada (5 pings ao vincular e 1 a cada 30 s; emenda de 29/09: medido no monotônico do app, ver `interfaces.md` §3). Pela menor RTT, a ponte carimba cada legenda v2 com `speech_started/last_monotonic_ns` e `clock_uncertainty_ms`, e descarta esses campos quando vêm do cliente. O instante zero é o primeiro frame do loopback. O worker converte os eventos carimbados para `ts_sec` do áudio e usa a incerteza medida; a janela temporal passa a valer quando ela é ≤ `INCERTEZA_TEMPO_MAX_MS`. O aviso de "nenhum nome" consulta o `EventStore` da sessão. | T-15.A2 |
| FR-15.A3 | Eventos gerados antes da sessão ou durante reconexão ficam em fila limitada (tamanho e idade em `config`) e são reenviados após `sessao` na ordem original, com `event_id` idempotente. A extensão consolida revisões: envia a primeira, no máximo 1 revisão por segundo e a final. A ponte persiste em lotes (tempo ou tamanho) em vez de um lacre por evento. Excesso de taxa gera contador e aviso, nunca perda silenciosa. | T-15.A3 |
| FR-15.B1 | Com DP-15-01 aprovada e `meet_idioma_legenda = "seguir_transcricao"`, a extensão pede pelo canal `media-session` o idioma da legenda igual ao idioma da transcrição, espera confirmação por até 5 s e registra `success/rejected/timeout/unavailable`. Com `"nao_alterar"`, apenas lê o idioma efetivo. O idioma efetivo vai no evento `capabilities`. A divergência entre idioma da legenda e da transcrição aparece no Diagnóstico e reduz a confiança de texto. | T-15.B1 |
| FR-15.B2 | A extensão identifica o `deviceId` do próprio usuário pelo request de `SyncMeetingSpaceCollections` ou pela resposta de `CreateMeetingDevice` e envia `self_device` uma vez por sessão. A atribuição rotula esse dispositivo como `<nome do Meet> (você)`, reconcilia com o canal mic e com o perfil de voz, e nunca o atribui a outro participante. | T-15.B2 |
| FR-15.B3 | A extensão abre `captions` (legado) e `captions_v2` e observa os canais que o próprio Meet cria (patch de `createDataChannel`). Pacotes equivalentes (`dispositivo|versão|texto` em até 700 ms) produzem uma única fala. O decodificador legado cobre as fixtures versionadas. A presença de `meta#tactiq-rtc` é reportada como `coexistencia_tactiq`. | T-15.B3 |
| NFR-15.B4 | O vigia recria os canais de legenda após `LEGENDA_SILENCIO_MS` sem pacote enquanto há fala detectada (atividade do tile ou energia no loopback), com até 3 tentativas. Queda de canal reabre na conexão atual ou na nova. Contadores `raw/parsed/control/rejected` por canal, motivos, lacuna de parsing com esqueleto sem conteúdo, recriações, quedas, conflitos e trocas de conexão são publicados no Diagnóstico ao fim da reunião. | T-15.B4 |
| FR-15.B5 | Com `meet_capturar_chat` ligado (padrão ligado, DP-15-03), mensagens de chat (canal `meet_messages` e resposta de `CreateMeetingMessage`) viram eventos `chat` com autor e horário e aparecem na transcrição marcadas como chat. Desligado, nenhum dado de chat é decodificado nem persistido. | T-15.B5 |
| FR-15.C1 | A transcrição usa `word_timestamps=True`. Palavras com início e fim são persistidas no segmento (`words`) sem alterar o texto do segmento. Resultados antigos sem `words` continuam legíveis. | T-15.C1 |
| FR-15.C2 | O alinhador constrói a linha do tempo de falas (dispositivo, início, fim e texto final no tempo do áudio). Ele estima o atraso global legenda→áudio por busca em grade sobre a concordância de palavras normalizadas e o refina em janelas de 60 s (±500 ms). Atribui cada palavra ao dispositivo cuja fala a cobre, com tolerância configurável, desempatando por âncora textual. Corta segmentos Whisper onde o dispositivo muda (fragmento mínimo configurável) e marca `overlap` quando duas falas se sobrepõem sem desempate. | T-15.C2 |
| FR-15.C3 | A política de nomes vota por cluster ECAPA com peso por duração. O nome é aplicado automaticamente (DP-15-02: desde já) quando a participação e a duração superam os limiares de `config.py`, provisórios até a recalibração em T-15.F1. Caso contrário vira sugestão. Conflito entre homônimos (ids distintos), cluster dividido ou relógio incerto mantêm a sugestão. Correção manual prevalece e é preservada em reprocessamento. | T-15.C3 |
| FR-15.C4 | Cada reunião com legendas gera também a "transcrição do Meet": falas agrupadas por falante contíguo, com horário e nome, igual ao modelo da Tactiq. Pode ser exportada e é mostrada na Central. Trechos com legenda e sem segmento Whisper correspondente (mais de 2 s) são inseridos na transcrição principal marcados `[legenda do Meet]`. | T-15.C4 |
| FR-15.D1 | O módulo `provedores_ia` oferece `ProvedorOllama` com URL configurável (`ollama_url`, padrão `OLLAMA_HOST` ou `http://127.0.0.1:11434`). Toda listagem de modelos, chat síncrono e streaming do assistente, resumos e Central passam por ele. As três cópias de `/api/tags` e as duas de `/api/chat` deixam de existir. O comportamento atual com Ollama ausente é mantido. | T-15.D1 |
| SEC-15.D2 | `ProvedorOpenRouter` usa `https://openrouter.ai/api/v1` (chat compatível com OpenAI, listagem de modelos, validação da chave). A chave é guardada cifrada por DPAPI, nunca volta ao front (só `configurada: true` e os 4 últimos caracteres) e é mascarada no sanitizador de log. O provedor só é usado depois de consentimento registrado com data que nomeia o que sai (texto da transcrição e perguntas) e o que não sai (áudio, voz). Toda resposta gerada remotamente é marcada com provedor e modelo. Sem rede ou com chave inválida, o erro é explícito e não há fallback silencioso para outro provedor. | T-15.D2 |
| UX-15.D3 | Configurações ganham a seção **Inteligência artificial**. **Transcrição:** modelo Whisper (lista atual + recomendado pelo hardware), dispositivo (automático/CPU/GPU) e precisão; o idioma é mostrado. **Resumos** e **Assistente (chat)** têm cada um seu provedor (Ollama/OpenRouter) e modelo, com a lista vinda do provedor, estado (online, offline, sem modelos) e "Testar". A escolha é persistida e usada por `resumo_reuniao` e pelo chat como padrão. Mutações exigem o header secreto e seguem o padrão 409 + confirmação para OpenRouter. | T-15.D3 |
| SEC-15.E1 | O manifest da extensão tem `key` fixa (ID estável em qualquer máquina). A ponte aceita apenas as Origins da lista `EXTENSAO_IDS_PERMITIDOS` (loja Chrome, loja Edge, desenvolvimento). O token legado estático é removido. O teste prova que outra extensão é recusada. | T-15.E1 |
| FR-15.E2 | Um host de Native Messaging `com.transkriptor.ponte`, registrado por usuário (HKCU) para Chrome e Edge com `allowed_origins` restrito, atende um único comando (`obter_codigo_pareamento`). Ele obtém do app em execução um código `pair-` de uso único por canal local autenticado. A extensão pareia sozinha ao instalar e quando a credencial expira. O pareamento manual continua como reserva. O host recusa qualquer outro comando e não executa nada além disso. | T-15.E2 |
| FR-15.E3 | O detector do Ollama segue a ordem de `interfaces.md` §6 (API em `ollama_url`/`OLLAMA_HOST`, PATH, pasta padrão, chave de desinstalação) e devolve `{estado, versao, url, modelos}`. O assistente de primeiro uso da Central mostra hardware e modelo Whisper recomendado, lista os modelos no seletor, oferece baixar o modelo recomendado pelo hardware (DP-15-11; `/api/pull` com progresso), iniciar o Ollama parado, abrir a página oficial de instalação, informar chave OpenRouter ou pular. Por fim oferece adicionar a extensão e mostra o pareamento automático. | T-15.E3 |
| FR-15.E4 | `TranskriptorSetup.exe` instala por usuário sem administrador e sem Python prévio. Ele provisiona o runtime a partir dos lockfiles com hash (rota CPU ou CUDA por detecção), registra o host de Native Messaging, cria atalhos e inicialização opcional, mostra o Ollama detectado e abre o assistente de primeiro uso. A desinstalação preserva dados por padrão e remove registro e host. O gate de instalação roda o setup numa máquina ou VM limpa. | T-15.E4 |
| FR-15.E5 | A extensão é empacotada com versão igual à de `manifest.json`, política de privacidade publicada e textos da loja. O instalador e o assistente abrem a página da loja (Chrome e Edge) em vez de pedir modo desenvolvedor. O README mantém o caminho "carregar sem compactação" apenas para desenvolvimento. | T-15.E5 |
| NFR-15.F1 | Corpus consentido de pelo menos 3 reuniões reais (2 a 5 pessoas, ≥ 20 min, com uma em idioma de legenda divergente simulado) com gabarito por palavra. Com ele, calibrar os limiares de FR-15.C2/C3 e medir as metas do concept. Rodar `gate_reuniao_real.py --segundos 600`, Chrome e Edge, coexistência com a Tactiq e instalação limpa. Evidência em `evidencias/GATE-FINAL.md`. | T-15.F1 |

## Contratos resumidos

Pontos que a implementação não pode reinterpretar (detalhes em `interfaces.md`):

- Evento de legenda v2 (extensão → ponte): `kind="caption"`, `caption_id="<utterance>/<dispositivo>"`, `caption_revision`, `participant_id` (dispositivo), `text`, `caption_started_ms`, `caption_last_ms`, `caption_lang`, `caption_final: bool`, mais os campos canônicos da v1.8. `schema_version=2`; a ponte aceita v1 e v2.
- Handshake de relógio: `ping {n, client_wall_ms, client_monotonic_ms}` → `pong {n, server_monotonic_ns}`. A amostra de menor RTT define `offset`; `incerteza = RTT_min / 2 + resolução`.
- `assignment` do segmento: `{estado, nome, participant_id, origem, confianca, evidencias: [event_id], palavras_cobertas}`.
- Chaves novas em `config_user.json`, todas opcionais com padrão em `config.py`:
  - `ollama_url`;
  - `ia_resumo_provedor`, `ia_resumo_modelo`, `ia_chat_provedor`, `ia_chat_modelo`;
  - `openrouter_chave_dpapi`, `openrouter_consentido_em`;
  - `whisper_dispositivo`, `whisper_precisao`;
  - `meet_idioma_legenda`, `meet_capturar_chat`;
  - `assistente_inicial_concluido`.
