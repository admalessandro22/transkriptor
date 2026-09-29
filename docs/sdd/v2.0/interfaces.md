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

```python
# linha_tempo_falas.py (novo)
@dataclass(frozen=True)
class Fala:
    fala_id: str; participant_id: str; nome: str | None
    inicio_ms: float; fim_ms: float; texto: str; idioma: str | None; proprio: bool
def construir_linha_tempo(eventos: Iterable[Mapping], conversor: Callable[[Mapping], float | None]) -> list[Fala]

# alinhador_falas.py (novo)
@dataclass(frozen=True)
class Alinhamento:
    atraso_global_ms: float; atrasos_janela: dict[int, float]; concordancia: float
def estimar_atraso(palavras: Sequence[Palavra], falas: Sequence[Fala], *, faixa_ms=(-4000, 1000), passo_ms=50) -> Alinhamento
def atribuir_palavras(palavras, falas, alinhamento, *, tolerancia_ms) -> list[AtribuicaoPalavra]
def cortar_segmentos(segmentos, atribuicoes, *, fragmento_min_ms) -> list[Segmento]
```

- A normalização de texto é a mesma da similaridade lexical atual (minúsculas, sem acento nem pontuação).
- Palavras de legenda são distribuídas uniformemente no intervalo da fala para a busca de atraso.
- Com concordância abaixo de `ALINHAMENTO_CONCORDANCIA_MIN`, a atribuição usa só o tempo, com confiança reduzida, e o Diagnóstico registra "legenda e áudio não concordam".
- Constantes novas em `config.py`: `RELOGIO_INCERTEZA_MAX_MS`, `ALINHAMENTO_FAIXA_MS`, `ALINHAMENTO_PASSO_MS`, `ALINHAMENTO_JANELA_MS=60000`, `ALINHAMENTO_REFINO_MS=500`, `ATRIBUICAO_TOLERANCIA_MS`, `FRAGMENTO_MIN_MS`, `NOME_AUTO_PARTICIPACAO_MIN`, `NOME_AUTO_DURACAO_MIN_S`, `LEGENDA_SILENCIO_MS=60000`, `FILA_PRE_SESSAO_MAX`, `FILA_PRE_SESSAO_IDADE_MS`, `LOTE_EVENTOS_MS`, `LOTE_EVENTOS_MAX`. Os valores iniciais são provisórios até T-15.F1.

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
- **ResultManifest:** ganha `meet_transcript_ref` (transcrição do Meet cifrada como os demais artefatos), `alinhamento: {atraso_global_ms, concordancia, relogio_incerteza_ms, idioma_legenda}` e `ia: {resumo: {provedor, modelo}}`.
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
