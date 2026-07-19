#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificação de launch duplicado — Fase 2 step 5."""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "Transkriptor.log"
LOCK = REPO / "Transkriptor.lock"


def _iniciar_Transkriptor(pyw):
    script = REPO / "Transkriptor.pyw"
    subprocess.run(
        [
            "powershell",
            "-Command",
            f'Start-Process -FilePath "{pyw}" '
            f'-ArgumentList "{script}" '
            f'-WorkingDirectory "{REPO}" -WindowStyle Hidden',
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


def _contar_processos():
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { ($_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe') "
        "-and $_.CommandLine -like '*Transkriptor.pyw*' } | Measure-Object | "
        "Select-Object -ExpandProperty Count"
    )
    r = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True, cwd=REPO)
    try:
        return int(r.stdout.strip() or "0")
    except ValueError:
        return -1


def _matar_processos():
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*Transkriptor.pyw*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-Command", ps], cwd=REPO)
    for _ in range(20):
        if _contar_processos() == 0:
            break
        time.sleep(0.5)
    if LOCK.is_file():
        try:
            LOCK.unlink()
        except OSError:
            pass


def _linhas_log():
    if not LOG.is_file():
        return 0
    return len(LOG.read_text(encoding="utf-8", errors="replace").splitlines())


def main():
    print("=== F2 bandeja launch verification ===")
    _matar_processos()
    time.sleep(1)
    pre = _contar_processos()
    print(f"processes_before_launch={pre}")
    if pre != 0:
        print("FAIL: processos Transkriptor ainda ativos apos kill")
        return 1
    antes = _linhas_log()
    pyw = subprocess.check_output([sys.executable, str(REPO / "scripts" / "resolver_pythonw.py")], text=True).strip()
    print(f"pythonw={pyw}")
    _iniciar_Transkriptor(pyw)
    time.sleep(12)
    texto = LOG.read_text(encoding="utf-8", errors="replace") if LOG.is_file() else ""
    depois1 = len(texto.splitlines())
    proc1 = _contar_processos()
    print(f"after_launch1 log_lines={depois1} delta={depois1 - antes} processes={proc1}")
    novas = texto.splitlines()[antes:]
    if not any("Transkriptor iniciado" in ln for ln in novas):
        print("FAIL: log nao recebeu Transkriptor iniciado")
        print(f"novas_linhas={novas[-5:]}")
        _matar_processos()
        return 1
    if proc1 != 1:
        print(f"FAIL: esperado 1 processo, obteve {proc1}")
        return 1
    _iniciar_Transkriptor(pyw)
    time.sleep(12)
    proc2 = _contar_processos()
    texto2 = LOG.read_text(encoding="utf-8", errors="replace") if LOG.is_file() else ""
    print(f"after_launch2 processes={proc2}")
    if proc2 != 1:
        print(f"FAIL: segunda instancia criou processo extra ({proc2})")
        _matar_processos()
        return 1
    if "Segunda instancia bloqueada pelo mutex." not in texto2:
        print("FAIL: log sem mensagem de mutex na segunda instancia")
        _matar_processos()
        return 1
    tail = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]
    print("log_tail:")
    for ln in tail:
        print(f"  {ln}")
    print("PASS: mutex bloqueou segunda instancia")
    _matar_processos()
    return 0


if __name__ == "__main__":
    sys.exit(main())