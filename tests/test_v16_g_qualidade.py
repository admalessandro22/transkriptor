# -*- coding: utf-8 -*-
"""F11.G — Qualidade técnica (T-11.G1/G2)."""
import py_compile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_limite_500_linhas():
    for caminho in sorted(list(REPO.glob("*.py")) + list(REPO.glob("*.pyw"))):
        if caminho.name == "conftest.py":
            continue
        linhas = len(caminho.read_text(encoding="utf-8").splitlines())
        assert linhas <= 500, f"{caminho.name}: {linhas} linhas >500 (NFR-11.G1)"


def test_py_compile_tres_editados():
    for nome in ["app_bandeja_menu.py", "transkriptor_menu_flows.py", "consentimento_gravacao.py"]:
        py_compile.compile(str(REPO / nome), doraise=True)


def test_compileall_raiz():
    import compileall
    assert compileall.compile_dir(str(REPO), quiet=1)


def test_tmp_path_isolation_existe():
    # SEC-11.G1: fixtures usam tmp_path
    conftest = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "tmp_path" in conftest
    assert "config_user" in conftest or "transkriptor.log" in conftest


def test_sem_plyer():
    req = (REPO / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "plyer" not in req
    notificador = (REPO / "notificador.py").read_text(encoding="utf-8").lower()
    assert "plyer" not in notificador


def test_assistente_host_local():
    # Flask sempre 127.0.0.1
    assistente = (REPO / "assistente.py").read_text(encoding="utf-8")
    assert '127.0.0.1' in assistente
    assert '0.0.0.0' not in assistente


def test_detect_zero_warnings_css_js():
    # v1.9 (T-14.F2): o CSS vive em static/css/*.css — o contrato vale para o conjunto.
    partes = [p.read_text(encoding="utf-8") for p in sorted((REPO / "static" / "css").glob("*.css"))]
    css = "".join(partes).lower()
    assert "bounce" not in css
    assert "color-scheme" in css
