# -*- coding: utf-8 -*-
"""T-F7-01 — helper do instalador."""
import subprocess
from types import SimpleNamespace

from scripts.instalar_helper import (
    comando_torch,
    ollama_status,
    python_compativel,
    tem_gpu_nvidia,
)


def test_python_312_ok():
    ok, msg = python_compativel(SimpleNamespace(major=3, minor=12))
    assert ok
    assert "OK" in msg


def test_python_311_reprovado():
    ok, msg = python_compativel(SimpleNamespace(major=3, minor=11))
    assert not ok
    assert "3.12" in msg
    assert "ERRO" in msg


def test_gpu_presente_ausente():
    assert tem_gpu_nvidia(lambda cmd: SimpleNamespace(returncode=0, stdout="GPU 0: GTX\n"))
    assert not tem_gpu_nvidia(lambda cmd: SimpleNamespace(returncode=1, stdout=""))


def test_ollama_ramos():
    c, m = ollama_status(lambda cmd: (_ for _ in ()).throw(FileNotFoundError()))
    assert c == "aviso" and "Ollama" in m
    c, m = ollama_status(lambda cmd: SimpleNamespace(returncode=1, stdout="", stderr="x"))
    assert c == "aviso"
    c, m = ollama_status(
        lambda cmd: SimpleNamespace(returncode=0, stdout="NAME\nllama3.1:8b\n", stderr="")
    )
    assert c == "ok"


def test_comando_torch_gpu_cpu():
    g = comando_torch(True)
    assert "cu128" in " ".join(g)
    c = comando_torch(False)
    assert "cu128" not in " ".join(c)


def test_rota_automatica_explicitada_sem_instalar(monkeypatch, capsys):
    from scripts import instalar_helper

    monkeypatch.setattr(instalar_helper, "tem_gpu_nvidia", lambda runner=None: True)
    assert instalar_helper.main(["--route"]) == 0
    assert capsys.readouterr().out.strip() == "cuda"
    monkeypatch.setattr(instalar_helper, "tem_gpu_nvidia", lambda runner=None: False)
    assert instalar_helper.main(["--route"]) == 0
    assert capsys.readouterr().out.strip() == "cpu"


def test_instalador_usa_somente_lock_da_rota():
    from pathlib import Path

    texto = (Path(__file__).resolve().parent.parent / "instalar.bat").read_text(encoding="utf-8")
    assert "requirements-%ROTA%.lock" in texto
    assert "--require-hashes" in texto
    assert "requirements.txt" not in texto
    assert "constraints-%ROTA%" not in texto
    assert "comando_torch" not in texto
    assert 'set "ROTA="' in texto
    assert texto.count("--check installed-route --rota %ROTA%") == 2
    assert "--require-installed" in texto
    assert "scripts\\instalar_helper.py --version" in texto


def test_venv_recusa_mistura_cpu_cuda(monkeypatch, capsys):
    from scripts import instalar_helper

    monkeypatch.setattr(instalar_helper, "versoes_torch_instaladas", lambda: ("2.11.0+cu128", "2.11.0+cu128"))
    assert instalar_helper.main(["--check", "installed-route", "--rota", "cpu"]) == 1
    assert "incompatível" in capsys.readouterr().out
    assert instalar_helper.main(["--check", "installed-route", "--rota", "cuda"]) == 0
    monkeypatch.setattr(instalar_helper, "versoes_torch_instaladas", lambda: (None, None))
    assert instalar_helper.main(["--check", "installed-route", "--rota", "cpu"]) == 0
    assert instalar_helper.main(["--check", "installed-route", "--rota", "cpu", "--require-installed"]) == 1
    monkeypatch.setattr(instalar_helper, "versoes_torch_instaladas", lambda: ("2.11.0", None))
    assert instalar_helper.main(["--check", "installed-route", "--rota", "cpu"]) == 1


def test_versao_lida_da_fonte_unica(capsys):
    import config
    from scripts import instalar_helper

    assert instalar_helper.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == config.VERSAO

    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "instalar_helper.py"
    resultado = subprocess.run([sys.executable, str(script), "--version"], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == config.VERSAO
