# -*- coding: utf-8 -*-
"""T-15.E4 / FR-15.E4 — provisionamento do instalador por usuário (Inno Setup + uv)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from instalador import provisionar as pv

RAIZ = Path(__file__).resolve().parent.parent
ISS = (RAIZ / "instalador" / "transkriptor.iss").read_text(encoding="utf-8")


def _runner(saida_nvidia):
    def rodar(cmd, **_kw):
        if cmd[0] == "nvidia-smi":
            if saida_nvidia is None:
                raise FileNotFoundError
            return SimpleNamespace(returncode=0, stdout=saida_nvidia)
        return SimpleNamespace(returncode=0, stdout="")
    return rodar


def test_rota_cpu_sem_nvidia():
    assert pv.escolher_rota(_runner(None)) == "cpu"
    assert pv.escolher_rota(_runner("")) == "cpu"


def test_rota_cuda_com_nvidia():
    assert pv.escolher_rota(_runner("GPU 0: NVIDIA GeForce GTX 1650 (UUID: GPU-x)")) == "cuda"


@pytest.mark.parametrize("rota", ["cpu", "cuda"])
def test_hash_obrigatorio(tmp_path, rota):
    comandos = pv.comandos(tmp_path, rota, uv="uv.exe")
    assert comandos[0][:4] == ["uv.exe", "venv", "--python", "3.12"]
    sync = comandos[1]
    assert sync[:3] == ["uv.exe", "pip", "sync"] and "--require-hashes" in sync
    assert sync[-1] == str(tmp_path / "requirements" / f"requirements-{rota}.lock")


def test_rota_invalida_recusada(tmp_path):
    with pytest.raises(ValueError):
        pv.comandos(tmp_path, "rocm")


def test_provisionar_executa_em_ordem_e_registra_host(tmp_path):
    feitos, registrado = [], {}
    pv.provisionar(tmp_path, rota="cpu", uv="uv.exe", executar=lambda cmd, **kw: feitos.append(cmd),
                   registrar=lambda pasta, python: registrado.update(pasta=pasta, python=python),
                   detectar=lambda: "Ollama 0.34.4 encontrado com 3 modelo(s).")
    assert [c[1] for c in feitos] == ["venv", "pip"]
    assert registrado["python"].endswith(r".venv\Scripts\python.exe")
    assert (tmp_path / "instalador" / "ollama-detectado.txt").read_text(encoding="utf-8").startswith("Ollama 0.34.4")


def test_detectar_json_sem_caminho_pessoal():
    d = SimpleNamespace(estado="online", versao="0.34.4", url="http://127.0.0.1:11434",
                        executavel=r"C:\Users\Fulano\AppData\Local\Programs\Ollama\ollama.exe",
                        modelos=[SimpleNamespace(id="granite4.1:3b"), SimpleNamespace(id="gemma4:latest")])
    dados = json.loads(pv.detectar_json(d))
    assert dados == {"estado": "online", "versao": "0.34.4", "modelos": ["granite4.1:3b", "gemma4:latest"]}
    assert "Fulano" not in pv.detectar_texto(d)
    parado = SimpleNamespace(estado="nao_instalado", versao=None, url="", executavel=None, modelos=[])
    assert "não está instalado" in pv.detectar_texto(parado)


def test_desinstalar_preserva_dados(tmp_path):
    (tmp_path / "transcricoes").mkdir()
    (tmp_path / "config_user.json").write_text("{}", encoding="utf-8")
    removidos = []
    pv.desinstalar(tmp_path, desregistrar=lambda: removidos.append("host"))
    assert (tmp_path / "transcricoes").is_dir() and (tmp_path / "config_user.json").is_file()
    assert removidos == ["host"]


def test_desinstalar_remove_registro_e_dados_so_se_pedido(tmp_path):
    (tmp_path / "transcricoes").mkdir()
    (tmp_path / "config_user.json").write_text("{}", encoding="utf-8")
    pv.desinstalar(tmp_path, apagar_dados=True, desregistrar=lambda: None)
    assert not (tmp_path / "transcricoes").exists() and not (tmp_path / "config_user.json").exists()


def test_iss_por_usuario_sem_admin_e_sem_dados_pessoais():
    assert re.search(r"(?m)^PrivilegesRequired=lowest$", ISS)
    assert r"DefaultDirName={localappdata}\Programs\Transkriptor" in ISS
    for fora in ("transcricoes", "config_user.json", "tests", ".venv", "node_modules", "*.log", "_modelo_voz"):
        assert fora in ISS.split("Excludes:", 1)[1].split("\n", 1)[0]
    assert "provisionar.py" in ISS and "--desinstalar" in ISS
    assert "uv.exe" in ISS


def test_rota_cuda_compara_indices_protegida_por_hash(tmp_path):
    """O lock CUDA foi gerado pelo pip (melhor versão entre índices); o uv, por padrão,
    para no primeiro índice. Com hash obrigatório, comparar índices é seguro."""
    cuda = pv.comandos(tmp_path, "cuda")[1]
    assert cuda[cuda.index("--index-strategy") + 1] == "unsafe-best-match" and "--require-hashes" in cuda
    assert "--index-strategy" not in pv.comandos(tmp_path, "cpu")[1]
