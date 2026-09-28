# -*- coding: utf-8 -*-
"""Aprender voz da reunião escolhida, sem depender da memória da bandeja."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from assistente import HEADER_TOKEN, app, obter_token_sessao
from fila_processamento import FilaProcessamento
from resultado_edicao import SegmentoResultado, carregar_segmentos, exportar_txt, salvar_segmentos
from resultado_reuniao import criar_manifesto_estruturado, salvar_manifesto


def _audio(caminho: Path, amplitude: int) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.full(16000 * 8, amplitude, dtype="<i2").tobytes())


def _reuniao(raiz: Path, nome: str, *, amplitude: int = 5000):
    audio = raiz / "audio" / f"{nome}-lb.wav"
    mic = raiz / "audio" / f"{nome}-mic.wav"
    _audio(audio, amplitude)
    _audio(mic, -amplitude)
    fila = FilaProcessamento(str(raiz))
    mid = fila.enfileirar(
        str(audio), str(mic), nome,
        {"inicio_iso": "2026-09-24T19:22:00-03:00", "diarizar": True},
    )
    segmentos = [
        SegmentoResultado(f"lb-{i}", i * 2000, (i + 1) * 2000,
                          "loopback", f"fala {i}", "FALANTE_00", False)
        for i in range(3)
    ] + [
        SegmentoResultado(f"mic-{i}", i * 2000, (i + 1) * 2000,
                          "microphone", f"fala mic {i}", "FALANTE_01", False)
        for i in range(3)
    ]
    json_path = raiz / "resultados" / f"{mid}.json"
    salvar_segmentos(json_path, segmentos, {})
    dados = carregar_segmentos(json_path)
    txt_path = raiz / f"{nome}.txt"
    txt_path.write_text(exportar_txt(dados["segmentos"], {}), encoding="utf-8")
    manifesto = criar_manifesto_estruturado(
        meeting_id=mid, segmentos=json_path, resultado=txt_path,
        fontes_audio=[audio, mic], raiz=raiz,
        warnings=(), diarizacao_solicitada=True,
    )
    manifest_path = raiz / f"{nome}.resultado.json"
    salvar_manifesto(manifest_path, manifesto)
    fila.reivindicar(mid)
    fila.concluir(mid, str(txt_path), str(manifest_path))
    return mid, dados["revision"], audio


def _encoder_sintetico(monkeypatch):
    import diarizador

    monkeypatch.setattr(diarizador, "_carregar_encoder", lambda: object())
    monkeypatch.setattr(
        diarizador, "_extrair_embedding",
        lambda _encoder, trecho: np.full(192, float(np.mean(trecho)), dtype=np.float32),
    )


def _post(mid, revisao, rotulo="FALANTE_00"):
    return app.test_client().post(
        "/api/acoes/aprender-voz",
        json={"meeting_id": mid, "expected_revision": revisao,
              "rotulo": rotulo, "nome": "Pessoa Teste"},
        headers={HEADER_TOKEN: obter_token_sessao()},
    )


def test_aprender_voz_da_reuniao_apos_reinicio_sem_centroide_global(
    tmp_path, monkeypatch, chave_teste,
):
    import central_api

    raiz = tmp_path / "transcricoes"
    mid, revisao, _audio_path = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz), raising=False)
    _encoder_sintetico(monkeypatch)
    resposta = _post(mid, revisao)

    assert resposta.status_code == 200, resposta.get_json()
    assert resposta.get_json() == {"salvo": "Pessoa Teste"}
    assert destino.with_suffix(".enc").is_file()


def test_aprender_voz_usa_o_audio_da_reuniao_escolhida(tmp_path, monkeypatch):
    from aprendizado_voz_reuniao import embedding_da_reuniao

    raiz = tmp_path / "transcricoes"
    _mid_a, _revisao_a, _ = _reuniao(raiz, "reuniao-a", amplitude=3000)
    mid_b, revisao_b, _ = _reuniao(raiz, "reuniao-b", amplitude=-6000)
    _encoder_sintetico(monkeypatch)

    emb = embedding_da_reuniao(mid_b, "FALANTE_00", revisao_b, raiz=raiz)

    assert emb.shape == (192,)
    assert np.all(emb < 0)


def test_revisao_divergente_nao_cadastra_biometria(tmp_path, monkeypatch, chave_teste):
    import central_api

    raiz = tmp_path / "transcricoes"
    mid, _revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    _encoder_sintetico(monkeypatch)

    resposta = _post(mid, "rev-antiga")

    assert resposta.status_code == 409
    assert "Revisão" in resposta.get_json()["erro"]
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_audio_adulterado_nao_cadastra_biometria(tmp_path, monkeypatch, chave_teste):
    import central_api

    raiz = tmp_path / "transcricoes"
    mid, revisao, audio = _reuniao(raiz, "reuniao-a")
    audio.write_bytes(audio.read_bytes() + b"adulterado")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))

    resposta = _post(mid, revisao)

    assert resposta.status_code == 422
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_audio_protegido_ilegivel_nao_vira_erro_interno(tmp_path, monkeypatch, chave_teste):
    import audio_trechos
    import central_api
    from crypto_storage import ErroDescriptografia

    raiz = tmp_path / "transcricoes"
    mid, revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    monkeypatch.setattr(
        audio_trechos, "extrair_trechos",
        lambda *_args: (_ for _ in ()).throw(ErroDescriptografia("chave indisponível")),
    )

    resposta = _post(mid, revisao)

    assert resposta.status_code == 503
    assert "protegido" in resposta.get_json()["erro"]
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_falante_sem_amostras_limpas_nao_cadastra(tmp_path, monkeypatch, chave_teste):
    import central_api

    raiz = tmp_path / "transcricoes"
    mid, revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    _encoder_sintetico(monkeypatch)

    resposta = _post(mid, revisao, "FALANTE_02")

    assert resposta.status_code == 404
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_sem_chave_falha_fechado_apos_extrair_amostras(tmp_path, monkeypatch):
    import central_api
    from politica_privacidade import ProtectionMode

    raiz = tmp_path / "transcricoes"
    mid, revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    monkeypatch.setattr("identificador_voz._usar_criptografia_voz", lambda: False)
    monkeypatch.setattr("politica_privacidade.modo_efetivo", lambda: ProtectionMode.PROTECTED)
    _encoder_sintetico(monkeypatch)

    resposta = _post(mid, revisao)

    assert resposta.status_code == 503
    assert "Proteção indisponível" in resposta.get_json()["erro"]
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_modelo_de_voz_indisponivel_responde_503_sem_cadastro(tmp_path, monkeypatch, chave_teste):
    import central_api
    import diarizador

    raiz = tmp_path / "transcricoes"
    mid, revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    monkeypatch.setattr(diarizador, "_carregar_encoder", lambda: (_ for _ in ()).throw(RuntimeError("modelo sintético ausente")))

    resposta = _post(mid, revisao)

    assert resposta.status_code == 503
    assert "modelo de voz" in resposta.get_json()["erro"].lower()
    assert not destino.exists() and not destino.with_suffix(".enc").exists()


def test_amostras_incoerentes_nao_cadastram_voz(tmp_path, monkeypatch, chave_teste):
    import central_api
    import diarizador

    raiz = tmp_path / "transcricoes"
    mid, revisao, _ = _reuniao(raiz, "reuniao-a")
    destino = tmp_path / "vozes_conhecidas.json"
    monkeypatch.setattr(central_api, "PASTA_TRANSCRICOES", str(raiz))
    monkeypatch.setattr(central_api, "ARQUIVO_VOZES_CONHECIDAS", str(destino))
    monkeypatch.setattr(diarizador, "_carregar_encoder", lambda: object())
    sinais = iter([1.0, -1.0, 1.0])
    monkeypatch.setattr(
        diarizador, "_extrair_embedding",
        lambda _encoder, _trecho: np.full(192, next(sinais), dtype=np.float32),
    )

    resposta = _post(mid, revisao)

    assert resposta.status_code == 422
    assert "consistentes" in resposta.get_json()["erro"]
    assert not destino.exists() and not destino.with_suffix(".enc").exists()
