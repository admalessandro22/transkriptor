# -*- coding: utf-8 -*-
"""Autodiagnóstico e autoteste de áudio (v1.4 — FR-9.5)."""
import numpy as np

import diagnostico
from audio_utils import diagnosticar_captura
from deteccao_reuniao import Sinal


# ---------------------------------------------------------------- captura

def test_captura_com_audio_e_ok():
    r = diagnosticar_captura(np.full(1600, 0.1, dtype=np.float32))
    assert r["ok"] is True
    assert r["frames"] == 1600
    assert r["rms"] > 0


def test_captura_em_silencio_ainda_e_ok():
    """Silêncio é normal (nada tocando); o que não pode é exceção."""
    r = diagnosticar_captura(np.zeros(1600, dtype=np.float32))
    assert r["ok"] is True and r["rms"] == 0.0


def test_excecao_na_captura_vira_erro_visivel():
    """Regressão da falha que ficou dias invisível: soundcard x numpy 2."""
    erro = ValueError("The binary mode of fromstring is removed")
    r = diagnosticar_captura(None, erro=erro)
    assert r["ok"] is False
    assert "fromstring" in r["motivo"]


def test_bloco_vazio_nao_e_captura_valida():
    assert diagnosticar_captura(np.array([], dtype=np.float32))["ok"] is False


# ---------------------------------------------------------------- dependências

def test_soundcard_instalado_e_compativel_com_numpy():
    """Gate permanente: soundcard < 0.4.6 + numpy 2 grava silêncio para sempre."""
    itens = diagnostico.checar_dependencias_audio()
    erros = [i for i in itens if i["estado"] == diagnostico.ERRO]
    assert erros == [], f"dependência de áudio incompatível: {erros}"


def test_comparacao_de_versoes():
    assert diagnostico._versao_menor("0.4.3", (0, 4, 6)) is True
    assert diagnostico._versao_menor("0.4.6", (0, 4, 6)) is False
    assert diagnostico._versao_maior_ou_igual("2.4.2", (2, 0)) is True
    assert diagnostico._versao_maior_ou_igual("1.26.4", (2, 0)) is False


# ---------------------------------------------------------------- relatório

class DetectorFake:
    def instantaneo(self):
        return [
            Sinal("titulo", True, forte=True, detalhe="Meet – abc-defg-hij"),
            Sinal("microfone", False, detalhe="nenhum app"),
        ]


def test_checar_deteccao_mostra_cada_fonte():
    itens = diagnostico.checar_deteccao(DetectorFake())
    nomes = [i["nome"] for i in itens]
    assert "Fonte: titulo" in nomes and "Fonte: microfone" in nomes
    assert any(i["nome"] == "Reunião agora" and i["estado"] == diagnostico.OK for i in itens)


def test_checar_deteccao_sem_detector_reporta_erro():
    itens = diagnostico.checar_deteccao(None)
    assert itens[0]["estado"] == diagnostico.ERRO


def test_checar_audio_reporta_erro_quando_captura_falha():
    itens = diagnostico.checar_audio(
        testar_loopback=lambda: {"ok": False, "motivo": "falha na captura: boom"},
        testar_microfone=lambda: {"ok": True, "dispositivo": "Mic"},
        capturar_mic=True,
    )
    assert itens[0]["estado"] == diagnostico.ERRO
    assert "boom" in itens[0]["detalhe"]


def test_relatorio_tem_resumo_e_caminho_do_log():
    itens = [
        {"nome": "A", "estado": diagnostico.OK, "detalhe": "tudo certo"},
        {"nome": "B", "estado": diagnostico.ERRO, "detalhe": "quebrou"},
        {"nome": "C", "estado": diagnostico.AVISO, "detalhe": "atenção"},
    ]
    assert diagnostico.resumir(itens) == (1, 1)
    texto = diagnostico.formatar_texto(itens)
    assert "1 erro(s), 1 aviso(s)" in texto
    assert "quebrou" in texto


def test_salvar_relatorio_grava_arquivo(tmp_path):
    caminho = diagnostico.salvar_relatorio("conteudo", pasta=str(tmp_path))
    assert caminho.endswith(".txt")
    with open(caminho, encoding="utf-8") as f:
        assert f.read() == "conteudo"
