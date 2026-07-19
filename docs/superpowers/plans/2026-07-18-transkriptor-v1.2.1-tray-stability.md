# Transkriptor v1.2.1 Tray Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manter o Transkriptor estável na bandeja, reconhecer janelas reais do Google Meet e criar um atalho único e confiável na Área de Trabalho.

**Architecture:** O `pystray.Icon` continuará na thread principal, mas sua visibilidade e os serviços de background serão iniciados pelo callback `setup`, após o backend Win32 criar o `HWND`. O detector continuará puro e ganhará suporte explícito a sufixos reais de Chrome/Edge; a ponte detector → app será extraída para um método testável. A criação do `.lnk` será centralizada em um script PowerShell parametrizado, chamado pelo instalador.

**Tech Stack:** Python 3.12+, pytest 8+, pystray/Win32, pygetwindow, PowerShell 5.1+, WScript.Shell, Windows 10/11.

## Global Constraints

- Python 3.12+, UTF-8 e constantes em `config.py`.
- Não duplicar lógica de transcrição; `transcricao_core.Transcritor` permanece o núcleo.
- Flask permanece em `host="127.0.0.1"`.
- Nunca registrar títulos completos de janelas, conteúdo de transcrições, prompts, áudio, tokens ou chaves.
- Nenhuma dependência nova de runtime.
- Executar uma tarefa `T-*` por vez e finalizar cada tarefa com testes verdes.
- Commits em português, no imperativo.
- O workspace atual não contém `.git`; os passos de commit só podem ser executados depois que o repositório Git estiver disponível.

## Registro de execução — 2026-07-18

- Baseline confirmado: 152 testes verdes antes do hotfix.
- `T-F1-01` e `T-F1-02`: lifecycle da bandeja corrigido com RED → GREEN.
- `T-F1-03` adicionado durante a validação: um processo terminado ainda era aceito por `OpenProcess`; a consulta de `GetExitCodeProcess` passou a distinguir `STILL_ACTIVE` de PID obsoleto.
- `T-F1-04` adicionado pelo gate NFR-2: `transcricao_core` carregava o Whisper no startup. O import foi adiado até `_iniciar_transcricao`, reduzindo a prontidão real de cerca de 13 s para 1,43 s.
- `T-F2-01` e `T-F2-02`: títulos reais e integração automática cobertos e verdes.
- `T-F3-01` e `T-F3-02`: atalho único criado e integrado ao instalador.
- `T-F4-01`: gate `estabilidade` criado e incluído no gate `all`.
- `T-F4-02`: validação manual aprovada; build final permaneceu 30,27 minutos ociosa com PID, mutex e ícone estáveis.
- Commits não executados: o diretório entregue não contém metadados `.git`.

---

## File map

| Arquivo | Responsabilidade após o hotfix |
|---------|--------------------------------|
| `transkriptor.pyw` | Orquestrar ciclo da bandeja, thread do monitor e reação a `iniciou/encerrou` |
| `detector_meet.py` | Classificar títulos e aplicar debounce sem efeitos colaterais |
| `scripts/criar_atalho_desktop.ps1` | Criar um `.lnk` parametrizado e validável |
| `instalar.bat` | Instalar dependências e chamar a criação única do atalho |
| `scripts/verificar_fase.py` | Expor gate `--fase estabilidade` |
| `tests/conftest.py` | Carregar `transkriptor.pyw` como módulo para testes |
| `tests/test_bandeja_lifecycle.py` | Provar ordem de prontidão, idempotência e falha segura |
| `tests/test_detector_meet.py` | Cobrir títulos reais e falsos positivos |
| `tests/test_integracao_monitor_meet.py` | Cobrir detector → início/parada da transcrição |
| `tests/test_atalho_desktop.py` | Criar e inspecionar `.lnk` em pasta temporária |

---

### Task 1: Corrigir a ordem de inicialização do ícone (`T-F1-01`)

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_bandeja_lifecycle.py`
- Modify: `transkriptor.pyw:198-250`
- Modify: `transkriptor.pyw:790-829`

**Interfaces:**
- Produces: fixture `modulo_transkriptor` que carrega `transkriptor.pyw` sem executar o bloco `__main__`.
- Produces: `AppTranskriptor._ao_bandeja_pronta(icon) -> None`.
- Consumes: `pystray.Icon.run(setup: Callable)` e `icon.visible`.

- [ ] **Step 1: adicionar fixture que carrega o `.pyw`**

Adicionar a `tests/conftest.py`:

```python
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path


@pytest.fixture(scope="session")
def modulo_transkriptor():
    caminho = Path(__file__).resolve().parent.parent / "transkriptor.pyw"
    loader = SourceFileLoader("transkriptor_app_test", str(caminho))
    spec = spec_from_loader(loader.name, loader)
    modulo = module_from_spec(spec)
    loader.exec_module(modulo)
    return modulo
```

- [ ] **Step 2: escrever os testes RED de ordenação**

Criar `tests/test_bandeja_lifecycle.py`:

```python
import threading


class IconeFalso:
    instancia = None

    def __init__(self, *args, **kwargs):
        type(self).instancia = self
        self.ready = False
        self.visible_events = []
        self.notifications = []
        self._visible = False

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, valor):
        self.visible_events.append((valor, self.ready))
        self._visible = valor

    def run(self, setup=None):
        self.ready = True
        if setup is not None:
            setup(self)

    def notify(self, mensagem, titulo):
        self.notifications.append((mensagem, titulo, self.ready))

    def stop(self):
        pass


class ThreadFalsa:
    eventos = []

    def __init__(self, target, daemon=False, name=None):
        self.target = target
        self.daemon = daemon
        self.name = name
        self._alive = False

    def start(self):
        self._alive = True
        ThreadFalsa.eventos.append(IconeFalso.instancia.ready)

    def is_alive(self):
        return self._alive


def _app_minimo(modulo):
    app = modulo.AppTranskriptor.__new__(modulo.AppTranskriptor)
    app.iniciar_com_windows = False
    app.usar_nomes_meet = False
    app._meet_bridge_thread = None
    app._monitor_thread = None
    app._bandeja_pronta = False
    app._lock = threading.Lock()
    app._menu = lambda: None
    app._monitorar_meet = lambda: None
    return app


def test_icone_so_fica_visivel_depois_do_backend_pronto(monkeypatch, modulo_transkriptor):
    ThreadFalsa.eventos.clear()
    monkeypatch.setattr(modulo_transkriptor.pystray, "Icon", IconeFalso)
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)
    monkeypatch.setattr(modulo_transkriptor, "criar_ico", lambda: None)
    monkeypatch.setattr(modulo_transkriptor, "criar_imagem", lambda: object())
    monkeypatch.setattr(modulo_transkriptor, "_startup_ativo", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)

    app = _app_minimo(modulo_transkriptor)
    app.rodar()

    assert IconeFalso.instancia.visible_events == [(True, True)]


def test_monitor_so_inicia_depois_da_bandeja_pronta(monkeypatch, modulo_transkriptor):
    ThreadFalsa.eventos.clear()
    monkeypatch.setattr(modulo_transkriptor.pystray, "Icon", IconeFalso)
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)
    monkeypatch.setattr(modulo_transkriptor, "criar_ico", lambda: None)
    monkeypatch.setattr(modulo_transkriptor, "criar_imagem", lambda: object())
    monkeypatch.setattr(modulo_transkriptor, "_startup_ativo", lambda: False)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)

    app = _app_minimo(modulo_transkriptor)
    app.rodar()

    assert ThreadFalsa.eventos == [True]
```

- [ ] **Step 3: executar RED e confirmar o motivo**

Run:

```powershell
python -m pytest tests/test_bandeja_lifecycle.py -v --tb=short
```

Expected: o primeiro teste encontra `[(True, False)]`, porque o código atual define `visible` antes de `run()`; o segundo encontra `[False]`, porque o monitor também inicia antes da prontidão.

- [ ] **Step 4: implementar o setup pós-prontidão mínimo**

Em `AppTranskriptor.__init__`, após `_meet_bridge_thread`:

```python
self._monitor_thread = None
self._bandeja_pronta = False
```

Adicionar antes de `rodar()`:

```python
def _ao_bandeja_pronta(self, icon):
    """Registra o ícone e inicia serviços após o backend Win32 estar pronto."""
    icon.visible = True
    self._bandeja_pronta = True
    if self.usar_nomes_meet:
        self._meet_bridge_thread = iniciar_bridge_em_thread(
            self.meet_bridge,
            "127.0.0.1",
            PORTA_MEET_BRIDGE,
        )
        logging.info("Ponte Meet iniciada em 127.0.0.1:%s", PORTA_MEET_BRIDGE)
    self._monitor_thread = threading.Thread(
        target=self._monitorar_meet,
        daemon=True,
        name="Transkriptor-MonitorMeet",
    )
    self._monitor_thread.start()
    logging.info("Bandeja pronta.")
    logging.info("Monitor do Meet iniciado.")
    notificar(
        "Transkriptor",
        "Ativo na bandeja. Se o ícone não aparecer, clique em ^ na barra de tarefas.",
    )
    icon.notify(
        "Transkriptor ativo",
        "Ícone na bandeja do sistema. Use ^ se estiver oculto.",
    )
```

Substituir o trecho de `rodar()` que define `visible`, inicia bridge/thread e notifica por:

```python
self.icone.run(setup=self._ao_bandeja_pronta)
```

`Icon.run(...)` deve permanecer na thread principal.

- [ ] **Step 5: executar GREEN**

Run:

```powershell
python -m pytest tests/test_bandeja_lifecycle.py tests/test_mutex.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 6: executar regressão próxima**

Run:

```powershell
python -m pytest tests/test_notificador.py tests/test_transkiptor_estado.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 7: commit**

```powershell
git add tests/conftest.py tests/test_bandeja_lifecycle.py transkriptor.pyw
git commit -m "fix: corrige ciclo de inicialização do ícone da bandeja"
```

---

### Task 2: Tornar setup idempotente e falhar de forma visível (`T-F1-02`)

**Files:**
- Modify: `tests/test_bandeja_lifecycle.py`
- Modify: `transkriptor.pyw:790-850`

**Interfaces:**
- Consumes: `AppTranskriptor._ao_bandeja_pronta(icon)` da Task 1.
- Produces: setup idempotente, `icon.stop()` em falha e liberação garantida do mutex quando o loop termina.

- [ ] **Step 1: escrever testes RED de idempotência e falha**

Adicionar a `IconeFalso`:

```python
self.stopped = False
```

Substituir `stop` por:

```python
def stop(self):
    self.stopped = True
```

Adicionar ao arquivo:

```python
def test_setup_repetido_nao_duplica_monitor(monkeypatch, modulo_transkriptor):
    ThreadFalsa.eventos.clear()
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)
    app = _app_minimo(modulo_transkriptor)
    icon = IconeFalso()
    icon.ready = True

    app._ao_bandeja_pronta(icon)
    app._ao_bandeja_pronta(icon)

    assert len(ThreadFalsa.eventos) == 1


def test_falha_no_setup_para_icone_e_mostra_erro(monkeypatch, modulo_transkriptor):
    class ThreadComFalha(ThreadFalsa):
        def start(self):
            raise RuntimeError("falha controlada")

    erros = []
    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadComFalha)
    monkeypatch.setattr(modulo_transkriptor, "notificar", lambda *args, **kwargs: None)
    monkeypatch.setattr(modulo_transkriptor, "_mostrar_erro_fatal", erros.append)
    app = _app_minimo(modulo_transkriptor)
    icon = IconeFalso()
    icon.ready = True

    app._ao_bandeja_pronta(icon)

    assert icon.stopped is True
    assert erros == ["Não foi possível preparar a bandeja do Transkriptor."]
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_bandeja_lifecycle.py::test_setup_repetido_nao_duplica_monitor tests/test_bandeja_lifecycle.py::test_falha_no_setup_para_icone_e_mostra_erro -v --tb=short
```

Expected: setup atual duplica a thread e propaga `RuntimeError` sem parar o ícone.

- [ ] **Step 3: implementar idempotência e falha segura**

Substituir `_ao_bandeja_pronta` por uma versão com guarda:

```python
def _ao_bandeja_pronta(self, icon):
    """Registra o ícone e inicia serviços uma vez após prontidão Win32."""
    try:
        icon.visible = True
        with self._lock:
            if self._bandeja_pronta:
                return
            self._bandeja_pronta = True

        if self.usar_nomes_meet:
            self._meet_bridge_thread = iniciar_bridge_em_thread(
                self.meet_bridge,
                "127.0.0.1",
                PORTA_MEET_BRIDGE,
            )
            logging.info("Ponte Meet iniciada em 127.0.0.1:%s", PORTA_MEET_BRIDGE)

        self._monitor_thread = threading.Thread(
            target=self._monitorar_meet,
            daemon=True,
            name="Transkriptor-MonitorMeet",
        )
        self._monitor_thread.start()
        logging.info("Bandeja pronta.")
        logging.info("Monitor do Meet iniciado.")
        notificar(
            "Transkriptor",
            "Ativo na bandeja. Se o ícone não aparecer, clique em ^ na barra de tarefas.",
        )
        try:
            icon.notify(
                "Transkriptor ativo",
                "Ícone na bandeja do sistema. Use ^ se estiver oculto.",
            )
        except Exception:
            logging.warning("Notificação nativa da bandeja indisponível.")
    except Exception:
        logging.exception("Falha ao preparar bandeja")
        with self._lock:
            self._bandeja_pronta = False
        _mostrar_erro_fatal("Não foi possível preparar a bandeja do Transkriptor.")
        icon.stop()
```

Envolver `run` em `rodar()`:

```python
try:
    self.icone.run(setup=self._ao_bandeja_pronta)
finally:
    liberar_lock()
```

- [ ] **Step 4: executar GREEN e gate F1**

```powershell
python -m pytest tests/test_bandeja_lifecycle.py tests/test_mutex.py tests/test_notificador.py tests/test_transkiptor_estado.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 5: commit**

```powershell
git add tests/test_bandeja_lifecycle.py transkriptor.pyw
git commit -m "fix: estabiliza prontidão da bandeja e thread do monitor"
```

---

### Task 3: Reconhecer títulos reais dos navegadores (`T-F2-01`)

**Files:**
- Modify: `tests/test_detector_meet.py`
- Modify: `detector_meet.py:14-31`

**Interfaces:**
- Consumes: `titulo_eh_meet(titulo, *, visivel=True, exigir_janela_visivel=False) -> bool`.
- Preserves: `DetectorMeet` e debounce 2/3.

- [ ] **Step 1: ampliar a matriz de testes RED**

Adicionar os seguintes casos positivos ao `parametrize` de `tests/test_detector_meet.py`:

```python
("Daily - Google Meet - Google Chrome", True),
("Planejamento - Google Meet — Microsoft\u200b Edge", True),
("Planejamento - Google Meet - Perfil 1 — Microsoft Edge", True),
```

Adicionar casos negativos:

```python
("Novidades do Google Meet - Google Chrome", False),
("como configurar Google Meet - Pesquisa Google", False),
("Google Meet Help - Google Chrome", False),
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_detector_meet.py -v --tb=short
```

Expected: os três títulos reais positivos falham porque o padrão atual exige `Google Meet$`.

- [ ] **Step 3: implementar o padrão mínimo**

Substituir `_PADRAO_MEET` por:

```python
_PADRAO_MEET = re.compile(
    r"(?:.+\s-\sGoogle\sMeet(?=$|\s[-—]\s))"
    r"|(?:meet\.google\.com/[a-z0-9]+(?:-[a-z0-9]+)+)",
    re.IGNORECASE,
)
```

Atualizar `_EXCLUIR` para manter os novos negativos:

```python
_EXCLUIR = re.compile(
    r"(pesquisa|search|como\s+(?:usar|configurar)|tutorial|ajuda|help|"
    r"sign\s?in|login|account|novidades)",
    re.IGNORECASE,
)
```

O padrão exige uma sala antes de ` - Google Meet`; assim, páginas intituladas somente `Google Meet ...` não são reuniões.

- [ ] **Step 4: executar GREEN e regressão do detector**

```powershell
python -m pytest tests/test_detector_meet.py tests/test_detector_meet_visivel.py tests/test_notificador.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 5: commit**

```powershell
git add tests/test_detector_meet.py detector_meet.py
git commit -m "fix: reconhece títulos reais do Google Meet nos navegadores"
```

---

### Task 4: Cobrir detector → início automático (`T-F2-02`)

**Files:**
- Create: `tests/test_integracao_monitor_meet.py`
- Modify: `transkriptor.pyw:380-404`

**Interfaces:**
- Produces: `AppTranskriptor._processar_mudanca_meet(mudanca: str | None) -> None`.
- Consumes: `DetectorMeet.verificar(titulos) -> "iniciou" | "encerrou" | None`.

- [ ] **Step 1: escrever testes RED do fluxo**

Criar `tests/test_integracao_monitor_meet.py`:

```python
from unittest.mock import Mock

from detector_meet import DetectorMeet


def _app_controlado(modulo, manual=False):
    app = modulo.AppTranskriptor.__new__(modulo.AppTranskriptor)
    app._modo_manual = manual
    app._iniciar_transcricao = Mock()
    app._parar_transcricao = Mock()
    app._status = Mock()
    return app


def test_titulo_real_inicia_transcricao_uma_vez(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    titulos = ["Daily - Google Meet - Google Chrome"]

    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))
    app._processar_mudanca_meet(detector.verificar(titulos))

    app._iniciar_transcricao.assert_called_once_with()


def test_fim_do_meet_para_transcricao_apos_debounce(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor)
    detector = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Daily - Google Meet - Google Chrome"]
    for _ in range(2):
        app._processar_mudanca_meet(detector.verificar(meet))
    for _ in range(3):
        app._processar_mudanca_meet(detector.verificar([]))

    app._parar_transcricao.assert_called_once_with()
    app._status.assert_called_with("Meet encerrado. Finalizando transcricao...")


def test_modo_manual_ignora_inicio_e_fim_do_meet(modulo_transkriptor):
    app = _app_controlado(modulo_transkriptor, manual=True)

    app._processar_mudanca_meet("iniciou")
    app._processar_mudanca_meet("encerrou")

    app._iniciar_transcricao.assert_not_called()
    app._parar_transcricao.assert_not_called()
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_integracao_monitor_meet.py -v --tb=short
```

Expected: `AttributeError`, pois `_processar_mudanca_meet` ainda não existe.

- [ ] **Step 3: extrair o tratamento sem mudar comportamento**

Adicionar antes de `_monitorar_meet`:

```python
def _processar_mudanca_meet(self, mudanca):
    if mudanca == "iniciou":
        if not self._modo_manual:
            self._iniciar_transcricao()
        return
    if deve_parar_transcricao_por_meet(mudanca, self._modo_manual):
        self._status("Meet encerrado. Finalizando transcricao...")
        self._parar_transcricao()
```

Em `_monitorar_meet`, substituir o bloco `if mudanca ... elif ...` por:

```python
self._processar_mudanca_meet(mudanca)
```

Manter o `try/except` externo e o intervalo configurado. O `except` pode registrar apenas tipo e mensagem da exceção, nunca a lista de títulos:

```python
except Exception:
    logging.exception("Erro no monitor do Meet")
```

- [ ] **Step 4: executar GREEN e gate F2**

```powershell
python -m pytest tests/test_detector_meet.py tests/test_detector_meet_visivel.py tests/test_integracao_monitor_meet.py tests/test_notificador.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 5: commit**

```powershell
git add tests/test_integracao_monitor_meet.py transkriptor.pyw
git commit -m "test: cobre início automático da transcrição pelo detector"
```

---

### Task 5: Criar atalho único e testável (`T-F3-01`)

**Files:**
- Create: `scripts/criar_atalho_desktop.ps1`
- Create: `tests/test_atalho_desktop.py`

**Interfaces:**
- Produces: CLI PowerShell com parâmetros `-Pythonw`, `-Aplicativo`, `-Icone` e `-Destino` opcional.
- Produces: stdout com caminho absoluto do `.lnk`; exit 0 em sucesso e diferente de 0 em erro.

- [ ] **Step 1: escrever teste RED que exige o script**

Criar `tests/test_atalho_desktop.py`:

```python
import json
import os
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "criar_atalho_desktop.ps1"


def _inspecionar_atalho(caminho):
    env = os.environ.copy()
    env["TRANSKRIPTOR_ATALHO_TESTE"] = str(caminho)
    codigo = r"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:TRANSKRIPTOR_ATALHO_TESTE)
[pscustomobject]@{
  TargetPath = $s.TargetPath
  Arguments = $s.Arguments
  WorkingDirectory = $s.WorkingDirectory
  IconLocation = $s.IconLocation
  WindowStyle = $s.WindowStyle
} | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", codigo],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_cria_atalho_com_metadados_e_caminhos_com_espacos(tmp_path):
    pasta = tmp_path / "instalacao com espacos"
    pasta.mkdir()
    pythonw = pasta / "pythonw.exe"
    aplicativo = pasta / "transkriptor.pyw"
    icone = pasta / "transkriptor.ico"
    for caminho in (pythonw, aplicativo, icone):
        caminho.write_bytes(b"teste")
    destino = tmp_path / "Desktop de teste" / "Transkriptor.lnk"

    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(SCRIPT),
            "-Pythonw", str(pythonw),
            "-Aplicativo", str(aplicativo),
            "-Icone", str(icone),
            "-Destino", str(destino),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert destino.is_file()
    dados = _inspecionar_atalho(destino)
    assert Path(dados["TargetPath"]).resolve() == pythonw.resolve()
    assert dados["Arguments"] == f'"{aplicativo.resolve()}"'
    assert Path(dados["WorkingDirectory"]).resolve() == pasta.resolve()
    assert str(icone.resolve()).lower() in dados["IconLocation"].lower()
    assert dados["WindowStyle"] == 7
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_atalho_desktop.py -v --tb=short
```

Expected: FAIL porque `scripts/criar_atalho_desktop.ps1` não existe.

- [ ] **Step 3: implementar o script parametrizado**

Criar `scripts/criar_atalho_desktop.ps1`:

```powershell
param(
    [Parameter(Mandatory = $true)][string]$Pythonw,
    [Parameter(Mandatory = $true)][string]$Aplicativo,
    [Parameter(Mandatory = $true)][string]$Icone,
    [string]$Destino = ""
)

$ErrorActionPreference = "Stop"

$Pythonw = (Resolve-Path -LiteralPath $Pythonw).Path
$Aplicativo = (Resolve-Path -LiteralPath $Aplicativo).Path
$Icone = (Resolve-Path -LiteralPath $Icone).Path

if (-not $Destino) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) {
        throw "Pasta da Área de Trabalho não encontrada."
    }
    $Destino = Join-Path $desktop "Transkriptor.lnk"
}

$Destino = [IO.Path]::GetFullPath($Destino)
$pastaDestino = Split-Path -Parent $Destino
if (-not (Test-Path -LiteralPath $pastaDestino -PathType Container)) {
    New-Item -ItemType Directory -Path $pastaDestino -Force | Out-Null
}

$shell = New-Object -ComObject WScript.Shell
$atalho = $shell.CreateShortcut($Destino)
$atalho.TargetPath = $Pythonw
$atalho.Arguments = '"' + $Aplicativo + '"'
$atalho.WorkingDirectory = Split-Path -Parent $Aplicativo
$atalho.IconLocation = $Icone
$atalho.Description = "Transkriptor - Transcrição automática de Google Meet"
$atalho.WindowStyle = 7
$atalho.Save()

if (-not (Test-Path -LiteralPath $Destino -PathType Leaf)) {
    throw "O atalho não foi criado."
}

Write-Output $Destino
```

- [ ] **Step 4: executar GREEN**

```powershell
python -m pytest tests/test_atalho_desktop.py -v --tb=short
```

Expected: PASS.

- [ ] **Step 5: commit**

```powershell
git add scripts/criar_atalho_desktop.ps1 tests/test_atalho_desktop.py
git commit -m "feat: adiciona criação confiável do atalho do Transkriptor"
```

---

### Task 6: Integrar o atalho ao instalador (`T-F3-02`)

**Files:**
- Modify: `tests/test_atalho_desktop.py`
- Modify: `instalar.bat:25-35`

**Interfaces:**
- Consumes: `scripts/criar_atalho_desktop.ps1` da Task 5.
- Preserves: resolução de `pythonw.exe` por `scripts/resolver_pythonw.py`.

- [ ] **Step 1: escrever teste RED do contrato do instalador**

Adicionar a `tests/test_atalho_desktop.py`:

```python
def test_instalador_usa_script_unico_e_nao_cria_atalho_redundante():
    texto = (REPO / "instalar.bat").read_text(encoding="utf-8")
    assert "scripts\\criar_atalho_desktop.ps1" in texto
    assert "if %errorlevel% neq 0" in texto.lower()
    assert "Iniciar Transkriptor.lnk" not in texto
    assert "$ws.CreateShortcut" not in texto
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_atalho_desktop.py::test_instalador_usa_script_unico_e_nao_cria_atalho_redundante -v --tb=short
```

Expected: FAIL porque o instalador atual contém PowerShell inline e cria dois atalhos.

- [ ] **Step 3: substituir o bloco de atalhos do instalador**

Após resolver `PYTHONW`, usar:

```bat
if not defined PYTHONW (
  echo [ERRO] pythonw.exe nao encontrado.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\criar_atalho_desktop.ps1" ^
  -Pythonw "%PYTHONW%" ^
  -Aplicativo "%~dp0transkriptor.pyw" ^
  -Icone "%~dp0transkriptor.ico"
if %errorlevel% neq 0 (
  echo [ERRO] Falha ao criar o atalho Transkriptor na Area de Trabalho.
  pause
  exit /b 1
)
```

Atualizar a mensagem final para mencionar apenas `Transkriptor`.

- [ ] **Step 4: executar GREEN e gate F3**

```powershell
python -m pytest tests/test_atalho_desktop.py tests/test_config_device.py -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 5: commit**

```powershell
git add tests/test_atalho_desktop.py instalar.bat
git commit -m "fix: integra atalho único ao instalador"
```

---

### Task 7: Adicionar gate de estabilidade (`T-F4-01`)

**Files:**
- Modify: `scripts/verificar_fase.py`
- Modify: `tests/test_gitignore_docs.py`

**Interfaces:**
- Produces: `python scripts/verificar_fase.py --fase estabilidade`.
- Preserves: gates numéricos 0–8 e `--fase all`.

- [ ] **Step 1: escrever teste RED do alias**

Adicionar a `tests/test_gitignore_docs.py`:

```python
def test_gate_estabilidade_lista_testes_do_hotfix():
    texto = (REPO / "scripts" / "verificar_fase.py").read_text(encoding="utf-8")
    assert '"estabilidade"' in texto
    assert "tests/test_bandeja_lifecycle.py" in texto
    assert "tests/test_integracao_monitor_meet.py" in texto
    assert "tests/test_atalho_desktop.py" in texto
```

- [ ] **Step 2: executar RED**

```powershell
python -m pytest tests/test_gitignore_docs.py::test_gate_estabilidade_lista_testes_do_hotfix -v --tb=short
```

Expected: FAIL porque o alias ainda não existe.

- [ ] **Step 3: adicionar o subset e incluí-lo em `all`**

Adicionar a `FASES`:

```python
"estabilidade": [
    "tests/test_bandeja_lifecycle.py",
    "tests/test_detector_meet.py",
    "tests/test_integracao_monitor_meet.py",
    "tests/test_atalho_desktop.py",
],
```

Alterar a seleção:

```python
if args.fase == "all":
    files = sorted({f for fl in FASES.values() for f in fl})
elif args.fase == "estabilidade":
    files = FASES["estabilidade"]
else:
    try:
        fase = int(args.fase)
    except ValueError:
        print(f"Fase inválida: {args.fase}", file=sys.stderr)
        return 1
    files = FASES.get(fase)
    if files is None:
        print(f"Fase {fase} não definida.", file=sys.stderr)
        return 1
```

Atualizar help para `Número da fase (0-8), 'estabilidade' ou 'all'`.

- [ ] **Step 4: executar GREEN e o gate novo**

```powershell
python -m pytest tests/test_gitignore_docs.py -v --tb=short
python scripts/verificar_fase.py --fase estabilidade
```

Expected: ambos exit 0.

- [ ] **Step 5: commit**

```powershell
git add scripts/verificar_fase.py tests/test_gitignore_docs.py
git commit -m "test: adiciona gate de estabilidade da bandeja e Meet"
```

---

### Task 8: Verificar manualmente e documentar (`T-F4-02`)

**Files:**
- Modify: `docs/VERIFICACAO.md`
- Create: `docs/sdd/v1.2.1/CHANGELOG.md`
- Modify: `docs/sdd/v1.2.1/tasks.md`

**Interfaces:**
- Consumes: todos os gates anteriores.
- Produces: evidência da entrega v1.2.1 e checklist manual preenchido.

- [ ] **Step 1: executar suíte automatizada completa**

```powershell
python scripts/verificar_fase.py --fase estabilidade
python -m pytest tests/ -v --tb=short
python scripts/verificar_fase.py --fase all
```

Expected: três comandos com exit 0. Registrar contagem total real; não copiar a baseline de 152 depois que novos testes forem adicionados.

- [ ] **Step 2: criar o atalho real**

```powershell
$pythonw = python scripts/resolver_pythonw.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/criar_atalho_desktop.ps1 `
  -Pythonw $pythonw `
  -Aplicativo (Resolve-Path transkriptor.pyw).Path `
  -Icone (Resolve-Path transkriptor.ico).Path
```

Expected: stdout contém o caminho de `Transkriptor.lnk` na Área de Trabalho.

- [ ] **Step 3: executar checklist manual Windows**

Registrar em `docs/VERIFICACAO.md`:

```markdown
## v1.2.1 — Estabilidade da bandeja e Meet

- Data/hora:
- Windows (versão/build):
- Navegador e versão:
- Python:
- [ ] Atalho abre via pythonw sem console.
- [ ] Ícone aparece em até 5s e menu abre.
- [ ] Ícone permanece após 30 min ocioso.
- [ ] Título real do Chrome/Edge inicia transcrição em até 15s.
- [ ] Fechar Meet finaliza após três ciclos.
- [ ] Segunda abertura permanece em uma instância.
- [ ] Reiniciar Explorer preserva processo e restaura ícone.
- [ ] Preferência “Iniciar com o Windows” não mudou.
- Resultado: APROVADO | REPROVADO
- Evidência do log (somente mensagens de sistema):
```

- [ ] **Step 4: criar changelog da versão**

Criar `docs/sdd/v1.2.1/CHANGELOG.md` com:

```markdown
# Changelog — Transkriptor v1.2.1

## Corrigido

- Registro do ícone somente após prontidão do backend Win32.
- Inicialização única do monitor do Meet.
- Detecção de títulos reais do Chrome e Microsoft Edge.
- Atalho único e silencioso na Área de Trabalho.

## Qualidade

- Testes de regressão do lifecycle da bandeja.
- Teste integrado detector → início/parada.
- Inspeção automatizada do `.lnk`.
- Gate `--fase estabilidade`.
```

- [ ] **Step 5: invocar verificação antes de concluir**

Invocar `superpowers:verification-before-completion` e repetir os comandos definidos pela skill. Só depois marcar as tarefas `[x]`.

- [ ] **Step 6: commit**

```powershell
git add docs/VERIFICACAO.md docs/sdd/v1.2.1/CHANGELOG.md docs/sdd/v1.2.1/tasks.md
git commit -m "docs: registra verificação do hotfix de estabilidade"
```

---

## Self-review

### Spec coverage

| Requisitos | Tarefas |
|------------|---------|
| FR-0.* | 1, 3, 7, 8 |
| FR-1.* | 1, 2 |
| FR-2.* | 3, 4 |
| FR-3.* | 5, 6 |
| FR-4.* | 7, 8 |
| NFR-1–7 | 1–8 + gate manual |
| SEC-1–5 | restrições globais, 3–6 |
| UX-1–6 | 1, 2, 5, 8 |

### Scope check

- Sem troca de framework.
- Sem alteração de transcrição, diarização, criptografia, Flask ou extensão.
- Sem ativação automática de startup.
- Sem dependência nova.
- O plano termina em software funcional, testado e com atalho real.

## Execution handoff

Plano completo. A execução deve começar por `T-F0-01`, seguida de `T-F1-01`, usando `superpowers:test-driven-development`. No ambiente atual não há `.git`; commits, push e publicação exigirão restaurar ou inicializar conscientemente o repositório antes da fase de entrega.
