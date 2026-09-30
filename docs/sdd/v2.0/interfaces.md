# Interfaces congeladas — SDD v2.0

Alterar qualquer contrato abaixo exige emenda neste arquivo antes do código. Nomes de módulos novos são normativos. Assinaturas Python são indicativas quanto a parâmetros opcionais, mas normativas quanto a nomes e tipos de retorno.

## 1. Mensagens página → content script (`transkriptor-meet-rtc`)

Mensagens JSON em `CustomEvent.detail`, sem id de sala (`spaces/<sala>` nunca sai do `rtc.js`; o dispositivo vira `dev-<n>`).

```jsonc
{"tipo": "legenda", "canal": "captions_v2|captions|meet", "dispositivo": "dev-127",
 "utterance": 4411, "versao": 3, "texto": "…", "idioma": "pt-BR|null",
 "t_inicio_ms": 1759150000123.4, "t_ultimo_ms": 1759150001890.2}
{"tipo": "nomes", "pares": [{"dispositivo": "dev-127", "nome": "Ana Silva"}]}
{"tipo": "proprio", "dispositivo": "dev-88"}
{"tipo": "idioma", "codigo": "pt-BR", "origem": "meet|transkriptor", "resultado": "success|rejected|timeout|unavailable|lido"}
{"tipo": "chat", "dispositivo": "dev-127", "mensagem_id": "…", "texto": "…", "t_ms": 1759150002000}
{"tipo": "saude", "contadores": {"captions_v2": {"raw": 0, "parsed": 0, "control": 0, "rejected": 0},
 "captions": {…}}, "motivos": {"decode": 0}, "recriacoes": 0, "quedas": 0, "conflitos": 0,
 "trocas_conexao": 0, "esqueleto": "1:LEN(12){1:VARINT 3:LEN(4)}", "build_meet": "…", "tactiq": false}
```

- `t_*_ms = performance.timeOrigin + performance.now()`, calculado no `rtc.js` no momento em que o pacote chega.
- `t_inicio_ms` é o do primeiro pacote daquele `utterance/dispositivo` visto em **qualquer** canal.
- Chat só é emitido com a configuração ligada. O `content.js` repassa essa configuração ao `rtc.js` por `CustomEvent` `transkriptor-meet-config`: `{idioma_legenda, idioma_desejado, capturar_chat}`.

## 2. Envelope de evento v2 (background → ponte)

Estende o envelope canônico da v1.8 (`v1.8/spec.md`, "Envelope de evento"). `schema_version` passa a `2`; a ponte aceita 1 e 2.

| Campo | Tipo | Regra |
|---|---|---|
| `kind` | `heartbeat` \| `caption` \| `participant_join` \| `speaker_activity` \| `capabilities` \| `self_device` \| `chat` \| `health` | — |
| `caption_started_ms` | float | obrigatório em `caption` v2; época da página |
| `caption_last_ms` | float | ≥ `caption_started_ms` |
| `caption_lang` | str \| null | BCP-47, ≤ 16 chars |
| `caption_final` | bool | `true` na revisão final ou após 3 s sem revisão |
| `origin_channel` | `captions_v2` \| `captions` \| `meet` \| `dom` | — |
| `queued` | bool | evento reenviado da fila pré-sessão |

`client_wall_ms`/`client_monotonic_ms` continuam sendo o horário do envio do envelope. **O tempo da fala é `caption_started_ms`.** O `capabilities` carrega `{caption_lang, lang_result, tactiq, build_meet}`, e `health` carrega o objeto `saude` da §1.

### 2.1 Emenda de 29/09/2026 (T-15.A3): fila, lote e ACK

- **Contrato substituído:** o da v1.8 `interfaces.md` ("`registrar_envelope` só confirma a sequência após `EventStore.descarregar(forcar=True)`"), que gerava um arquivo cifrado por evento (G-09).
- **Lote:** a ponte faz `append` e deixa o lote do `EventStore` fechar sozinho. Isso ocorre ao completar `MEET_EVENTOS_DRENO_SEG` (agora **30 s**), 500 eventos ou 1 MiB, no heartbeat (que chama `descarregar()` sem forçar, para fechar o lote vencido em silêncio) e no `seal()` do fim da reunião.
- **ACK:** passa a ser `{"tipo": "ack", "connection_id", "seq": <recebido>, "duravel": <último seq em disco ou -1>}` (`MeetBridge.seq_duravel()`).
- **Troca aceita:** uma queda do app perde no máximo 30 s de legendas; o áudio não é afetado.
- **Fila no background:** sem sessão (início da reunião ou reconexão), cada evento de conteúdo espera numa fila por aba (`FILA_MAX = 200`, os mais antigos saem primeiro; `FILA_IDADE_MS = 120000`, os vencidos caem na drenagem). Ao aceitar `sessao`, a fila é drenada em ordem com `queued: true`. O heartbeat (`reuniao`) não entra na fila.
- **Revisão final:** sem revisão por 3 s, o `content.js` reenvia a fala uma vez com `caption_final: true`.
- **Validação:** `queued` e `caption_final`, se presentes, são booleanos.
- **Excesso de taxa:** o contador `contador_descarte_rajada` vira aviso no Diagnóstico ("Eventos do Meet descartados").

## 3. Handshake de relógio

**Emenda de 29/09/2026 (T-15.A2):** a medição passou para a ponte, no relógio monotônico do app. O cliente não mede nada; apenas devolve o próprio relógio de parede. O `anotar_handshake` por sessão foi substituído por relógio por conexão e carimbo por evento. Motivo: a sessão da ponte e a do app são cópias imutáveis distintas, e cada aba tem o próprio relógio.

```
ponte → background : {"tipo":"relogio_ping","connection_id":…,"n":3}
background → ponte : {"tipo":"relogio_pong","connection_id":…,"n":3,"client_wall_ms":Date.now()}
```

- **Quando:** 5 pings a 200 ms após o `sessao` e depois 1 a cada 30 s, enquanto o socket vive (`RELOGIO_*` em `config.py`). Um pong só é aceito para `n` pendente e conexão vinculada no mesmo socket.
- **Amostra** (`relogio_meet.AmostraRelogio`): envio (monotônico e parede do app), recebimento (monotônico) e parede do cliente.
- **Cálculo:** `rtt = recebido − envio`; `offset_ms = cliente_wall − (envio_wall + rtt/2)`; vale a amostra de menor RTT entre as 20 mais recentes, com `incerteza = rtt/2 + 1 ms`.
- **Página → parede:** cada legenda leva `page_perf_ms` e `page_wall_ms`, lidos juntos no envio pelo `content.js`, e `cliente_wall(t) = t − (page_perf_ms − page_wall_ms)`.
- **Carimbo na ponte** (`relogio_meet.carimbar_fala`), com `agora_mono`/`agora_wall` do recebimento: `speech_started_monotonic_ns`, `speech_last_monotonic_ns` e `clock_uncertainty_ms` (= incerteza + 1 ms). Esses campos são **do servidor**: se vierem do cliente, são descartados. Sem relógio, sem amostra da página ou com a fala no futuro além de `RELOGIO_FOLGA_FUTURO_MS`, nada é carimbado.
- **Worker** (`processador_reuniao._eventos_no_tempo_do_audio`): `ts_sec = (speech_started_monotonic_ns − first_frame_monotonic_ns) / 1e9`. `clock_uncertainty_ms` do job = maior incerteza entre os eventos carimbados, arredondada para cima. Sem nenhum carimbo, mantém o valor legado (5000 se o snapshot marcar relógio incerto). Fala anterior ao primeiro frame fica sem `ts_sec`.
- **Primeiro frame:** `CapturaLeveMixin.primeiro_frame_monotonic_ns` é marcado no primeiro bloco do loopback, descontada a duração do bloco (o `record()` devolve 1 s). O snapshot do job prefere esse valor ao instante após `start()` (`app_processamento.primeiro_frame_do_job`). O `soundcard` preenche o silêncio do loopback com zeros pelo tempo decorrido (`mediafoundation._record_chunk`), então a linha do tempo não encolhe.

```python
# relogio_meet.py
@dataclass(frozen=True)
class AmostraRelogio: n: int; envio_mono_ns: int; envio_wall_ns: int; recebido_mono_ns: int; cliente_wall_ms: float
def melhor_offset(amostras) -> tuple[float, float] | None          # (offset_ms, incerteza_ms)
def para_monotonic_servidor_ns(t_pagina_ms, *, page_perf_ms, page_wall_ms, offset_ms, agora_mono_ns, agora_wall_ns) -> int
class RelogiosConexao: iniciar_ping(cid) -> dict; registrar_pong(cid, n, *, cliente_wall_ms); relogio_de(cid); esquecer(cid)
def carimbar_fala(evento, relogio, *, agora_mono_ns, agora_wall_ns) -> dict
async def pingar(enviar, relogios, cid) -> None
def eventos_no_tempo_do_audio(eventos, primeiro_frame_ns) -> tuple[list[dict], float | None]
```

## 4. Linha do tempo e alinhamento

**Emenda de 29/09/2026 (T-15.C2):** contrato ajustado ao que foi implementado e medido.

```python
# linha_tempo_falas.py
@dataclass(frozen=True)
class Fala:
    fala_id: str; participant_id: str; nome: str | None
    inicio_ms: int; fim_ms: int; texto: str; evento_ids: tuple[str, ...]
def construir_linha_tempo(eventos: Iterable[Mapping]) -> list[Fala]   # eventos já com ts_sec/ts_fim_sec

# alinhador_falas.py
@dataclass(frozen=True)
class Alinhamento: atraso_global_ms: float; atrasos_janela: dict[int, float]; concordancia: float; estimado: bool
@dataclass(frozen=True)
class AtribuicaoPalavra: participant_id: str | None; fala_idx: int | None; ambigua: bool; forte: bool
@dataclass(frozen=True)
class ResultadoAlinhamento: fundidos: list[SegmentoSTT]; atribuicoes: dict[str, Atribuicao]; alinhamento: dict | None
def estimar_atraso(palavras, falas) -> Alinhamento
def atribuir_palavras(palavras, falas, alinhamento) -> list[AtribuicaoPalavra]
def alinhar_segmentos(fundidos, eventos, *, incerteza_ms) -> ResultadoAlinhamento
def combinar_atribuicoes(por_texto: Mapping[str, dict], por_alinhamento: Mapping[str, Atribuicao]) -> dict[str, dict]
```

- **Tempos:** `relogio_meet.eventos_no_tempo_do_audio` passa a dar também `ts_fim_sec`, a partir de `speech_last_monotonic_ns`. Revisões do mesmo `caption_id` viram uma fala: início mínimo, fim máximo, texto e nome da revisão mais nova (o nome também pode vir de qualquer revisão).
- **Sinal do atraso:** `tempo alinhado = tempo da legenda + δ`. A legenda chega depois da fala, então `δ < 0`. A busca vai de −4000 a +1000 ms, em passos de 50 ms.
- **Pontuação:** as palavras da legenda são espalhadas por igual no intervalo da fala. Cada palavra do Whisper cuja palavra igual da legenda esteja a até 700 ms soma `1 − |d|/700`. A contagem simples de pares não tem pico (a tolerância cria platôs) e foi descartada. Empate fica com o `δ` mais próximo da referência.
- **Pouca concordância:** menos de 8 pares resulta em `estimado=False` e atraso padrão de −1000 ms. Com isso, ou com concordância < 0,3, a confiança do segmento é multiplicada por 0,6 (atribuição só pelo tempo).
- **Refino:** por janela de 60 s, ±500 ms em torno do global. A janela só adota o próprio `δ` com pelo menos 4 pares; senão, fica com o global.
- **Palavra:**
  - Contida numa única fala (sem outra fala que cubra e tenha a mesma palavra): atribuição **forte**.
  - Senão, entre as falas que a cobrem com ±300 ms, a âncora de texto única também é forte.
  - Todas do mesmo participante: atribuição fraca a ele.
  - Participantes diferentes sem desempate: **ambígua**.
  - Fora de qualquer fala: vai para a fala mais próxima em até 1500 ms, como fraca.
- **Corte:** grupos contíguos por participante; palavras sem atribuição seguem o grupo corrente. Um grupo com menos de 600 ms ou uma só palavra volta ao vizinho **somente se alguma palavra for fraca**, então um "sim" forte vira segmento próprio. O primeiro e o último corte herdam as bordas do segmento original. Os IDs ficam `<id>-c<k>`, e `overlap=True` quando há palavra ambígua.
- **Sugestão por segmento** (`source="meet_alinhamento"`):
  - participante dominante por duração;
  - `score = cobertura × fator`;
  - evidências = `event_id` das falas usadas;
  - nome ausente dá UNKNOWN; mais da metade ambígua dá CONFLICT.
  - Por ora SUGGESTED: a aplicação automática é da T-15.C3.
- **Combinação** com a atribuição por texto: o alinhamento substitui a comparação de texto, a confirmação manual prevalece, e um UNKNOWN do alinhamento não apaga uma sugestão por texto.
- **Pipeline:** `retranscritor` alinha logo após `mesclar_segmentos`, antes da diarização, que casa por `(início, fim, texto)`. Com incerteza de relógio acima de `INCERTEZA_TEMPO_MAX_MS` ou sem falas, nada muda.
- **Diagnóstico** (só números): vai em `ResultadoProcessamento.alinhamento` e no log `[meet_alinhamento]` (`atraso_ms` = quanto a legenda chega depois, `concordancia`, `falas`, `palavras`, `atribuidas`, `cortes`). A persistência no `ResultManifest` fica para a T-15.C4, que é quem o exibe.
- **Constantes:** `ALINHAMENTO_*`, `ATRIBUICAO_*` e `FRAGMENTO_MIN_MS` em `config.py`, provisórias até a T-15.F1. O antigo `RELOGIO_INCERTEZA_MAX_MS` é o `INCERTEZA_TEMPO_MAX_MS` já existente.

## 4.1 Política de nomes (T-15.C3)

- **Confirmação por segmento:** uma atribuição `suggested` com `source ∈ {meet_alinhamento, meet_proprio}`, `participant_id` e nome, sem `overlap` e com `confidence ≥ NOME_AUTO_CONFIANCA_MIN` (0,6), vira `status: "confirmed"` com `auto: true`.
- **Nome do cluster de voz:** o participante com `auto` que cobre ≥ `NOME_AUTO_PARTICIPACAO_MIN` (0,8) da duração do cluster, com ≥ `NOME_AUTO_DURACAO_MIN_S` (5 s) e sem homônimo (mesmo nome, outro `participant_id`), entra no mapeamento: `{participant_id, display_name, origem: "meet_auto", confianca}`. Uma entrada manual existente nunca é sobrescrita.
- **Nome no TXT** (`resultado_edicao._nome_do_segmento`), em ordem:
  1. correção manual do cluster;
  2. confirmação do segmento;
  3. nome automático do cluster;
  4. "Identificação pendente".
- **Desligar:** `NOMES_AUTO_MEET = False` devolve o comportamento anterior (só sugestão).
- **Central:** o painel mostra a origem ("Meet", "Meet (você)", "Meet (automático) · 86%").

## 5. Provedores de IA

```python
# provedores_ia.py (novo; ≤ 500 linhas, dividir em provedor_ollama.py / provedor_openrouter.py se preciso)
@dataclass(frozen=True)
class ModeloIA: id: str; nome: str; tamanho_bytes: int | None; contexto: int | None; local: bool
@dataclass(frozen=True)
class EstadoProvedor: estado: Literal["online","offline","sem_modelos","sem_chave","chave_invalida","nao_instalado","parado"]; detalhe: str; versao: str | None
class ProvedorIA(Protocol):
    id: Literal["ollama","openrouter"]
    def estado(self) -> EstadoProvedor
    def listar_modelos(self) -> list[ModeloIA]
    def conversar(self, mensagens: list[dict], *, modelo: str, temperatura: float | None = None,
                  max_tokens: int | None = None, cancelar: threading.Event | None = None) -> str
    def conversar_stream(self, mensagens, *, modelo, **kw) -> Iterator[str]
def provedor_para(funcao: Literal["resumo","chat"]) -> ProvedorIA   # lê config_user
```

- **Ollama:** `/api/version`, `/api/tags`, `/api/show`, `/api/chat` (NDJSON), `/api/pull` (NDJSON com progresso). Preserva `think:false` e as opções atuais do resumo.
- **OpenRouter:** `GET /api/v1/models`, `POST /api/v1/chat/completions` (SSE para stream), validação da chave pelo endpoint de informações da chave. Cabeçalhos `Authorization: Bearer`, `X-Title: Transkriptor`. Enviar a preferência de provedor que nega coleta de dados (`provider.data_collection = "deny"`), se a documentação vigente a mantiver. **Conferir a documentação oficial no momento da implementação e registrar a data na evidência.**
- Erros viram `ErroProvedor(codigo, mensagem_segura)`. A mensagem nunca contém a chave nem o texto enviado.

## 6. Detecção do Ollama

```python
# detector_ollama.py (novo)
@dataclass(frozen=True)
class DeteccaoOllama:
    estado: Literal["online","parado","nao_instalado"]; versao: str | None
    url: str; executavel: str | None; modelos: list[ModeloIA]
def detectar_ollama(url_config: str | None = None, *, timeout_s: float = 2.0) -> DeteccaoOllama
```

Ordem de busca:

1. URL: `url_config` → `OLLAMA_HOST` (normalizar `host:porta` para `http://`) → `http://127.0.0.1:11434`.
2. `GET <url>/api/version`. Se responder, `online` e `GET /api/tags`.
3. Executável: `shutil.which("ollama")` → `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` → `InstallLocation` da chave de desinstalação em `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` cujo `DisplayName` contém "Ollama".
4. Executável presente e API muda: `parado`, com a ação "Iniciar Ollama" (`ollama app.exe` na mesma pasta, ou `ollama serve` desanexado). Sem executável: `nao_instalado`, com ações "Abrir página oficial" (`https://ollama.com/download`) e "Instalar com winget" (`winget install Ollama.Ollama`, só após confirmação).

A URL do Ollama só pode apontar para loopback (`127.0.0.1`, `localhost`, `::1`). Outra origem exige DP-15-09.

## 7. Configurações (Central)

`GET/POST /api/config` recebe as chaves abaixo, somadas às de `central_config.CHAVES`:

| Chave | Tipo | Padrão | Confirmação |
|---|---|---|---|
| `whisper_dispositivo` | `auto\|cpu\|cuda` | `auto` | não |
| `whisper_precisao` | `auto\|int8\|int8_float16\|float16` | `auto` | não |
| `ollama_url` | URL loopback | `http://127.0.0.1:11434` | não |
| `ia_resumo_provedor` / `ia_chat_provedor` | `ollama\|openrouter` | `ollama` | 409 ao escolher `openrouter` sem consentimento |
| `ia_resumo_modelo` / `ia_chat_modelo` | str ≤ 120 | `""` (automático) | não |
| `openrouter_chave` | str (só escrita) | — | grava `openrouter_chave_dpapi`; resposta traz só `{configurada, final}` |
| `openrouter_consentimento` | bool | `false` | 409 + texto de consequência |
| `meet_idioma_legenda` | `seguir_transcricao\|nao_alterar` | `seguir_transcricao` (DP-15-01) | não |
| `meet_capturar_chat` | bool | `true` (DP-15-03) | não |

Endpoints novos, todos sob o header secreto nas mutações:

- `GET /api/ia/provedores`: estado dos dois provedores, sem chave.
- `GET /api/ia/modelos?provedor=`: lista de `ModeloIA`.
- `POST /api/ia/testar`: `{provedor, modelo}` → `{ok, latencia_ms, erro?}`, com prompt fixo e sem transcrição.
- `POST /api/ia/ollama/baixar`: `{modelo}` → progresso via `GET /api/ia/ollama/baixar/<id>`.
- `GET /api/primeiro-uso`: `{hardware, whisper_recomendado, ollama: DeteccaoOllama, extensao: {pareada, ultima_conexao}}`.

## 8. Native Messaging

- **Nome do host:** `com.transkriptor.ponte`.
- **Manifest:** `%LOCALAPPDATA%\Transkriptor\native\com.transkriptor.ponte.json`:

```json
{"name":"com.transkriptor.ponte","description":"Transkriptor — pareamento local",
 "path":"transkriptor-ponte.exe","type":"stdio",
 "allowed_origins":["chrome-extension://<ID_CHROME>/","chrome-extension://<ID_EDGE>/"]}
```

- **Registro por usuário:** `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.transkriptor.ponte` e `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.transkriptor.ponte`, valor padrão = caminho do JSON.
- **Protocolo** (stdio, 4 bytes de tamanho + JSON). Qualquer outra mensagem recebe `{"ok":false,"erro":"comando_invalido"}` e o host sai.

```
→ {"cmd":"obter_codigo_pareamento","v":1}
← {"ok":true,"codigo":"pair-…","porta":5051}   |  {"ok":false,"erro":"app_nao_iniciado|recusado"}
```

- **Canal host → app:** `POST http://127.0.0.1:<porta_central>/api/ponte/codigo` com o segredo local lido de `%LOCALAPPDATA%\Transkriptor\ponte.segredo`. O arquivo tem ACL só do usuário e é gerado pelo app a cada início. A ponte confere também a origem do chamador recebida pelo host como argumento do Chrome.
- A extensão usa `chrome.runtime.connectNative` apenas quando não há credencial válida. Exige a permissão `nativeMessaging` no manifest.

## 9. Extensão

- `manifest.json`:
  - ganha `key` (DP-15-05) e as permissões `nativeMessaging` e `storage`;
  - mantém `host_permissions` só para `https://meet.google.com/*`;
  - a versão acompanha `config.VERSAO`.
- `rtc.js` continua em `world: MAIN`, `document_start`. A lógica de protocolo pode ser dividida em módulos (`rtc_proto.js`, `rtc_canais.js`, `rtc_idioma.js`) injetados em ordem, cada um exportável para Vitest como hoje (`module.exports`).
- Os ids de canal começam em 61001 e são sequenciais, fora da faixa usada pela Tactiq.

## 10. Resultado

- **Segmento:** ganha `words: [{w, ini_ms, fim_ms, prob, participant_id?}]` e `assignment` conforme `spec.md`.
- **Resultado estruturado** (emenda de 29/09, T-15.C4): ganha `transcricao_meet` (blocos `{inicio_ms, fim_ms, participant_id, nome, texto}`) e `lacunas_meet` (mesmo formato), somente quando existem e cifrados junto com os segmentos no modo protegido. As lacunas ficam **fora** de `segmentos`, porque não têm áudio. A saída não usa `meet_transcript_ref` no manifesto. O diagnóstico do alinhamento continua no log e em `ResultadoProcessamento`, e `ia` no manifesto fica para a T-15.D2.
- **Exportação TXT:**

```
[00:03:12] Ana Silva: …
[00:03:20] Alessandro (você): …
[00:03:41] FALANTE_03 — identificação pendente: …
[00:04:02] [legenda do Meet] Bruno Costa: …
[00:04:10] [chat] Ana Silva: …
```

## 11. Arquivos por módulo

| Módulo | Papel | Task |
|---|---|---|
| `extension/meet/rtc*.js` | captura, idioma, próprio, canais, saúde, chat | A1, B1–B5 |
| `extension/meet/content.js` | consolidação, fila, config para a página | A1, A3 |
| `extension/meet/background.js` | handshake de relógio, fila, native messaging | A2, A3, E2 |
| `relogio_meet.py` | offset/incerteza | A2 |
| `meet_bridge.py`, `sessao_reuniao.py`, `eventos_meet_store.py` | envelope v2, ping/pong, lotes | A2, A3 |
| `linha_tempo_falas.py`, `alinhador_falas.py` | linha do tempo e alinhamento | C2 |
| `identidade_reuniao.py`, `correlacionador.py` | política de nomes | C3 |
| `transcricao_meet.py` | transcrição do Meet e preenchimento | C4 |
| `audio_fontes.py`, `transcricao_core.py` | palavras, dispositivo e precisão | C1, D3 |
| `provedores_ia.py`, `detector_ollama.py` | IA | D1, D2, E3 |
| `central_config.py`, `central_ia.py`, `templates/configuracoes.html`, `templates/primeiro_uso.html`, `static/js/ia.js` | UI | D3, E3 |
| `ponte_nativa.py`, `instalador/` | host e setup | E2, E4 |
