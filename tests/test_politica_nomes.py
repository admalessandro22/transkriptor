# -*- coding: utf-8 -*-
"""T-15.C3 / FR-15.C3 — nomes do Meet aplicados sozinhos quando a evidência é forte.

DP-15-02 ("sim, desde já"): limiares provisórios em `config.py`, recalibrados
na T-15.F1. Só o alinhamento com o Meet aplica sozinho; a comparação de texto
continua sugestão. Correção manual prevalece sempre.
"""
from __future__ import annotations

import pytest

import politica_nomes
from politica_nomes import aplicar_politica
from resultado_edicao import SegmentoResultado, exportar_txt, montar_payload


def _seg(sid, ini_s, fim_s, cluster, nome=None, pid=None, *, fonte="meet_alinhamento", conf=0.9,
         status="suggested", overlap=False):
    atrib = None
    if nome is not None:
        atrib = {"status": status, "participant_id": pid, "display_name": nome, "source": fonte,
                 "confidence": conf, "evidence_event_ids": ["e"], "calibration_version": "v"}
    return SegmentoResultado(sid, int(ini_s * 1000), int(fim_s * 1000), "loopback", f"fala {sid}",
                             cluster, overlap, atrib)


def _txt(segmentos, mapeamento):
    dados = montar_payload(segmentos, mapeamento)
    return exportar_txt(dados["segmentos"], dados["mapeamento"])


def test_cluster_dominante_recebe_nome():
    segs = [_seg("s1", 0, 3, "FALANTE_00", "Ana", "dev-1"), _seg("s2", 3, 6, "FALANTE_00", "Ana", "dev-1"),
            _seg("s3", 6, 7, "FALANTE_00")]
    novos, mapa = aplicar_politica(segs)
    assert mapa["FALANTE_00"]["display_name"] == "Ana"
    assert mapa["FALANTE_00"]["origem"] == "meet_auto"
    assert mapa["FALANTE_00"]["confianca"] == pytest.approx(6 / 7, abs=0.001)
    assert [s.assignment["status"] for s in novos[:2]] == ["confirmed", "confirmed"]
    assert all(s.assignment.get("auto") for s in novos[:2])
    # o segmento sem legenda herda o nome do cluster no TXT
    assert _txt(novos, mapa).splitlines()[2].startswith("[00:00:06] Ana:")


def test_cluster_dividido_fica_sem_nome_de_cluster_mas_cada_fala_mantem_o_seu():
    segs = [_seg("s1", 0, 4, "FALANTE_00", "Ana", "dev-1"), _seg("s2", 4, 8, "FALANTE_00", "Bruno", "dev-2")]
    novos, mapa = aplicar_politica(segs)
    assert "FALANTE_00" not in mapa
    linhas = _txt(novos, mapa).splitlines()
    assert linhas[0].endswith("Ana: fala s1") and linhas[1].endswith("Bruno: fala s2")


def test_confianca_baixa_ou_sobreposicao_ficam_sugestao():
    segs = [_seg("s1", 0, 4, "FALANTE_00", "Ana", "dev-1", conf=0.4),
            _seg("s2", 4, 8, "FALANTE_01", "Bruno", "dev-2", overlap=True)]
    novos, mapa = aplicar_politica(segs)
    assert [s.assignment["status"] for s in novos] == ["suggested", "suggested"]
    assert mapa == {}
    assert all("Identificação pendente" in linha for linha in _txt(novos, mapa).splitlines())


def test_relogio_incerto_nao_aplica_auto():
    """Sugestão por texto (sem alinhamento) nunca é aplicada sozinha."""
    novos, mapa = aplicar_politica([_seg("s1", 0, 9, "FALANTE_00", "Ana", "dev-1", fonte="caption")])
    assert novos[0].assignment["status"] == "suggested" and mapa == {}


def test_homonimos_nao_fundem():
    segs = [_seg("s1", 0, 5, "FALANTE_00", "Ana", "dev-1"), _seg("s2", 5, 10, "FALANTE_00", "Ana", "dev-7")]
    _, mapa = aplicar_politica(segs)
    assert "FALANTE_00" not in mapa


def test_curto_demais_nao_nomeia_cluster():
    _, mapa = aplicar_politica([_seg("s1", 0, 2, "FALANTE_00", "Ana", "dev-1")])
    assert mapa == {}


def test_manual_prevalece_no_reprocessamento():
    manual = {"FALANTE_00": {"participant_id": None, "display_name": "Carla", "origem": "manual", "autor": "local"}}
    segs = [_seg("s1", 0, 6, "FALANTE_00", "Ana", "dev-1")]
    novos, mapa = aplicar_politica(segs, manual)
    assert mapa["FALANTE_00"]["display_name"] == "Carla"
    assert _txt(novos, mapa).splitlines()[0].endswith("Carla: fala s1")


def test_proprio_confirmado():
    novos, _ = aplicar_politica([_seg("m1", 0, 3, "VOCÊ", "Alessandro (você)", "dev-88", fonte="meet_proprio",
                                      conf=1.0)])
    assert novos[0].assignment["status"] == "confirmed"


def test_desligado_nao_muda_nada(monkeypatch):
    monkeypatch.setattr(politica_nomes, "NOMES_AUTO_MEET", False)
    segs = [_seg("s1", 0, 9, "FALANTE_00", "Ana", "dev-1")]
    novos, mapa = aplicar_politica(segs)
    assert novos[0].assignment["status"] == "suggested" and mapa == {}


def test_nenhum_id_interno_no_txt():
    novos, mapa = aplicar_politica([_seg("s1", 0, 3, "FALANTE_03")])
    assert "FALANTE_" not in _txt(novos, mapa)
