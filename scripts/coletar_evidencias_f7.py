#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta evidências da Fase 7 para o scratch do goal."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from diarizador import aplicar_identificacao_usuario, diarizar
from identificador_voz import carregar_perfil, identificar_cluster, salvar_perfil


def _perfil_checks(scratch: Path):
    runs = []
    for i in range(1, 3):
        emb = np.array([float(i), 0.5, 0.25], dtype=np.float32)
        path = scratch / f"perfil_run{i}.npz"
        salvar_perfil(emb, path)
        loaded = carregar_perfil(path)
        centroides = [
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
            emb,
        ]
        idx = identificar_cluster(centroides, emb, limiar=0.72)
        runs.append({
            "run": i,
            "roundtrip_ok": bool(loaded is not None and np.allclose(loaded, emb)),
            "cluster_idx": idx,
        })
    out = scratch / "perfil_voz_checks.json"
    out.write_text(json.dumps(runs, indent=2), encoding="utf-8")
    return runs


def _diarizacao_sample(scratch: Path):
    resultado = [
        ("FALANTE_00", 0.0, 1.0, "outro"),
        ("FALANTE_01", 1.0, 2.0, "eu"),
    ]
    centroides = [
        np.array([0.0, 1.0], dtype=np.float32),
        np.array([0.95, 0.05], dtype=np.float32),
    ]
    perfil = np.array([1.0, 0.0], dtype=np.float32)
    com_perfil = aplicar_identificacao_usuario(
        resultado, centroides, perfil, limiar=0.72, rotulo_usuario="VOCÊ"
    )
    sem_perfil = aplicar_identificacao_usuario(resultado, centroides, None, limiar=0.72)
    linhas = [
        "=== com perfil ===",
        *[f"{r[0]} {r[1]}-{r[2]} {r[3]}" for r in com_perfil],
        "=== sem perfil ===",
        *[f"{r[0]} {r[1]}-{r[2]} {r[3]}" for r in sem_perfil],
    ]
    texto = "\n".join(linhas)
    (scratch / "diarizacao_voce_sample.txt").write_text(texto, encoding="utf-8")
    return "VOCÊ" in texto and "FALANTE_01" in texto.split("sem perfil")[-1]


def _menu_check(scratch: Path):
    texto = (REPO / "Transkriptor.pyw").read_text(encoding="utf-8")
    checks = [
        ("cadastrar_minha_voz", "cadastrar_minha_voz" in texto),
        ("20s", "20s" in texto or "DURACAO_CADASTRO_SEG" in texto),
        ("alternar_identificar_voz", "alternar_identificar_voz" in texto),
        ("apagar_perfil_voz", "apagar_perfil_voz" in texto),
        ("Perfil de voz salvo", "Perfil de voz salvo" in texto),
    ]
    linhas = [f"[{'PASS' if ok else 'FAIL'}] {nome}" for nome, ok in checks]
    linhas.append(f"RESULTADO: {'OK' if all(ok for _, ok in checks) else 'FALHAS'}")
    (scratch / "menu_f7_check.txt").write_text("\n".join(linhas), encoding="utf-8")
    return all(ok for _, ok in checks)


def main():
    if len(sys.argv) < 2:
        print("Uso: coletar_evidencias_f7.py <scratch_dir>", file=sys.stderr)
        return 1
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)

    r = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/test_identificador_voz.py",
            "tests/test_captura_mic.py",
            "tests/test_diarizacao_voce.py",
            "-v", "--tb=short",
        ],
        cwd=REPO, capture_output=True, text=True,
    )
    (scratch / "pytest_f7.log").write_text(r.stdout + r.stderr, encoding="utf-8")

    for nome in ("gate_f7_run1.log", "gate_f7_run2.log"):
        g = subprocess.run(
            [sys.executable, "scripts/verificar_fase.py", "--fase", "7"],
            cwd=REPO, capture_output=True, text=True,
        )
        (scratch / nome).write_text(g.stdout + g.stderr, encoding="utf-8")

    _perfil_checks(scratch)
    diar_ok = _diarizacao_sample(scratch)
    menu_ok = _menu_check(scratch)
    ok = r.returncode == 0 and diar_ok and menu_ok
    print(f"pytest exit={r.returncode} diar={diar_ok} menu={menu_ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())