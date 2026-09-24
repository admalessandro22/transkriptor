# -*- coding: utf-8 -*-
"""UX-14.E1 — ícone vetorial, estados por forma e favicon (T-14.E1)."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_icones", REPO / "scripts" / "gerar_icones.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _mascara(img: Image.Image) -> str:
    """Hash da forma (só alfa e brancos), independente da cor de fundo."""
    rgba = img.convert("RGBA")
    dados = bytes(1 if (a > 128 and r > 200 and g > 200 and b > 200) else 0 for r, g, b, a in rgba.getdata())
    return hashlib.sha256(dados).hexdigest()


def test_ico_tem_seis_tamanhos():
    ico = Image.open(REPO / "transkriptor.ico")
    assert set(ico.info.get("sizes", set())) == {(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (256, 256)}
    fav = Image.open(REPO / "static" / "favicon.ico")
    assert (16, 16) in fav.info.get("sizes", set()) and (32, 32) in fav.info.get("sizes", set())


def test_estados_diferem_por_forma_nao_so_cor():
    from bandeja_icone import desenhar_icone

    formas = {estado: _mascara(desenhar_icone(64, estado, cor_fundo=(0, 0, 0))) for estado in ("aguardando", "transcrevendo", "diarizando", "processando", "erro", "pausado")}
    assert len(set(formas.values())) == 6, "dois estados com a mesma forma"


def test_cores_iguais_aos_tokens():
    from bandeja_icone import desenhar_icone

    tokens = json.loads((REPO / "design" / "tokens.json").read_text(encoding="utf-8"))
    mapa = {"aguardando": "idle", "transcrevendo": "recording", "diarizando": "diarizing", "processando": "processing", "erro": "error", "pausado": "paused"}
    for estado, chave in mapa.items():
        hexa = tokens["color"]["state"][chave].lstrip("#")
        esperado = tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))
        pixel = desenhar_icone(64, estado).getpixel((12, 32))[:3]
        assert pixel == esperado, (estado, pixel, esperado)


def test_pngs_gerados_batem_com_o_desenho():
    gerador = _gerador()
    assert gerador.verificar(REPO / "static" / "icones" / "bandeja") == []
    for t in (16, 32, 48, 128):
        assert (REPO / "extension" / "meet" / "icons" / f"icone-{t}.png").is_file()
    manifest = json.loads((REPO / "extension" / "meet" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["icons"] == {"16": "icons/icone-16.png", "32": "icons/icone-32.png", "48": "icons/icone-48.png", "128": "icons/icone-128.png"}


def test_fallback_pil_quando_png_falta(monkeypatch, tmp_path):
    import bandeja_icone

    monkeypatch.setattr(bandeja_icone, "PASTA_PNG", str(tmp_path))
    bandeja_icone._IMAGENS.clear()
    img = bandeja_icone.imagem_por_estado("erro")
    assert img.size == (64, 64)
    assert _mascara(img) == _mascara(bandeja_icone.desenhar_icone(64, "erro"))
    bandeja_icone._IMAGENS.clear()


def test_icone_legivel_em_16px_tem_microfone_branco_no_centro():
    from bandeja_icone import desenhar_icone

    pequeno = desenhar_icone(16, "aguardando")
    r, g, b, a = pequeno.getpixel((8, 6))
    assert a > 200 and min(r, g, b) > 180, "cápsula do microfone deve continuar visível em 16 px"


def test_svg_de_referencia_existe_e_usa_a_cor_idle():
    svg = (REPO / "design" / "icone" / "transkriptor.svg").read_text(encoding="utf-8")
    tokens = json.loads((REPO / "design" / "tokens.json").read_text(encoding="utf-8"))
    assert tokens["color"]["state"]["idle"].upper() in svg.upper()
    assert 'viewBox="0 0 64 64"' in svg
