#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate de verificação por fase — Transkriptor SDD."""
import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FASES = {
    0: ["tests/test_detector_meet.py", "tests/test_fixtures.py"],
    1: ["tests/test_assistente_seguranca.py", "tests/test_assistente_startup.py"],
    2: ["tests/test_config_device.py", "tests/test_mutex.py", "tests/test_transkiptor_estado.py"],
    3: ["tests/test_crypto_storage.py", "tests/test_transcricao_crypto.py"],
    4: [
        "tests/test_notificador.py",
        "tests/test_diarizador_progresso.py",
        "tests/test_assistente_api.py",
    ],
    5: ["tests/test_token_sessao.py", "tests/test_detector_meet_visivel.py"],
    6: ["tests/test_gitignore_docs.py"],
    7: [
        "tests/test_identificador_voz.py",
        "tests/test_captura_mic.py",
        "tests/test_diarizacao_voce.py",
        "tests/test_assistente_badge_voce.py",
    ],
    8: [
        "tests/test_meet_bridge.py",
        "tests/test_correlacionador.py",
        "tests/test_renomear_falante_flow.py",
        "tests/test_config_portas.py",
    ],
    "estabilidade": [
        "tests/test_bandeja_lifecycle.py",
        "tests/test_detector_meet.py",
        "tests/test_integracao_monitor_meet.py",
        "tests/test_atalho_desktop.py",
    ],
    "v1.5-estatico": [
        "tests/test_versao.py",
        "tests/test_manual_usuario.py",
        "tests/test_limite_linhas.py",
        "tests/test_fluxo_reuniao_v15.py",
    ],
    "v1.6-estatico": [
        "tests/test_v16_a_tokens.py",
        "tests/test_v16_b_assistente.py",
        "tests/test_v16_c_a11y.py",
        "tests/test_v16_d_bandeja.py",
        "tests/test_v16_e_dialogs.py",
        "tests/test_v16_f_consentimento.py",
        "tests/test_v16_g_qualidade.py",
        "tests/test_limite_linhas.py",
        "tests/test_versao.py",
    ],
}


def main():
    parser = argparse.ArgumentParser(description="Verifica gate de fase SDD")
    parser.add_argument(
        "--fase",
        required=True,
        help="Número da fase (0-8), 'estabilidade', 'v1.5-estatico' ou 'all'",
    )
    args = parser.parse_args()

    if args.fase == "all":
        files = sorted({f for fl in FASES.values() for f in fl})
    elif args.fase in FASES:
        files = FASES[args.fase]
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

    missing = [f for f in files if not (REPO / f).is_file()]
    if missing:
        print(f"TESTES AUSENTES: {missing}", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "pytest", *files, "-v", "--tb=short"]
    print(f"Executando: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=REPO)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
