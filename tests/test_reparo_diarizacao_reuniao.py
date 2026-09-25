# -*- coding: utf-8 -*-
"""Reparo de uma reunião sem refazer ou perder a transcrição."""
from __future__ import annotations

import wave
from dataclasses import replace
from pathlib import Path

import pytest

from fila_processamento import FilaProcessamento
from indice_transcricoes import listar_reunioes
from resultado_edicao import SegmentoResultado, carregar_segmentos, exportar_txt, salvar_segmentos
from resultado_reuniao import (
    StageState, carregar_manifesto, criar_manifesto_estruturado, salvar_manifesto,
    validar_manifesto,
)
from scripts.reparar_diarizacao_reuniao import _diarizar_job, main, reparar


def _reuniao_parcial(tmp_path):
    raiz = tmp_path / "transcricoes"
    audio_dir = raiz / "audio"
    audio_dir.mkdir(parents=True)
    audio = audio_dir / "reuniao.wav"
    with wave.open(str(audio), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16000)
        arquivo.writeframes(b"\0" * 48000)
    fila = FilaProcessamento(str(raiz))
    mid = fila.enfileirar(
        str(audio), None, "reuniao",
        {"inicio_iso": "2026-09-24T19:22:00-03:00", "diarizar": True},
    )
    segmentos = [
        SegmentoResultado("lb-1", 0, 1000, "loopback", "fala remota", "FALANTE_01", True),
        SegmentoResultado("mic-1", 500, 1500, "microphone", "fala local", "FALANTE_00", True),
    ]
    json_path = raiz / "resultados" / f"{mid}.json"
    salvar_segmentos(json_path, segmentos, {})
    dados = carregar_segmentos(json_path)
    txt_path = raiz / "reuniao.txt"
    txt_path.write_text(exportar_txt(dados["segmentos"], {}), encoding="utf-8")
    manifesto = criar_manifesto_estruturado(
        meeting_id=mid, segmentos=json_path, resultado=txt_path,
        fontes_audio=[audio], raiz=raiz,
        warnings=("segment_alignment_failed",), diarizacao_solicitada=True,
    )
    manifest_path = raiz / "reuniao.resultado.json"
    salvar_manifesto(manifest_path, manifesto)
    fila.reivindicar(mid)
    fila.concluir(mid, str(txt_path), str(manifest_path))
    return raiz, mid, json_path, txt_path, manifest_path


def _rotulos_validos(_job, _dados):
    return [
        ("FALANTE_01", 0.0, 1.0, "fala remota"),
        ("FALANTE_02", 0.5, 1.5, "fala local"),
    ]


def test_inspecao_nao_altera_artefatos_nem_roda_modelo(tmp_path):
    raiz, mid, json_path, txt_path, manifest_path = _reuniao_parcial(tmp_path)
    antes = [p.read_bytes() for p in (json_path, txt_path, manifest_path)]

    resultado = reparar(
        raiz, mid, diarizar_fn=lambda *_: pytest.fail("modelo não deve rodar na inspeção")
    )

    assert resultado["estado"] == "inspecao"
    assert [p.read_bytes() for p in (json_path, txt_path, manifest_path)] == antes


def test_reparo_preserva_falas_e_atualiza_manifesto_e_indice(tmp_path):
    raiz, mid, json_path, txt_path, manifest_path = _reuniao_parcial(tmp_path)
    antes = carregar_segmentos(json_path)
    hash_audio = carregar_manifesto(manifest_path).source_audio_hashes

    resultado = reparar(raiz, mid, aplicar=True, diarizar_fn=_rotulos_validos)

    depois = carregar_segmentos(json_path)
    manifesto = carregar_manifesto(manifest_path)
    assert resultado["estado"] == "reparado"
    assert depois["revision"] != antes["revision"]
    assert [(s["segment_id"], s["start_ms"], s["end_ms"], s["text"]) for s in depois["segmentos"]] == [
        (s["segment_id"], s["start_ms"], s["end_ms"], s["text"]) for s in antes["segmentos"]
    ]
    assert [s["speaker_cluster_id"] for s in depois["segmentos"]] == ["FALANTE_01", "FALANTE_02"]
    assert manifesto.source_audio_hashes == hash_audio
    assert manifesto.stage_status["diarizacao"] is StageState.COMPLETE
    assert "segment_alignment_failed" not in manifesto.warnings
    assert validar_manifesto(manifest_path, raiz)
    assert txt_path.read_text(encoding="utf-8") == exportar_txt(depois["segmentos"], {})
    pagina, _ = listar_reunioes(raiz / "indice.json", cursor=None, limit=1)
    assert pagina[0].quality_state == "pronto"
    assert not (raiz / "resultados" / f".{mid}.rollback").exists()


def test_saida_incompleta_nao_toca_resultado_parcial(tmp_path):
    raiz, mid, json_path, txt_path, manifest_path = _reuniao_parcial(tmp_path)
    antes = [p.read_bytes() for p in (json_path, txt_path, manifest_path)]

    with pytest.raises(ValueError, match="alinhamento"):
        reparar(
            raiz, mid, aplicar=True,
            diarizar_fn=lambda *_: [("FALANTE_01", 0.0, 1.0, "fala remota")],
        )

    assert [p.read_bytes() for p in (json_path, txt_path, manifest_path)] == antes
    assert validar_manifesto(manifest_path, raiz)


def test_manifesto_invalido_bloqueia_reparo(tmp_path):
    raiz, mid, json_path, _txt_path, _manifest_path = _reuniao_parcial(tmp_path)
    json_path.write_bytes(json_path.read_bytes() + b"adulterado")

    with pytest.raises(ValueError, match="manifesto"):
        reparar(raiz, mid, aplicar=True, diarizar_fn=_rotulos_validos)


def test_falha_apos_json_novo_restaurar_original(tmp_path, monkeypatch):
    import resultado_reuniao

    raiz, mid, json_path, txt_path, manifest_path = _reuniao_parcial(tmp_path)
    antes = [p.read_bytes() for p in (json_path, txt_path, manifest_path)]
    monkeypatch.setattr(
        resultado_reuniao, "salvar_manifesto",
        lambda *_args: (_ for _ in ()).throw(OSError("falha sintética")),
    )

    with pytest.raises(OSError, match="falha sintética"):
        reparar(raiz, mid, aplicar=True, diarizar_fn=_rotulos_validos)

    assert [p.read_bytes() for p in (json_path, txt_path, manifest_path)] == antes
    assert validar_manifesto(manifest_path, raiz)
    assert not (raiz / "resultados" / f".{mid}.rollback").exists()


def test_diarizacao_real_do_reparo_le_loopback_e_microfone(tmp_path, monkeypatch):
    import audio_trechos
    from audio_reader import AudioSource

    raiz, mid, json_path, _txt_path, _manifest_path = _reuniao_parcial(tmp_path)
    mic = raiz / "audio" / "mic.wav"
    mic.write_bytes((raiz / "audio" / "reuniao.wav").read_bytes())
    job = replace(FilaProcessamento(str(raiz)).obter(mid), mic=str(mic))
    vistos = []
    extrair = audio_trechos.extrair_trechos

    def espiar(path, fonte, intervalos):
        vistos.append(fonte)
        return extrair(path, fonte, intervalos)

    monkeypatch.setattr(audio_trechos, "extrair_trechos", espiar)
    monkeypatch.setattr("diarizador._carregar_encoder", lambda: object())
    monkeypatch.setattr("diarizador._extrair_embedding", lambda _encoder, _trecho: None)

    rotulos = _diarizar_job(job, carregar_segmentos(json_path))

    assert vistos == [AudioSource.LOOPBACK, AudioSource.MICROPHONE]
    assert [(round(i * 1000), round(f * 1000)) for _, i, f, _ in rotulos] == [
        (0, 1000), (500, 1500),
    ]


def test_cli_inspeciona_id_especifico_sem_aplicar(tmp_path, capsys):
    import json

    raiz, mid, _json_path, _txt_path, _manifest_path = _reuniao_parcial(tmp_path)

    codigo = main(["--raiz", str(raiz), "--meeting-id", mid])

    assert codigo == 0
    assert json.loads(capsys.readouterr().out)["estado"] == "inspecao"
