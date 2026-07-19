#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificação live do assistente Flask — Fase 1 (step 4 do plano)."""
import json
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from assistente import aguardar_servidor, app, iniciar_servidor_em_thread


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    porta = _porta_livre()
    host = "127.0.0.1"
    base = f"http://{host}:{porta}"
    print(f"=== F1 live launch on {base} ===")

    thread = iniciar_servidor_em_thread(app, host, porta)
    print(f"thread_started daemon={thread.daemon} alive={thread.is_alive()}")

    ok = aguardar_servidor(base, timeout=10, intervalo=0.5)
    print(f"aguardar_servidor={ok}")
    if not ok:
        print("FAIL: servidor nao respondeu em 10s")
        return 1

    req = urllib.request.Request(base, method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode("utf-8")
    has_select = 'id="transcricao"' in html
    has_build = "buildSelectOptions" in html
    print(f"GET / status={resp.status} has_select={has_select} has_buildSelectOptions={has_build}")
    if not has_select:
        print("FAIL: HTML sem select de transcricao")
        return 1

    payload = json.dumps(
        {
            "modelo": "test",
            "transcricao": "../../etc/passwd",
            "pergunta": "probe",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        print("FAIL: POST /api/chat deveria retornar 403")
        return 1
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        data = json.loads(body)
        print(f"POST /api/chat status={e.code} body={data}")
        if e.code != 403:
            print("FAIL: status esperado 403")
            return 1
        if data.get("erro") != "Acesso negado":
            print("FAIL: corpo JSON esperado Acesso negado")
            return 1

    print("PASS: live launch checks OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())