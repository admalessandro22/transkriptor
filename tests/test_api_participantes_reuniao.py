# -*- coding: utf-8 -*-
"""Participantes por reunião para a lista (pedido do usuário, 24/09/2026).

Os nomes saem do resultado na hora da leitura; nada é gravado no índice.
"""
from __future__ import annotations

from resultado_edicao import SegmentoResultado, salvar_segmentos


def _seg(sid, cluster, texto, assignment=None):
    return SegmentoResultado(sid, 0, 1000, "loopback", texto, cluster, assignment=assignment)


def test_participantes_unicos_na_ordem_da_fala(tmp_path, monkeypatch, headers_token):
    from assistente import app

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "resultados").mkdir()
    confirmado = {"status": "confirmed", "display_name": "Ana Fictícia"}
    sugerido = {"status": "suggested", "display_name": "Bruno Fictício"}
    pendente = {"status": "pending", "display_name": "Não Deve Aparecer"}
    salvar_segmentos(
        tmp_path / "resultados" / "reuniao-x.json",
        [
            _seg("s1", "FALANTE_00", "fala sigilosa", confirmado),
            _seg("s2", "FALANTE_01", "fala sigilosa", sugerido),
            _seg("s3", "FALANTE_00", "fala sigilosa", confirmado),
            _seg("s4", "FALANTE_02", "fala sigilosa", pendente),
            _seg("s5", "FALANTE_03", "fala sigilosa"),
        ],
        {"FALANTE_03": {"participant_id": None, "display_name": "Carla Manual", "origem": "manual", "autor": "local"}},
    )
    r = app.test_client().get("/api/reunioes/reuniao-x/participantes", headers=headers_token)
    assert r.status_code == 200
    dados = r.get_json()
    assert dados == {"participantes": ["Ana Fictícia", "Bruno Fictício", "Carla Manual"], "sem_nome": 1}
    assert "sigilosa" not in r.get_data(as_text=True)


def test_participantes_404_e_path_invalido(tmp_path, monkeypatch, headers_token):
    from assistente import app

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    client = app.test_client()
    assert client.get("/api/reunioes/sem-tal/participantes", headers=headers_token).status_code == 404
    assert client.get("/api/reunioes/../x/participantes", headers=headers_token).status_code == 404


def test_resultado_malformado_nao_quebra():
    from participantes_reuniao import participantes_do_resultado

    assert participantes_do_resultado({"segmentos": ["x", None, {"assignment": "y"}], "mapeamento": []}) == {
        "participantes": [], "sem_nome": 0,
    }
    assert participantes_do_resultado(None) == {"participantes": [], "sem_nome": 0}
