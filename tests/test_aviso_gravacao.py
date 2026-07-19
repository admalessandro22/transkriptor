# -*- coding: utf-8 -*-
"""FR-2.9/FR-2.10 — aviso pós-início com opção de recusar a gravação."""
from pathlib import Path
from unittest.mock import MagicMock

from transcricao_core import Transcritor
from transkriptor_acoes import (
    IDNO,
    IDYES,
    MB_TIMEDOUT,
    deve_iniciar_gravacao_auto,
    resposta_continuar_gravacao,
)


def test_resposta_continuar_gravacao():
    """FR-2.9: só o 'Não' explícito recusa; timeout/erro continuam gravando."""
    assert resposta_continuar_gravacao(IDYES) is True
    assert resposta_continuar_gravacao(MB_TIMEDOUT) is True
    assert resposta_continuar_gravacao(0) is True
    assert resposta_continuar_gravacao(IDNO) is False


def test_deve_iniciar_gravacao_auto():
    """FR-2.10: recusa ativa bloqueia novo início automático."""
    assert deve_iniciar_gravacao_auto(False) is True
    assert deve_iniciar_gravacao_auto(True) is False


def test_descartar_apaga_arquivos_e_nao_preserva(tmp_path):
    """FR-2.9: descartar() para e remove texto + WAVs, sem mover para audio/."""
    t = Transcritor(
        pasta_saida=str(tmp_path),
        diarizar_ao_final=True,
        capturar_mic=True,
        criptografar=False,
    )
    t._abrir_arquivo()
    t._arq.write("[00:00:01] fala\n")
    t._wav.writeframes(b"\x00\x00" * 1600)
    t._wav_mic.writeframes(b"\x00\x00" * 1600)
    caminhos = (t._caminho_saida, t._caminho_wav, t._caminho_wav_mic)
    t._segmentos = [(0.0, 1.0, "fala")]
    t.rodando = True

    resultado = t.descartar()

    assert resultado is None
    for c in caminhos:
        assert not Path(c).exists(), f"{c} deveria ter sido apagado"
    pasta_audio = tmp_path / "audio"
    assert not pasta_audio.exists() or not list(pasta_audio.iterdir())
    assert t.rodando is False


def _app(modulo, monkeypatch):
    import app_bandeja_menu

    monkeypatch.setattr(modulo, "chave_disponivel", lambda: False)
    monkeypatch.setattr(modulo, "perfil_existe", lambda *a, **k: False)
    monkeypatch.setattr(modulo, "_carregar_config_user", lambda: {})
    monkeypatch.setattr(modulo, "_salvar_config_user", lambda cfg: None)
    monkeypatch.setattr(modulo, "sincronizar_token_extensao", lambda *a, **k: None)
    monkeypatch.setattr(modulo, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_bandeja_menu, "notificar", lambda *a, **k: None)
    return modulo.AppTranskriptor()


def test_recusa_descarta_e_bloqueia_ate_fim_da_reuniao(modulo_transkriptor, monkeypatch):
    """FR-2.9/2.10: 'Não' descarta a gravação e impede reinício até o Meet acabar."""
    app = _app(modulo_transkriptor, monkeypatch)
    t = MagicMock()
    t.rodando = True
    t.descartar.side_effect = lambda: setattr(t, "rodando", False)
    app.transcritor = t
    app.watchdog = None
    app._perguntar_continuar_gravacao = lambda: IDNO

    app._avisar_gravacao_iniciada()

    assert app._recusa_reuniao_ativa is True
    t.descartar.assert_called_once()
    assert app._modo_manual is False

    iniciou = []
    app._iniciar_transcricao = lambda manual=False: iniciou.append(1)
    app._processar_mudanca_meet("iniciou")
    assert iniciou == []

    app._processar_mudanca_meet("encerrou")
    assert app._recusa_reuniao_ativa is False
    app._processar_mudanca_meet("iniciou")
    assert iniciou == [1]


def test_sim_ou_timeout_mantem_gravacao(modulo_transkriptor, monkeypatch):
    """FR-2.9: Sim ou timeout não descartam nada."""
    app = _app(modulo_transkriptor, monkeypatch)
    t = MagicMock()
    t.rodando = True
    app.transcritor = t
    for resposta in (IDYES, MB_TIMEDOUT):
        app._perguntar_continuar_gravacao = lambda r=resposta: r
        app._avisar_gravacao_iniciada()
        assert app._recusa_reuniao_ativa is False
        t.descartar.assert_not_called()


def test_aviso_so_para_gravacao_automatica(modulo_transkriptor, monkeypatch):
    """FR-2.9: início manual não dispara o diálogo; automático dispara."""
    import transcricao_core

    app = _app(modulo_transkriptor, monkeypatch)
    fake = MagicMock()
    fake.rodando = False
    monkeypatch.setattr(transcricao_core, "Transcritor", MagicMock(return_value=fake))
    monkeypatch.setattr(modulo_transkriptor, "Watchdog", MagicMock())

    alvos = []

    class ThreadFalsa:
        def __init__(self, target=None, daemon=None, args=(), name=None):
            alvos.append(target)

        def start(self):
            pass

    monkeypatch.setattr(modulo_transkriptor.threading, "Thread", ThreadFalsa)

    app._iniciar_transcricao(manual=True)
    assert app._avisar_gravacao_iniciada not in alvos

    app.transcritor = None
    app._modo_manual = False
    app._iniciar_transcricao(manual=False)
    assert app._avisar_gravacao_iniciada in alvos
