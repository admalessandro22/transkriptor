# Transkriptor v1.5 Reuniões e Pós-processamento Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gravar somente reuniões consentidas, sem IA ou notificações por trecho durante a chamada, e produzir transcrição `.txt` depois do encerramento.

**Architecture:** O detector exige sinal forte e uma máquina de estados pede consentimento antes da captura. `Transcritor` ganha modo `processar_ao_vivo=False`, que só drena áudio para WAV; ao finalizar, um job atômico é processado por subprocesso de baixa prioridade, gerando `.txt` e cópia `.tkpt` opcional.

**Tech Stack:** Python 3.12, pystray/Win32, soundcard/numpy, faster-whisper, SpeechBrain, AES-GCM/DPAPI, pytest.

## Global Constraints

- `config.VERSAO` é a única fonte de versão.
- Flask continua limitado a `127.0.0.1`.
- Conteúdo falado nunca entra em log, job JSON ou mensagem de erro.
- Paths de job/resultado precisam permanecer sob `PASTA_TRANSCRICOES`.
- Uma tarefa T-10 = um commit em português, no imperativo.
- Toda tarefa começa com teste RED e termina com o teste direcionado verde.
- Nenhuma tarefa seguinte começa se o teste final da atual falhar.
- A versão antiga permanece desligada até o gate de startup da v1.5.

## File Structure

- `deteccao_reuniao.py`: política pura de sinais fortes/fracos e debounce.
- `consentimento_gravacao.py`: decisão Win32 silenciosa e testável.
- `transcricao_core.py`: captura e transcrição; modo posterior não carrega IA.
- `fila_processamento.py`: jobs atômicos e retomáveis, sem conteúdo sensível.
- `processador_reuniao.py`: CLI do subprocesso posterior.
- `retranscritor.py`: transcrição offline com nome de saída estável e leitura em blocos.
- `notificador.py`: log seguro e, quando explicitamente ligado, reutilização do ícone.
- `transkriptor.pyw`: orquestra detector, consentimento, captura e job.
- `app_bandeja_menu.py`: estado e ações compatíveis com reunião estrita.
- `crypto_storage.py`: chave DPAPI dedicada e cópia criptografada opcional.
- `scripts/recuperar_intervalos_audio.py`: extrator genérico, não destrutivo.

---

### Task 1: T-10.A1 — Preservar configuração e chave DPAPI

**Files:**
- Modify: `config.py`
- Modify: `config_user.py`
- Modify: `crypto_storage.py`
- Modify: `transkriptor.pyw`
- Test: `tests/test_config_user_modulo.py`
- Test: `tests/test_crypto_storage.py`

**Interfaces:**
- Produces: `config_user.atualizar(**kv) -> dict` como única escrita parcial.
- Produces: `crypto_storage.caminho_chave_dpapi() -> Path` e carregamento dedicado.

- [ ] **Step 1: escrever testes RED**

```python
def test_atualizacao_de_default_nao_apaga_chave(tmp_path, monkeypatch):
    # salvar chave + token; aplicar default; ambos permanecem

def test_chave_dpapi_dedicada_sobrevive_config_vazia(tmp_path, monkeypatch):
    # gerar, zerar config e recarregar bytes cifrados com a mesma chave
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_config_user_modulo.py tests/test_crypto_storage.py -v --tb=short -x`

Expected: falha porque a chave só está no snapshot JSON e o bootstrap usa `salvar`.

- [ ] **Step 3: implementar merge e chave dedicada**

```python
def caminho_chave_dpapi() -> Path:
    return Path(_config.ARQUIVO_CHAVE_DPAPI)

def _salvar_blob_dpapi(blob: bytes) -> None:
    # tmp no mesmo diretório, flush, fsync e os.replace

def garantir_chave_mestra() -> bool:
    # dedicado -> legado config -> gerar; migrar sem logar valor
```

Substituir defaults do bootstrap por `config_user.atualizar(**defaults)`, nunca salvar
o `cfg` antigo inteiro.

- [ ] **Step 4: rodar teste final da tarefa**

Run: `python -m pytest tests/test_config_user_modulo.py tests/test_crypto_storage.py -v --tb=short`

Expected: todos PASS; nenhum arquivo real muda.

- [ ] **Step 5: commit**

```powershell
git add config.py config_user.py crypto_storage.py transkriptor.pyw tests/test_config_user_modulo.py tests/test_crypto_storage.py
git commit -m "fix: preserva configuracao e chave de criptografia"
```

### Task 2: T-10.A2 — Provar isolamento de estado nos testes

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_isolamento_estado_local.py`

**Interfaces:**
- Produces: fixture autouse que falha se config/chave/transcrições reais mudarem.

- [ ] **Step 1: escrever teste RED que executa subprocesso de teste controlado**

```python
def test_suite_controlada_nao_altera_hashes_do_estado_real(snapshot_estado_real):
    antes = snapshot_estado_real()
    subprocess.run([sys.executable, "-m", "pytest", "tests/test_config_user_modulo.py", "-q"], check=True)
    assert snapshot_estado_real() == antes
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_isolamento_estado_local.py -v -x`

- [ ] **Step 3: implementar fixture com paths temporários e guard de hashes**

O guard inclui `config_user.json`, chave dedicada, `transcricoes/` e atalhos; só
compara metadados/hashes, nunca lê conteúdo de transcrição.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_isolamento_estado_local.py tests/test_config_user_modulo.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add tests/conftest.py tests/test_isolamento_estado_local.py
git commit -m "test: isola estado local da suite"
```

### Task 3: T-10.B1 — Proibir início por microfone

**Files:**
- Modify: `deteccao_reuniao.py`
- Modify: `config.py`
- Modify: `tests/test_deteccao_multi_fonte.py`

**Interfaces:**
- Produces: `DetectorReuniao._processar(algum, forte, fontes_ativas)` inicia apenas com `forte=True`.

- [ ] **Step 1: inverter o teste legado e adicionar persistência fraca longa**

```python
def test_sinal_fraco_nunca_inicia():
    det, _forte, fraca = _detector()
    fraca.ativo = True
    assert all(det.verificar() is None for _ in range(120))
    assert det.reuniao_ativa is False
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_deteccao_multi_fonte.py::test_sinal_fraco_nunca_inicia -v`

- [ ] **Step 3: remover `confirmou_fraca` da transição de início**

Manter o sinal no diagnóstico, mas não no gatilho.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_deteccao_multi_fonte.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add config.py deteccao_reuniao.py tests/test_deteccao_multi_fonte.py
git commit -m "fix: impede microfone de iniciar reuniao"
```

### Task 4: T-10.B2 — Encerrar sem fonte forte

**Files:**
- Modify: `deteccao_reuniao.py`
- Modify: `config.py`
- Modify: `monitor_reuniao.py`
- Modify: `tests/test_deteccao_multi_fonte.py`
- Modify: `tests/test_integracao_monitor_meet.py`

**Interfaces:**
- Produces: `CONFIRMACAO_FIM_SEM_SINAL_FORTE = 6` ciclos.

- [ ] **Step 1: escrever RED**

```python
def test_microfone_nao_mantem_reuniao_sem_fonte_forte():
    # inicia por título; deixa somente microfone; encerra no sexto ciclo

def test_extensao_mantem_reuniao_com_aba_em_segundo_plano():
    # extensão forte ativa impede fim
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_deteccao_multi_fonte.py tests/test_integracao_monitor_meet.py -v -x`

- [ ] **Step 3: contar ciclos sem forte, não ciclos sem qualquer fonte**

Atualizar comentários e heartbeat para distinguir `fortes` e `auxiliares`.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_deteccao_multi_fonte.py tests/test_integracao_monitor_meet.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add config.py deteccao_reuniao.py monitor_reuniao.py tests/test_deteccao_multi_fonte.py tests/test_integracao_monitor_meet.py
git commit -m "fix: encerra captura sem sinal forte de reuniao"
```

### Task 5: T-10.C1 — Pedir consentimento antes da captura

**Files:**
- Create: `consentimento_gravacao.py`
- Modify: `transkriptor.pyw`
- Modify: `app_bandeja_menu.py`
- Modify: `transkriptor_acoes.py`
- Modify: `tests/test_aviso_gravacao.py`

**Interfaces:**
- Produces: `pedir_consentimento(timeout_seg: int) -> bool`.
- Consumes: `DetectorReuniao.reuniao_ativa` antes de iniciar.

- [ ] **Step 1: escrever RED para Sim, Não, timeout, erro e pergunta única**

```python
@pytest.mark.parametrize("retorno, esperado", [(IDYES, True), (IDNO, False), (MB_TIMEDOUT, False), (0, False)])
def test_so_sim_explicito_autoriza(retorno, esperado):
    assert resposta_autoriza_gravacao(retorno) is esperado

def test_captura_nao_comeca_antes_da_resposta(modulo_transkriptor, monkeypatch):
    app = _app(modulo_transkriptor, monkeypatch)
    iniciou = []
    app._pedir_consentimento = lambda: False
    app._iniciar_transcricao = lambda manual=False: iniciou.append(manual)
    app._pedir_e_iniciar()
    assert iniciou == []
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_aviso_gravacao.py -v -x`

- [ ] **Step 3: implementar diálogo sem `ICONQUESTION` e transição atômica**

`_processar_mudanca_meet("iniciou")` despacha `_pedir_e_iniciar`; a função só
chama `_iniciar_transcricao` depois de `True`. Timeout define recusa até `encerrou`.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_aviso_gravacao.py tests/test_integracao_monitor_meet.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add consentimento_gravacao.py transkriptor.pyw app_bandeja_menu.py transkriptor_acoes.py tests/test_aviso_gravacao.py tests/test_integracao_monitor_meet.py
git commit -m "fix: exige consentimento antes de gravar"
```

### Task 6: T-10.C2 — Eliminar toasts ao vivo e ícones-fantasma

**Files:**
- Modify: `notificador.py`
- Modify: `transkriptor.pyw`
- Modify: `app_bandeja_menu.py`
- Modify: `tests/test_notificador.py`
- Modify: `tests/test_bandeja_lifecycle.py`

**Interfaces:**
- Produces: `configurar_icone(icone)` e `notificar(titulo, mensagem, visivel=False)` sem `plyer`.

- [ ] **Step 1: escrever RED**

```python
class IconeFake:
    def __init__(self):
        self.chamadas = []

    def notify(self, mensagem, titulo):
        self.chamadas.append((titulo, mensagem))

def test_notificacao_padrao_nao_abre_balao():
    icone = IconeFake()
    configurar_icone(icone)
    notificar("Transkriptor", "trecho sensível")
    assert icone.chamadas == []

def test_notificacao_visivel_reutiliza_icone_existente():
    icone = IconeFake()
    configurar_icone(icone)
    notificar("Transkriptor", "Processamento concluído", visivel=True)
    assert icone.chamadas == [("Transkriptor", "Processamento concluído")]

def test_modulo_nao_referencia_plyer():
    assert "plyer" not in Path(notificador.__file__).read_text(encoding="utf-8")
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_notificador.py tests/test_bandeja_lifecycle.py -v -x`

- [ ] **Step 3: remover `_status` -> toast e chamadas duplicadas de startup**

`notificar` registra somente mensagem sanitizada por padrão. Somente chamada com
`visivel=True` usa `Icon.notify`; nenhuma chamada por trecho passa essa flag.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_notificador.py tests/test_bandeja_lifecycle.py tests/test_status_seguro.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add notificador.py transkriptor.pyw app_bandeja_menu.py tests/test_notificador.py tests/test_bandeja_lifecycle.py
git commit -m "fix: elimina notificacoes por trecho e icones extras"
```

### Task 7: T-10.D1 — Capturar sem carregar Whisper

**Files:**
- Modify: `transcricao_core.py`
- Create: `tests/test_gravacao_pos_reuniao.py`

**Interfaces:**
- Produces: `Transcritor(processar_ao_vivo: bool = True)`.
- Produces: `Transcritor.audios_preservados: list[str]` após `stop()`.

- [ ] **Step 1: escrever RED**

```python
def test_modo_posterior_nao_carrega_modelo(monkeypatch, tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), processar_ao_vivo=False, capturar_mic=False)
    monkeypatch.setattr(t, "_carregar_modelo", lambda: pytest.fail("Whisper carregado"))
    monkeypatch.setattr(t, "_capturar", lambda: t._stop.wait())
    t.start()
    t.stop()

def test_modo_posterior_grava_todos_blocos_em_ordem(tmp_path):
    t = Transcritor(pasta_saida=str(tmp_path), processar_ao_vivo=False, capturar_mic=False, criptografar=False)
    t._abrir_arquivo()
    for valor in (0.1, 0.2, 0.3):
        t._gravar_audio_bloco(np.full(1600, valor, dtype=np.float32))
    t._wav.close()
    with wave.open(t._caminho_wav, "rb") as wav:
        assert wav.getnframes() == 4800

def test_stop_expoe_audio_preservado(tmp_path, monkeypatch):
    t = Transcritor(pasta_saida=str(tmp_path), processar_ao_vivo=False, capturar_mic=False, criptografar=False)
    monkeypatch.setattr(t, "_capturar", lambda: t._stop.wait())
    t.start()
    t.stop()
    assert t.audios_preservados
    assert all(Path(path).is_file() for path in t.audios_preservados)
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_gravacao_pos_reuniao.py -v -x`

- [ ] **Step 3: implementar ramo posterior em `start`/`stop`**

No ramo posterior, iniciar `_processar_somente_audio` imediatamente e não chamar
`_carregar_modelo`. A fila usa `put(data, timeout=1)` e não remove o mais antigo.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_gravacao_pos_reuniao.py tests/test_gravacao_garantida.py tests/test_transcricao_stop.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add transcricao_core.py tests/test_gravacao_pos_reuniao.py tests/test_gravacao_garantida.py
git commit -m "feat: grava reuniao sem carregar inteligencia artificial"
```

### Task 8: T-10.D2 — Flush, métricas e watchdog leve

**Files:**
- Modify: `transcricao_core.py`
- Modify: `watchdog.py`
- Modify: `config.py`
- Modify: `tests/test_gravacao_pos_reuniao.py`
- Modify: `tests/test_watchdog.py`

**Interfaces:**
- Produces: `Transcritor.metricas_captura() -> dict` com frames, falhas e descartes.

- [ ] **Step 1: escrever RED para flush periódico, zero descartes e reinício correto**

```python
def test_metricas_modo_posterior_sem_descartes(transcritor_posterior):
    assert transcritor_posterior.metricas_captura()["blocos_descartados"] == 0

def test_flush_periodico_chama_flush(monkeypatch, transcritor_posterior):
    flush = MagicMock()
    monkeypatch.setattr(transcritor_posterior, "_flush_audio", flush)
    transcritor_posterior._segundos_desde_flush = FLUSH_AUDIO_SEG
    transcritor_posterior._gravar_audio_bloco(np.zeros(SAMPLE_RATE, dtype=np.float32))
    flush.assert_called_once()

def test_watchdog_reinicia_processador_sem_mencionar_whisper(transcritor_posterior):
    statuses = []
    watchdog = Watchdog(transcritor_posterior, on_status=statuses.append)
    watchdog._verificar()
    assert all("Whisper" not in status for status in statuses)
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_gravacao_pos_reuniao.py tests/test_watchdog.py -v -x`

- [ ] **Step 3: implementar `FLUSH_AUDIO_SEG=5`, contadores e watchdog**

O watchdog trata processador de áudio como crítico, mas sua mensagem não afirma
que Whisper falhou. Qualquer descarte incrementa métrica e torna o gate vermelho.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_gravacao_pos_reuniao.py tests/test_watchdog.py tests/test_diagnostico.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add config.py transcricao_core.py watchdog.py diagnostico.py tests/test_gravacao_pos_reuniao.py tests/test_watchdog.py tests/test_diagnostico.py
git commit -m "fix: garante flush e observa captura leve"
```

### Task 9: T-10.E1 — Criar fila durável

**Files:**
- Create: `fila_processamento.py`
- Create: `tests/test_fila_processamento.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `enfileirar(audio, mic, base_saida, metadados) -> str`.
- Produces: `reivindicar_proximo() -> Job | None`, `concluir(id, resultado)`, `falhar(id, erro_seguro)`, `recuperar_interrompidos()`.

- [ ] **Step 1: escrever RED para estados, atomicidade, retomada e path traversal**

```python
def test_job_nao_aceita_audio_fora_da_pasta(tmp_path, fila):
    fora = tmp_path.parent / "fora.wav"
    fora.write_bytes(b"RIFF")
    with pytest.raises(ValueError):
        fila.enfileirar(str(fora), None, "reuniao", {})

def test_processing_interrompido_volta_a_pending(fila, audio_valido):
    job_id = fila.enfileirar(audio_valido, None, "reuniao", {})
    fila.reivindicar_proximo()
    fila.recuperar_interrompidos()
    assert fila.obter(job_id).estado == "pending"

def test_job_json_nao_contem_texto_falado(fila, audio_valido):
    segredo = "conteúdo confidencial falado"
    job_id = fila.enfileirar(audio_valido, None, "reuniao", {"origem": "meet"})
    assert segredo not in fila.caminho_job(job_id).read_text(encoding="utf-8")
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_fila_processamento.py -v -x`

- [ ] **Step 3: implementar um JSON por job com `os.replace`**

Validar paths com `Path.resolve().is_relative_to(Path(PASTA_TRANSCRICOES).resolve())`.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_fila_processamento.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add .gitignore fila_processamento.py tests/test_fila_processamento.py
git commit -m "feat: adiciona fila duravel de processamento"
```

### Task 10: T-10.E2 — Processar depois e gerar texto legível

**Files:**
- Create: `processador_reuniao.py`
- Modify: `retranscritor.py`
- Modify: `crypto_storage.py`
- Create: `tests/test_processador_reuniao.py`
- Modify: `tests/test_retranscritor.py`

**Interfaces:**
- Produces: `processar_job(job_id: str) -> Path`.
- Produces: `retranscrever(caminho_audio, nome_base_saida: str | None, gerar_copia_tkpt: bool) -> str`.

- [ ] **Step 1: escrever RED com modelo fake**

```python
def test_processador_cria_txt_utf8_e_copia_tkpt(job_pending, modelo_fake):
    resultado = processar_job(job_pending.id, modelo_whisper=modelo_fake)
    assert resultado.suffix == ".txt"
    assert resultado.read_text(encoding="utf-8").startswith("=== Transcricao")
    assert resultado.with_suffix(".tkpt").is_file()

def test_falha_mantem_audio_e_marca_job(job_pending, monkeypatch):
    def falhar(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(retranscritor, "retranscrever", falhar)
    with pytest.raises(RuntimeError):
        processar_job(job_pending.id)
    assert Path(job_pending.audio).is_file()
    assert fila.obter(job_pending.id).estado == "failed"

def test_flags_windows_sao_sem_janela_e_prioridade_baixa():
    flags = flags_subprocesso_windows()
    assert flags & subprocess.CREATE_NO_WINDOW
    assert flags & subprocess.BELOW_NORMAL_PRIORITY_CLASS
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_processador_reuniao.py tests/test_retranscritor.py -v -x`

- [ ] **Step 3: implementar CLI `python -m processador_reuniao --job <id>`**

O texto é gravado em `.tmp`, recebe `flush/fsync`, e só então `os.replace`. A
cópia `.tkpt` lê o `.txt` em memória sem registrar o conteúdo.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_processador_reuniao.py tests/test_retranscritor.py tests/test_transcricao_crypto.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add processador_reuniao.py retranscritor.py crypto_storage.py tests/test_processador_reuniao.py tests/test_retranscritor.py
git commit -m "feat: transcreve reuniao depois e entrega texto"
```

### Task 11: T-10.F1 — Integrar ciclo completo na bandeja

**Files:**
- Modify: `transkriptor.pyw`
- Modify: `app_bandeja_menu.py`
- Modify: `estado_icone.py`
- Create: `tests/test_fluxo_reuniao_v15.py`

**Interfaces:**
- Consumes: consentimento, `Transcritor(processar_ao_vivo=False)`, fila e worker.

- [ ] **Step 1: escrever RED de fluxo ponta a ponta com fakes**

```python
def test_fluxo_aceito_fecha_e_enfileira(app_v15):
    app_v15._pedir_consentimento = lambda: True
    app_v15._processar_mudanca_meet("iniciou")
    app_v15.aguardar_threads()
    assert app_v15._gravando()
    app_v15._processar_mudanca_meet("encerrou")
    app_v15.aguardar_threads()
    assert not app_v15._gravando()
    assert app_v15.fila.quantidade("pending") == 1

def test_menu_nao_oferece_captura_generica(app_v15):
    textos = [str(item.text) for item in app_v15._menu() if item is not pystray.Menu.SEPARATOR]
    assert all("transcrição manual" not in texto.lower() for texto in textos)
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_fluxo_reuniao_v15.py -v -x`

- [ ] **Step 3: integrar e remover modo manual irrestrito**

No startup, recuperar jobs interrompidos e iniciar um worker; no fim, armazenar
paths preservados, enfileirar e zerar `self.transcritor`/`self._modo_manual`.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_fluxo_reuniao_v15.py tests/test_aviso_gravacao.py tests/test_integracao_monitor_meet.py tests/test_transkiptor_estado.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add transkriptor.pyw app_bandeja_menu.py estado_icone.py tests/test_fluxo_reuniao_v15.py
git commit -m "feat: integra ciclo de reuniao com pos-processamento"
```

### Task 12: T-10.F2 — Versão, manual e gate de recursos

**Files:**
- Modify: `config.py`
- Modify: `docs/MANUAL-USUARIO.md`
- Modify: `docs/MANUAL-USUARIO.pdf`
- Modify: `scripts/verificar_fase.py`
- Create: `scripts/verificar_recursos_gravacao.py`
- Modify: `tests/test_versao.py`
- Modify: `tests/test_manual_usuario.py`
- Modify: `tests/test_limite_linhas.py`

- [ ] **Step 1: escrever RED para versão 1.5, manual sem toast/manual irrestrito e script de recursos**

```python
def test_versao_15_config_e_pyproject():
    assert config.VERSAO == "1.5.0"
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert dados["project"]["version"] == "1.5.0"

def test_manual_descreve_processamento_posterior():
    texto = (REPO / "docs/MANUAL-USUARIO.md").read_text(encoding="utf-8")
    assert "processamento após a reunião" in texto.lower()
    assert "toasts ao vivo" not in texto.lower()

def test_verificador_recursos_tem_limites_executaveis():
    modulo = carregar_script("scripts/verificar_recursos_gravacao.py")
    resultado = modulo.avaliar(amostras_memoria_mb=[200, 220], amostras_cpu=[1, 2])
    assert resultado["ok"] is True
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_versao.py tests/test_manual_usuario.py tests/test_limite_linhas.py -v -x`

- [ ] **Step 3: atualizar versão, manual, PDF e verificador**

O script recebe PID/duração, amostra working set/CPU/ícones e falha os limites de
`NFR-10.C2`. Não lê títulos nem conteúdo.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_versao.py tests/test_manual_usuario.py tests/test_limite_linhas.py -v --tb=short`

Run: `python scripts/verificar_fase.py --fase v1.5-estatico`

- [ ] **Step 5: commit**

```powershell
git add config.py docs/MANUAL-USUARIO.md docs/MANUAL-USUARIO.pdf scripts/verificar_fase.py scripts/verificar_recursos_gravacao.py tests/test_versao.py tests/test_manual_usuario.py tests/test_limite_linhas.py
git commit -m "docs: publica operacao da versao 1.5"
```

### Task 13: T-10.G1 — Extrair intervalos sem destruir o original

**Files:**
- Create: `scripts/recuperar_intervalos_audio.py`
- Create: `tests/test_recuperacao_audio.py`

**Interfaces:**
- Produces: `extrair_intervalo(origem, destino, inicio_seg, fim_seg) -> dict`.

- [ ] **Step 1: escrever RED para duração, limites, colisão, WAV inválido e original imutável**

```python
def test_extrair_intervalo_preserva_original(wav_10s, tmp_path):
    hash_antes = sha256(Path(wav_10s).read_bytes()).hexdigest()
    destino = tmp_path / "trecho.wav"
    info = extrair_intervalo(wav_10s, destino, 2.0, 5.0)
    assert info["duracao_seg"] == pytest.approx(3.0)
    assert sha256(Path(wav_10s).read_bytes()).hexdigest() == hash_antes

def test_extrair_intervalo_recusa_sobrescrita(wav_10s, tmp_path):
    destino = tmp_path / "existente.wav"
    destino.write_bytes(b"preservar")
    with pytest.raises(FileExistsError):
        extrair_intervalo(wav_10s, destino, 0.0, 1.0)

def test_extrair_intervalo_valida_limites(wav_10s, tmp_path):
    with pytest.raises(ValueError):
        extrair_intervalo(wav_10s, tmp_path / "x.wav", 8.0, 2.0)
```

- [ ] **Step 2: confirmar RED**

Run: `python -m pytest tests/test_recuperacao_audio.py -v -x`

- [ ] **Step 3: copiar frames por streaming e gravar destino novo**

Nunca sobrescrever origem/destino existente. Retornar frames, sample rate,
duração e SHA-256 do original antes/depois.

- [ ] **Step 4: teste final da tarefa**

Run: `python -m pytest tests/test_recuperacao_audio.py -v --tb=short`

- [ ] **Step 5: commit**

```powershell
git add scripts/recuperar_intervalos_audio.py tests/test_recuperacao_audio.py
git commit -m "feat: extrai intervalos de audio com seguranca"
```

### Task 14: T-10.G2 — Recuperar as duas reuniões reais

**Files:**
- Runtime only: `transcricoes/recuperacao-2026-08-06/`
- Modify: `docs/sdd/v1.5/tasks.md` apenas com evidências sem conteúdo.

- [ ] **Step 1: calcular e registrar hashes/metadados do original**

- [ ] **Step 2: extrair cópias `0..5825` e `16150..18325`**

Run: `python scripts/recuperar_intervalos_audio.py --origem <wav> --intervalo reuniao-1:0:5825 --intervalo reuniao-2:16150:18325 --destino transcricoes/recuperacao-2026-08-06`

- [ ] **Step 3: retranscrever cada cópia pelo worker v1.5**

O segundo `.txt` recebe cabeçalho `AVISO DE INTEGRIDADE: lacuna estimada de 285 s`.

- [ ] **Step 4: teste final da tarefa**

Verificar: dois WAVs válidos, dois `.txt` não vazios, timestamps monotônicos,
UTF-8 válido, original com hash inalterado e nenhuma linha de conteúdo no log.

- [ ] **Step 5: mover para Lixeira somente depois da auditoria**

Mover o combinado, mic combinado e `.tkpt` ilegível de forma recuperável; nunca
apagar diretamente.

- [ ] **Step 6: commit de evidência sem dados sensíveis**

```powershell
git add docs/sdd/v1.5/tasks.md
git commit -m "docs: registra recuperacao das duas reunioes"
```

### Task 15: T-10.H1 — Auditoria final de qualidade, coerência e segurança

**Files:**
- Create: `docs/sdd/v1.5/auditoria-final.md`
- Modify: `docs/sdd/v1.5/tasks.md`

- [ ] **Step 1: rodar todos os gates frescos**

```powershell
python scripts/verificar_fase.py --fase all
python -m pytest tests/ -q --tb=short
python -m py_compile transkriptor.pyw deteccao_reuniao.py transcricao_core.py fila_processamento.py processador_reuniao.py
```

- [ ] **Step 2: auditoria de qualidade e coerência**

Cruzar cada FR/SEC/UX/NFR com arquivo, teste e evidência; procurar placeholders,
duplicação, arquivos acima de 500 linhas, mojibake e divergência versão/manual.

- [ ] **Step 3: auditoria de segurança do diff**

Verificar path traversal, exposição de texto/log, subprocesso, permissões de
arquivos, DPAPI, temporários, corrida de jobs, bind Flask e dependências.

- [ ] **Step 4: gate real Windows**

Validar um processo/ícone, Explorer restart, áudio fora de reunião sem captura,
consentimento, captura leve, fim automático e `.txt` posterior. Registrar PID,
versão, duração, CPU, memória e contagem de ícones, sem conteúdo falado.

- [ ] **Step 5: corrigir todo residual e repetir o gate afetado**

Nenhum residual P0/P1, requisito sem evidência ou teste apenas estrutural pode
ser marcado como concluído.

- [ ] **Step 6: teste final e commit**

```powershell
git add docs/sdd/v1.5/auditoria-final.md docs/sdd/v1.5/tasks.md
git commit -m "docs: audita entrega completa da versao 1.5"
```

Expected: todos os requisitos comprovados; só então marcar v1.5 concluída.
