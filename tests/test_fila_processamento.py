# -*- coding: utf-8 -*-
"""FR-10.D1/D2/D4 e SEC-10.F4 — fila durável pós-reunião."""
from __future__ import annotations

from pathlib import Path

import pytest

from fila_processamento import FilaProcessamento


@pytest.fixture
def fila(tmp_path):
    pasta = tmp_path / "transcricoes"
    pasta.mkdir()
    return FilaProcessamento(str(pasta))


@pytest.fixture
def audio_valido(fila):
    audio = fila.pasta_transcricoes / "audio" / "reuniao.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"RIFF" + b"\x00" * 64)
    return str(audio)


def test_job_nao_aceita_audio_fora_da_pasta(tmp_path, fila):
    fora = tmp_path / "fora.wav"
    fora.write_bytes(b"RIFF")
    with pytest.raises(ValueError):
        fila.enfileirar(str(fora), None, "reuniao", {})


def test_processing_interrompido_volta_a_pending(fila, audio_valido):
    job_id = fila.enfileirar(audio_valido, None, "reuniao", {"origem": "meet"})
    reivindicado = fila.reivindicar_proximo()
    assert reivindicado.id == job_id
    assert reivindicado.estado == "processing"

    assert fila.recuperar_interrompidos() == 1
    assert fila.obter(job_id).estado == "pending"


def test_job_json_nao_contem_texto_falado(fila, audio_valido):
    segredo = "conteúdo confidencial falado na reunião"
    job_id = fila.enfileirar(
        audio_valido,
        None,
        "reuniao",
        {"origem": "meet", "texto": segredo},
    )
    bruto = fila.caminho_job(job_id).read_text(encoding="utf-8")
    assert segredo not in bruto
    assert "texto" not in bruto


def test_escrita_do_job_e_atomica(monkeypatch, fila, audio_valido):
    import fila_processamento

    chamadas = []
    original = fila_processamento.os.replace

    def substituir(origem, destino):
        chamadas.append((Path(origem), Path(destino)))
        return original(origem, destino)

    monkeypatch.setattr(fila_processamento.os, "replace", substituir)
    job_id = fila.enfileirar(audio_valido, None, "reuniao", {})

    assert chamadas
    assert chamadas[-1][1] == fila.caminho_job(job_id)
    assert not list(fila.pasta_jobs.glob("*.tmp"))


def test_concluir_e_falhar_preservam_estados_seguros(fila, audio_valido):
    pronto_id = fila.enfileirar(audio_valido, None, "reuniao-pronta", {})
    assert fila.reivindicar_proximo().id == pronto_id
    resultado = fila.pasta_transcricoes / "reuniao-pronta.txt"
    resultado.write_text("resultado", encoding="utf-8")
    fila.concluir(pronto_id, str(resultado))
    pronto = fila.obter(pronto_id)
    assert pronto.estado == "ready"
    assert pronto.resultado == str(resultado.resolve())

    falho_id = fila.enfileirar(audio_valido, None, "reuniao-falha", {})
    assert fila.reivindicar_proximo().id == falho_id
    fila.falhar(falho_id, "modelo_indisponivel")
    falho = fila.obter(falho_id)
    assert falho.estado == "failed"
    assert falho.erro_seguro == "modelo_indisponivel"
    assert Path(falho.audio).is_file()


@pytest.mark.parametrize("base", ["../fora", "sub/pasta", "", "."])
def test_base_saida_rejeita_path_traversal(fila, audio_valido, base):
    with pytest.raises(ValueError):
        fila.enfileirar(audio_valido, None, base, {})
