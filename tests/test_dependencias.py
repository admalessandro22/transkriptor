# -*- coding: utf-8 -*-
"""T-13.G1 — seleção validada, locks reproduzíveis e SBOM íntegro."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_locks_de_producao_e_dev_possuem_hashes():
    pasta = REPO / "requirements"
    cpu = (pasta / "requirements-cpu.lock").read_text(encoding="utf-8")
    cuda = (pasta / "requirements-cuda.lock").read_text(encoding="utf-8")
    dev = (pasta / "requirements-dev.lock").read_text(encoding="utf-8")
    assert "torch==2.11.0" in cpu
    assert "torch==2.11.0+cu128" in cuda
    assert "pytest==" in dev
    for conteudo in (cpu, cuda, dev):
        assert "--hash=sha256:" in conteudo
    for conteudo in (cpu, cuda):
        assert "cryptography==50.0.1 " in conteudo
        assert "flask==3.1.3 " in conteudo
        assert "pillow==12.3.0 " in conteudo


def test_workflow_instala_locks_e_roda_auditoria():
    workflow = (REPO / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "requirements/requirements-cpu.lock" in workflow
    assert "requirements/requirements-dev.lock" in workflow
    assert "--require-hashes" in workflow
    assert "pip-audit" in workflow
    assert "scripts/gerar_sbom.py" in workflow
    assert ".ci-venv\\Scripts\\python.exe -m pytest" in workflow


def test_sbom_cyclonedx_contem_dependencias_transitivas():
    sbom = json.loads((REPO / "docs" / "sbom.json").read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    componentes = {item["name"].lower() for item in sbom["components"]}
    assert {"torch", "flask", "werkzeug", "numpy", "pynacl"} <= componentes


def test_lock_windows_exige_hash_e_arvore_exata(tmp_path):
    import pytest
    from scripts.gerar_lock_windows import gerar_lock

    pins = tmp_path / "pacotes.pins"
    pins.write_text("Flask[async]==3.1.2\nWerkzeug==3.1.8\n", encoding="utf-8")
    relatorio = tmp_path / "report.json"
    dados = {
        "version": "1", "install": [
            {"metadata": {"name": nome, "version": versao},
             "download_info": {"archive_info": {"hashes": {"sha256": letra * 64}}}}
            for nome, versao, letra in (("Flask", "3.1.2", "a"), ("Werkzeug", "3.1.8", "b"))
        ],
    }
    relatorio.write_text(json.dumps(dados), encoding="utf-8")
    lock = tmp_path / "requirements.lock"
    gerar_lock(pins, relatorio, lock)
    texto = lock.read_text(encoding="utf-8")
    assert "flask==3.1.2 --hash=sha256:" + "a" * 64 in texto
    assert "werkzeug==3.1.8 --hash=sha256:" + "b" * 64 in texto
    dados["install"][1]["download_info"]["archive_info"]["hashes"] = {}
    relatorio.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        gerar_lock(pins, relatorio, lock)


def test_lock_cuda_preserva_arvore_cpu_e_troca_apenas_wheels_pytorch(tmp_path):
    from scripts.gerar_lock_windows import gerar_cuda_de_cpu

    cpu = tmp_path / "cpu.lock"
    cuda = tmp_path / "cuda.lock"
    sha = "a" * 64
    cpu.write_text(
        f"flask==3.1.2 --hash=sha256:{sha}\n"
        f"torch==2.11.0 --hash=sha256:{sha}\n"
        f"torchaudio==2.11.0 --hash=sha256:{sha}\n",
        encoding="utf-8",
    )
    gerar_cuda_de_cpu(cpu, cuda, "b" * 64, "c" * 64)
    texto = cuda.read_text(encoding="utf-8")
    assert "--extra-index-url https://download.pytorch.org/whl/cu128" in texto
    assert f"flask==3.1.2 --hash=sha256:{sha}" in texto
    assert f"torch==2.11.0+cu128 --hash=sha256:{'b' * 64}" in texto
    assert f"torchaudio==2.11.0+cu128 --hash=sha256:{'c' * 64}" in texto


def test_sbom_fica_so_com_arvore_cpu_e_hashes():
    from scripts.gerar_sbom import filtrar_sbom

    sha = "a" * 64
    bruto = {
        "bomFormat": "CycloneDX", "specVersion": "1.6",
        "components": [
            {"name": "Flask", "version": "3.1.2", "bom-ref": "flask"},
            {"name": "Werkzeug", "version": "3.1.8", "bom-ref": "werkzeug"},
            {"name": "pytest", "version": "9.1.1", "bom-ref": "pytest"},
        ],
        "dependencies": [
            {"ref": "flask", "dependsOn": ["werkzeug", "pytest"]},
            {"ref": "pytest", "dependsOn": []},
        ],
    }
    lock = f"flask==3.1.2 --hash=sha256:{sha}\nwerkzeug==3.1.8 --hash=sha256:{sha}\n"
    sbom = filtrar_sbom(bruto, lock)
    assert {c["name"] for c in sbom["components"]} == {"Flask", "Werkzeug"}
    assert all(c["hashes"] == [{"alg": "SHA-256", "content": sha}] for c in sbom["components"])
    assert sbom["dependencies"] == [{"ref": "flask", "dependsOn": ["werkzeug"]}]


def _ler_lock(rota: str) -> dict[str, str]:
    caminho = REPO / "requirements" / f"requirements-{rota}.lock"
    pinos = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "-", "--")):
            continue
        nome, sep, versao_hash = linha.partition("==")
        assert sep, f"pino sem versão exata: {linha}"
        versao, marcador, hash_sha = versao_hash.partition(" --hash=sha256:")
        assert marcador and len(hash_sha) == 64, f"pino sem hash: {linha}"
        pinos[nome.strip().lower()] = versao.strip()
    return pinos


def test_locks_reproduzem_arvore_aprovada():
    """Locks CPU/CUDA fixam o mesmo núcleo; só a rota torch diverge."""
    cpu = _ler_lock("cpu")
    cuda = _ler_lock("cuda")
    núcleo = {
        "faster-whisper", "soundcard", "numpy", "pystray", "pygetwindow",
        "pillow", "speechbrain", "scikit-learn", "flask", "websockets",
        "cryptography", "pynacl",
    }
    assert núcleo <= set(cpu) and núcleo <= set(cuda)
    for nome in núcleo:
        assert cpu[nome] == cuda[nome], f"{nome} diverge entre rotas"
    assert set(cpu) == set(cuda)
    assert cpu["torch"] == cpu["torchaudio"] == "2.11.0"
    assert cuda["torch"] == cuda["torchaudio"] == "2.11.0+cu128"
    assert all(cpu[nome] == cuda[nome] for nome in cpu if nome not in {"torch", "torchaudio"})


def test_helper_rejeita_conjunto_incompativel():
    from scripts.instalar_helper import main as _main  # noqa
    import scripts.instalar_helper as helper

    ok, msg = helper.combinacao_valida({"torch_cuda": True, "tem_gpu": False})
    assert ok is False
    assert "cuda" in msg.lower() or "gpu" in msg.lower()
    ok, msg = helper.combinacao_valida({"torch_cuda": True, "tem_gpu": True})
    assert ok is True
    assert helper.combinacao_valida({"torch_cuda": False, "tem_gpu": False})[0] is True


def test_helper_check_deps_falha_clara(monkeypatch):
    import scripts.instalar_helper as helper

    monkeypatch.setattr(helper, "tem_gpu_nvidia", lambda runner=None: False)
    rc = helper.main(["--check", "deps", "--rota", "cuda"])
    assert rc == 1


def test_sbom_confere_instalado():
    """SBOM commitado cobre exatamente o lock CPU sem dados de sessão."""
    sbom = json.loads((REPO / "docs" / "sbom.json").read_text(encoding="utf-8"))
    from scripts.gerar_sbom import filtrar_sbom

    lock = (REPO / "requirements" / "requirements-cpu.lock").read_text(encoding="utf-8")
    assert filtrar_sbom(sbom, lock) == sbom
    texto = json.dumps(sbom).lower()
    assert "token=" not in texto and "sess-" not in texto and "pair-" not in texto
