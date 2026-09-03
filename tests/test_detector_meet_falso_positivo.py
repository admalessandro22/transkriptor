# -*- coding: utf-8 -*-
"""FR-10.A3 — só título inequívoco de reunião pode iniciar gravação.

O padrão `^Meet – <qualquer coisa>` existe para a sala nomeada pelo Calendar,
mas casava também com `Meet - Google Chrome` — o título da janela quando a aba
do Meet está aberta **fora** de uma chamada. Isso pedia consentimento e abria
gravação com o usuário só olhando a página inicial do Meet.

A distinção: numa chamada real, depois de `Meet – ` vem o nome da sala e só
então o navegador. Fora da chamada, o que vem depois é o navegador e mais nada.
"""
from __future__ import annotations

import pytest

from detector_meet import classificar_titulo, titulo_eh_meet

FORA_DE_CHAMADA = [
    "Meet - Google Chrome",
    "Meet – Google Chrome",
    "Meet — Google Chrome",
    "Meet - Microsoft Edge",
    "Meet – Mozilla Firefox",
    "Meet - Brave",
    "Meet - Chromium",
    "Meet - Vivaldi",
    "Meet - Opera",
    "Meet - Google Chrome - Alessandro",
]

EM_CHAMADA = [
    "Meet - abc-defg-hij - Google Chrome",
    "Meet – abc-defg-hij - Google Chrome",
    "Meet – Reunião semanal - Google Chrome",
    "Meet - Planejamento 2026 - Microsoft Edge",
    "Meet: Reunião semanal - Google Chrome",
    "Meet: abc-defg-hij",
    "meet.google.com/abc-defg-hij - Google Chrome",
    "abc-defg-hij - Google Meet - Google Chrome",
]


@pytest.mark.parametrize("titulo", FORA_DE_CHAMADA)
def test_aba_do_meet_fora_de_chamada_nao_e_reuniao(titulo):
    assert classificar_titulo(titulo) == "", f"{titulo!r} não é uma reunião ativa"
    assert titulo_eh_meet(titulo) is False


@pytest.mark.parametrize("titulo", EM_CHAMADA)
def test_reuniao_de_verdade_continua_sendo_forte(titulo):
    assert classificar_titulo(titulo) == "forte", f"{titulo!r} é reunião ativa"


def test_sala_com_nome_de_navegador_no_meio_ainda_conta():
    """A exclusão é do navegador como sufixo, não da palavra em qualquer lugar."""
    assert classificar_titulo("Meet – Squad Firefox - Google Chrome") == "forte"
