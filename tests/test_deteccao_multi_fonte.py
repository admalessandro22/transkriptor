# -*- coding: utf-8 -*-
"""Detecção multi-fonte de reunião (v1.4 — FR-9.1, FR-9.2, FR-9.3)."""
import pytest

from deteccao_reuniao import (
    DetectorReuniao,
    FonteMicrofone,
    FontePonte,
    FonteTitulo,
    Sinal,
    fundir,
)
from detector_meet import classificar_titulo, titulo_eh_meet


# ---------------------------------------------------------------- FR-9.2 títulos

@pytest.mark.parametrize(
    "titulo",
    [
        # formato atual do Google Meet (travessão) — era o que não casava
        "Meet – abc-defg-hij",
        "Meet – abc-defg-hij - Google Chrome",
        "Meet - abc-defg-hij - Google Chrome",
        "Meet — abcd-efgh-ijk — Microsoft​ Edge",
        "Meet – Reunião semanal de produto - Google Chrome",
        # formato legado
        "Reuniao de equipe - Google Meet",
        "Daily - Google Meet - Google Chrome",
        "Planejamento - Google Meet — Microsoft​ Edge",
        "meet.google.com/abc-defg-hij",
        # Zoom em chamada
        "Zoom Meeting",
        "Reunião do Zoom",
    ],
)
def test_titulos_de_reuniao_sao_detectados(titulo):
    assert titulo_eh_meet(titulo) is True


@pytest.mark.parametrize(
    "titulo",
    [
        "como usar google meet - Pesquisa Google",
        "Novidades do Google Meet - Google Chrome",
        "como configurar Google Meet - Pesquisa Google",
        "Google Meet Help - Google Chrome",
        "Google Meet - Sign in",
        "tutorial google meet ajuda",
        "Google Meet - Google Chrome",  # página inicial, sem sala
        "Zoom Workplace",  # app aberto, fora de chamada
        "(32) WhatsApp - Google Chrome",
        "",
        "   ",
    ],
)
def test_titulos_que_nao_sao_reuniao(titulo):
    assert titulo_eh_meet(titulo) is False


def test_sala_com_palavra_de_exclusao_ainda_e_reuniao():
    """Regressão: 'ajuda' não pode derrubar um casamento forte (FR-9.2)."""
    assert classificar_titulo("Meet – hlp-abcd-xyz - Google Chrome") == "forte"
    assert titulo_eh_meet("Meet – Reunião de ajuda ao cliente") is True


def test_classificacao_distingue_forte_de_nomeado():
    assert classificar_titulo("Meet – abc-defg-hij") == "forte"
    assert classificar_titulo("Daily - Google Meet") == "nomeado"
    assert classificar_titulo("Bloco de notas") == ""


# ---------------------------------------------------------------- fontes

def test_fonte_titulo_reporta_sinal_forte():
    fonte = FonteTitulo(lambda: ["Bloco de notas", "Meet – abc-defg-hij - Google Chrome"])
    sinal = fonte.ler()
    assert sinal.ativo is True and sinal.forte is True
    assert "abc-defg-hij" in sinal.detalhe


def test_fonte_titulo_sem_reuniao():
    fonte = FonteTitulo(lambda: ["Bloco de notas", "Spotify"])
    assert fonte.ler().ativo is False


def test_fonte_titulo_nao_derruba_monitor_quando_falha():
    def explode():
        raise OSError("falha do pygetwindow")

    assert FonteTitulo(explode).ler().ativo is False


def test_fonte_microfone_e_sinal_fraco():
    sinal = FonteMicrofone(lambda: ["chrome.exe"]).ler()
    assert sinal.ativo is True
    assert sinal.forte is False  # sozinho, precisa se sustentar por mais ciclos
    assert "chrome.exe" in sinal.detalhe


def test_fonte_ponte_e_sinal_forte():
    class PonteFake:
        def reuniao_ativa(self):
            return True

    assert FontePonte(PonteFake()).ler().forte is True
    assert FontePonte(None).ler().ativo is False


def test_fundir_agrega_fontes():
    algum, forte, nomes = fundir(
        [Sinal("titulo", False), Sinal("microfone", True), Sinal("extensao", True, forte=True)]
    )
    assert algum is True and forte is True
    assert nomes == ["microfone", "extensao"]


# ---------------------------------------------------------------- FR-9.1 fusão

class FonteFake:
    def __init__(self, nome, forte=False):
        self.nome = nome
        self.ativo = False
        self._forte = forte

    def ler(self):
        return Sinal(self.nome, self.ativo, forte=self._forte)


def _detector(**kwargs):
    forte = FonteFake("titulo", forte=True)
    fraca = FonteFake("microfone")
    opcoes = {"confirma_inicio": 2, "confirma_inicio_fraca": 4, "confirma_fim": 6}
    opcoes.update(kwargs)
    return DetectorReuniao([forte, fraca], **opcoes), forte, fraca


def test_sinal_forte_inicia_em_dois_ciclos():
    det, forte, _fraca = _detector()
    forte.ativo = True
    assert det.verificar() is None
    assert det.verificar() == "iniciou"
    assert det.reuniao_ativa is True


def test_sinal_fraco_sozinho_exige_mais_ciclos():
    """Chrome pegando o microfone por 10s (áudio de WhatsApp) não vira reunião."""
    det, _forte, fraca = _detector()
    fraca.ativo = True
    assert det.verificar() is None
    assert det.verificar() is None
    assert det.verificar() is None
    assert det.verificar() == "iniciou"


def test_sinal_fraco_curto_nao_inicia():
    det, _forte, fraca = _detector()
    fraca.ativo = True
    det.verificar()
    det.verificar()
    fraca.ativo = False
    assert det.verificar() is None
    assert det.reuniao_ativa is False


def test_troca_de_aba_nao_encerra_a_reuniao():
    """Regressão central: título some, microfone segura (FR-9.1)."""
    det, forte, fraca = _detector()
    forte.ativo = True
    fraca.ativo = True
    det.verificar()
    assert det.verificar() == "iniciou"

    forte.ativo = False  # usuário trocou de aba: o título sumiu
    for _ in range(10):
        assert det.verificar() is None
    assert det.reuniao_ativa is True


def test_fim_so_quando_nenhuma_fonte_ve_reuniao():
    det, forte, fraca = _detector()
    forte.ativo = fraca.ativo = True
    det.verificar()
    det.verificar()
    forte.ativo = fraca.ativo = False
    for _ in range(5):
        assert det.verificar() is None
    assert det.verificar() == "encerrou"
    assert det.reuniao_ativa is False


def test_fim_e_mais_lento_que_inicio():
    det, _f, _fr = _detector()
    assert det.confirma_fim > det.confirma_inicio


def test_fonte_que_explode_nao_derruba_o_detector():
    class FonteRuim:
        nome = "ruim"

        def ler(self):
            raise RuntimeError("boom")

    forte = FonteFake("titulo", forte=True)
    det = DetectorReuniao([FonteRuim(), forte], confirma_inicio=2, confirma_fim=6)
    forte.ativo = True
    det.verificar()
    assert det.verificar() == "iniciou"


def test_instantaneo_expoe_todas_as_fontes_para_diagnostico():
    det, forte, fraca = _detector()
    forte.ativo = True
    sinais = det.instantaneo()
    assert [s.fonte for s in sinais] == ["titulo", "microfone"]
    assert sinais[0].ativo is True and sinais[1].ativo is False
