# Interfaces congeladas para a execução v1.8

Estas interfaces evitam que agentes diferentes inventem nomes incompatíveis. São contratos planejados, ainda não implementados. Uma alteração exige emenda em `spec.md`, `tasks.md` e neste arquivo antes do código consumidor.

## Princípios de tipos e serialização

- Python 3.12; `from __future__ import annotations`; dataclasses congeladas para valores transferidos entre módulos.
- Instantes persistidos: UTC ISO-8601 com sufixo `Z`. Duração/alinhamento: inteiros em milissegundos; relógio interno: `time.monotonic_ns()`.
- IDs locais: UUID em string. Paths persistidos: relativos à raiz validada; nunca absolutos.
- JSON: UTF-8, `ensure_ascii=False`, schema version inteiro, escrita atômica. Campos desconhecidos são preservados ao migrar, mas nunca executados.
- Enums são serializados pelo `.value`; consumidor rejeita valor desconhecido com erro seguro.

## Sessão e eventos

```python
# sessao_reuniao.py
@dataclass(frozen=True)
class SessaoReuniao:
    session_id: str
    meeting_key: str
    consented_at_utc: str
    first_frame_monotonic_ns: int | None
    policy_id: str

def criar_sessao(meeting_key: str, consented_at_utc: str, policy_id: str) -> SessaoReuniao: ...
def validar_envelope(evento: Mapping[str, object], sessao: SessaoReuniao) -> dict[str, object]: ...

class SessoesAtivas:
    def vincular(self, connection_id: str, tab_id: str, sessao: SessaoReuniao) -> None: ...
    def aceitar_evento(self, connection_id: str, evento: Mapping[str, object]) -> dict[str, object]: ...
```

O WebSocket pode ser único, mas `connection_id` é lógico e exclusivo por aba. O servidor vincula `session_id` e `meeting_key` após consentimento e rejeita evento que tente substituí-los. O cliente envia seus relógios; o bridge acrescenta `received_monotonic_ns=time.monotonic_ns()` no recebimento. Apenas o envelope canônico persistido inclui esse campo de servidor.

O envelope canônico tem exatamente os campos de `spec.md`. `event_id`, `session_id`, `connection_id`, `tab_id`, `meeting_key` são strings não vazias; `seq >= 0`; tamanhos obedecem à spec. `caption_revision` maior substitui revisão anterior do mesmo `caption_id`; eventos duplicados são idempotentes por `event_id`.

```python
# artefatos.py — criado em B2
@dataclass(frozen=True)
class ArtifactRef:
    relative_path: str
    format: str
    schema_version: int
    sha256: str
    size_bytes: int

class ArtifactCipher(Protocol):
    def seal(self, plaintext: bytes, destination: Path) -> ArtifactRef: ...
    def open(self, ref: ArtifactRef, root: Path) -> bytes: ...

# resultado_pipeline.py — materializado nas Tasks 5–6 da remediação
@dataclass(frozen=True)
class ResultadoProcessamento:
    txt_path: Path
    segmentos: tuple[SegmentoResultado, ...]
    atribuicoes: Mapping[str, Mapping[str, object]]
    stage_status: Mapping[str, StageState]
    warnings: tuple[str, ...]

# resultado_storage.py — materializado na Task 8 da remediação
class ResultadoStorage:
    def save(self, meeting_id: str, payload: Mapping[str, object]) -> ArtifactRef: ...
    def load(self, ref: ArtifactRef) -> dict[str, object]: ...

# eventos_meet_store.py — criado em D4 e importa os contratos acima

class EventStore:
    def __init__(self, root: Path, session: SessaoReuniao, cipher: "ArtifactCipher") -> None: ...
    def append(self, event: Mapping[str, object]) -> int: ...  # ack_seq durável
    def read_events(self) -> Iterator[dict[str, object]]: ...
    def seal(self) -> tuple[ArtifactRef, ...]: ...
```

Cada segmento JSONL fecha ao atingir 1 MiB ou 1 s. Só depois de `flush + fsync + replace` e cifra validada o servidor envia ACK. O índice contém seq, hashes, tamanhos e paths, nunca nome/texto.

## Jobs, lease e resultado

```python
# fila_lock.py
@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created_at_100ns: int

@dataclass(frozen=True)
class Lease:
    owner: ProcessIdentity
    nonce: str
    acquired_at_utc: str
    heartbeat_at_utc: str

@contextmanager
def job_lock(lock_path: Path, timeout_s: float = 5.0) -> Iterator[None]: ...
def current_process_identity() -> ProcessIdentity: ...
def process_matches(identity: ProcessIdentity) -> bool: ...
```

`job_lock` usa `msvcrt.locking` em um byte de lockfile criado dentro de `jobs/.locks/`. Toda leitura-modificação-escrita de um job ocorre dentro do lock. `process_matches` usa PID + criação do processo; acesso negado produz estado indeterminado e impede recuperação destrutiva.

```python
# fila_processamento.py
def renovar_lease(job_id: str) -> Job: ...
def registrar_progresso(job_id: str, stage: str, units: int) -> Job: ...
def solicitar_cancelamento(job_id: str) -> Job: ...
def cancelar(job_id: str) -> Job: ...
def registrar_falha_de_spawn(job_id: str, erro_seguro: str) -> Job: ...
def reabrir_se_retry(job_id: str, max_tentativas: int | None = None) -> Job: ...
def finalizar_por_supervisor(
    job_id: str, pid_esperado: int, erro_seguro: str, *,
    estado: str = "failed", max_tentativas: int | None = None,
) -> Job: ...

# worker_liveness.py
def avaliar_inatividade(stage, ocioso_seg, aviso_seg, falha_seg, modelo_init_seg) -> str: ...
def encerrar_se_lease_valido(lease, pid_esperado, encerrar) -> bool: ...
```

`renovar_lease` só aceita o proprietário cujo `ProcessIdentity` coincide com o
lease persistido. Ela preserva `owner`, `nonce` e `acquired_at_utc`, atualiza
`heartbeat_at_utc` e incrementa `revision` dentro do mesmo lock do job. As
transições `processing -> ready|failed|cancelled` aplicam a mesma prova de
propriedade; um processo que perdeu a disputa não pode abrir a transcrição nem
concluir o job.

`registrar_progresso` é do detentor do lease e conta como avanço de etapa/unidades,
não como mero heartbeat. `finalizar_por_supervisor` e o encerramento forçado só
aceitam o PID que consta no lease validado daquele job. Cancelamento cooperativo
grava `cancelled` e preserva as fontes. Retry de falha para em
`WORKER_MAX_TENTATIVAS`.

```python
# resultado_reuniao.py
class StageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass(frozen=True)
class ResultManifest:
    meeting_id: str
    schema_version: int
    source_audio_hashes: tuple[str, ...]
    participants_ref: ArtifactRef | None
    segments_ref: ArtifactRef
    stage_status: Mapping[str, StageState]
    warnings: tuple[str, ...]
    exports: tuple[ArtifactRef, ...]
    created_at: str
    pipeline_version: str

def salvar_manifesto(path: Path, manifesto: ResultManifest) -> None: ...
def carregar_manifesto(path: Path) -> ResultManifest: ...
def validar_manifesto(path: Path, root: Path) -> bool: ...
def criar_manifesto_inicial(*, meeting_id: str, resultado: Path,
                             fontes_audio: Sequence[Path], raiz: Path,
                             created_at: str | None = None) -> ResultManifest: ...
def validar_manifesto_para_job(*, resultado: Path, manifesto: Path,
                               fontes_audio: Sequence[Path], raiz: Path) -> str: ...
```

Na B2, `criar_manifesto_inicial` referencia o TXT legado por hash como
artefato de saída até D7 materializar segmentos estruturados. A ausência de
fala fica como `stage_status["stt"] == PARTIAL` e aviso `stt_sem_fala`; ela não
é resultado útil para retenção. Job v2 adiciona os campos da spec ao JSON
atual. Leitor aceita v1, mas escritor gera v2. Estado `ready` só é escrito
depois de `validar_manifesto(...) is True`, com hash da fonte do job e ref do
resultado conferidos. O TXT não é manifesto.

## Áudio e STT por fonte

```python
# audio_reader.py
class AudioSource(StrEnum):
    LOOPBACK = "loopback"
    MICROPHONE = "microphone"

@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    channels: int
    sample_width: int
    total_frames: int
    source: AudioSource

@dataclass(frozen=True)
class AudioChunk:
    start_frame: int
    samples: np.ndarray

def inspect_audio(path: Path, source: AudioSource) -> AudioInfo: ...
def iter_audio(path: Path, source: AudioSource, max_seconds: float = 30.0) -> Iterator[AudioChunk]: ...
```

Somente PCM 16/24/32 explicitamente implementado é aceito. Formato desconhecido levanta `UnsupportedAudioFormat`; nunca cai em uint8 genérico. `.wav.enc` legado passa por API de decifragem tipada e respeita limite definido em `config.py`.

```python
# audio_fontes.py
@dataclass(frozen=True)
class SegmentoSTT:
    segment_id: str
    start_ms: int
    end_ms: int
    source: AudioSource
    text: str
    overlap: bool

def transcrever_fonte(path: Path, source: AudioSource, *, model: object) -> list[SegmentoSTT]: ...
def mesclar_segmentos(loopback: Sequence[SegmentoSTT], microphone: Sequence[SegmentoSTT]) -> list[SegmentoSTT]: ...
```

Deduplicação de eco exige sobreposição temporal e similaridade textual/acústica conforme teste; em dúvida, preserva os dois e marca sobreposição.

## Identidade e correção

```python
# identidade_reuniao.py
class AssignmentStatus(StrEnum):
    CONFIRMED = "confirmed"
    SUGGESTED = "suggested"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"

@dataclass(frozen=True)
class Atribuicao:
    participant_id: str | None
    display_name: str | None
    source: str
    score: float | None
    evidence_ids: tuple[str, ...]
    status: AssignmentStatus

def resolver_atribuicao(segmento: SegmentoSTT, eventos: Sequence[Mapping[str, object]], *, clock_uncertainty_ms: int, calibration_version: str | None) -> Atribuicao: ...
```

Precedência: confirmação manual da revisão atual → entry oficial ligada a participant/time → legenda lexicalmente compatível + tempo → voz conhecida consentida → atividade como evidência auxiliar. Conflito/empate/ausência de calibração automática produz `SUGGESTED`, `UNKNOWN` ou `CONFLICT`; jamais `CONFIRMED` por frequência.

Correção recebe `meeting_id`, `expected_revision`, `speaker_cluster_id`, novo participante/nome e autor local. Retorna nova revisão imutável; undo cria outra revisão. Não altera perfil de voz.

```python
# resultado_reuniao.py
def format_segment_txt(start_ms: int, display_name: str | None, text: str) -> str: ...
```

O retorno é exatamente `[HH:MM:SS] Nome: texto`. `display_name is None` produz `Identificação pendente`; não expõe IDs internos como `FALANTE_00` na exportação nominal.

## Proteção e recuperação

Áudio longo protegido usa **TKAS/1**, implementado em E1 sobre os bindings PyNaCl de `crypto_secretstream_xchacha20poly1305`, cuja API detecta alteração, remoção, reordenação, duplicação e truncamento de mensagens. Referência normativa da primitiva: [Libsodium SecretStream](https://doc.libsodium.org/secret-key_cryptography/secretstream). Layout: magic ASCII `TKAS` (4 bytes), versão `0x01`, chunk size little-endian uint32 fixado em 1.048.576 bytes, header SecretStream, e ciphertexts de chunks consecutivos. O último usa `TAG_FINAL`; os demais `TAG_MESSAGE`. Associated data de cada chunk é o cabeçalho TKAS de 9 bytes concatenado ao índice uint64 little-endian. A chave de stream é derivada da chave mestra existente com HKDF-SHA256, `info=b"transkriptor-audio-secretstream-v1"`; ela não é persistida. Resultado parcial produzido antes de falha de autenticação/truncamento é descartado e o job falha preservando a fonte.

`crypto_stream.py` expõe somente:

```python
def encrypt_file(source: Path, destination: Path, master_key: bytes) -> ArtifactRef: ...
def iter_decrypt_file(path: Path, master_key: bytes) -> Iterator[bytes]: ...
```

Escrita usa arquivo temporário no mesmo diretório, `flush`, `fsync`, validação por leitura autenticada e `replace`. O original só pode ser removido depois dessa validação. `.wav.enc` AES-GCM legado continua legível pelo caminho legado e não é reescrito automaticamente.

```python
# politica_privacidade.py
class ProtectionMode(StrEnum):
    COMPATIBLE = "compatible"
    PROTECTED = "protected"

class ProtectionState(StrEnum):
    PLAINTEXT_ALLOWED = "plaintext_allowed"
    PROTECTED = "protected"
    PROTECTION_PENDING = "protection_pending"
    UNREADABLE = "unreadable"

class ProtectionUnavailable(RuntimeError): ...

@dataclass(frozen=True)
class ArtifactProtection:
    mode: ProtectionMode
    state: ProtectionState
    relative_path: str
    sha256: str

def protect_artifact(path: Path, mode: ProtectionMode) -> ArtifactProtection: ...
def resolve_initial_mode(existing_config: Mapping[str, object] | None) -> ProtectionMode: ...
```

`resolve_initial_mode(None)` retorna `PROTECTED`. Configuração existente sem `protection_mode` retorna `COMPATIBLE`; valor explícito válido é preservado. Perfil/embedding novo começa desativado e, em modo protegido, falha sem criar plaintext. Áudio já capturado nunca é apagado por falha de cifra: move para área restrita, retorna `PROTECTION_PENDING` e exige aviso.

```python
# retencao_audio.py — EventStore importa esta política
@dataclass(frozen=True)
class RetentionPolicy:
    audio_days_after_valid_result: int = 7
    meet_events_days_after_valid_result: int = 7
    auto_delete_results: bool = False
    voice_profile_until_revoked: bool = True

def pode_expirar(audio: Path, jobs: Iterable[object], manifesto: Path,
                 agora: datetime, *, dias: int = 7) -> bool: ...
def inventariar_audios_vencidos(pasta_audio: Path, pasta_transcricoes: Path,
                 *, jobs: Iterable[object] | None = None,
                 agora: datetime | None = None, dias: int = 7) -> tuple[list[str], list[str]]: ...
def aplicar_exclusao_confirmada(candidatos: Iterable[str | Path], *,
                 pasta_audio: Path, confirmados: Iterable[str | Path],
                 dry_run: bool = True) -> list[str]: ...
```

O marco temporal para áudio/eventos é `ResultManifest.created_at` validado, não início/fim da reunião. Job pendente, falho com retry, reprocessamento ou hash inválido suspende o prazo. Inventário não remove; `dry_run` é o padrão e a remoção só considera a interseção entre candidatos e a lista exata de paths confirmados. Resultados/manifests não entram em candidatos de retenção.

```python
# recuperacao_sessao.py
@dataclass(frozen=True)
class RecoveryItem:
    relative_path: str
    owner_session_id: str | None
    state: str
    action: str

def inventariar(root: Path, live_sessions: Collection[str]) -> tuple[RecoveryItem, ...]: ...
def recuperar(root: Path, items: Sequence[RecoveryItem], *, dry_run: bool = True) -> tuple[RecoveryItem, ...]: ...
```

`recuperar` recusa path fora da raiz após `resolve()`, junction/reparse point externo, sessão viva, ownership desconhecido e remoção da única cópia.

## API e assistente

```python
# assistente_validacao.py
@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str

@dataclass(frozen=True)
class ChatRequest:
    meeting_id: str
    transcript_revision: str
    generation_id: str
    question: str
    history: tuple[ChatMessage, ...]
    model: str

def validar_chat_payload(value: object) -> ChatRequest: ...
```

Payload inválido retorna 400; corpo excedido 413; concorrência excedida 429; upstream indisponível 502/503; erro interno inesperado 500 com mensagem segura. Nunca ecoar token/path/conteúdo no erro.

```python
# indice_transcricoes.py
@dataclass(frozen=True)
class MeetingSummary:
    meeting_id: str
    title: str | None
    started_at: str
    duration_ms: int | None
    revision: str
    quality_state: str

def listar_reunioes(index_path: Path, *, cursor: str | None, limit: int) -> tuple[tuple[MeetingSummary, ...], str | None]: ...
def atualizar_indice(index_path: Path, manifesto: ResultManifest) -> None: ...
```

`limit` permitido: 1–100. A listagem não abre TXT/TKPT nem descriptografa conteúdo.

## Google opcional

```python
# google_meet_capabilities.py
@dataclass(frozen=True)
class GoogleMeetCapabilities:
    participants: bool
    transcript_entries: bool
    reason: str | None

def detectar_capacidades(credentials: object) -> GoogleMeetCapabilities: ...

# google_meet_import.py
@dataclass(frozen=True)
class GoogleImportResult:
    conference_record: str
    participants_ref: ArtifactRef | None
    transcript_entries_ref: ArtifactRef | None
    warnings: tuple[str, ...]

def importar_conferencia(credentials: object, conference_record: str, root: Path) -> GoogleImportResult: ...
```

O importador pagina até `nextPageToken` ausente, aplica backoff limitado com jitter para 429/5xx e é idempotente por resource name + revisão. Um roster sem entries nunca vira atribuição de fala.

## Responsabilidade por arquivo

| Arquivo novo | Única responsabilidade | Primeiro produtor | Consumidores posteriores |
|---|---|---|---|
| `fila_lock.py` | lock/identidade/lease Windows | B1 | B3, E2 |
| `artefatos.py` | referências e porta de cifra de artefatos | B2 | B2, D4, D7, E1, Google |
| `resultado_reuniao.py` | manifesto e validação | B2 | D7, retenção, UI, Google |
| `audio_reader.py` | leitura tipada; streaming ampliado em C3 | C2 | C2, C3, diarização |
| `audio_fontes.py` | STT/fusão por fonte | C2 | D6, resultado |
| `sessao_reuniao.py` | identidade temporal da reunião | D1 | D2–D7 |
| `eventos_meet_store.py` | spool cifrado durável | D4 | D5, D6 |
| `identidade_reuniao.py` | resolver evidências | D6 | D7, H2 |
| `crypto_stream.py` | TKAS/1 com SecretStream, sem política de UX | E1 | áudio protegido, recuperação |
| `politica_privacidade.py` | política/estado de proteção | E1 | E2–E4 |
| `recuperacao_sessao.py` | inventário/recuperação segura | E2 | startup/diagnóstico |
| `assistente_validacao.py` | contrato HTTP de chat | E3 | API/JS |
| `indice_transcricoes.py` | índice sem conteúdo | F3 | API/UI |
| `google_meet_auth.py` | OAuth desktop | H1 | H2 |
| `google_meet_capabilities.py` | capacidade da conta | H1 | UI/H2 |
| `google_meet_import.py` | REST participants/entries | H2 | resultado/identidade |
