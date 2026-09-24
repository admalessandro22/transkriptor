# -*- coding: utf-8 -*-
"""Rotas de exclusão (dupla confirmação) e título da reunião na Central."""
from __future__ import annotations

import json

from tests.test_exclusao_reuniao import MID, SESSAO, _reuniao


def _cliente(tmp_path, monkeypatch):
    from assistente import app

    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    _reuniao(raiz, MID, "transcricao_24-09-26_16h05", SESSAO)
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(raiz))
    return app.test_client(), raiz


def test_exclusao_exige_plano_confirmado_e_palavra(tmp_path, monkeypatch, headers_token):
    cliente, raiz = _cliente(tmp_path, monkeypatch)
    plano = cliente.get(f"/api/reunioes/{MID}/exclusao", headers=headers_token)
    assert plano.status_code == 200
    dados = plano.get_json()
    assert dados["itens"] and dados["plano_id"]
    url = f"/api/reunioes/{MID}/excluir"
    sem_palavra = cliente.post(url, headers=headers_token, json={"plano_id": dados["plano_id"]})
    assert sem_palavra.status_code == 400
    plano_errado = cliente.post(url, headers=headers_token, json={"plano_id": "0" * 64, "confirmacao": "EXCLUIR"})
    assert plano_errado.status_code == 409
    assert (raiz / "transcricao_24-09-26_16h05.txt").is_file()
    ok = cliente.post(url, headers=headers_token, json={"plano_id": dados["plano_id"], "confirmacao": "EXCLUIR"})
    assert ok.status_code == 200 and ok.get_json()["excluidos"] == len(dados["itens"])
    assert not (raiz / "transcricao_24-09-26_16h05.txt").exists()
    assert cliente.get(f"/api/reunioes/{MID}/exclusao", headers=headers_token).status_code == 404


def test_exclusao_bloqueada_em_processamento(tmp_path, monkeypatch, headers_token):
    cliente, raiz = _cliente(tmp_path, monkeypatch)
    job = raiz / ".jobs_processamento" / f"{MID}.json"
    dados = json.loads(job.read_text(encoding="utf-8"))
    dados["estado"] = "processing"
    job.write_text(json.dumps(dados), encoding="utf-8")
    assert cliente.get(f"/api/reunioes/{MID}/exclusao", headers=headers_token).status_code == 409


def test_titulo_da_reuniao(tmp_path, monkeypatch, headers_token):
    cliente, raiz = _cliente(tmp_path, monkeypatch)
    url = f"/api/reunioes/{MID}/titulo"
    assert cliente.post(url, headers=headers_token, json={"titulo": "Retro da sprint"}).get_json() == {"titulo": "Retro da sprint"}
    entrada = json.loads((raiz / "indice.json").read_text(encoding="utf-8"))["meetings"][MID]
    assert entrada["titulo_usuario"] == "Retro da sprint"
    assert cliente.post(url, headers=headers_token, json={"titulo": "x" * 81}).status_code == 400
    assert cliente.post("/api/reunioes/nao-existe/titulo", headers=headers_token, json={"titulo": "a"}).status_code == 404


def test_rotas_exigem_token(tmp_path, monkeypatch):
    cliente, _ = _cliente(tmp_path, monkeypatch)
    assert cliente.get(f"/api/reunioes/{MID}/exclusao").status_code in (401, 403)
    assert cliente.post(f"/api/reunioes/{MID}/excluir", json={}).status_code in (401, 403)
