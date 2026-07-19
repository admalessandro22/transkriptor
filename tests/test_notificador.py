# -*- coding: utf-8 -*-
"""Testes de toast ao vivo e ações de menu (Fase 3 — FR-3.1–3.4)."""
from pathlib import Path

from detector_meet import titulo_eh_meet
from notificador import (
    deve_toast_ao_vivo,
    formatar_mensagem_toast,
    meet_em_foco,
)
from transkriptor_acoes import (
    confirmacao_saida_necessaria,
    deve_parar_transcricao_por_meet,
    saida_permitida,
    texto_transcricao_manual,
)

REPO = Path(__file__).resolve().parent.parent
TRANSKRIPTOR = REPO / "transkriptor.pyw"


def test_toast_quando_meet_nao_focado_e_transcricao_ativa():
    msg = "Bloco transcrito: ola equipe reuniao hoje"
    assert deve_toast_ao_vivo(msg, meet_em_foco=False, transcricao_ativa=True) is True


def test_sem_toast_quando_meet_em_foco():
    msg = "Bloco transcrito: ola equipe reuniao hoje"
    assert deve_toast_ao_vivo(msg, meet_em_foco=True, transcricao_ativa=True) is False


def test_sem_toast_prefixos_ruido():
    assert deve_toast_ao_vivo("Watchdog reiniciou thread", False, True) is False
    assert deve_toast_ao_vivo("Carregando modelo base...", False, True) is False
    assert deve_toast_ao_vivo("ERRO CRITICO: falha", False, True) is False


def test_sem_toast_mensagem_curta():
    assert deve_toast_ao_vivo("ok pronto", False, True) is False


def test_sem_toast_sem_transcricao_ativa():
    assert deve_toast_ao_vivo("Bloco transcrito longo o suficiente", False, False) is False


def test_truncar_60_chars():
    longa = "A" * 80
    assert formatar_mensagem_toast(longa) == ("A" * 60) + "..."
    assert formatar_mensagem_toast("curta") == "curta"


def test_meet_em_foco_por_titulo():
    assert meet_em_foco("Daily - Google Meet", titulo_eh_meet) is True
    assert meet_em_foco("Visual Studio Code", titulo_eh_meet) is False
    assert meet_em_foco("", titulo_eh_meet) is False


def test_saida_bloqueada_sem_confirmacao():
    assert confirmacao_saida_necessaria(True) is True
    assert saida_permitida(True, usuario_confirmou=False) is False
    assert saida_permitida(True, usuario_confirmou=True) is True
    assert saida_permitida(False, usuario_confirmou=False) is True


def test_texto_menu_transcricao_manual():
    assert texto_transcricao_manual(False) == "Transcrição manual"
    assert texto_transcricao_manual(True) == "Parar transcrição manual"


def test_modo_manual_ignora_meet_encerrado():
    assert deve_parar_transcricao_por_meet("encerrou", modo_manual=True) is False
    assert deve_parar_transcricao_por_meet("encerrou", modo_manual=False) is True
    assert deve_parar_transcricao_por_meet("iniciou", modo_manual=False) is False
    assert deve_parar_transcricao_por_meet(None, modo_manual=False) is False


def test_monitorar_meet_usa_guard_modo_manual():
    texto = TRANSKRIPTOR.read_text(encoding="utf-8")
    bloco = texto.split("def _processar_mudanca_meet")[1].split("def _monitorar_meet")[0]
    assert "deve_parar_transcricao_por_meet" in bloco
    assert "not self._modo_manual" in bloco


def test_menu_contem_itens_fase3():
    texto = TRANSKRIPTOR.read_text(encoding="utf-8")
    assert "Abrir log" in texto
    assert "abrir_log" in texto
    assert "alternar_transcricao_manual" in texto
    assert "LOG_FILE" in texto
    assert "saida_permitida" in texto or "confirmacao_saida" in texto
