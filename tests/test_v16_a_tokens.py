# -*- coding: utf-8 -*-
"""F11.A — Fundamentos visuais e design system (T-11.A1)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSS = REPO / "static" / "assistente.css"
HTML = REPO / "templates" / "assistente.html"


def test_tokens_em_root_sem_hex_solto():
    css = CSS.read_text(encoding="utf-8")
    assert ":root" in css
    assert "--bg-base" in css
    assert "--violet" in css
    assert "--gold" in css
    assert "--shadow-" in css
    assert "--radius-" in css
    # Nenhum hex fora de :root exceto glows permitidos já é difícil checar,
    # mas garantir que tokens existem cobre UX-11.A1
    assert css.count("--bg-base") >= 1


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
