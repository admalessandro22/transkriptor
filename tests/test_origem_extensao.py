# -*- coding: utf-8 -*-
"""T-15.E1 / SEC-15.E1 — só a nossa extensão fala com a ponte; ID fixo pela `key`."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import config
from meet_bridge import origem_permitida

RAIZ = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((RAIZ / "extension" / "meet" / "manifest.json").read_text(encoding="utf-8"))


def id_da_chave(chave_b64: str) -> str:
    """Regra do Chrome: SHA-256 da chave pública, 32 hex mapeados de 0-f para a-p."""
    digest = hashlib.sha256(base64.b64decode(chave_b64)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(c, 16)) for c in digest)


def test_id_derivado_da_key_confere():
    assert "key" in MANIFEST
    assert id_da_chave(MANIFEST["key"]) in config.EXTENSAO_IDS_PERMITIDOS


def test_id_permitido_aceito():
    for ext_id in config.EXTENSAO_IDS_PERMITIDOS:
        assert origem_permitida(f"chrome-extension://{ext_id}") is True


def test_outro_id_recusado():
    assert origem_permitida("chrome-extension://abcdefghijklmnopabcdefghijklmnop") is False
    assert origem_permitida("chrome-extension://" + "a" * 32) is False


def test_loopback_continua_para_ferramentas_locais():
    assert origem_permitida("http://127.0.0.1:5050") is True
    assert origem_permitida("https://evil.example.com") is False


def test_token_legado_recusado():
    """Com pareador, o token estático antigo não autentica mais (fim da transição D2→D4)."""
    fonte = (RAIZ / "meet_bridge.py").read_text(encoding="utf-8")
    assert "Transição D2→D4" not in fonte
    assert "token_sessao, era_convite = bridge.token, False" not in fonte
