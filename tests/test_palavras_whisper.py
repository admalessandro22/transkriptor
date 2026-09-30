# -*- coding: utf-8 -*-
"""T-15.C1 / FR-15.C1 — tempos por palavra do Whisper, sem mudar o texto."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from audio_fontes import AudioSource, SegmentoSTT, mesclar_segmentos, transcrever_fonte


class _ModeloComPalavras:
    """Dublê do faster-whisper: devolve palavras só se pedirem word_timestamps."""

    def __init__(self):
        self.chamadas = []

    def transcribe(self, samples, **kwargs):
        self.chamadas.append(kwargs)
        palavras = None
        if kwargs.get("word_timestamps"):
            palavras = [
                SimpleNamespace(word=" Bom", start=0.10, end=0.32, probability=0.98),
                SimpleNamespace(word=" dia", start=0.32, end=0.61, probability=0.91),
                SimpleNamespace(word=" ", start=0.61, end=0.62, probability=0.10),
            ]
        segmento = SimpleNamespace(text=" Bom dia", start=0.10, end=0.61, words=palavras)
        return [segmento], SimpleNamespace()


def _wav(wav_sintetico, segundos=1.0):
    return wav_sintetico("loopback", frames=int(16_000 * segundos))


def test_transcricao_pede_tempos_por_palavra(wav_sintetico):
    modelo = _ModeloComPalavras()
    transcrever_fonte(_wav(wav_sintetico), AudioSource.LOOPBACK, model=modelo)
    assert modelo.chamadas and all(c.get("word_timestamps") is True for c in modelo.chamadas)


def test_segmento_tem_palavras_no_tempo_absoluto(wav_sintetico):
    modelo = _ModeloComPalavras()
    segs = transcrever_fonte(_wav(wav_sintetico, 3.0), AudioSource.LOOPBACK, model=modelo, max_seconds=1.0)
    segundo_bloco = segs[1]
    assert [p.w for p in segundo_bloco.words] == ["Bom", "dia"]
    assert segundo_bloco.words[0].ini_ms == 1100
    assert segundo_bloco.words[1].fim_ms == 1610
    assert segundo_bloco.words[0].prob == pytest.approx(0.98)


def test_texto_do_segmento_inalterado(wav_sintetico):
    segs = transcrever_fonte(_wav(wav_sintetico), AudioSource.LOOPBACK, model=_ModeloComPalavras())
    assert segs[0].text == "Bom dia"
    assert (segs[0].start_ms, segs[0].end_ms) == (100, 610)


def test_modelo_sem_palavras_deixa_tupla_vazia(wav_sintetico):
    class _SemPalavras(_ModeloComPalavras):
        def transcribe(self, samples, **kwargs):
            return [SimpleNamespace(text="oi", start=0.0, end=0.5)], SimpleNamespace()

    segs = transcrever_fonte(_wav(wav_sintetico), AudioSource.LOOPBACK, model=_SemPalavras())
    assert segs[0].words == ()


def test_fusao_preserva_palavras():
    from audio_fontes import PalavraSTT

    palavras = (PalavraSTT("oi", 0, 200, 0.9),)
    lb = [SegmentoSTT("lb-0-0", 0, 200, AudioSource.LOOPBACK, "oi", False, palavras)]
    mic = [SegmentoSTT("mic-0-0", 100, 300, AudioSource.MICROPHONE, "tudo bem", False)]
    fundidos = mesclar_segmentos(lb, mic)
    assert fundidos[0].words == palavras
    assert fundidos[1].overlap is True


def test_resultado_persiste_e_recarrega_palavras(tmp_path):
    from audio_fontes import PalavraSTT
    from resultado_edicao import carregar_segmentos, montar_payload, salvar_segmentos
    from resultado_pipeline import criar_segmentos

    fundidos = [SegmentoSTT("lb-0-0", 0, 610, AudioSource.LOOPBACK, "Bom dia", False,
                            (PalavraSTT("Bom", 100, 320, 0.98), PalavraSTT("dia", 320, 610, 0.91)))]
    segmentos, _ = criar_segmentos(fundidos)
    caminho = tmp_path / "seg.json"
    salvar_segmentos(caminho, segmentos, {})
    dados = carregar_segmentos(caminho)
    assert dados["segmentos"][0]["words"] == [
        {"w": "Bom", "ini_ms": 100, "fim_ms": 320, "prob": 0.98},
        {"w": "dia", "ini_ms": 320, "fim_ms": 610, "prob": 0.91},
    ]
    # Reescrita pela edição (caminho Mapping) não perde as palavras.
    reescrito = montar_payload(dados["segmentos"], {})
    assert reescrito["segmentos"][0]["words"] == dados["segmentos"][0]["words"]


def test_resultado_antigo_sem_palavras_carrega(tmp_path):
    from resultado_edicao import carregar_segmentos, salvar_segmentos
    from resultado_pipeline import criar_segmentos

    segmentos, _ = criar_segmentos([SegmentoSTT("lb-0-0", 0, 500, AudioSource.LOOPBACK, "oi", False)])
    caminho = tmp_path / "seg.json"
    salvar_segmentos(caminho, segmentos, {})
    dados = carregar_segmentos(caminho)
    assert "words" not in dados["segmentos"][0]


@pytest.mark.parametrize("words", [
    "nao-lista",
    [{"w": "oi", "ini_ms": 10, "fim_ms": 5, "prob": 0.5}],
    [{"w": 3, "ini_ms": 0, "fim_ms": 5, "prob": 0.5}],
    [{"w": "oi", "ini_ms": 0.5, "fim_ms": 5, "prob": 0.5}],
])
def test_palavras_malformadas_rejeitadas(words):
    from resultado_edicao import validar_dados_segmentos

    dados = {"schema_version": 1, "revision": "rev-1", "segmentos": [
        {"segment_id": "s", "start_ms": 0, "end_ms": 10, "audio_source": "loopback",
         "text": "oi", "speaker_cluster_id": "FALANTE_00", "words": words}]}
    import resultado_edicao

    dados["schema_version"] = resultado_edicao.VERSAO_SEGMENTOS
    with pytest.raises(ValueError):
        validar_dados_segmentos(dados)


def _resultado_com_palavras(tmp_path, monkeypatch):
    from audio_fontes import PalavraSTT
    from resultado_edicao import SegmentoResultado, salvar_segmentos

    monkeypatch.setattr("assistente.PASTA_TRANSCRICOES", str(tmp_path))
    (tmp_path / "resultados").mkdir()
    caminho = tmp_path / "resultados" / "reuniao-w.json"
    salvar_segmentos(caminho, [SegmentoResultado(
        "s1", 0, 610, "loopback", "Bom dia", "FALANTE_00",
        words=(PalavraSTT("Bom", 100, 320, 0.98), PalavraSTT("dia", 320, 610, 0.91)))], {})
    return caminho


def test_api_de_resultado_nao_envia_palavras(tmp_path, monkeypatch, headers_token):
    """A tela não usa palavras; elas ficam no disco para o alinhamento."""
    from assistente import app

    _resultado_com_palavras(tmp_path, monkeypatch)
    dados = app.test_client().get("/api/reunioes/reuniao-w/resultado", headers=headers_token).get_json()
    assert dados["segmentos"][0]["text"] == "Bom dia"
    assert "words" not in dados["segmentos"][0]


def test_correcao_pela_api_preserva_palavras(tmp_path, monkeypatch, headers_token):
    from assistente import app
    from resultado_edicao import carregar_segmentos

    caminho = _resultado_com_palavras(tmp_path, monkeypatch)
    resposta = app.test_client().post(
        "/api/reunioes/reuniao-w/correcao", headers=headers_token,
        json={"expected_revision": "rev-1", "speaker_cluster_id": "FALANTE_00", "display_name": "Ana"})
    assert resposta.status_code == 200
    assert [p["w"] for p in carregar_segmentos(caminho)["segmentos"][0]["words"]] == ["Bom", "dia"]
