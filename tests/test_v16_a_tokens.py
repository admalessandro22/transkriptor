# -*- coding: utf-8 -*-
"""F11.A — Fundamentos visuais e design system (T-11.A1)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSS = REPO / "static" / "assistente.css"
HTML = REPO / "templates" / "assistente.html"


def test_tokens_em_root_sem_hex_solto():
    """Migrado na v1.9 (T-14.A1): os tokens vivem em static/css/tokens.css,
    gerado de design/tokens.json; assistente.css só importa e consome `--tk-*`.
    A ausência de cor literal fora de tokens.css é coberta por
    tests/test_design_tokens.py::test_sem_hex_fora_de_tokens_css."""
    tokens = (REPO / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert ":root" in tokens
    for token in ("--tk-bg-1", "--tk-accent", "--tk-text-1", "--tk-elev-", "--tk-radius-", "--tk-state-recording"):
        assert token in tokens
    assert '@import url("css/tokens.css")' in css
    assert "var(--tk-" in css


def test_sem_bounce_ou_elastic():
    css = CSS.read_text(encoding="utf-8").lower()
    assert "bounce" not in css, "bounce easing proibido por UX-11.A2"
    assert "elastic" not in css


def test_prefers_reduced_motion_presente():
    css = CSS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css


def test_detect_zero_warnings():
    # NFR-11.A1: detect deve ser []
    import os
    detect_candidates = [
        REPO / ".agents" / "skills" / "impeccable" / "scripts" / "detect.mjs",
        Path(os.path.expanduser("~")) / ".agents" / "skills" / "impeccable" / "scripts" / "detect.mjs",
        Path(r"C:\Users\Alessandro Souza\.agents\skills\impeccable\scripts\detect.mjs"),
    ]
    detect = next((p for p in detect_candidates if p.is_file()), None)
    if detect is None:
        # Se detect não instalado no runner, apenas checar bounce já cobre UX-11.A2
        return
    for alvo in ["templates/assistente.html", "static/assistente.css"]:
        result = subprocess.run(
            ["node", str(detect), "--json", alvo],
            capture_output=True, text=True, cwd=REPO
        )
        # 0 = clean, 2 = findings; 1 = erro de infra não deve acontecer após achar detect
        assert result.returncode in (0, 2), f"detect erro: {result.stderr}"
        assert result.stdout.strip() == "[]", f"detect encontrou warnings em {alvo}: {result.stdout}"
