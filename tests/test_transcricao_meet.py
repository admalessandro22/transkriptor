# -*- coding: utf-8 -*-
"""T-15.C4 / FR-15.C4 — transcrição do Meet como saída e reserva."""
from __future__ import annotations

import pytest

from resultado_edicao import (
    SegmentoResultado,
    carregar_segmentos,
    exportar_txt_resultado,
    montar_payload,
    salvar_segmentos,
    validar_dados_segmentos,
)
from transcricao_meet import blocos_meet, exportar_meet_txt, lacunas_meet


def _fala(i, pid, nome, ini_s, fim_s, texto):
    return {"kind": "caption", "caption_id": f"rtc-{i}/{pid}", "caption_revision": 1, "participant_id": pid,
            "display_name": nome, "text": texto, "event_id": f"e{i}", "ts_sec": ini_s, "ts_fim_sec": fim_s}


def test_agrupa_mesmo_falante():
    eventos = [_fala(1, "dev-1", "Ana", 1.0, 2.0, "bom dia"), _fala(2, "dev-1", "Ana", 3.0, 4.0, "a todos"),
               _fala(3, "dev-2", "Bruno", 5.0, 6.0, "oi")]
    blocos = blocos_meet(eventos, atraso_ms=-1000)
    assert [(b["nome"], b["texto"]) for b in blocos] == [("Ana", "bom dia a todos"), ("Bruno", "oi")]
    assert blocos[0]["inicio_ms"] == 0 and blocos[1]["inicio_ms"] == 4000  # tempo do áudio (δ aplicado)


def test_quebra_por_intervalo_e_por_tamanho():
    longe = [_fala(1, "dev-1", "Ana", 1.0, 2.0, "um"), _fala(2, "dev-1", "Ana", 9.0, 10.0, "dois")]
    assert len(blocos_meet(longe, atraso_ms=0)) == 2
    muitas = [_fala(i, "dev-1", "Ana", i, i + 0.5, f"f{i}") for i in range(1, 9)]
    assert [len(b["texto"].split()) for b in blocos_meet(muitas, atraso_ms=0)] == [6, 2]


def test_voce_e_nome_ausente():
    eventos = [_fala(1, "dev-88", "Alessandro", 1.0, 2.0, "eu"), _fala(2, "dev-2", "", 3.0, 4.0, "ele")]
    blocos = blocos_meet(eventos, atraso_ms=0, proprio="dev-88")
    assert [b["nome"] for b in blocos] == ["Alessandro (você)", "Participante"]


def test_sem_legendas_sem_artefato():
    assert blocos_meet([], atraso_ms=0) == []
    sem_tempo = _fala(1, "dev-1", "Ana", 1.0, 2.0, "x")
    del sem_tempo["ts_sec"]
    assert blocos_meet([sem_tempo], atraso_ms=0) == []


def _seg(sid, ini_s, fim_s, texto="fala"):
    return SegmentoResultado(sid, int(ini_s * 1000), int(fim_s * 1000), "loopback", texto, "FALANTE_00")


def test_lacuna_preenchida_marcada():
    """Legenda de 3 s sem nenhum segmento do Whisper vira lacuna; a coberta, não."""
    eventos = [_fala(1, "dev-1", "Ana", 1.0, 3.0, "coberta"), _fala(2, "dev-2", "Bruno", 11.0, 14.0, "perdida"),
               _fala(3, "dev-2", "Bruno", 21.0, 22.0, "curta")]
    segmentos = [_seg("s1", 0.0, 2.5)]
    lacunas = lacunas_meet(eventos, segmentos, atraso_ms=-1000)
    assert [(l["nome"], l["texto"], l["inicio_ms"]) for l in lacunas] == [("Bruno", "perdida", 10000)]
    dados = montar_payload(segmentos, {}, transcricao_meet=blocos_meet(eventos, atraso_ms=-1000), lacunas_meet=lacunas)
    linhas = exportar_txt_resultado(dados).splitlines()
    assert linhas == ["[00:00:00] Identificação pendente: fala", "[00:00:10] [legenda do Meet] Bruno: perdida"]


def test_persistencia_e_validacao(tmp_path):
    eventos = [_fala(1, "dev-1", "Ana", 1.0, 2.0, "bom dia")]
    caminho = tmp_path / "seg.json"
    salvar_segmentos(caminho, [_seg("s1", 0, 1)], {}, transcricao_meet=blocos_meet(eventos, atraso_ms=0),
                     lacunas_meet=[])
    dados = carregar_segmentos(caminho)
    assert dados["transcricao_meet"][0]["nome"] == "Ana"
    antigo = montar_payload([_seg("s1", 0, 1)], {})
    assert "transcricao_meet" not in antigo  # resultado antigo segue idêntico
    ruim = dict(antigo, transcricao_meet=[{"inicio_ms": "0", "nome": "Ana", "texto": "x"}])
    with pytest.raises(ValueError):
        validar_dados_segmentos(ruim)


def test_exportacao_da_transcricao_do_meet():
    blocos = [{"inicio_ms": 3_723_000, "fim_ms": 3_725_000, "participant_id": "dev-1", "nome": "Ana",
               "texto": "bom dia"}]
    assert exportar_meet_txt(blocos) == "[01:02:03] Ana: bom dia\n"
