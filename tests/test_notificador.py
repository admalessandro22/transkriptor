# -*- coding: utf-8 -*-
"""UX-10.B — notificações silenciosas e reutilização do ícone existente."""
from pathlib import Path

import notificador
from notificador import configurar_icone, notificar
from transkriptor_acoes import (
    confirmacao_saida_necessaria,
    deve_parar_transcricao_por_meet,
    saida_permitida,
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


def test_fim_detectado_sempre_encerra_captura():
    assert deve_parar_transcricao_por_meet("encerrou") is True
    assert deve_parar_transcricao_por_meet("iniciou") is False
    assert deve_parar_transcricao_por_meet(None) is False


def test_fluxo_nao_contem_modo_manual_irrestrito():
    texto = TRANSKRIPTOR.read_text(encoding="utf-8")
    assert "_modo_manual" not in texto
    assert "manual=True" not in texto


def test_menu_contem_itens_fase3():
    # FR-8.2: menu pode estar em app_bandeja_menu.py
    texto = TRANSKRIPTOR.read_text(encoding="utf-8")
    menu = (REPO / "app_bandeja_menu.py").read_text(encoding="utf-8")
    combined = texto + "\n" + menu
    assert "Abrir log" in combined
    assert "abrir_log" in combined
    assert "alternar_transcricao_manual" not in combined
    assert "LOG_FILE" in combined
    assert "saida_permitida" in combined or "confirmacao_saida" in combined
