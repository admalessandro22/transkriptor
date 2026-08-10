# -*- coding: utf-8 -*-
"""FR-2.4 — a thread de captura precisa de COM viva do início ao fim.

Sintoma em produção (2026-08-10, app de bandeja):

    [INFO] Erro ao abrir audio: Error 0x800401f0

`0x800401f0` é `CO_E_NOTINITIALIZED`. O `soundcard` inicializa COM num objeto
`_COMLibrary` de vida curta cujo `__del__` chama `CoUninitialize()`. Num
processo com várias threads (bandeja, consentimento, captura, autoteste) esse
par init/uninit desbalanceia e a thread de captura fica sem COM — o loopback
nunca abre e a reunião é gravada em branco.

Reprodução que originou este teste: `CoUninitialize()` a mais numa thread faz
`sc.default_speaker()` falhar com 0x800401f0; um `CoInitializeEx` explícito,
mantido durante toda a thread, conserta.
"""
from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest

from com_audio import com_inicializada

RAIZ = Path(__file__).resolve().parent.parent


def test_com_inicializada_reporta_que_inicializou():
    with com_inicializada() as inicializou:
        assert inicializou is True


def test_com_inicializada_pode_aninhar():
    with com_inicializada():
        with com_inicializada():
            pass


def test_com_inicializada_nao_vaza_entre_threads():
    resultados = []

    def _alvo():
        with com_inicializada() as ok:
            resultados.append(ok)

    threads = [threading.Thread(target=_alvo) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert resultados == [True] * 4


# Derrubar o MTA é destrutivo para o processo inteiro: roda em subprocesso para
# não contaminar o resto da suíte (foi o que aconteceu na primeira versão).
_SCRIPT_REPRO = """
import ctypes, sys, threading
sys.path.insert(0, {raiz!r})

def usar_soundcard():
    import soundcard as sc
    alto_falante = sc.default_speaker()
    sc.get_microphone(id=str(alto_falante.id), include_loopback=True)

def derrubar_com():
    # `soundcard` inicializa COM num singleton de módulo (`_com = _COMLibrary()`),
    # só na thread que importar primeiro. As outras dependem do MTA do processo —
    # e é esse MTA que um CoUninitialize desbalanceado (o do `__del__`) derruba.
    usar_soundcard()
    for _ in range(4):
        ctypes.windll.ole32.CoUninitialize()

USAR_CORRECAO = {usar_correcao!r}
resultado = []

def alvo():
    derrubar_com()
    try:
        if USAR_CORRECAO:
            from com_audio import com_inicializada
            with com_inicializada():
                usar_soundcard()
        else:
            usar_soundcard()
        resultado.append("OK")
    except Exception as e:
        resultado.append(f"ERRO {{e}}")

t = threading.Thread(target=alvo)
t.start(); t.join(30)
print(resultado[0] if resultado else "SEM RESULTADO")
"""


def _rodar_repro(usar_correcao: bool) -> str:
    import subprocess
    import sys as _sys

    script = _SCRIPT_REPRO.format(raiz=str(RAIZ), usar_correcao=usar_correcao)
    saida = subprocess.run(
        [_sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=90,
        cwd=str(RAIZ),
    )
    return saida.stdout.strip().splitlines()[-1] if saida.stdout.strip() else saida.stderr


def test_reproduz_a_falha_de_com_desbalanceada():
    """Prova que o sintoma de produção é este, e não falha de dispositivo."""
    resultado = _rodar_repro(usar_correcao=False)

    assert "0x800401f0" in resultado.lower(), (
        f"esperava CO_E_NOTINITIALIZED, veio: {resultado}"
    )


def test_com_inicializada_conserta_a_thread_desbalanceada():
    """Mesma sequência, agora com o contexto que a correção instala."""
    resultado = _rodar_repro(usar_correcao=True)

    assert resultado == "OK", f"loopback ainda falhou com com_inicializada: {resultado}"


# --- garantia estrutural: as threads de áudio realmente usam o contexto ------


@pytest.mark.parametrize(
    "arquivo,metodo",
    [
        ("transcricao_core.py", "_capturar"),
        ("captura_leve.py", "_capturar_mic"),
    ],
)
def test_thread_de_audio_mantem_com_inicializada(arquivo, metodo):
    arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"), filename=arquivo)
    funcao = next(
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.FunctionDef) and n.name == metodo
    )

    usa = any(
        isinstance(no, ast.Call)
        and getattr(no.func, "id", getattr(no.func, "attr", "")) == "com_inicializada"
        for no in ast.walk(funcao)
    )

    assert usa, (
        f"{arquivo}::{metodo} roda numa thread própria e chama o soundcard; "
        "sem com_inicializada o loopback falha com 0x800401f0"
    )
