#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta evidências da Fase 4 para o scratch do goal."""
import json
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from assistente import HTML, aguardar_servidor, app, iniciar_servidor_em_thread


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _api_json(scratch: Path):
    pasta = Path(tempfile.mkdtemp(prefix="tkpt_f4_"))
    arquivo = pasta / "transcricao_2026-07-08_10h00.txt"
    arquivo.write_text(
        "=== Transcricao iniciada em 2026-07-08 10:00:00 ===\n\n"
        "[10:00:01] Ola equipe\n",
        encoding="utf-8",
    )
    import assistente

    assistente.PASTA_TRANSCRICOES = str(pasta)
    client = app.test_client()
    runs = []
    for i in range(1, 3):
        resp = client.get("/api/transcricoes")
        dados = resp.get_json()
        runs.append({"run": i, "status": resp.status_code, "body": dados})
    out = scratch / "api_transcricoes.json"
    out.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    return runs


def _html_check(scratch: Path):
    checks = []
    def chk(nome, ok, detalhe=""):
        checks.append({"check": nome, "ok": ok, "detail": detalhe})

    chk("progress-bar class", ".progress-bar" in HTML)
    chk("timer pensando 15s", "O modelo está pensando" in HTML)
    inicio = HTML.find("function iniciarTimer")
    bloco_timer = HTML[inicio : inicio + 600] if inicio != -1 else ""
    chk("timer seg>=15", "15" in bloco_timer and "O modelo está pensando" in bloco_timer)
    inicio = HTML.find("function mostrarBotoes")
    bloco_busy = HTML[inicio : inicio + 400] if inicio != -1 else ""
    chk("progress bar ligado a busy", "progress" in bloco_busy.lower())
    chk("menu toggle hamburger", "☰" in HTML or "menu-toggle" in HTML)
    chk("media 375px", "375px" in HTML)
    inicio = HTML.find("function navegarActionCards")
    bloco_nav = HTML[inicio : inicio + 600] if inicio != -1 else ""
    chk("arrow nav action-card", "ArrowDown" in bloco_nav and "action-card" in bloco_nav)
    chk("nav ignora textarea", "TEXTAREA" in bloco_nav)
    chk("nav nao rouba foco", "cards[0].focus" not in bloco_nav)
    chk("botao copiar", "copiar" in HTML.lower())
    chk("tamanho_kb label", "tamanho_kb" in HTML or "tamanho-kb" in HTML)

    linhas = []
    all_ok = True
    for c in checks:
        status = "PASS" if c["ok"] else "FAIL"
        if not c["ok"]:
            all_ok = False
        linhas.append(f"[{status}] {c['check']}" + (f" — {c['detail']}" if c["detail"] else ""))
    linhas.append(f"\nRESULTADO: {'TODOS OK' if all_ok else 'FALHAS DETECTADAS'}")
    (scratch / "html_f4_check.txt").write_text("\n".join(linhas), encoding="utf-8")
    return all_ok


def _launch(scratch: Path):
    porta = _porta_livre()
    host = "127.0.0.1"
    base = f"http://{host}:{porta}"
    linhas = [f"=== F4 live launch on {base} ==="]
    try:
        thread = iniciar_servidor_em_thread(app, host, porta)
        linhas.append(f"thread_started daemon={thread.daemon} alive={thread.is_alive()}")
        ok = aguardar_servidor(base, timeout=10, intervalo=0.5)
        linhas.append(f"aguardar_servidor={ok}")
        if not ok:
            linhas.append("FAIL: servidor nao respondeu em 10s")
            (scratch / "launch_f4.log").write_text("\n".join(linhas), encoding="utf-8")
            return False
        for run in (1, 2):
            with urllib.request.urlopen(base, timeout=5) as resp:
                html = resp.read().decode("utf-8")
            has_brand = "Transkriptor" in html
            has_progress = "progress-bar" in html
            has_menu = "menu-toggle" in html
            linhas.append(
                f"run{run} GET / status={resp.status} len={len(html)} "
                f"Transkriptor={has_brand} progress-bar={has_progress} menu-toggle={has_menu}"
            )
            if not has_brand or len(html) < 100:
                linhas.append(f"FAIL run{run}: HTML invalido")
                (scratch / "launch_f4.log").write_text("\n".join(linhas), encoding="utf-8")
                return False
            with urllib.request.urlopen(f"{base}/api/transcricoes", timeout=5) as resp:
                api_body = resp.read().decode("utf-8")
            linhas.append(f"run{run} GET /api/transcricoes status={resp.status} body_len={len(api_body)}")
        linhas.append("PASS: live launch checks OK")
        (scratch / "launch_f4.log").write_text("\n".join(linhas), encoding="utf-8")
        return True
    except Exception as exc:
        linhas.append(f"ERROR: {type(exc).__name__}: {exc}")
        (scratch / "launch_f4.log").write_text("\n".join(linhas), encoding="utf-8")
        return False


def main():
    if len(sys.argv) < 2:
        print("Uso: coletar_evidencias_f4.py <scratch_dir>", file=sys.stderr)
        return 1
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)
    runs = _api_json(scratch)
    print(f"api_transcricoes.json: {len(runs)} runs")
    html_ok = _html_check(scratch)
    print(f"html_f4_check: {'OK' if html_ok else 'FAIL'}")
    launch_ok = _launch(scratch)
    print(f"launch_f4: {'OK' if launch_ok else 'FAIL/ERROR'}")
    return 0 if html_ok else 1


if __name__ == "__main__":
    sys.exit(main())