# -*- coding: utf-8 -*-
"""Proteção efetiva de áudio e resultado no pipeline de produção."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from diarizacao_final import preservar_audios
from fila_processamento import FilaProcessamento
from politica_privacidade import ProtectionMode
from processador_reuniao import processar_job
from resultado_reuniao import carregar_manifesto, validar_manifesto
from resultado_storage import ResultadoStorage
import pytest


def test_pipeline_protegido_nao_deixa_audio_ou_resultado_plaintext(
    tmp_path, wav_sintetico, chave_teste, monkeypatch,
):
    import politica_privacidade

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    origem = wav_sintetico("fala")
    preservados = preservar_audios(
        ProtectionMode.PROTECTED, str(origem), pasta_audio=str(raiz / "audio"),
    )
    assert len(preservados) == 1
    assert preservados[0].endswith(".tks")
    assert not origem.exists()
    # Mudança de preferência entre captura e worker não rebaixa o artefato.
    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.COMPATIBLE)
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(
        preservados[0], None, "reuniao-protegida",
        {"origem": "meet", "diarizar": False, "idioma": "pt"},
    )
    modelo = MagicMock()
    modelo.transcribe.return_value = ([
        SimpleNamespace(text="fala sintética", start=0, end=0.1)
    ], MagicMock())
    processar_job(job_id, modelo_whisper=modelo, fila=fila)
    job = fila.obter(job_id)
    manifesto = carregar_manifesto(job.manifesto_resultado)
    assert job.estado == "ready"
    assert manifesto.segments_ref.relative_path.endswith(".json.enc")
    assert not list(raiz.rglob("*.wav"))
    assert not list((raiz / "resultados").glob("*.json"))
    assert not list(raiz.glob("*.txt"))
    assert validar_manifesto(job.manifesto_resultado, raiz)


def test_audio_sem_dpapi_fica_pendente_e_preserva_original(tmp_path, wav_sintetico, monkeypatch):
    import crypto_storage
    from politica_privacidade import ProtectionState

    origem = wav_sintetico("fala")
    original = origem.read_bytes()
    monkeypatch.setattr(crypto_storage, "garantir_chave_mestra", lambda: False)
    estados = []
    caminhos = preservar_audios(ProtectionMode.PROTECTED, str(origem),
                                pasta_audio=str(tmp_path / "audio"), estados=estados)
    assert len(estados) == 1 and estados[0].state == ProtectionState.PROTECTION_PENDING
    assert len(caminhos) == 1 and "restrito" in caminhos[0]
    assert __import__("pathlib").Path(caminhos[0]).read_bytes() == original
    assert not list((tmp_path / "audio").glob("*.tks"))


def test_storage_cifrado_valida_schema_hash_e_confinamento(tmp_path, chave_teste):
    from dataclasses import replace

    storage = ResultadoStorage(tmp_path, ProtectionMode.PROTECTED)
    ref = storage.save("m1", {"schema_version": 1, "revision": "rev-1", "segmentos": [
        {"text": "sem campos obrigatórios"}], "mapeamento": {}})
    with pytest.raises(ValueError, match="segmento estruturado"):
        storage.load(ref)
    ref_valido = storage.save("m1", {"schema_version": 1, "revision": "rev-1",
                                      "segmentos": [], "mapeamento": {}, "historico": []})
    assert storage.load(ref_valido)["revision"] == "rev-1"
    with pytest.raises(ValueError, match="referência"):
        storage.load(replace(ref_valido, relative_path="../fora.json.enc"))
    (tmp_path / ref_valido.relative_path).write_bytes(b"cifra adulterada")
    with pytest.raises(ValueError, match="referência"):
        storage.load(ref_valido)


def test_recuperacao_orfao_protegido_gera_tkas_sem_sobrescrever(tmp_path, wav_sintetico,
                                                                chave_teste, monkeypatch):
    import politica_privacidade
    import crypto_storage
    from crypto_storage import recuperar_orfaos_wav, iterar_audio_tkas

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    monkeypatch.setattr(crypto_storage, "criptografia_ativa", lambda: False)
    pasta = tmp_path / "audio"
    pasta.mkdir()
    origem = wav_sintetico("fala")
    wav = pasta / "reuniao.wav"
    wav.write_bytes(origem.read_bytes())
    assert recuperar_orfaos_wav(str(pasta)) == 1
    assert not wav.exists()
    tks = pasta / "reuniao.tks"
    assert b"".join(iterar_audio_tkas(tks)) == origem.read_bytes()
    outro = wav_sintetico("outra")
    wav.write_bytes(outro.read_bytes())
    cifrado_original = tks.read_bytes()
    assert recuperar_orfaos_wav(str(pasta)) == 0
    assert tks.read_bytes() == cifrado_original
    assert (pasta / "restrito" / "reuniao.wav").read_bytes() == outro.read_bytes()


@pytest.mark.parametrize("tipo_falha", [OSError, KeyboardInterrupt])
def test_edicao_falha_intermediaria_preserva_manifesto_e_revisao(
    tmp_path, wav_sintetico, chave_teste, monkeypatch, tipo_falha,
):
    import crypto_storage
    import politica_privacidade

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    audio = preservar_audios(ProtectionMode.PROTECTED, str(wav_sintetico("fala")),
                             pasta_audio=str(raiz / "audio"))[0]
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(audio, None, "reuniao-edicao", {"diarizar": False})
    modelo = MagicMock()
    modelo.transcribe.return_value = ([SimpleNamespace(text="fala", start=0, end=0.1)], MagicMock())
    processar_job(job_id, modelo_whisper=modelo, fila=fila)
    job = fila.obter(job_id)
    storage = ResultadoStorage(raiz, ProtectionMode.PROTECTED)
    manifesto_antes = carregar_manifesto(job.manifesto_resultado)
    monkeypatch.setattr(crypto_storage, "salvar_transcricao",
                        lambda *_a: (_ for _ in ()).throw(tipo_falha("falha simulada")))
    with pytest.raises(tipo_falha):
        storage.editar(job_id, acao="corrigir", expected_revision="rev-1",
                      speaker_cluster_id="FALANTE_00", display_name="Ana")
    if tipo_falha is KeyboardInterrupt:
        assert not validar_manifesto(job.manifesto_resultado, raiz)
        assert storage._journal(job_id).is_dir()
        storage.manifesto(job_id)  # simula reabertura após interrupção abrupta
    assert validar_manifesto(job.manifesto_resultado, raiz)
    assert storage.manifesto(job_id)[1] == manifesto_antes
    assert storage.load(manifesto_antes.segments_ref)["revision"] == "rev-1"


def test_correcoes_concorrentes_nao_perdem_revisao(tmp_path, wav_sintetico,
                                                  chave_teste, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import politica_privacidade

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    audio = preservar_audios(ProtectionMode.PROTECTED, str(wav_sintetico("fala")),
                             pasta_audio=str(raiz / "audio"))[0]
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(audio, None, "reuniao-concorrente", {"diarizar": False})
    modelo = MagicMock()
    modelo.transcribe.return_value = ([SimpleNamespace(text="fala", start=0, end=0.1)], MagicMock())
    processar_job(job_id, modelo_whisper=modelo, fila=fila)
    storage = ResultadoStorage(raiz, ProtectionMode.PROTECTED)

    def corrigir(nome):
        try:
            return storage.editar(job_id, acao="corrigir", expected_revision="rev-1",
                                  speaker_cluster_id="FALANTE_00", display_name=nome)
        except ValueError:
            return "conflito"

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(corrigir, ("Ana", "Bia")))
    assert sorted(resultados) == ["conflito", "rev-2"]
    manifesto = storage.manifesto(job_id)[1]
    assert storage.load(manifesto.segments_ref)["revision"] == "rev-2"


def test_diarizacao_protegida_nao_cria_temp_plaintext(tmp_path, wav_sintetico,
                                                     chave_teste, monkeypatch):
    import politica_privacidade
    import retranscritor
    import diarizador

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    lb = wav_sintetico("loopback")
    mic = wav_sintetico("microfone")
    lb.rename(lb.with_name("reuniao_audio.wav"))
    mic.rename(mic.with_name("reuniao_mic.wav"))
    audio, microfone = preservar_audios(ProtectionMode.PROTECTED,
                                        str(tmp_path / "reuniao_audio.wav"),
                                        str(tmp_path / "reuniao_mic.wav"),
                                        pasta_audio=str(raiz / "audio"))
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(audio, microfone, "reuniao-diar", {"diarizar": True})
    modelo = MagicMock()
    modelo.transcribe.return_value = ([SimpleNamespace(text="fala", start=0, end=0.1)], MagicMock())
    monkeypatch.setattr(retranscritor.tempfile, "TemporaryDirectory",
                        lambda **_kw: (_ for _ in ()).throw(AssertionError("temp plaintext")))
    observado = {}

    def diarizar_fake(trechos, segmentos, **kwargs):
        observado["trechos"] = trechos
        return ([("FALANTE_00", *segmentos[0])], {})

    monkeypatch.setattr(diarizador, "diarizar", diarizar_fake)
    processar_job(job_id, modelo_whisper=modelo, fila=fila)
    assert observado["trechos"] and observado["trechos"][0].size > 0
    assert not list(raiz.rglob("*.wav"))
    assert not list(raiz.rglob("*.txt"))


def test_mic_cifrado_reforca_voce_em_memoria(tmp_path, chave_teste):
    import numpy as np
    import wave
    from audio_trechos import extrair_trechos
    from audio_reader import AudioSource
    from diarizador import reforcar_rotulo_por_mic

    wav = tmp_path / "reuniao_mic.wav"
    with wave.open(str(wav), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(16000)
        arquivo.writeframes((np.ones(16000) * 0.5 * 32767).astype(np.int16).tobytes())
    tks = preservar_audios(ProtectionMode.PROTECTED, str(wav),
                           pasta_audio=str(tmp_path / "audio"))[0]
    trechos = extrair_trechos(__import__("pathlib").Path(tks), AudioSource.MICROPHONE,
                              [(0.0, 1.0, "eu falo")])
    resultado = reforcar_rotulo_por_mic(
        [("FALANTE_00", 0.0, 1.0, "eu falo")], None,
        limiar_rms=0.1, rotulo_usuario="VOCÊ",
        rms_loopback_por_segmento=[0.1], trechos_mic=trechos,
    )
    assert resultado[0][0] == "VOCÊ"


def test_resultado_cifrado_api_corrige_e_desfaz_sem_plaintext(
    tmp_path, wav_sintetico, chave_teste, monkeypatch, headers_token,
):
    from assistente import app
    import politica_privacidade

    monkeypatch.setattr(politica_privacidade, "modo_efetivo", lambda: ProtectionMode.PROTECTED)
    raiz = tmp_path / "transcricoes"
    raiz.mkdir()
    audio = preservar_audios(ProtectionMode.PROTECTED, str(wav_sintetico("fala")),
                             pasta_audio=str(raiz / "audio"))[0]
    fila = FilaProcessamento(str(raiz))
    job_id = fila.enfileirar(audio, None, "reuniao-api", {"diarizar": False, "idioma": "pt"})
    modelo = MagicMock()
    modelo.transcribe.return_value = ([SimpleNamespace(text="fala", start=0, end=0.1)], MagicMock())
    processar_job(job_id, modelo_whisper=modelo, fila=fila)
    job = fila.obter(job_id)
    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(raiz))
    client = app.test_client()
    assert job_id in client.get("/api/reunioes", headers=headers_token).get_json()
    url = f"/api/reunioes/{job_id}"
    primeiro = client.get(f"{url}/resultado", headers=headers_token)
    assert primeiro.status_code == 200
    assert primeiro.get_json()["revision"] == "rev-1"
    resposta = client.post(f"{url}/correcao", headers=headers_token,
                           json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00",
                                 "display_name": "Ana"})
    assert resposta.status_code == 200
    assert resposta.get_json()["revision"] == "rev-2"
    assert client.post(f"{url}/correcao", headers=headers_token,
                       json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00",
                             "display_name": "Bia"}).status_code == 409
    assert client.get(f"{url}/resultado", headers=headers_token).get_json()["mapeamento"]["FALANTE_00"]["display_name"] == "Ana"
    desfazer = client.post(f"{url}/desfazer", headers=headers_token,
                           json={"expected_revision": "rev-2"})
    assert desfazer.status_code == 200
    assert client.get(f"{url}/resultado", headers=headers_token).get_json()["mapeamento"] == {}
    assert validar_manifesto(job.manifesto_resultado, raiz)
    assert not list((raiz / "resultados").glob("*.json"))
    assert not list(raiz.glob("*.txt"))
