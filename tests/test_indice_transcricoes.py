# -*- coding: utf-8 -*-
"""T-13.F3 — índice sem conteúdo, paginação e invalidação por manifesto."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from indice_transcricoes import atualizar_indice, listar_reunioes


def _manifesto(meeting_id, pasta: Path, conteudo="x"):
    from resultado_reuniao import (
        ResultManifest,
        StageState,
        criar_manifesto_inicial,
        salvar_manifesto,
    )

    resultado = pasta / f"{meeting_id}.txt"
    resultado.write_text(conteudo, encoding="utf-8")
    audio = pasta / f"{meeting_id}.wav"
    audio.write_bytes(b"\x00" * 64)
    manifesto = criar_manifesto_inicial(
        meeting_id=meeting_id,
        resultado=resultado,
        fontes_audio=[audio],
        raiz=pasta,
        created_at="2026-09-19T20:00:00Z",
    )
    caminho = pasta / f"{meeting_id}.resultado.json"
    salvar_manifesto(caminho, manifesto)
    return caminho


def test_mil_reunioes_sem_ler_texto(tmp_path, monkeypatch):
    """1000 reuniões listadas sem abrir nenhum .txt (canário)."""
    import indice_transcricoes

    pasta = tmp_path / "tr"
    pasta.mkdir()
    for i in range(1000):
        _manifesto(f"m{i:04d}", pasta, conteudo=f"CANARIO-{i}")
    aberturas_txt = []
    original = Path.read_bytes

    def espiao(self):
        if str(self).endswith(".txt"):
            aberturas_txt.append(str(self))
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", espiao)
    indice = tmp_path / "indice.json"
    listar_reunioes(indice, cursor=None, limit=100)
    t0 = time.monotonic()
    pagina, proximo = listar_reunioes(indice, cursor=None, limit=100)
    dt = time.monotonic() - t0
    assert len(pagina) == 100
    assert proximo == "m0099"
    assert aberturas_txt == []
    assert all("CANARIO" not in (s.title or "") for s in pagina)
    assert dt < 1.0, f"p95 em cache acima de 1 s: {dt:.3f}s"
    print(f"\np95 em cache (1000 Reunioes): {dt:.3f}s")


def test_indice_desatualizado_apos_job(tmp_path):
    pasta = tmp_path / "tr"
    pasta.mkdir()
    _manifesto("m1", pasta)
    indice = tmp_path / "indice.json"
    pagina, _ = listar_reunioes(indice, cursor=None, limit=10)
    assert [s.meeting_id for s in pagina] == ["m1"]
    _manifesto("m2", pasta)
    pagina, _ = listar_reunioes(indice, cursor=None, limit=10)
    assert sorted(s.meeting_id for s in pagina) == ["m1", "m2"]


def test_paginacao_cursor_e_limites(tmp_path):
    pasta = tmp_path / "tr"
    pasta.mkdir()
    for i in range(5):
        _manifesto(f"m{i}", pasta)
    indice = tmp_path / "indice.json"
    vistos = []
    cursor = None
    for _ in range(3):
        pagina, cursor = listar_reunioes(indice, cursor=cursor, limit=2)
        vistos.extend(s.meeting_id for s in pagina)
        if cursor is None:
            break
    assert sorted(vistos) == [f"m{i}" for i in range(5)]
    with pytest.raises(ValueError):
        listar_reunioes(indice, cursor=None, limit=0)
    with pytest.raises(ValueError):
        listar_reunioes(indice, cursor=None, limit=101)


def test_manifesto_adulterado_marca_desatualizado(tmp_path):
    pasta = tmp_path / "tr"
    pasta.mkdir()
    caminho = _manifesto("m1", pasta)
    indice = tmp_path / "indice.json"
    pagina, _ = listar_reunioes(indice, cursor=None, limit=10)
    assert pagina[0].quality_state != "desatualizado"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["warnings"].append("edicao manual")
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    pagina, _ = listar_reunioes(indice, cursor=None, limit=10)
    assert pagina[0].quality_state == "desatualizado"


def test_api_indice_paginado_sem_conteudo(tmp_path, monkeypatch, headers_token):
    from assistente import app

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    for i in range(3):
        _manifesto(f"m{i}", tmp_path)
    client = app.test_client()
    r1 = client.get("/api/reunioes-indice?limit=2", headers=headers_token)
    assert r1.status_code == 200
    dados = r1.get_json()
    assert [r["meeting_id"] for r in dados["reunioes"]] == ["m0", "m1"]
    assert dados["proximo"] == "m1"
    r2 = client.get("/api/reunioes-indice?limit=2&cursor=m1", headers=headers_token)
    assert [r["meeting_id"] for r in r2.get_json()["reunioes"]] == ["m2"]
    assert client.get("/api/reunioes-indice?limit=0", headers=headers_token).status_code == 400
    assert client.get("/api/reunioes-indice?limit=101", headers=headers_token).status_code == 400


def test_atualizar_indice_explicito(tmp_path):
    from resultado_reuniao import carregar_manifesto

    pasta = tmp_path / "tr"
    pasta.mkdir()
    caminho = _manifesto("m9", pasta)
    indice = tmp_path / "indice.json"
    atualizar_indice(indice, carregar_manifesto(caminho))
    pagina, _ = listar_reunioes(indice, cursor=None, limit=10)
    assert [s.meeting_id for s in pagina] == ["m9"]
