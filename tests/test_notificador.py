# -*- coding: utf-8 -*-
"""UX-10.B — notificações silenciosas e reutilização do ícone existente."""
from pathlib import Path

import notificador
from notificador import configurar_icone, notificar
from transkriptor_acoes import (
    confirmacao_saida_necessaria,
    deve_parar_transcricao_por_meet,
    saida_permitida,
    texto_transcricao_manual,
)

REPO = Path(__file__).resolve().parent.parent
TRANSKRIPTOR = REPO / "transkriptor.pyw"


class IconeFake:
    def __init__(self):
        self.chamadas = []

    def notify(self, mensagem, titulo):
        self.chamadas.append((titulo, mensagem))


def test_notificacao_padrao_nao_abre_balao():
    icone = IconeFake()
    configurar_icone(icone)
    notificar("Transkriptor", "trecho sensível")
    assert icone.chamadas == []


def test_notificacao_visivel_reutiliza_icone_existente():
    icone = IconeFake()
    configurar_icone(icone)
    notificar("Transkriptor", "Processamento concluído", visivel=True)
    assert icone.chamadas == [("Transkriptor", "Processamento concluído")]


def test_modulo_nao_referencia_backend_plyer():
    assert "plyer" not in Path(notificador.__file__).read_text(encoding="utf-8").lower()


def test_backend_removido_das_dependencias():
    requisitos = (REPO / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "plyer" not in requisitos


def test_saida_bloqueada_sem_confirmacao():
    assert confirmacao_saida_necessaria(True) is True
    assert saida_permitida(True, usuario_confirmou=False) is False
    assert saida_permitida(True, usuario_confirmou=True) is True
    assert saida_permitida(False, usuario_confirmou=False) is True


def test_texto_menu_transcricao_manual():
    assert texto_transcricao_manual(False) == "Iniciar transcrição manual"
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
    # FR-8.2: menu pode estar em app_bandeja_menu.py
    texto = TRANSKRIPTOR.read_text(encoding="utf-8")
    menu = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")
    combined = texto + "\n" + menu
    assert "Abrir log" in combined
    assert "abrir_log" in combined
    assert "alternar_transcricao_manual" in combined
    assert "LOG_FILE" in combined
    assert "saida_permitida" in combined or "confirmacao_saida" in combined
