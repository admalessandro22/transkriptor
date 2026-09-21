# -*- coding: utf-8 -*-
"""T-13.G1 — seleção validada, locks reproduzíveis e SBOM íntegro."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _ler_constraints(rota: str) -> dict[str, str]:
    caminho = REPO / "requirements" / f"constraints-{rota}.txt"
    pinos = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "-", "--")):
            continue
        nome, sep, versao = linha.partition("==")
        assert sep, f"pino sem versão exata: {linha}"
        pinos[nome.strip().lower()] = versao.strip()
    return pinos


def test_locks_reproduzem_arvore_aprovada():
    """Locks CPU/CUDA fixam o mesmo núcleo; só a rota torch diverge."""
    cpu = _ler_constraints("cpu")
    cuda = _ler_constraints("cuda")
    núcleo = {
        "faster-whisper", "soundcard", "numpy", "pystray", "pygetwindow",
        "pillow", "speechbrain", "scikit-learn", "flask", "websockets",
        "cryptography", "pynacl",
    }
    assert núcleo <= set(cpu) and núcleo <= set(cuda)
    for nome in núcleo:
        assert cpu[nome] == cuda[nome], f"{nome} diverge entre rotas"
    assert cpu["torch"] != cuda["torch"] or "cpu" in cpu["torch"].lower()


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
    """SBOM commitado bate com o ambiente (sem credenciais)."""
    import importlib.metadata as meta

    sbom = json.loads((REPO / "docs" / "sbom.json").read_text(encoding="utf-8"))
    pacotes = {p["nome"].lower(): p["versao"] for p in sbom["pacotes"]}
    for nome in ("websockets", "cryptography", "pynacl", "flask", "numpy"):
        assert pacotes[nome] == meta.version(nome)
    texto = json.dumps(sbom).lower()
    assert "token=" not in texto and "sess-" not in texto and "pair-" not in texto
