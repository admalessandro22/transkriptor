# Remediação integral da auditoria v1.8 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Antes de cada alteração de código, usar `superpowers:test-driven-development`; em falha, `superpowers:systematic-debugging`; antes de concluir cada tarefa/fase, `superpowers:verification-before-completion`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** corrigir todas as divergências confirmadas na auditoria de 22/09/2026 e entregar o Transkriptor pronto para uso local, com fluxo Meet ponta a ponta, resultados editáveis, proteção efetiva, CI reproduzível, instalação validada e gates reais aprovados.

**Architecture:** manter `Transcritor` como núcleo e fechar quatro contratos que hoje estão desconectados: extensão → sessão/eventos → job/worker → resultado estruturado. Todo artefato passa por uma política de proteção única, e toda declaração de pronto depende de evidência produzida pelo mesmo commit. Gates de navegador, captura, identificação e instalação ficam depois dos gates automatizados e nunca são substituídos por mocks.

**Tech Stack:** Python 3.12+, Windows/PowerShell, pytest, JavaScript Manifest V3, Vitest, Playwright, WebSocket em `127.0.0.1`, Flask/Ollama local, PyNaCl/Libsodium SecretStream TKAS/1, pip-tools, pip-audit e CycloneDX.

## Checkpoint de execução — 24/09/2026

Tasks 1–11 foram implementadas em sequência, com commits e RED→GREEN indexados em `docs/sdd/v1.8/evidencias/REMEDIACAO-2026-09-22.md`. A automação da Task 12 passou no código `4128cd6253ab94a0e83c4234b737f5ec4bf1291a`: suíte local 806 passed; CI Windows CPU 804 passed e 2 skipped pela ausência comprovada de alto-falantes no runner; Vitest 22 passed; Playwright 21 passed; auditoria de dependências, SBOM e pré-checagem de instalação verdes. O workflow dispatch `36003594423` e o check da PR #1 `36004713892` terminaram com sucesso no mesmo SHA. A branch `remediacao-auditoria-v18` foi publicada e a PR #1 está aberta, sem merge.

Com autorização do usuário, a bandeja em uso foi reiniciada após verificação de ociosidade; uma instância nova registrou `Bandeja pronta` e heartbeats. O usuário dispensou os testes reais nesta etapa. Isso deixa **não executados**, sem PASS, a captura 25/600 s, a prova D2 em Chrome e Edge, a reunião consentida de três pessoas, a instalação CUDA limpa e a segunda partida real da bandeja. As duas exceções temporárias de dependências ainda precisam de aceite explícito. A Task 12 e o gate formal G3 permanecem **BLOCKED** para release: `config.VERSAO` segue `1.7.0`, sem bump, tag ou merge. Este checkpoint de resultado prevalece sobre instruções futuras ainda desmarcadas abaixo; elas não representam gates concluídos.

## Global Constraints

- `config.VERSAO` continua sendo a única fonte de versão; manter `1.7.0` até o gate final e fazer um único bump autorizado.
- Python 3.12+, UTF-8 e textos de interface em português do Brasil.
- `transcricao_core.Transcritor` permanece o núcleo; não duplicar captura ou transcrição.
- Flask e WebSocket escutam somente em `127.0.0.1`.
- Nenhum callback pode executar sob `self._lock`; `_status` não adquire esse lock.
- Toda thread que usa `soundcard` executa dentro de `com_audio.com_inicializada()`.
- Áudio, legenda, nome, token, path pessoal e texto transcrito não entram em logs, jobs ou evidências.
- Testes usam somente dados sintéticos e diretórios temporários; não importam `transkriptor` durante coleta.
- Nenhum processo do usuário, navegador real, atalho real, gravação real ou arquivo de produção é alterado nos gates automatizados.
- Original sensível só é removido depois de cópia equivalente autenticada, hash verificado e troca atômica.
- Tarefa técnica = teste RED, implementação mínima, seletor GREEN, regressão, revisão, evidência com SHA real e commit imperativo em português.
- Não executar tarefas dependentes em paralelo. A ordem deste documento é obrigatória.
- Chrome/Edge reais, gates de 25 s/600 s, reunião com três pessoas, instalação real e bump/release exigem autorização específica no momento da execução.

## Estado auditado de entrada

Base imutável deste plano: `64b415bdc1ae26100b533cbd3c94abafa2dcb0e8`, sincronizada com `origin/master` em 22/09/2026.

| Área | Estado de entrada | Decisão deste plano |
|---|---|---|
| A, B | suíte automatizada verde; nenhum bloqueador encontrado | preservar e rodar regressão |
| C | automação verde; gates físicos só têm evidência anterior | preservar; repetir no fechamento |
| D1, D4, D5 | fluxo v1 desconectado da extensão e do job | reabrir |
| D2 | código incompleto e demo real pendente | reabrir implementação; manter gate real bloqueado |
| D3 | parser isolado funcional | preservar |
| D6, D7 | sugestões e resultado estruturado não chegam à produção | reabrir |
| E1 | TKAS/política não integrados; leitor aceita sufixo | reabrir |
| E2, E3 | automação existente preservada | regressão obrigatória |
| E4 | título pode entrar no log; mutações locais sem validação uniforme de origem | reabrir |
| F1, F2 | automação verde | preservar |
| F3 | UI existe, mas não recebe resultado real | reabrir integração |
| G1 | CI oficial vermelho; locks/SBOM incompletos | reabrir |
| G2 | aceite de instalação real não executado | reabrir |
| G3 | gates humanos e release pendentes | manter bloqueado até Task 12 |
| H1–H3 | opcionais, dependem de conta/OAuth | fora deste plano de prontidão do núcleo |

## File Structure

### Novos arquivos

- `tests/test_fluxo_meet_ponta_a_ponta.py` — prova extensão lógica → bridge → EventStore → job v2 → worker.
- `tests/js/background-pairing.test.js` — exercita o listener real, não apenas funções auxiliares.
- `resultado_pipeline.py` — converte saída STT/diarização/identidade em `SegmentoResultado` e `ResultManifest`.
- `resultado_storage.py` — leitura/escrita atômica de resultado estruturado em modo compatível ou protegido.
- `stream_io.py` — adapta `Iterator[bytes]` autenticado para leitor binário incremental usado pelo WAV.
- `tests/test_resultado_pipeline.py` — integração worker → JSON canônico → manifesto → índice/API.
- `tests/test_resultado_storage.py` — round-trip protegido, edição, undo e ausência de plaintext.
- `tests/test_assistente_mutacoes.py` — Host/Origin/content-type para todas as rotas mutáveis.
- `requirements/base.in`, `requirements/cpu.in`, `requirements/cuda.in` e `requirements/dev.in` — entradas humanas separadas para produção e ferramentas de teste.
- `requirements/requirements-cpu.lock` e `requirements/requirements-cuda.lock` — árvores resolvidas com hashes.
- `requirements/requirements-dev.lock` — ferramentas de teste/auditoria com hashes, sem contaminar o instalador de produção.
- `scripts/gerar_sbom.py` — CycloneDX reproduzível, sem credenciais.
- `scripts/gate_instalacao.py` — aceite não interativo em pasta temporária com espaço e acentos.
- `tests/test_gate_instalacao.py` — contrato e salvaguardas do gate de instalação.
- `docs/sdd/v1.8/evidencias/REMEDIACAO-2026-09-22.md` — índice de tarefas, comandos, SHAs e gates deste plano.

### Arquivos principais modificados

- `docs/sdd/v1.8/{plan,tasks,spec,interfaces,executor-llm}.md` — emenda auditada e estados honestos.
- `extension/meet/{background,content,pairing}.js` — pareamento real, sessão lógica por aba e envelope v1.
- `meet_bridge.py`, `sessao_reuniao.py`, `eventos_meet_store.py` — handshake, validação, ACK e isolamento.
- `app_ciclo_reuniao.py`, `app_processamento.py`, `job_v2.py` — selo único e passagem dos refs ao job.
- `retranscritor.py`, `diarizacao_final.py`, `diarizador.py`, `identidade_reuniao.py` — resultado estruturado e atribuição preservada.
- `resultado_reuniao.py`, `resultado_edicao.py`, `indice_transcricoes.py`, `assistente.py` — manifesto canônico, edição e UI reais.
- `crypto_stream.py`, `crypto_storage.py`, `audio_reader.py`, `politica_privacidade.py`, `diarizacao_final.py` — TKAS/1 e política efetiva.
- `status_seguro.py`, `assistente_validacao.py` — logs tipados e validação uniforme das mutações.
- `.github/workflows/tests.yml`, `instalar.bat`, `desinstalar.bat`, `scripts/instalar_helper.py` — CI e instalação reproduzível.

---

### Task 1: Reconciliar a fonte SDD com a auditoria

**Files:**
- Modify: `docs/sdd/v1.8/plan.md`
- Modify: `docs/sdd/v1.8/tasks.md`
- Modify: `docs/sdd/v1.8/spec.md`
- Modify: `docs/sdd/v1.8/interfaces.md`
- Modify: `docs/sdd/v1.8/executor-llm.md`
- Create: `docs/sdd/v1.8/evidencias/REMEDIACAO-2026-09-22.md`
- Test: `tests/test_sdd_rastreabilidade.py`

**Interfaces:**
- Consumes: relatório da auditoria e base `64b415b`.
- Produces: estados `REOPENED`, dependências revisadas e os contratos adicionais `SessoesAtivas.vincular(...)`, `ResultadoProcessamento` e `ResultadoStorage` usados nas tarefas seguintes.

- [ ] **Step 1: escrever o teste de rastreabilidade que rejeita falso `DONE`**

Adicionar a `tests/test_sdd_rastreabilidade.py`:

```python
def test_remediacao_reabre_tarefas_incompletas():
    tasks = (ROOT / "docs/sdd/v1.8/tasks.md").read_text(encoding="utf-8")
    for tarefa in ("D1", "D2", "D4", "D5", "D6", "D7", "E1", "E4", "F3", "G1", "G2"):
        linha = next(l for l in tasks.splitlines() if f"T-13.{tarefa}" in l and "Requisito" in l)
        assert "REOPENED" in linha or "BLOCKED" in linha
    assert "23 DONE" not in tasks
```

- [ ] **Step 2: confirmar RED pelo estado documental atual**

Run: `python -m pytest tests/test_sdd_rastreabilidade.py::test_remediacao_reabre_tarefas_incompletas -v`

Expected: FAIL porque as tarefas auditadas ainda aparecem como `DONE`.

- [ ] **Step 3: aplicar a emenda documental completa**

Registrar nos cinco documentos:

```text
REOPENED = implementação existente não satisfaz o contrato auditado; exige novo RED/GREEN.
BLOCKED = implementação automatizável verde, mas falta gate externo autorizado.
DONE = requisito, teste específico, regressão, aceite, evidência e SHA concordam.
```

Acrescentar às interfaces congeladas:

```python
class SessoesAtivas:
    def vincular(self, connection_id: str, tab_id: str, sessao: SessaoReuniao) -> None: ...
    def aceitar_evento(self, connection_id: str, evento: Mapping[str, object]) -> dict[str, object]: ...

@dataclass(frozen=True)
class ResultadoProcessamento:
    txt_path: Path
    segmentos: tuple[SegmentoResultado, ...]
    atribuicoes: Mapping[str, Mapping[str, object]]
    stage_status: Mapping[str, StageState]
    warnings: tuple[str, ...]

class ResultadoStorage:
    def save(self, meeting_id: str, payload: Mapping[str, object]) -> ArtifactRef: ...
    def load(self, ref: ArtifactRef) -> dict[str, object]: ...
```

Definir explicitamente que o WebSocket pode ser único, mas `connection_id` é lógico e exclusivo por aba; o servidor é a autoridade de `session_id` e `meeting_key` depois do consentimento. O cliente envia relógios próprios; o bridge acrescenta `received_monotonic_ns=time.monotonic_ns()` ao receber e somente o envelope canônico persistido contém esse campo de servidor.

- [ ] **Step 4: rodar rastreabilidade e diff documental**

Run: `python -m pytest tests/test_sdd_rastreabilidade.py tests/test_versao.py -v`

Expected: PASS; `config.VERSAO == "1.7.0"`.

- [ ] **Step 5: registrar evidência e commit**

```powershell
git add docs/sdd/v1.8 tests/test_sdd_rastreabilidade.py
git commit -m "docs: reabre tarefas divergentes da auditoria"
```

Registrar o SHA produzido em `REMEDIACAO-2026-09-22.md`; nunca escrever “commit de fechamento”.

---

### Task 2: Corrigir pareamento e envelope v1 da extensão

**Files:**
- Modify: `extension/meet/background.js`
- Modify: `extension/meet/content.js`
- Modify: `extension/meet/pairing.js`
- Modify: `tests/js/background.test.js`
- Create: `tests/js/background-pairing.test.js`
- Modify: `tests/e2e/meet-transport.spec.js`

**Interfaces:**
- Consumes: `Envelope v1` de `spec.md` e mensagem de sessão enviada pelo bridge.
- Produces: `hello` por aba e a porção cliente do envelope com `event_id`, `session_id`, `connection_id`, `seq`, `tab_id`, `meeting_key`, `kind`, `client_wall_ms`, `client_monotonic_ms` e campos opcionais. O bridge acrescenta o único campo de servidor, `received_monotonic_ns`.

- [ ] **Step 1: escrever RED para o listener real de pareamento**

Exportar `aoReceberMensagem` somente no ramo CommonJS e testar:

```javascript
it("aceita pareamento apenas da própria página da extensão", () => {
  const sender = {
    id: "abcdefghijklmnop",
    frameId: 0,
    url: "chrome-extension://abcdefghijklmnop/pairing.html"
  };
  const resposta = vi.fn();
  expect(fundo.aoReceberMensagem({ tipo: "parear" }, sender, resposta, {
    runtimeId: "abcdefghijklmnop",
    conectar: vi.fn()
  })).toBe(true);
});
```

Adicionar casos que rejeitam outra extensão, `http://`, subframe e página diferente.

- [ ] **Step 2: confirmar RED**

Run: `npm run test:unit -- tests/js/background-pairing.test.js`

Expected: FAIL porque o listener não é exportado e o validador atual rejeita `pairing.html`.

- [ ] **Step 3: separar validadores por tipo de mensagem**

Implementar em `background.js`:

```javascript
function validarSenderPareamento(sender, runtimeId) {
  if (!sender || sender.id !== runtimeId || sender.frameId !== 0) return false;
  try {
    const url = new URL(sender.url || "");
    return url.protocol === "chrome-extension:" &&
      url.hostname === runtimeId && url.pathname === "/pairing.html";
  } catch (_e) {
    return false;
  }
}

function validarSenderMeet(sender) {
  if (!sender || sender.frameId !== 0 || !sender.tab || typeof sender.tab.id !== "number") return false;
  return /^https:\/\/meet\.google\.com\//.test(sender.url || sender.tab.url || "");
}
```

O listener escolhe o validador depois de ler `mensagem.tipo`; `parear` nunca exige uma aba Meet, e `meet-evento` nunca aceita a página da extensão.

- [ ] **Step 4: criar estado lógico por aba**

Em `background.js`, manter somente em memória:

```javascript
const abas = new Map();
function estadoAba(tabId) {
  if (!abas.has(tabId)) {
    abas.set(tabId, { connectionId: crypto.randomUUID(), session: null, seq: 0 });
  }
  return abas.get(tabId);
}
```

Ao primeiro evento de uma aba, enviar `hello` sem conteúdo sensível. Eventos de conteúdo aguardam a resposta `sessao`; heartbeat pode provocar o handshake, mas não persistir nome/texto antes do consentimento.

- [ ] **Step 5: produzir o envelope exato**

```javascript
function montarEnvelope(evento, sender, agora = {}) {
  const tabId = String(sender.tab.id);
  const estado = estadoAba(sender.tab.id);
  if (!estado.session) return null;
  return {
    schema_version: 1,
    event_id: crypto.randomUUID(),
    session_id: estado.session.session_id,
    connection_id: estado.connectionId,
    seq: estado.seq++,
    tab_id: tabId,
    meeting_key: estado.session.meeting_key,
    kind: evento.kind,
    client_wall_ms: agora.wallMs ?? Date.now(),
    client_monotonic_ms: agora.monotonicMs ?? performance.now(),
    ...evento.payload
  };
}
```

Mapear `reuniao` → `heartbeat`, legenda → `caption`, atividade → `speaker_activity`; parser fornece `caption_id`, `caption_revision`, `participant_id`, `display_name` e `text` quando disponíveis. A mensagem `hello` leva somente `connection_id`, `tab_id`, o código normalizado da sala como `meeting_hint` e relógios do cliente; o bridge compara esse hint com a sessão ativa e nunca persiste o código bruto.

- [ ] **Step 6: executar unitários e E2E de transporte**

Run:

```powershell
npm run test:unit
npm run test:e2e -- meet-transport.spec.js
```

Expected: todos PASS; o E2E chama o listener real com sender de `pairing.html` e prova que a porção cliente contém todos os campos sob sua autoridade, sem token e sem fingir o relógio de recebimento do servidor.

- [ ] **Step 7: commit**

```powershell
git add extension/meet tests/js tests/e2e/meet-transport.spec.js
git commit -m "fix: conecta pareamento e envelope da extensao Meet"
```

---

### Task 3: Vincular sessão, conexão e EventStore no bridge

**Files:**
- Modify: `sessao_reuniao.py`
- Modify: `meet_bridge.py`
- Modify: `eventos_meet_store.py`
- Modify: `tests/test_sessao_meet.py`
- Modify: `tests/test_meet_bridge.py`
- Modify: `tests/test_meet_bridge_seguranca.py`
- Modify: `tests/test_eventos_meet_store.py`

**Interfaces:**
- Consumes: mensagens `hello` e envelopes v1 da Task 2; sessão consentida definida pelo app.
- Produces: ACK durável por conexão lógica e `ArtifactRef` isolado por sessão.

- [ ] **Step 1: escrever RED para duas abas no mesmo socket**

```python
def test_duas_abas_no_mesmo_socket_mantem_estado_independente(sessao):
    registro = SessoesAtivas()
    registro.vincular("c1", "aba-1", sessao)
    registro.vincular("c2", "aba-2", sessao)
    assert registro.aceitar_evento("c1", envelope(sessao, "c1", "aba-1", 0))["seq"] == 0
    assert registro.aceitar_evento("c2", envelope(sessao, "c2", "aba-2", 0))["seq"] == 0
```

Adicionar rejeição de `tab_id` diferente, sessão antiga, `event_id` duplicado e sequência regressiva.

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_sessao_meet.py -v -x`

Expected: FAIL porque `vincular` ainda não existe.

- [ ] **Step 3: implementar vínculo com sessão criada pelo app**

```python
def vincular(self, connection_id: str, tab_id: str, sessao: SessaoReuniao) -> None:
    if not connection_id or not tab_id:
        raise EnvelopeRejeitado("conexão/aba vazia")
    self._por_conexao[connection_id] = {
        "sessao": sessao,
        "tab_id": tab_id,
        "last_seq": -1,
        "event_ids": set(),
    }
```

`aceitar_evento` também compara `evento["tab_id"]` ao `tab_id` registrado.

- [ ] **Step 4: tornar o handshake autoridade do servidor**

Adicionar ao `MeetBridge`:

```python
def definir_sessao_ativa(self, sessao: SessaoReuniao | None, store: EventStore | None) -> None: ...
def iniciar_conexao_logica(self, connection_id: str, tab_id: str, client_wall_ms: float) -> dict: ...
def registrar_envelope(self, connection_id: str, evento: Mapping[str, object]) -> int: ...
```

`iniciar_conexao_logica` só devolve `session_id`/`meeting_key` quando existe sessão consentida e o `meeting_hint` corresponde à chave opaca ativa; calcula RTT/offset sem aceitar relógio do cliente como tempo de áudio. `registrar_envelope` copia o payload, acrescenta `received_monotonic_ns=time.monotonic_ns()`, passa por `SessoesAtivas.aceitar_evento` e só depois por `EventStore.append`.

- [ ] **Step 5: serializar resposta e ACK no handler WebSocket**

O handler responde:

```json
{"tipo":"sessao","connection_id":"...","tab_id":"...","session_id":"...","meeting_key":"..."}
```

Após `append`, responde `{"tipo":"ack","connection_id":"...","seq":7}`. Envelope inválido recebe erro seguro e não cai na fila legada. Remover o fallback de conteúdo v1 para `normalizar_evento`; manter legado somente para instalações explicitamente compatíveis e cobertas por teste separado.

- [ ] **Step 6: proteger concorrência entre append e seal**

Adicionar `threading.RLock` ao `EventStore`; `append`, `descarregar`, `read_events`, `seal` e `revogar` compartilham o lock. `seal()` marca o store como fechado e chamadas posteriores de `append()` levantam `ColetaBloqueada`.

- [ ] **Step 7: rodar gates da tarefa**

Run:

```powershell
python -m pytest tests/test_sessao_meet.py tests/test_meet_bridge.py tests/test_meet_bridge_seguranca.py tests/test_eventos_meet_store.py -v
npm run test:unit
```

Expected: PASS, sem nomes/textos nos logs de erro.

- [ ] **Step 8: commit**

```powershell
git add sessao_reuniao.py meet_bridge.py eventos_meet_store.py tests
git commit -m "fix: isola sessoes e confirma eventos Meet duraveis"
```

---

### Task 4: Selar eventos uma vez e entregá-los ao job v2

**Files:**
- Modify: `app_ciclo_reuniao.py`
- Modify: `app_processamento.py`
- Modify: `job_v2.py`
- Create: `tests/test_fluxo_meet_ponta_a_ponta.py`
- Modify: `tests/test_nomes_meet_worker.py`
- Modify: `tests/test_fila_processamento.py`

**Interfaces:**
- Consumes: `EventStore.seal() -> tuple[ArtifactRef, ...]`.
- Produces: `_enfileirar_reuniao(..., eventos_refs=...)` e job v2 com refs imutáveis.

- [ ] **Step 1: escrever RED para o encerramento real do mixin**

```python
def test_parar_sela_e_entrega_refs_ao_job(app_com_store, wav):
    app_com_store.transcritor.stop.return_value = str(wav)
    app_com_store._parar_transcricao()
    job = app_com_store.fila.listar()[0]
    assert len(job.eventos_refs) == 1
    assert job.eventos_refs[0]["format"] == "meet-events-jsonl-enc"
```

O teste deve chamar `_parar_transcricao()` e o `_enfileirar_reuniao()` reais; não pode construir o job diretamente.

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py::test_parar_sela_e_entrega_refs_ao_job -v`

Expected: FAIL com `job.eventos_refs == ()`.

- [ ] **Step 3: passar refs como valor, nunca reler o atributo descartado**

Alterar a assinatura:

```python
def _enfileirar_reuniao(self, transcritor, caminho_saida, *, eventos_refs=()):
    refs_dict = [dataclasses.asdict(ref) if dataclasses.is_dataclass(ref) else dict(ref)
                 for ref in eventos_refs]
    return self.fila.enfileirar(..., eventos_refs=refs_dict, ...)
```

No ciclo:

```python
eventos_refs = ()
store = getattr(self, "_eventos_store", None)
if store is not None:
    eventos_refs = store.seal()
caminho = t.stop()
if caminho:
    self._enfileirar_reuniao(t, caminho, eventos_refs=eventos_refs)
self._eventos_store = None
```

O desligamento do bridge/store ocorre em `finally`, depois da captura local dos refs.

- [ ] **Step 4: provar restart e adulteração pelo fluxo real**

Estender o teste para reconstruir `FilaProcessamento`, processar o job e verificar: refs sobrevivem; hash alterado gera warning seguro; job v1 continua sem nomes inventados.

- [ ] **Step 5: rodar gates**

Run:

```powershell
python -m pytest tests/test_fluxo_meet_ponta_a_ponta.py tests/test_nomes_meet_worker.py tests/test_fila_processamento.py tests/test_processador_reuniao.py -v
```

Expected: PASS.

- [ ] **Step 6: commit**

```powershell
git add app_ciclo_reuniao.py app_processamento.py job_v2.py tests
git commit -m "fix: preserva referencias Meet ate o worker"
```

---

### Task 5: Produzir resultado estruturado canônico no worker

**Files:**
- Create: `resultado_pipeline.py`
- Modify: `resultado_reuniao.py`
- Modify: `resultado_edicao.py`
- Modify: `diarizacao_final.py`
- Modify: `transcricao_core.py`
- Modify: `retranscritor.py`
- Modify: `processador_reuniao.py`
- Create: `tests/test_resultado_pipeline.py`
- Modify: `tests/test_resultado_reuniao.py`
- Modify: `tests/test_processador_reuniao.py`

**Interfaces:**
- Consumes: segmentos com origem, resultado da diarização e eventos validados.
- Produces: `ResultadoProcessamento`, JSON em `resultados/{meeting_id}.json`, TXT derivado e `ResultManifest` apontando para ambos.

- [ ] **Step 1: escrever RED worker → resultado → manifesto**

```python
def test_worker_materializa_resultado_estruturado(fila_com_audio, modelo_fake):
    job_id = fila_com_audio.job_id
    processar_job(job_id, modelo_whisper=modelo_fake, fila=fila_com_audio.fila)
    job = fila_com_audio.fila.obter(job_id)
    manifesto = carregar_manifesto(Path(job.manifesto_resultado))
    assert manifesto.segments_ref.relative_path == f"resultados/{job_id}.json"
    dados = carregar_segmentos(fila_com_audio.raiz / manifesto.segments_ref.relative_path)
    assert dados["segmentos"][0]["segment_id"]
    assert dados["segmentos"][0]["audio_source"] in {"loopback", "microphone"}
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_resultado_pipeline.py::test_worker_materializa_resultado_estruturado -v`

Expected: FAIL porque o manifesto ainda referencia o TXT legado.

- [ ] **Step 3: devolver a diarização ao chamador**

`diarizacao_final.rodar_diarizacao(...) -> list[tuple[str, float, float, str]]` devolve `resultado`; `Transcritor._rodar_diarizacao` repassa esse retorno. `retranscrever` passa a chamar uma função interna `_retranscrever_resultado(...) -> ResultadoProcessamento`; o wrapper público continua retornando `str(resultado.txt_path)` para manter compatibilidade.

```python
def retranscrever_resultado(...)-> ResultadoProcessamento:
    ...

def retranscrever(...)-> str:
    return str(retranscrever_resultado(...).txt_path)
```

- [ ] **Step 4: alinhar segmentos sem perder origem**

`resultado_pipeline.criar_segmentos(...)` combina por `segment_id` e tempos, nunca apenas por índice silencioso. Divergência vira `StageState.PARTIAL` + `segment_alignment_failed`; o texto STT continua utilizável.

```python
def criar_segmentos(fundidos, diarizados, atribuicoes) -> tuple[SegmentoResultado, ...]:
    return tuple(SegmentoResultado(
        segment_id=s.segment_id,
        start_ms=s.start_ms,
        end_ms=s.end_ms,
        audio_source=s.source.value,
        text=s.text,
        speaker_cluster_id=rotulo_por_segmento.get(s.segment_id, "FALANTE_00"),
        assignment=atribuicoes.get(s.segment_id),
        overlap=s.overlap,
    ) for s in fundidos)
```

Adicionar `assignment: Mapping[str, object] | None = None` ao `SegmentoResultado` e preservar o campo no load/save.

- [ ] **Step 5: materializar arquivos antes de concluir o job**

O worker deve executar, nesta ordem:

1. transcrever/diarizar;
2. salvar `resultados/{job.id}.json` atomicamente;
3. derivar TXT por `exportar_txt` sem sobrescrever correção manual existente;
4. criar refs e `ResultManifest` final;
5. validar hashes/formato;
6. só então `fila.concluir(...)`.

Falha entre 2 e 5 mantém o job fora de `ready` e preserva fontes.

- [ ] **Step 6: rodar regressões**

Run:

```powershell
python -m pytest tests/test_resultado_pipeline.py tests/test_resultado_reuniao.py tests/test_processador_reuniao.py tests/test_retencao_resultado.py -v
```

Expected: PASS; retenção só libera áudio com manifesto estrutural válido.

- [ ] **Step 7: commit**

```powershell
git add resultado_pipeline.py resultado_reuniao.py resultado_edicao.py diarizacao_final.py transcricao_core.py retranscritor.py processador_reuniao.py tests
git commit -m "fix: materializa resultado estruturado no worker"
```

---

### Task 6: Preservar sugestões, proveniência e revisão na UI

**Files:**
- Modify: `identidade_reuniao.py`
- Modify: `correlacionador.py`
- Modify: `resultado_pipeline.py`
- Modify: `resultado_edicao.py`
- Modify: `assistente.py`
- Modify: `templates/assistente.html`
- Modify: `static/assistente.js`
- Modify: `tests/test_identidade_reuniao.py`
- Modify: `tests/test_resultado_reuniao.py`
- Modify: `tests/e2e/participants.spec.js`

**Interfaces:**
- Consumes: `Atribuicao` por segmento.
- Produces: campo persistido `assignment` com status, fonte, confiança e IDs de evidência; confirmação manual continua separada de biometria.

- [ ] **Step 1: escrever RED para sugestão persistida**

```python
def test_sugestao_nao_nomeia_automaticamente_mas_chega_ao_json():
    atribuicao = resolver_atribuicao(segmento, eventos, clock_uncertainty_ms=0,
                                    calibration_version="corpus-v1")
    assert atribuicao.status is AssignmentStatus.SUGGESTED
    dados = serializar_atribuicao(atribuicao)
    assert dados == {
        "status": "suggested",
        "participant_id": "p1",
        "display_name": "Ana",
        "source": "caption",
        "confidence": 1.0,
        "evidence_event_ids": ["e1"],
        "calibration_version": "corpus-v1",
    }
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_identidade_reuniao.py tests/test_resultado_pipeline.py -v -x`

Expected: FAIL porque `calibration_version` é descartada e a sugestão não é serializada.

- [ ] **Step 3: tornar calibração e atribuição dados reais**

Remover `del calibration_version`. Acrescentar o campo à dataclass `Atribuicao` e implementar `serializar_atribuicao()`. `MODO_AUTO_NOMES=False` mantém status `suggested`; somente `confirmed` ou correção manual altera o nome exportado.

- [ ] **Step 4: mostrar sugestão sem apresentá-la como certeza**

O drawer exibe:

```text
Identificação pendente
Sugestão: Ana · origem: legenda · confiança: 100%
[Confirmar Ana] [Escolher outro nome]
```

“Confirmar” usa a rota de correção com `expected_revision`; conflito 409 recarrega a revisão antes de nova tentativa. Undo restaura o mapeamento anterior e nunca cria perfil de voz.

- [ ] **Step 5: testar UI e exportação**

Playwright deve provar: sugestão visível; TXT antes da confirmação contém `Identificação pendente`; depois da confirmação contém o nome; undo volta ao estado pendente; HTML de nome/texto é escapado.

Run:

```powershell
python -m pytest tests/test_identidade_reuniao.py tests/test_correlacionador.py tests/test_resultado_reuniao.py -v
npm run test:e2e -- participants.spec.js
```

Expected: PASS.

- [ ] **Step 6: commit**

```powershell
git add identidade_reuniao.py correlacionador.py resultado_pipeline.py resultado_edicao.py assistente.py templates static tests
git commit -m "fix: preserva sugestoes e proveniencia dos participantes"
```

---

### Task 7: Corrigir o formato TKAS/1 e leitura verdadeiramente incremental

**Files:**
- Modify: `crypto_stream.py`
- Create: `stream_io.py`
- Modify: `audio_reader.py`
- Modify: `tests/test_crypto_stream.py`
- Modify: `tests/test_audio_streaming.py`

**Interfaces:**
- Consumes: TKAS/1 congelado em `interfaces.md`.
- Produces: leitor autenticado que rejeita qualquer byte depois de `TAG_FINAL` e nunca agrega o plaintext inteiro.

- [ ] **Step 1: escrever RED para sufixo e memória**

```python
def test_tkas_rejeita_sufixo_apos_chunk_final_cheio(tmp_path, chave):
    src = tmp_path / "audio.wav"
    src.write_bytes(b"A" * TAMANHO_CHUNK)
    enc = tmp_path / "audio.tks"
    encrypt_file(src, enc, chave)
    with enc.open("ab") as arquivo:
        arquivo.write(b"NAO-AUTENTICADO")
    with pytest.raises(ErroTKAS, match="após tag final"):
        list(iter_decrypt_file(enc, chave))
```

Adicionar teste que monkeypatcha o iterador para contar o pico e proíbe `list(iter_decrypt_file(...))` na validação de `encrypt_file`.

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_crypto_stream.py -v -x`

Expected: FAIL porque o sufixo é aceito e a validação usa `list(...)`.

- [ ] **Step 3: verificar EOF depois da tag final**

Depois de produzir o último plaintext, ler um byte adicional do arquivo cifrado; se existir, levantar `ErroTKAS("dados após tag final")`. Não fazer `break` antes dessa verificação.

- [ ] **Step 4: validar sem materializar plaintext**

```python
for _chunk in iter_decrypt_file(temporario_path, master_key):
    pass
```

Não acumular chunks, bytes ou hashes do plaintext se o contrato só exige autenticação.

- [ ] **Step 5: adaptar iterator para WAV não seekable**

`stream_io.IteratorReader(io.RawIOBase)` mantém no máximo o chunk atual e implementa `readable()` e `readinto()`. `audio_reader` abre `.tks` com `wave.open(io.BufferedReader(IteratorReader(...)), "rb")`; nenhum tempfile plaintext é criado.

- [ ] **Step 6: rodar gates**

Run:

```powershell
python -m pytest tests/test_crypto_stream.py tests/test_audio_streaming.py tests/test_audio_utils.py -v
```

Expected: PASS para truncamento, alteração, reordenação, duplicação, sufixo e áudio de duas horas em blocos limitados.

- [ ] **Step 7: commit**

```powershell
git add crypto_stream.py stream_io.py audio_reader.py tests
git commit -m "fix: autentica fim e limita memoria do formato TKAS"
```

---

### Task 8: Integrar a política protegida a áudio e resultados reais

**Files:**
- Create: `resultado_storage.py`
- Modify: `politica_privacidade.py`
- Modify: `crypto_storage.py`
- Modify: `diarizacao_final.py`
- Modify: `retranscritor.py`
- Modify: `resultado_pipeline.py`
- Modify: `assistente.py`
- Create: `tests/test_resultado_storage.py`
- Modify: `tests/test_politica_privacidade.py`
- Modify: `tests/test_crypto_storage.py`
- Modify: `tests/test_transcricao_crypto.py`

**Interfaces:**
- Consumes: `ProtectionMode`, TKAS/1 e chave mestra DPAPI existente.
- Produces: estado efetivo por artefato, áudio `.tks` para novas gravações protegidas e resultado estruturado cifrado em repouso.

- [ ] **Step 1: escrever RED de instalação nova protegida**

```python
def test_pipeline_protegido_nao_deixa_audio_ou_resultado_plaintext(tmp_path, chave_dpapi):
    resultado = executar_pipeline_sintetico(tmp_path, config_existente=None)
    assert resultado.audio_ref.relative_path.endswith(".tks")
    assert resultado.segments_ref.relative_path.endswith(".json.enc")
    assert not list(tmp_path.rglob("*.wav"))
    assert not list((tmp_path / "resultados").glob("*.json"))
```

Adicionar casos: instalação existente sem campo → `compatible`; DPAPI indisponível → `PROTECTION_PENDING` e original preservado; `.wav.enc` legado continua legível.

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_politica_privacidade.py tests/test_resultado_storage.py -v -x`

Expected: FAIL porque produção ainda usa `criptografar_wav` e JSON plaintext.

- [ ] **Step 3: criar adaptadores tipados de proteção**

Em `crypto_storage.py`:

```python
def cifrar_audio_tkas(source: Path, destination: Path) -> ArtifactRef:
    return encrypt_file(source, destination, _exigir_chave())

def iterar_audio_tkas(path: Path) -> Iterator[bytes]:
    return iter_decrypt_file(path, _exigir_chave())
```

Não expor a chave em log, JSON ou retorno. O caller remove o WAV somente depois de validar ref, hash e leitura autenticada.

- [ ] **Step 4: aplicar política no fechamento do áudio**

`preservar_audios` recebe `ProtectionMode`, não apenas booleano. Em `PROTECTED`, escreve `.tks`; em `COMPATIBLE`, preserva o comportamento legado explicitamente documentado. Falha retorna `PROTECTION_PENDING`, mantém o original em área restrita e gera sinal visível.

- [ ] **Step 5: armazenar resultado por abstração única**

`ResultadoStorage.save` serializa JSON determinístico, cifra no modo protegido e devolve `ArtifactRef`. `load` valida confinamento/hash e decifra em memória. Correção e undo fazem read-modify-write com `expected_revision`, arquivo temporário no mesmo diretório e replace atômico.

`assistente.py` deixa de construir `resultados/{id}.json` diretamente e resolve o `segments_ref` do manifesto/índice por `ResultadoStorage`.

- [ ] **Step 6: provar compatibilidade e recuperação**

Run:

```powershell
python -m pytest tests/test_resultado_storage.py tests/test_politica_privacidade.py tests/test_crypto_stream.py tests/test_crypto_storage.py tests/test_transcricao_crypto.py tests/test_recuperacao_sessao.py -v
```

Expected: PASS; nenhum teste escreve dados reais.

- [ ] **Step 7: commit**

```powershell
git add resultado_storage.py politica_privacidade.py crypto_storage.py diarizacao_final.py retranscritor.py resultado_pipeline.py assistente.py tests
git commit -m "fix: aplica modo protegido aos artefatos de producao"
```

---

### Task 9: Fechar privacidade de logs e mutações HTTP locais

**Files:**
- Modify: `status_seguro.py`
- Modify: `app_ciclo_reuniao.py`
- Modify: `assistente_validacao.py`
- Modify: `assistente.py`
- Modify: `tests/test_status_seguro.py`
- Modify: `tests/test_privacidade_eventos.py`
- Create: `tests/test_assistente_mutacoes.py`

**Interfaces:**
- Consumes: eventos operacionais tipados e token de sessão.
- Produces: logs por código/campos permitidos e guard comum de Host/Origin/content-type para rotas mutáveis.

- [ ] **Step 1: escrever RED para título-canário e mutação cross-origin**

```python
def test_status_reuniao_nao_registra_titulo_canario(caplog):
    status("Reunião detectada (janela) — TITULO-CANARIO. Iniciando gravação...")
    assert "TITULO-CANARIO" not in caplog.text

def test_correcao_rejeita_origin_de_outra_porta(client_autenticado):
    resposta = client_autenticado.post(
        "/api/reunioes/m1/correcao",
        headers={"Origin": "http://localhost:9999"},
        json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Ana"},
    )
    assert resposta.status_code == 403
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_status_seguro.py tests/test_assistente_mutacoes.py -v -x`

Expected: FAIL; o título aparece e a mutação retorna 200 com cookie válido.

- [ ] **Step 3: substituir string livre por evento operacional**

Criar API:

```python
def registrar_evento(codigo: str, **campos_permitidos: object) -> str:
    permitidos = {"fontes", "estado", "contagem", "duracao_ms", "erro_codigo"}
    seguro = {k: v for k, v in campos_permitidos.items() if k in permitidos}
    return json.dumps({"evento": codigo, **seguro}, ensure_ascii=False, sort_keys=True)
```

O tooltip pode mostrar título sanitizado em memória; o logger recebe somente `meeting_detected` + fontes. Remover a regra que libera a mensagem inteira apenas pelo prefixo “Reunião”.

- [ ] **Step 4: aplicar guard comum às mutações**

```python
def validar_mutacao_local(request) -> tuple[dict | None, tuple | None]:
    if not hosts_locais_aceitos(request.host):
        return None, (jsonify({"erro": "Host não permitido"}), 403)
    if not origem_exata_assistente(request.headers.get("Origin"), request.host_url):
        return None, (jsonify({"erro": "Origem não permitida"}), 403)
    if request.mimetype != "application/json":
        return None, (jsonify({"erro": "Content-Type inválido"}), 415)
    return request.get_json(silent=True), None
```

Aplicar a chat, correção, undo e demais POST/PUT/DELETE. Navegação/curl sem `Origin` só é aceita quando usa o header secreto, não apenas cookie.

- [ ] **Step 5: rodar gates de privacidade/API**

Run:

```powershell
python -m pytest tests/test_status_seguro.py tests/test_privacidade_eventos.py tests/test_assistente_mutacoes.py tests/test_assistente_seguranca.py tests/test_token_sessao.py tests/test_assistente_api.py -v
```

Expected: PASS; canários não aparecem em log/job/diagnóstico.

- [ ] **Step 6: commit**

```powershell
git add status_seguro.py app_ciclo_reuniao.py assistente_validacao.py assistente.py tests
git commit -m "fix: remove titulos dos logs e protege mutacoes locais"
```

---

### Task 10: Tornar dependências e CI realmente reproduzíveis

**Files:**
- Create: `requirements/base.in`
- Create: `requirements/cpu.in`
- Create: `requirements/cuda.in`
- Create: `requirements/dev.in`
- Create: `requirements/requirements-cpu.lock`
- Create: `requirements/requirements-cuda.lock`
- Create: `requirements/requirements-dev.lock`
- Modify: `requirements.txt`
- Modify: `.github/workflows/tests.yml`
- Create: `scripts/gerar_sbom.py`
- Modify: `docs/DEPENDENCIAS.md`
- Replace: `docs/sbom.json`
- Modify: `tests/test_dependencias.py`
- Modify: `tests/test_instalador_helper.py`

**Interfaces:**
- Consumes: Python 3.12/Windows, rotas CPU e CUDA 12.8.
- Produces: locks completos com hashes, ambiente de teste com pytest e SBOM CycloneDX transitivo.

- [ ] **Step 1: escrever RED para ferramentas de teste e hashes**

```python
def test_locks_de_producao_e_dev_possuem_hashes():
    cpu = (ROOT / "requirements/requirements-cpu.lock").read_text(encoding="utf-8")
    dev = (ROOT / "requirements/requirements-dev.lock").read_text(encoding="utf-8")
    assert "pytest==" in dev
    assert "--hash=sha256:" in cpu
    assert "--hash=sha256:" in dev
    assert "torch==2.11.0" in cpu

def test_workflow_instala_lock_de_desenvolvimento():
    workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "requirements/requirements-cpu.lock" in workflow
    assert "requirements/requirements-dev.lock" in workflow
    assert "python -m pytest" in workflow
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_dependencias.py tests/test_instalador_helper.py -v -x`

Expected: FAIL porque não há lock com hashes nem pytest instalado no CI.

- [ ] **Step 3: definir entradas e gerar locks**

`base.in` contém dependências diretas comuns de produção e não contém torch. `cpu.in` inclui `-r base.in`, `torch==2.11.0` e `torchaudio==2.11.0`; `cuda.in` inclui as variantes `2.11.0+cu128`. `dev.in` contém apenas `pytest`, `pytest-timeout`, `pip-audit`, `pip-tools` e `cyclonedx-bom`. Gerar com `pip-compile --generate-hashes --resolver=backtracking`, PyPI como índice principal e PyTorch apenas como índice adicional específico da rota.

Comandos registrados em `docs/DEPENDENCIAS.md`:

```powershell
python -m piptools compile requirements/cpu.in --generate-hashes --output-file requirements/requirements-cpu.lock
python -m piptools compile requirements/cuda.in --generate-hashes --extra-index-url https://download.pytorch.org/whl/cu128 --output-file requirements/requirements-cuda.lock
python -m piptools compile requirements/dev.in --generate-hashes --output-file requirements/requirements-dev.lock
```

- [ ] **Step 4: corrigir workflow**

O CI executa em ordem: criar venv limpo; instalar lock CPU e lock dev com `--require-hashes`; `pip check`; `pip-audit`; Python; npm ci; unit; Playwright; diff-check; upload de XML/log seguro em falha. Não usa o Python global do runner depois de criar a venv. O instalador consome somente o lock de produção da rota e não instala pytest/auditoria.

- [ ] **Step 5: gerar SBOM completo**

`scripts/gerar_sbom.py` chama CycloneDX dentro da venv resolvida, normaliza timestamp volátil para comparação e grava componentes transitivos, versões, licenças quando declaradas e hashes disponíveis. Licenças dos modelos ficam em seção separada de `docs/DEPENDENCIAS.md`.

- [ ] **Step 6: provar CPU local limpo e CI remoto**

Run em venv temporária:

```powershell
python -m venv .tmp-audit-cpu
.\.tmp-audit-cpu\Scripts\python.exe -m pip install --require-hashes -r requirements\requirements-cpu.lock
.\.tmp-audit-cpu\Scripts\python.exe -m pip install --require-hashes -r requirements\requirements-dev.lock
.\.tmp-audit-cpu\Scripts\python.exe -m pip check
.\.tmp-audit-cpu\Scripts\python.exe -m pytest tests\ -q --tb=short
```

Expected: três comandos exit 0. Remover somente `.tmp-audit-cpu` após resolver e validar o path absoluto dentro do repo. Depois do push autorizado, o run GitHub Actions do mesmo SHA deve ficar verde.

- [ ] **Step 7: commit**

```powershell
git add requirements requirements.txt .github/workflows/tests.yml scripts/gerar_sbom.py docs/DEPENDENCIAS.md docs/sbom.json tests
git commit -m "fix: reproduz dependencias e instala testes no CI"
```

---

### Task 11: Implementar o aceite isolado de instalação e desinstalação

**Files:**
- Modify: `instalar.bat`
- Modify: `desinstalar.bat`
- Modify: `scripts/instalar_helper.py`
- Create: `scripts/gate_instalacao.py`
- Create: `tests/test_gate_instalacao.py`
- Modify: `tests/test_instalacao_caminhos.py`

**Interfaces:**
- Consumes: lock CPU/CUDA da Task 10.
- Produces: gate repetível em raiz temporária, sem tocar atalhos/processos/dados reais.

- [ ] **Step 1: escrever RED do modo não interativo isolado**

```python
def test_gate_recusa_raiz_real_do_checkout(tmp_path):
    with pytest.raises(ValueError, match="raiz temporária"):
        validar_raiz_gate(REPO)

def test_gate_preserva_dados_sinteticos_ao_desinstalar(tmp_path):
    resultado = executar_gate(tmp_path / "Pasta Com Acento çã", rota="cpu", fake_shortcuts=True)
    assert resultado.instancias_primeiro_start == 1
    assert resultado.instancias_segundo_start == 1
    assert resultado.dados_preservados is True
    assert resultado.venv_removida is True
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_gate_instalacao.py -v -x`

Expected: FAIL porque o gate ainda não existe.

- [ ] **Step 3: adicionar flags seguras**

`instalar.bat --non-interactive --route cpu --skip-warmup --shortcut-dir <temp>` e `desinstalar.bat --non-interactive --preserve-data --shortcut-dir <temp>` não usam `pause`/`set /p`. Em modo normal, a UX atual permanece.

Todos os alvos destrutivos são resolvidos por `scripts/instalar_helper.py`; o batch não constrói globs. O helper rejeita qualquer `.venv` fora da raiz temporária autorizada no gate.

- [ ] **Step 4: implementar o gate subprocesso**

`gate_instalacao.py` copia apenas arquivos versionados para um `TemporaryDirectory`, cria dados sintéticos, instala pelo lock, inicia duas vezes com PID/porta controlados, confirma uma instância, encerra somente os PIDs filhos que criou, desinstala e verifica preservação/remoção exata.

Nenhum atalho real é criado; um diretório Desktop/Startup falso é injetado por argumento.

- [ ] **Step 5: rodar teste e gate CPU**

Run:

```powershell
python -m pytest tests/test_gate_instalacao.py tests/test_instalacao_caminhos.py tests/test_instalador_helper.py tests/test_atalho_desktop.py tests/test_assistente_startup.py tests/test_versao.py -v
python scripts/gate_instalacao.py --route cpu
```

Expected: PASS; relatório contém paths temporários, PIDs filhos, hashes dos dados sintéticos e zero alvo real tocado.

- [ ] **Step 6: commit**

```powershell
git add instalar.bat desinstalar.bat scripts tests
git commit -m "fix: valida instalacao e desinstalacao em ambiente isolado"
```

---

### Task 12: Fechar automação, evidências, gates humanos e release

**Files:**
- Modify: `docs/sdd/v1.8/evidencias/T-13.*.md`
- Modify: `docs/sdd/v1.8/evidencias/REMEDIACAO-2026-09-22.md`
- Modify: `docs/sdd/v1.8/plan.md`
- Modify: `docs/sdd/v1.8/tasks.md`
- Modify only after authorization and all gates: `config.py`
- Generated from version source: `extension/meet/manifest.json`

**Interfaces:**
- Consumes: todos os commits e gates das Tasks 1–11.
- Produces: evidência verificável, estado SDD honesto e release local pronta para uso.

- [ ] **Step 1: executar gate automatizado completo em ambiente ocioso**

Run, sem paralelizar comandos pesados:

```powershell
python -m pytest tests/ -q --tb=short
python scripts/verificar_fase.py --fase all
python -m compileall -q .
npm ci
npm run test:unit
npm run test:e2e
python -m pip check
git diff --check
```

Expected: todos exit 0. Flake deve ser diagnosticado e corrigido; rerun isolado não transforma uma suíte vermelha em gate verde.

- [ ] **Step 2: verificar CI e artefatos do mesmo SHA**

Após autorização para push, confirmar no GitHub: job Windows CPU verde; pytest realmente coletado; JS e Playwright executados; pip-audit/SBOM gerados; nenhum segredo nos artifacts.

- [ ] **Step 3: solicitar e executar gates físicos de captura**

Somente após confirmar `reunião=False`, `gravando=False` e ausência de escrita ativa:

```powershell
python scripts/gate_reuniao_real.py --segundos 25
python scripts/gate_reuniao_real.py --segundos 600
```

Expected: frames avançam, WAV válido, Whisper real produz fala lexical legível, zero falha COM/lock. Registrar somente métricas, nunca transcrição.

- [ ] **Step 4: solicitar e executar demo D2 em Chrome e Edge**

Roteiro controlado, sem `Stop-Process` genérico:

1. usar perfis temporários separados;
2. instalar a extensão unpacked nesses perfis;
3. parear com convite descartável;
4. provar reconexão após restart do service worker;
5. validar rejeição de origem/token inválidos;
6. encerrar somente os processos iniciados pelo gate, por PID conhecido.

Expected: pareamento, sessão e ACK visíveis; nenhum token em arquivo/content script/log.

- [ ] **Step 5: solicitar e executar gate G3 com três pessoas consentidas**

Executar Chrome e Edge, três pessoas, duas abas/reuniões, falas alternadas, mic exclusivo, legenda desligada/ligada, troca de aba, reconexão, homônimos, sobreposição, correção e undo. O corpus consentido fica fora do repositório; evidência registra apenas agregados.

Critérios:

- zero vazamento entre reuniões;
- `VOCÊ` preservado quando sustentado por perfil/mic;
- sugestões ficam revisáveis até o corpus liberar modo automático;
- precisão seletiva, cobertura e abstinência publicadas;
- nenhum nome automático recorrente incorreto;
- resultado sobrevive a restart do worker e abre na UI.

- [ ] **Step 6: executar gate CUDA e instalação real de teste**

Em hardware compatível e pasta de teste com espaço/acentos: instalar pelo lock CUDA, `pip check`, suíte direcionada de STT/diarização, duas inicializações/uma instância e desinstalação preservando dados sintéticos. Não alterar a instalação em uso.

- [ ] **Step 7: corrigir todas as evidências**

Cada arquivo deve conter:

```text
- Estado: DONE | BLOCKED
- Base: <SHA pai real>
- Resultado: <SHA real do commit>
- Comandos: <comando exato + exit code + contagem>
- Gate real: <data/ambiente/resultado ou bloqueio explícito>
- Resíduos: <nenhum ou lista objetiva>
```

Remover todas as ocorrências de “commit de fechamento deste arquivo”. Não reescrever incidentes históricos; acrescentar a remediação e o estado atual.

- [ ] **Step 8: autorizar e fazer bump uma única vez**

Somente se Tasks 1–11, CI, captura 25/600, D2, G2 e G3 estiverem verdes. Alterar apenas `config.VERSAO` para a versão aprovada e rodar o sincronizador da extensão; não hardcodar versão em outro arquivo.

- [ ] **Step 9: gate pós-bump e commit de release**

Run:

```powershell
python -m pytest tests/test_versao.py tests/test_sdd_rastreabilidade.py -v
python -m pytest tests/ -q --tb=short
npm run test:unit
npm run test:e2e
git diff --check
```

Commit, apenas com autorização:

```powershell
git add config.py extension/meet/manifest.json docs/sdd/v1.8
git commit -m "release: publica Transkriptor com gates v1.8 aprovados"
```

- [ ] **Step 10: verificar estado final**

Registrar e comparar:

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/master
git rev-list --left-right --count HEAD...origin/master
```

Pronto para uso significa: worktree limpa; HEAD/origin coerentes depois do push autorizado; CI do SHA verde; app reiniciado somente após confirmação de ociosidade; exatamente uma instância; logs de prontidão sem conteúdo sensível.

---

## Gates de parada imediata

Interromper a execução e manter a tarefa aberta se ocorrer qualquer um destes casos:

- perda, movimento ou renomeação de arquivo real não listado no escopo do gate;
- processo do usuário encerrado ou alterado;
- áudio sem frames, falha COM, callback sob lock ou worker sem progresso;
- evento de uma reunião aceito em outra sessão/aba;
- nome automático incorreto apresentado como confirmado;
- plaintext residual no modo protegido;
- hash/ref/manifesto inválido com job marcado `ready`;
- CI que não coleta pytest ou ignora falha;
- rerun isolado usado para esconder gate completo vermelho;
- evidência sem SHA/comando/exit code;
- gate humano indisponível tratado como PASS.

## Matriz final de rastreabilidade

| Achado da auditoria | Tarefa corretiva | Prova final |
|---|---|---|
| Pareamento recusado | 2 | listener real + E2E |
| Envelope v1 ausente | 2–3 | unit JS + bridge |
| Sessões/abas não isoladas | 3 | duas conexões lógicas e duas reuniões |
| Refs descartados no stop | 4 | mixin real → job v2 |
| JSON canônico não produzido | 5 | worker → manifesto/API |
| Sugestão/proveniência perdida | 6 | JSON/UI/export/undo |
| TKAS aceita sufixo | 7 | teste exato de 1 MiB + sufixo |
| Validação TKAS usa memória total | 7 | teste de pico/chunks |
| Política protegida não integrada | 8 | pipeline sem plaintext |
| Título em log | 9 | canário ausente |
| Mutação local sem origem uniforme | 9 | 403 cross-origin |
| CI sem pytest | 10 | GitHub Actions verde |
| Locks/SBOM incompletos | 10 | hashes + árvore CycloneDX + audit |
| Aceite G2 ausente | 11–12 | gate de instalação e repetição controlada |
| Evidências sem SHA/base errada | 1 e 12 | validador documental + SHAs reais |
| D2/G3/release pendentes | 12 | gates humanos + bump único |

## Definition of Done

O Transkriptor só está “pronto para uso” quando todos os itens abaixo forem verdadeiros simultaneamente:

- fluxo extensão → sessão → store cifrado → job → worker → JSON → API/UI provado pelo teste de integração;
- resultado parcial nunca aparece como completo e nenhuma fonte é removida prematuramente;
- modo protegido efetivo em instalação nova, compatibilidade explícita em instalação existente e zero fallback silencioso;
- logs, diagnósticos, jobs e evidências sem fala/nome/título/token/path pessoal;
- suíte Python, verificador de fase, unit JS, E2E, pip check, audit, compile e diff verdes;
- GitHub Actions verde no SHA candidato;
- instalação CPU e CUDA suportada validada em ambiente limpo;
- gates físicos 25 s/600 s, D2 Chrome/Edge e G3 três pessoas aprovados com autorização;
- documentação e evidências apontam para os SHAs reais;
- bump, commit, push e reinício final feitos somente após autorização, com uma instância saudável.
