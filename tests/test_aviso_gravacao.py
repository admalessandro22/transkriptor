# -*- coding: utf-8 -*-
"""FR-10.B — consentimento obrigatório antes de qualquer captura."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import consentimento_gravacao
from transcricao_core import Transcritor
from transkriptor_acoes import (
    IDNO,
    IDYES,
    MB_TIMEDOUT,
    deve_iniciar_gravacao_auto,
    resposta_autoriza_gravacao,
)


@pytest.mark.parametrize(
    ("retorno", "esperado"),
    [(IDYES, True), (IDNO, False), (MB_TIMEDOUT, False), (0, False)],
)
def test_so_sim_explicito_autoriza(retorno, esperado):
    """FR-10.B2: timeout, erro e Não são sempre fail-closed."""
    assert resposta_autoriza_gravacao(retorno) is esperado


def test_dialogo_de_consentimento_falha_fechado(monkeypatch):
    monkeypatch.setattr(
        consentimento_gravacao,
        "_mostrar_dialogo",
        lambda _timeout: (_ for _ in ()).throw(OSError("indisponível")),
    )
    assert consentimento_gravacao.pedir_consentimento(timeout_seg=1) is False


def test_dialogo_nao_usa_icone_de_pergunta_com_som():
    fonte = Path(consentimento_gravacao.__file__).read_text(encoding="utf-8")
    assert "ICONQUESTION" not in fonte


def test_dialogo_eh_reapresentado_acima_da_janela_do_zoom():
    """FR-10.B1: consentimento não pode ficar atrás da janela da reunião."""
    fonte = Path(consentimento_gravacao.__file__).read_text(encoding="utf-8")
    assert "_criar_janela_consentimento" in fonte
    assert "_WS_EX_TOPMOST" in fonte
    assert "CreateWindowExW" in fonte
    assert "SetWindowPos" in fonte
    assert "SetForegroundWindow" in fonte


def test_dialogo_nao_modal_mantem_zoom_interativo():
    """UX-10.B1: decidir não pode desabilitar a janela da reunião."""
    fonte = Path(consentimento_gravacao.__file__).read_text(encoding="utf-8")
    assert "MessageBoxTimeoutW" not in fonte
    assert "DisableWindow" not in fonte
    assert "_WS_EX_TOOLWINDOW" in fonte


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
    monkeypatch.setattr(modulo, "_atualizar_config_user", lambda **kv: None)
    monkeypatch.setattr(modulo, "sincronizar_token_extensao", lambda *a, **k: None)
    monkeypatch.setattr(modulo, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(app_bandeja_menu, "notificar", lambda *a, **k: None)
    return modulo.AppTranskriptor()


def test_captura_nao_comeca_antes_de_resposta_positiva(modulo_transkriptor, monkeypatch):
    """FR-10.B1: responder Não não cria Transcritor nem arquivo."""
    app = _app(modulo_transkriptor, monkeypatch)
    app.detector = SimpleNamespace(reuniao_ativa=True)
    app._pedir_consentimento = lambda: False
    app._iniciar_transcricao = MagicMock()

    app._pedir_e_iniciar()

    assert app._recusa_reuniao_ativa is True
    app._iniciar_transcricao.assert_not_called()

    app._em_thread = lambda alvo, _nome: alvo()
    app._processar_mudanca_meet("iniciou")
    app._iniciar_transcricao.assert_not_called()

    app._processar_mudanca_meet("encerrou")
    assert app._recusa_reuniao_ativa is False


def test_sim_inicia_somente_depois_da_resposta(modulo_transkriptor, monkeypatch):
    app = _app(modulo_transkriptor, monkeypatch)
    app.detector = SimpleNamespace(reuniao_ativa=True)
    ordem = []
    app._pedir_consentimento = lambda: ordem.append("resposta") or True
    app._iniciar_transcricao = lambda: ordem.append("captura")

    app._pedir_e_iniciar()

    assert ordem == ["resposta", "captura"]
    assert app._recusa_reuniao_ativa is False


def test_resposta_tardia_apos_fim_nao_bloqueia_proxima_reuniao(
    modulo_transkriptor, monkeypatch
):
    app = _app(modulo_transkriptor, monkeypatch)
    app.detector = SimpleNamespace(reuniao_ativa=False)
    app._pedir_consentimento = lambda: False
    app._iniciar_transcricao = MagicMock()

    app._pedir_e_iniciar()

    assert app._recusa_reuniao_ativa is False
    app._iniciar_transcricao.assert_not_called()


def test_reuniao_gera_no_maximo_uma_pergunta(modulo_transkriptor, monkeypatch):
    """FR-10.B3: eventos duplicados não abrem duas caixas de consentimento."""
    app = _app(modulo_transkriptor, monkeypatch)
    app.detector = SimpleNamespace(reuniao_ativa=True)
    perguntas = []
    pendentes = []
    app._pedir_consentimento = lambda: perguntas.append(1) or False
    app._em_thread = lambda alvo, _nome: pendentes.append(alvo)

    app._processar_mudanca_meet("iniciou")
    app._processar_mudanca_meet("iniciou")
    assert len(pendentes) == 1

    pendentes[0]()
    assert perguntas == [1]
