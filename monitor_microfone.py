# -*- coding: utf-8 -*-
"""Quem está usando o microfone agora, segundo o próprio Windows (FR-9.3).

O Windows registra em `CapabilityAccessManager\\ConsentStore\\microphone` qual
app pegou o microfone e quando soltou. É a mesma fonte do ícone de microfone da
barra de tarefas. Enquanto o app está **usando** o microfone,
`LastUsedTimeStop == 0`.

Por que isso importa para o Transkriptor: o título da janela só revela a aba em
primeiro plano. Se você entra na reunião e troca de aba, o título some e o
detector antigo concluía "reunião encerrada" em 15 segundos, no meio da
conversa. O microfone, não: o Chrome continua segurando o microfone durante toda
a chamada, independente de qual aba está visível ou de a janela estar
minimizada. Também cobre Zoom, Teams e Webex sem precisar de regex nova.

Só apps de conferência entram na lista — senão qualquer ditado por voz
(WisprFlow, digitação por voz do Windows) viraria "reunião".
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

CHAVE_MICROFONE = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager"
    r"\ConsentStore\microphone"
)

# Executáveis que, ao segurar o microfone, indicam chamada em andamento.
APPS_CONFERENCIA = (
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "zoom.exe",
    "teams.exe",
    "ms-teams.exe",
    "webex.exe",
    "webexmta.exe",
    "slack.exe",
    "discord.exe",
    "gotomeeting.exe",
)


def nome_executavel(chave_registro: str) -> str:
    """Extrai `chrome.exe` de `C:#Program Files#Google#Chrome#...#chrome.exe`.

    O Windows troca `\\` por `#` no nome da subchave.
    """
    bruto = str(chave_registro or "").replace("#", "\\")
    return os.path.basename(bruto).strip().lower()


def eh_app_conferencia(chave_registro: str, apps=APPS_CONFERENCIA) -> bool:
    """True se a subchave do registro corresponde a um app de conferência."""
    return nome_executavel(chave_registro) in {a.lower() for a in apps}


def apps_em_chamada(entradas, apps=APPS_CONFERENCIA) -> list[str]:
    """Filtra `[(chave, last_used_stop)]` deixando só conferência em uso agora.

    Função pura: é ela que os testes exercitam, sem tocar no registro real.
    `last_used_stop == 0` é a marca do Windows para "ainda em uso".
    """
    ativos = []
    for chave, stop in entradas:
        if stop != 0:
            continue
        if not eh_app_conferencia(chave, apps):
            continue
        nome = nome_executavel(chave)
        if nome not in ativos:
            ativos.append(nome)
    return ativos


def _ler_entradas_registro() -> list[tuple[str, int]]:
    """Lê `(subchave, LastUsedTimeStop)` do ConsentStore do usuário."""
    try:
        import winreg
    except ImportError:  # não-Windows: fonte simplesmente não contribui
        return []

    entradas: list[tuple[str, int]] = []
    for sufixo in ("", r"\NonPackaged"):
        try:
            chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_MICROFONE + sufixo)
        except OSError:
            continue
        try:
            indice = 0
            while True:
                try:
                    nome_sub = winreg.EnumKey(chave, indice)
                except OSError:
                    break
                indice += 1
                try:
                    with winreg.OpenKey(chave, nome_sub) as sub:
                        stop, _tipo = winreg.QueryValueEx(sub, "LastUsedTimeStop")
                    entradas.append((nome_sub, int(stop)))
                except (OSError, ValueError, TypeError):
                    continue
        finally:
            chave.Close()
    return entradas


def microfone_em_uso_por_conferencia(apps=APPS_CONFERENCIA) -> list[str]:
    """Lista de apps de conferência com o microfone aberto neste instante."""
    try:
        return apps_em_chamada(_ler_entradas_registro(), apps)
    except Exception:  # noqa: BLE001 — fonte auxiliar nunca derruba o monitor
        logger.debug("Falha ao consultar microfone em uso", exc_info=True)
        return []
