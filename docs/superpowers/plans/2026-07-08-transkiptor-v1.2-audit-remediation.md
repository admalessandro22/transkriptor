# Transkriptor v1.2 — Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir todos os achados da auditoria sênior 2026-07-08 com SDD rastreável, TDD e gates de verificação por fase.

**Architecture:** Infra pytest primeiro; correções P0 em `assistente.py`/`Transkriptor.pyw`; P1 em config/mutex/logs; UX em camadas bandeja → assistente; segurança token no final. Cada fase = subset de testes + `scripts/verificar_fase.py`.

**Tech Stack:** Python 3.12, pytest, Flask, pystray, faster-whisper, Ollama (local)

## Global Constraints

- Flask: `host="127.0.0.1"` only
- Constantes em `config.py` — sem magic numbers novos
- Transcrições: nunca logar conteúdo completo
- Commits: português, uma tarefa `T-*` por commit
- Spec IDs: todo código referencia `FR-*` / `SEC-*` em comentário mínimo só se não óbvio
- Windows 10/11 target

---

## Fase 0 — Fundação QA

### Task 0.1: pyproject.toml + requirements-dev

**Files:**
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`

**Interfaces:**
- Produces: `pytest` invocable via `python -m pytest`

- [ ] **Step 1: Create requirements-dev.txt**

```
pytest>=8.0
pytest-cov>=5.0
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "Transkriptor"
version = "1.2.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
```

- [ ] **Step 3: Install and verify**

Run: `python -m pip install -r requirements-dev.txt && python -m pytest --version`
Expected: pytest 8.x

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml requirements-dev.txt
git commit -m "chore: adiciona infraestrutura pytest para v1.2"
```

---

### Task 0.2: conftest fixtures

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: `tmp_transcricoes` fixture → `pathlib.Path`

- [ ] **Step 1: Write conftest**

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def tmp_transcricoes(tmp_path):
    pasta = tmp_path / "transcricoes"
    pasta.mkdir()
    (pasta / "transcricao_2026-07-08_10h00.txt").write_text(
        "=== Transcricao ===\n\n[10:00:01] Ola equipe\n", encoding="utf-8"
    )
    return pasta
```

- [ ] **Step 2: Commit**

```bash
git add tests/
git commit -m "test: adiciona fixtures pytest base"
```

---

### Task 0.3: test_detector_meet baseline

**Files:**
- Create: `tests/test_detector_meet.py`

**Interfaces:**
- Consumes: `detector_meet.titulo_eh_meet`, `detector_meet.DetectorMeet`

- [ ] **Step 1: Write tests (should PASS immediately — baseline)**

```python
import pytest
from detector_meet import titulo_eh_meet, DetectorMeet

@pytest.mark.parametrize("titulo,esperado", [
    ("Reuniao de equipe - Google Meet", True),
    ("meet.google.com/abc-defg-hij", True),
    ("como usar google meet - Pesquisa Google", False),
    ("Google Meet - Sign in", False),
    ("", False),
])
def test_titulo_eh_meet(titulo, esperado):
    assert titulo_eh_meet(titulo) == esperado

def test_debounce_inicio():
    d = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    titulos = ["Equipe - Google Meet"]
    assert d.verificar(titulos) is None
    assert d.verificar(titulos) == "iniciou"

def test_debounce_fim():
    d = DetectorMeet(confirma_inicio=2, confirma_fim=3)
    meet = ["Equipe - Google Meet"]
    d.verificar(meet); d.verificar(meet)
    for _ in range(3):
        r = d.verificar([])
    assert r == "encerrou"
```

- [ ] **Step 2: Run**

Run: `python -m pytest tests/test_detector_meet.py -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_detector_meet.py
git commit -m "test: baseline detector_meet com debounce"
```

---

### Task 0.4: verificar_fase.py

**Files:**
- Create: `scripts/verificar_fase.py`

**Interfaces:**
- Produces: CLI `--fase N|all` → exit 0/1

- [ ] **Step 1: Implement script**

```python
#!/usr/bin/env python3
"""Gate de verificação por fase — v1.2 SDD."""
import argparse, subprocess, sys

FASES = {
    0: ["tests/test_detector_meet.py"],
    1: ["tests/test_assistente_seguranca.py", "tests/test_assistente_startup.py"],
    2: ["tests/test_config_device.py", "tests/test_mutex.py", "tests/test_Transkriptor_estado.py"],
    3: ["tests/test_notificador.py", "tests/test_diarizador_progresso.py"],
    4: ["tests/test_assistente_api.py"],
    5: ["tests/test_token_sessao.py", "tests/test_detector_meet_visivel.py"],
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fase", required=True)
    args = p.parse_args()
    if args.fase == "all":
        files = [f for fl in FASES.values() for f in fl]
    else:
        files = FASES.get(int(args.fase), [])
        if not files:
            print(f"Fase {args.fase} sem testes definidos ainda — OK placeholder")
            return 0
    missing = [f for f in files if not __import__("pathlib").Path(f).exists()]
    if missing:
        print(f"TESTES AUSENTES (fase incompleta): {missing}")
        return 1
    r = subprocess.run([sys.executable, "-m", "pytest", *files, "-v", "--tb=short"])
    return r.returncode

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run gate F0**

Run: `python scripts/verificar_fase.py --fase 0`
Expected: exit 0

- [ ] **Step 3: Commit + marcar GATE F0**

---

## Fase 1 — P0 Crítico

### Task 1.1: caminho_transcricao_seguro (TDD)

**Files:**
- Modify: `assistente.py`
- Create: `tests/test_assistente_seguranca.py`

**Interfaces:**
- Produces: `caminho_transcricao_seguro(nome: str) -> str | None`

- [ ] **Step 1: Write failing test**

```python
import pytest
from assistente import caminho_transcricao_seguro

def test_rejeita_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    assert caminho_transcricao_seguro("../../etc/passwd") is None
    assert caminho_transcricao_seguro("..\\..\\windows\\win.ini") is None

def test_aceita_arquivo_valido(tmp_path, monkeypatch):
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    result = caminho_transcricao_seguro("ok.txt")
    assert result is not None
    assert result.endswith("ok.txt")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_assistente_seguranca.py -v`
Expected: FAIL `ImportError` or `AttributeError`

- [ ] **Step 3: Implement**

```python
# assistente.py
def caminho_transcricao_seguro(nome: str):
    if not nome or ".." in nome.replace("\\", "/"):
        return None
    base = os.path.realpath(PASTA_TRANSCRICOES)
    caminho = os.path.realpath(os.path.join(PASTA_TRANSCRICOES, nome))
    if not caminho.startswith(base + os.sep) and caminho != base:
        return None
    if not os.path.isfile(caminho):
        return None
    return caminho
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Wire /api/chat**

```python
# api_chat — substituir join direto:
caminho = caminho_transcricao_seguro(nome)
if not caminho:
    return jsonify({"erro": "Acesso negado"}), 403
```

- [ ] **Step 6: Commit**

```bash
git commit -m "fix(SEC-1): valida path de transcricao na API"
```

---

### Task 1.2: Startup assistente thread-first (TDD)

**Files:**
- Modify: `assistente.py`, `Transkriptor.pyw`
- Create: `tests/test_assistente_startup.py`

**Interfaces:**
- Produces: `iniciar_servidor_em_thread(app, host, port) -> threading.Thread`

- [ ] **Step 1: Write failing test**

```python
import threading
import time
from unittest.mock import MagicMock, patch
from assistente import iniciar_servidor_em_thread, app

def test_servidor_responde_antes_timeout():
    thread = iniciar_servidor_em_thread(app, "127.0.0.1", 0)  # porta 0 = OS assign
    try:
        # extrair porta real do servidor — implementar callback ou atributo
        time.sleep(0.5)
        assert thread.is_alive()
    finally:
        # shutdown via requests ou werkzeug shutdown hook
        pass
```

> **Nota implementação:** usar `porta_livre()` fixa em teste (5099) ou `make_server` do werkzeug para shutdown limpo.

- [ ] **Step 2: Implement `iniciar_servidor_em_thread` em assistente.py**

```python
def iniciar_servidor_em_thread(flask_app, host, port):
    def _run():
        flask_app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
```

- [ ] **Step 3: Refatorar `_iniciar_assistente` em Transkriptor.pyw**

Ordem correta:
1. `porta = assistente.porta_livre()`
2. `thread = assistente.iniciar_servidor_em_thread(app, "127.0.0.1", porta)`
3. `_aguardar_servidor(url, timeout=10)` — loop retry 0.5s
4. `webbrowser.open(url)`
5. **Não** chamar `app.run()` novamente na thread principal

- [ ] **Step 4: Run tests + manual 3×**

- [ ] **Step 5: Commit**

```bash
git commit -m "fix(FR-1.1): corrige ordem startup assistente Flask"
```

---

### Task 1.3: Anti-XSS buildSelectOptions

**Files:**
- Modify: `assistente.py` (bloco JS)

- [ ] **Step 1: Extrair helper testável (opcional Python mirror para teste)**

Criar `tests/test_escape_html.py` com função Python `escape_html` espelhada no JS ou testar via Flask route de teste.

- [ ] **Step 2: Substituir innerHTML no loadList**

```javascript
function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function buildSelectOptions(items) {
  selTrans.replaceChildren();
  for (const t of items) {
    const opt = document.createElement('option');
    opt.value = t.arquivo;
    opt.textContent = `${t.data} — ${t.preview || '(vazio)'}`;
    selTrans.appendChild(opt);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git commit -m "fix(SEC-2): elimina innerHTML com dados de transcricao"
```

**GATE F1:** `python scripts/verificar_fase.py --fase 1`

---

## Fase 2 — Engenharia P1

### Task 2.1: Ícone erro (TDD com mock)

**Files:**
- Modify: `Transkriptor.pyw`
- Create: `tests/test_Transkriptor_estado.py`

- [ ] **Step 1: Test que `_resolver_estado_icone` retorna `erro`**

Extrair lógica pura:

```python
def resolver_estado_icone(transcritor, deteccao_ativa, em_erro=False):
    if em_erro: return "erro", "Erro"
    if transcritor and getattr(transcritor, "diarizando", False):
        return "diarizando", "Separando vozes..."
    ...
```

- [ ] **Step 2: `_erro_critico` seta `self._em_erro=True` + timer 30s**

- [ ] **Step 3: Estado pausado → cor `COR_PAUSADO = (100, 116, 139)`**

**GATE F2:** `python scripts/verificar_fase.py --fase 2`

---

### Task 2.2: DEVICE_WHISPER

**Files:**
- Modify: `config.py`, `transcricao_core.py`
- Create: `tests/test_config_device.py`

```python
def resolver_device_whisper(valor: str) -> str:
    if valor != "auto":
        return valor
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"
```

**GATE F2 (continuação)**

---

### Task 2.3: Mutex + log rotation + instalar.bat

**Files:**
- Modify: `Transkriptor.pyw`, `instalar.bat`
- Create: `scripts/resolver_pythonw.py`, `tests/test_mutex.py`

```python
# tests/test_mutex.py
def test_segundo_lock_falha(tmp_path):
    from Transkriptor_lock import adquirir_lock  # extrair módulo pequeno
    lock1 = tmp_path / "t.lock"
    assert adquirir_lock(lock1) is True
    assert adquirir_lock(lock1) is False
```

---

## Fase 3 — UX Bandeja

### Task 3.1: Toast ao vivo

**Files:**
- Modify: `Transkriptor.pyw`, `transcricao_core.py`

Lógica em `_status`:
```python
if msg and not msg.startswith(("Watchdog", "Carregando", "ERRO")):
    if self._meet_em_foco() is False and len(msg) > 10:
        notificar("Transkriptor", msg[:60] + ("..." if len(msg) > 60 else ""))
```

### Task 3.2–3.5: Menu items + diarização progresso

**GATE F3:** `python scripts/verificar_fase.py --fase 3`

---

## Fase 4 — UX Assistente

### Task 4.1: Timer 15s + progress bar

**Files:** `assistente.py` CSS + JS

```javascript
if (seg >= 15 && firstToken) {
  timerEl.textContent = 'O modelo está pensando... (' + seg + 's)';
}
```

### Task 4.2: Mobile drawer + keyboard nav

**GATE F4:** `python scripts/verificar_fase.py --fase 4`

---

## Fase 5 — Segurança Avançada

### Task 5.1: Token sessão

```python
# assistente.py
SESSAO_TOKEN = os.environ.get("Transkriptor_TOKEN") or secrets.token_urlsafe(32)

@app.before_request
def verificar_token():
    if request.path.startswith("/api/"):
        if request.headers.get("X-Transkriptor-Token") != SESSAO_TOKEN:
            return jsonify({"erro": "Token inválido"}), 403
```

**GATE F5:** `python scripts/verificar_fase.py --fase 5`

---

## Fase 6 — Manutenção

### Task 6.1: .gitignore + VERIFICACAO.md

**GATE F6:** `python scripts/verificar_fase.py --fase 6`

---

## Fase 7 — Identificação da Voz do Usuário

> **Contexto:** loopback = áudio do alto-falante (outros participantes). Sua voz exige
> microfone + perfil cadastrado. Reusa ECAPA-TDNN (`speechbrain`) já usado em `diarizador.py`.

### Task 7.1: identificador_voz.py (TDD)

**Files:**
- Create: `identificador_voz.py`
- Modify: `config.py`
- Create: `tests/test_identificador_voz.py`

**Interfaces:**
- Produces: `salvar_perfil(embedding, path)`, `carregar_perfil(path) -> ndarray|None`
- Produces: `identificar_cluster(centroides: list[ndarray], perfil: ndarray, limiar: float) -> int|None`
- Produces: `extrair_embedding_perfil(encoder, audio_float32) -> ndarray` (wrap diarizador)

- [ ] **Step 1: Write failing tests**

```python
import numpy as np
from identificador_voz import salvar_perfil, carregar_perfil, identificar_cluster

def test_salvar_carregar_roundtrip(tmp_path):
    emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    p = tmp_path / "perfil.npz"
    salvar_perfil(emb, p)
    loaded = carregar_perfil(p)
    assert np.allclose(loaded, emb)

def test_identificar_cluster_mais_similar():
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    centroides = [
        np.array([0.0, 1.0], dtype=np.float32),  # cluster 0 — diferente
        np.array([0.95, 0.05], dtype=np.float32),  # cluster 1 — similar
    ]
    idx = identificar_cluster(centroides, perfil, limiar=0.72)
    assert idx == 1

def test_identificar_cluster_abaixo_limiar_retorna_none():
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    centroides = [np.array([0.0, 1.0], dtype=np.float32)]
    assert identificar_cluster(centroides, perfil, limiar=0.72) is None
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# identificador_voz.py
import numpy as np

def _cosseno(a, b):
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    return float(np.dot(a, b))

def salvar_perfil(embedding, path):
    np.savez(path, embedding=embedding.astype(np.float32), versao=1)

def carregar_perfil(path):
    if not path.exists():
        return None
    data = np.load(path)
    return data["embedding"]

def identificar_cluster(centroides, perfil, limiar=0.72):
    melhor, melhor_sim = None, -1.0
    for i, c in enumerate(centroides):
        sim = _cosseno(c, perfil)
        if sim > melhor_sim:
            melhor, melhor_sim = i, sim
    return melhor if melhor_sim >= limiar else None
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(FR-7.1): modulo identificador_voz com matching por cosseno"
```

---

### Task 7.2: Captura paralela do microfone

**Files:**
- Modify: `transcricao_core.py`
- Create: `tests/test_captura_mic.py`

**Interfaces:**
- Consumes: `config.CAPTURAR_MIC`, `config.SAMPLE_RATE`
- Produces: `Transcritor._caminho_wav_mic`, método `_capturar_mic()`

- [ ] **Step 1: Test — WAV mic criado quando flag True**

```python
def test_abrir_arquivo_cria_mic_wav_quando_habilitado(monkeypatch, tmp_path):
    monkeypatch.setattr("config.CAPTURAR_MIC", True)
    # mock soundcard; assert _caminho_wav_mic ends with _mic.wav
```

- [ ] **Step 2: Implement thread `_capturar_mic`** — espelha `_capturar` mas usa `sc.default_microphone()` sem loopback.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(FR-7.5): grava microfone paralelo em _mic.wav"
```

---

### Task 7.3: Integrar VOCÊ na diarização

**Files:**
- Modify: `diarizador.py`, `transcricao_core.py`
- Create: `tests/test_diarizacao_voce.py`

- [ ] **Step 1: Test com embeddings mock**

```python
def test_diarizar_rotula_voce_quando_perfil_match():
    # segmentos + trechos mock + perfil → resultado contém ("VOCÊ", ...)
```

- [ ] **Step 2: Após clustering, calcular centróide por label e chamar `identificar_cluster`**

- [ ] **Step 3: Reforço RMS** — função `_segmento_tem_voz_mic(mic_wav, start, end, limiar_rms)`

```python
def _rms(trecho):
    return float(np.sqrt(np.mean(trecho ** 2))) if trecho.size else 0.0
```

- [ ] **Step 4: Escrever `[VOCÊ mm:ss-mm:ss] texto` em `_diarizado.txt`**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(FR-7.6): rotula falas do usuario como VOCE na diarizacao"
```

---

### Task 7.4: Wizard cadastro na bandeja

**Files:**
- Modify: `Transkriptor.pyw`, `identificador_voz.py`

- [ ] **Step 1: Menu "Cadastrar minha voz"**

Fluxo:
1. Toast: "Fale por 20 segundos após o sinal..."
2. Thread grava mic 20s → lista de chunks float32
3. `extrair_embedding_perfil` média de embeddings por chunk
4. `salvar_perfil` em `config.ARQUIVO_PERFIL_VOZ`
5. Toast sucesso

Texto sugerido na notificação:
> "Olá, esta é a minha voz para o Transkriptor identificar minhas falas nas reuniões..."

- [ ] **Step 2: Menus toggle + apagar perfil (FR-7.9, FR-7.10)**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(FR-7.4): wizard cadastro de voz na bandeja"
```

**GATE F7:** `python scripts/verificar_fase.py --fase 7`

**GATE FINAL:** `python scripts/verificar_fase.py --fase all`

---

## Self-Review (spec coverage)

| Spec ID | Task |
|---------|------|
| FR-0.* | 0.1–0.4 |
| FR-1.* | 1.1–1.3 |
| FR-2.* | 2.1–2.3 |
| FR-3.* | 3.1–3.5 |
| FR-4.* | 4.1–4.2 |
| FR-5.* | 5.1 |
| FR-6.* | 6.1 |
| FR-7.* | 7.1–7.4 |
| SEC-1,2 | 1.1, 1.3 |
| SEC-4 | 5.1 |
| SEC-7 | 7.1 |
| UX-3.* | 7.4 |

**Gaps intencionais (v1.3):** FR-4.7 markdown, FR-6.4 teste 24h manual, FR-7.11 badge assistente

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-08-Transkriptor-v1.2-audit-remediation.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per `T-*` task, review between tasks
2. **Inline Execution** — execute phase-by-phase in this session with gate checkpoints

**Which approach?**