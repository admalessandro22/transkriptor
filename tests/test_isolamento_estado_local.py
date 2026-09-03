# -*- coding: utf-8 -*-
"""SEC-10.F3 — prova de que a suíte não altera o estado real do usuário."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_suite_controlada_nao_altera_estado_real(snapshot_estado_real):
    antes = snapshot_estado_real()
    resultado = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_config_user_modulo.py",
            "tests/test_crypto_storage.py",
            "-q",
            "--tb=short",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert snapshot_estado_real() == antes
