# -*- coding: utf-8 -*-
"""T-13.D7 — resultado canônico, correção por reunião, undo e TXT exato."""
from __future__ import annotations

import re

import pytest

from resultado_reuniao import (
    NOME_PENDENTE,
    ResultManifest,
    SegmentoResultado,
    StageState,
    aplicar_correcao,
    carregar_segmentos,
    desfazer_correcao,
    exportar_txt,
    format_segment_txt,
    resultado_global,
    salvar_segmentos,
)

PADRAO_LINHA = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] .+: .+$")


def _segmentos():
    return [
        SegmentoResultado("s1", 0, 4000, "loopback", "bom dia a todos", "FALANTE_00"),
        SegmentoResultado("s2", 4000, 9000, "microphone", "vamos revisar o cronograma", "FALANTE_01", True),
    ]


def test_formato_exato_txt():
    linha = format_segment_txt(3661000, "Ana", "bom dia")
    assert linha == "[01:01:01] Ana: bom dia"
    assert PADRAO_LINHA.match(linha)
    assert format_segment_txt(0, None, "x") == f"[00:00:00] {NOME_PENDENTE}: x"
    assert format_segment_txt(0, "FALANTE_00", "x") == f"[00:00:00] {NOME_PENDENTE}: x"


def test_exportacao_pendente_sem_nome_inventado(tmp_path):
    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    dados = carregar_segmentos(caminho)
    texto = exportar_txt(dados["segmentos"], dados["mapeamento"])
    assert "FALANTE_00" not in texto
    assert texto.count(NOME_PENDENTE) == 2
    for linha in texto.strip().splitlines():
        assert PADRAO_LINHA.match(linha)


def test_correcao_apos_restart(tmp_path):
    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    del caminho
    caminho = tmp_path / "r.json"
    rev = aplicar_correcao(
        caminho,
        expected_revision="rev-1",
        speaker_cluster_id="FALANTE_00",
        participant_id="p-ana",
        display_name="Ana",
    )
    dados = carregar_segmentos(caminho)
    assert dados["revision"] == rev != "rev-1"
    texto = exportar_txt(dados["segmentos"], dados["mapeamento"])
    assert "[00:00:00] Ana: bom dia a todos" in texto.splitlines()


def test_duas_reunioes_isoladas(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    salvar_segmentos(a, _segmentos(), {})
    salvar_segmentos(b, _segmentos(), {})
    aplicar_correcao(a, expected_revision="rev-1", speaker_cluster_id="FALANTE_00",
                     participant_id="p-ana", display_name="Ana")
    db = carregar_segmentos(b)
    assert db["mapeamento"] == {}
    assert NOME_PENDENTE in exportar_txt(db["segmentos"], db["mapeamento"])


def test_edicao_concorrente_recusada(tmp_path):
    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    with pytest.raises(ValueError):
        aplicar_correcao(caminho, expected_revision="rev-1-antiga",
                         speaker_cluster_id="FALANTE_00",
                         participant_id="p-ana", display_name="Ana")
    assert carregar_segmentos(caminho)["revision"] == "rev-1"


def test_desfazer_restaura(tmp_path):
    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    rev2 = aplicar_correcao(caminho, expected_revision="rev-1",
                            speaker_cluster_id="FALANTE_00",
                            participant_id="p-ana", display_name="Ana")
    rev3 = desfazer_correcao(caminho, expected_revision=rev2)
    assert rev3 != rev2
    dados = carregar_segmentos(caminho)
    assert dados["mapeamento"] == {}
    assert len(dados["historico"]) == 2


def test_correcao_e_undo_atualizam_txt_derivado_e_manifesto(tmp_path):
    from resultado_reuniao import (
        criar_manifesto_estruturado, salvar_manifesto, validar_manifesto,
    )

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")
    caminho = tmp_path / "resultados" / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    txt = tmp_path / "r.txt"
    txt.write_text(exportar_txt(carregar_segmentos(caminho)["segmentos"], {}), encoding="utf-8")
    manifesto = tmp_path / "r.resultado.json"
    salvar_manifesto(manifesto, criar_manifesto_estruturado(
        meeting_id="r", segmentos=caminho, resultado=txt, fontes_audio=[audio], raiz=tmp_path,
    ))
    assert validar_manifesto(manifesto, tmp_path)
    assert NOME_PENDENTE in txt.read_text(encoding="utf-8")

    revisao = aplicar_correcao(
        caminho, expected_revision="rev-1", speaker_cluster_id="FALANTE_00",
        participant_id="p1", display_name="Ana",
    )
    assert "[00:00:00] Ana: bom dia a todos" in txt.read_text(encoding="utf-8")
    assert validar_manifesto(manifesto, tmp_path)
    desfazer_correcao(caminho, expected_revision=revisao)
    assert NOME_PENDENTE in txt.read_text(encoding="utf-8")
    assert validar_manifesto(manifesto, tmp_path)


def test_txt_editado_fora_do_app_nao_e_sobrescrito_nem_muda_revisao(tmp_path):
    from resultado_reuniao import criar_manifesto_estruturado, salvar_manifesto

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")
    caminho = tmp_path / "resultados" / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    txt = tmp_path / "r.txt"
    txt.write_text(exportar_txt(carregar_segmentos(caminho)["segmentos"], {}), encoding="utf-8")
    salvar_manifesto(tmp_path / "r.resultado.json", criar_manifesto_estruturado(
        meeting_id="r", segmentos=caminho, resultado=txt, fontes_audio=[audio], raiz=tmp_path,
    ))
    txt.write_text("correção manual fora do app", encoding="utf-8")
    with pytest.raises(ValueError, match="TXT alterado"):
        aplicar_correcao(caminho, expected_revision="rev-1", speaker_cluster_id="FALANTE_00",
                        participant_id=None, display_name="Ana")
    assert txt.read_text(encoding="utf-8") == "correção manual fora do app"
    assert carregar_segmentos(caminho)["revision"] == "rev-1"


def test_api_reunioes_lista_corrige_desfaz(tmp_path, monkeypatch, headers_token):
    from assistente import app

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "resultados").mkdir()
    salvar_segmentos(
        tmp_path / "resultados" / "reuniao-x.json",
        [
            SegmentoResultado("s1", 0, 1000, "loopback", "bom dia", "FALANTE_00"),
        ],
        {},
    )
    client = app.test_client()
    assert client.get("/api/reunioes", headers=headers_token).get_json() == ["reuniao-x"]
    get = client.get("/api/reunioes/reuniao-x/resultado", headers=headers_token)
    assert get.status_code == 200 and get.get_json()["revision"] == "rev-1"
    post = client.post(
        "/api/reunioes/reuniao-x/correcao",
        headers=headers_token,
        json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Ana"},
    )
    assert post.status_code == 200
    rev2 = post.get_json()["revision"]
    get2 = client.get("/api/reunioes/reuniao-x/resultado", headers=headers_token).get_json()
    assert get2["mapeamento"]["FALANTE_00"]["display_name"] == "Ana"
    velha = client.post(
        "/api/reunioes/reuniao-x/correcao",
        headers=headers_token,
        json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Bruno"},
    )
    assert velha.status_code == 409
    desf = client.post(
        "/api/reunioes/reuniao-x/desfazer",
        headers=headers_token,
        json={"expected_revision": rev2},
    )
    assert desf.status_code == 200
    assert client.get("/api/reunioes/reuniao-x/resultado", headers=headers_token).get_json()["mapeamento"] == {}
    assert client.get("/api/reunioes/sem-tal/resultado", headers=headers_token).status_code == 404
    assert client.get("/api/reunioes/../x/resultado", headers=headers_token).status_code == 404


def test_api_correcao_sem_biometria(tmp_path, monkeypatch, headers_token):
    """Corrigir nome na reunião não cadastra voz (ação separada)."""
    from assistente import app
    from renomear_falante_flow import corrigir_nome_reuniao

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "resultados").mkdir()
    caminho = tmp_path / "resultados" / "reuniao-y.json"
    salvar_segmentos(caminho, [SegmentoResultado("s1", 0, 1000, "loopback", "oi", "FALANTE_00")], {})
    rev = corrigir_nome_reuniao(str(caminho), "rev-1", "FALANTE_00", "Ana", autor="api")
    assert rev != "rev-1"
    assert carregar_segmentos(caminho)["mapeamento"]["FALANTE_00"]["display_name"] == "Ana"


def test_falha_diarizacao_preserva_stt(tmp_path):
    manifesto = ResultManifest(
        meeting_id="m1",
        schema_version=1,
        source_audio_hashes=("a" * 64,),
        participants_ref=None,
        segments_ref=None,
        stage_status={"stt": StageState.COMPLETE, "diarizacao": StageState.FAILED},
        warnings=("diarizacao_falhou",),
        exports=(),
        created_at="2026-09-19T20:00:00Z",
        pipeline_version="1.7.0",
    )
    assert resultado_global(manifesto) != StageState.COMPLETE.value
    caminho = tmp_path / "r.json"
    salvar_segmentos(caminho, _segmentos(), {})
    dados = carregar_segmentos(caminho)
    assert "bom dia a todos" in exportar_txt(dados["segmentos"], dados["mapeamento"])
