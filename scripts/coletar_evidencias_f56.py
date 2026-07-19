#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta evidências das Fases 5 e 6 para o scratch do goal."""
import json
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from assistente import HEADER_TOKEN, aguardar_servidor, app, iniciar_servidor_em_thread, obter_token_sessao


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _api_f5_checks(scratch: Path):
    pasta = Path(tempfile.mkdtemp(prefix="tkpt_f5_"))
    (pasta / "ok.txt").write_text("x" * 50, encoding="utf-8")
    (pasta / "grande.txt").write_text("A" * 5000, encoding="utf-8")
    import assistente

    assistente.PASTA_TRANSCRICOES = str(pasta)
    token = obter_token_sessao()
    headers = {HEADER_TOKEN: token}
    client = app.test_client()
    runs = []
    for i in range(1, 3):
        sem = client.post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "ok.txt", "pergunta": "q"},
        )
        com = client.post(
            "/api/chat",
            json={"modelo": "m", "transcricao": "ok.txt", "pergunta": "q"},
            headers=headers,
        )
        assistente.MAX_CHARS_TRANSCRICAO = 1000
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = MagicMock(
            return_value=iter([b'{"message":{"content":"r"},"done":true}\n'])
        )
        with patch("assistente.urllib.request.urlopen", return_value=mock_resp):
            trunc = client.post(
                "/api/chat",
                json={"modelo": "m", "transcricao": "grande.txt", "pergunta": "q"},
                headers=headers,
            )
            trunc_body = trunc.get_data(as_text=True)
        runs.append({
            "run": i,
            "sem_token_status": sem.status_code,
            "sem_token_erro": sem.get_json().get("erro"),
            "com_token_status": com.status_code,
            "truncada_header": trunc.headers.get("X-Transkriptor-Truncada"),
            "truncada_body_snippet": trunc_body[:80],
        })
    out = scratch / "api_f5_checks.json"
    out.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    return runs


def _launch(scratch: Path):
    porta = _porta_livre()
    host = "127.0.0.1"
    base = f"http://{host}:{porta}"
    token = obter_token_sessao()
    linhas = [f"=== F5/F6 live launch on {base} ==="]
    try:
        thread = iniciar_servidor_em_thread(app, host, porta)
        linhas.append(f"thread_started daemon={thread.daemon} alive={thread.is_alive()}")
        ok = aguardar_servidor(base, timeout=10, intervalo=0.5)
        linhas.append(f"aguardar_servidor={ok}")
        if not ok:
            linhas.append("FAIL: servidor nao respondeu")
            (scratch / "launch_f56.log").write_text("\n".join(linhas), encoding="utf-8")
            return False
        for run in (1, 2):
            try:
                urllib.request.urlopen(f"{base}/api/transcricoes", timeout=5)
                linhas.append(f"run{run} sem_token FAIL deveria ser 403")
                (scratch / "launch_f56.log").write_text("\n".join(linhas), encoding="utf-8")
                return False
            except urllib.error.HTTPError as e:
                linhas.append(f"run{run} sem_token status={e.code}")
            req = urllib.request.Request(
                f"{base}/api/transcricoes",
                headers={HEADER_TOKEN: token},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8")
            linhas.append(f"run{run} com_token status={resp.status} body_len={len(body)}")
        linhas.append("PASS: launch F5/F6 OK")
        (scratch / "launch_f56.log").write_text("\n".join(linhas), encoding="utf-8")
        return True
    except Exception as exc:
        linhas.append(f"ERROR: {type(exc).__name__}: {exc}")
        (scratch / "launch_f56.log").write_text("\n".join(linhas), encoding="utf-8")
        return False


def main():
    if len(sys.argv) < 2:
        print("Uso: coletar_evidencias_f56.py <scratch_dir>", file=sys.stderr)
        return 1
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)

    r1 = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_token_sessao.py",
         "tests/test_detector_meet_visivel.py", "-v", "--tb=short"],
        cwd=REPO, capture_output=True, text=True,
    )
    (scratch / "pytest_f5.log").write_text(r1.stdout + r1.stderr, encoding="utf-8")

    for nome in ("gate_f5_run1.log", "gate_f5_run2.log"):
        r = subprocess.run(
            [sys.executable, "scripts/verificar_fase.py", "--fase", "5"],
            cwd=REPO, capture_output=True, text=True,
        )
        (scratch / nome).write_text(r.stdout + r.stderr, encoding="utf-8")

    r6 = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_gitignore_docs.py", "-v", "--tb=short"],
        cwd=REPO, capture_output=True, text=True,
    )
    (scratch / "pytest_f6.log").write_text(r6.stdout + r6.stderr, encoding="utf-8")

    for nome in ("gate_f6_run1.log", "gate_f6_run2.log"):
        r = subprocess.run(
            [sys.executable, "scripts/verificar_fase.py", "--fase", "6"],
            cwd=REPO, capture_output=True, text=True,
        )
        (scratch / nome).write_text(r.stdout + r.stderr, encoding="utf-8")

    _api_f5_checks(scratch)
    launch_ok = _launch(scratch)
    ok = r1.returncode == 0 and r6.returncode == 0 and launch_ok
    print(f"pytest_f5 exit={r1.returncode} pytest_f6 exit={r6.returncode} launch={launch_ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())