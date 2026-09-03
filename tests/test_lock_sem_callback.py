# -*- coding: utf-8 -*-
"""Nenhum bloco `with self._lock:` pode chamar callback (regressão 2026-08-07).

O app congelou por três dias porque `Transcritor.start()` rodava sob
`self._lock` e chamava `on_status` — que é `_status`, que pedia o mesmo lock.
Testar só o caso conhecido não basta: qualquer chamada nova que volte para
`_status` recria o travamento. Este teste lê o código e reprova a *forma*.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

MODULOS = ("transkriptor.pyw", "app_processamento.py", "app_bandeja_menu.py")

# Chamadas que voltam (direta ou indiretamente) para `_status`/`_atualizar_tooltip`.
PROIBIDAS = {
    "_status",
    "on_status",
    "_erro_critico",
    "_atualizar_tooltip",
    "update_menu",
    "notificar",
    "_parar_transcricao",
    "_iniciar_transcricao",
    "_pedir_e_iniciar",
}

# Objetos cujo `start()`/`stop()` dispara callback de status.
OBJETOS_COM_CALLBACK = {"transcritor", "watchdog"}


def _carregar(nome: str) -> ast.Module:
    return ast.parse((RAIZ / nome).read_text(encoding="utf-8"), filename=nome)


def _e_lock_do_app(item: ast.withitem) -> bool:
    alvo = item.context_expr
    return (
        isinstance(alvo, ast.Attribute)
        and alvo.attr == "_lock"
        and isinstance(alvo.value, ast.Name)
        and alvo.value.id == "self"
    )


def _blocos_com_lock(arvore: ast.Module):
    for no in ast.walk(arvore):
        if isinstance(no, ast.With) and any(_e_lock_do_app(i) for i in no.items):
            yield no


def _chamada_proibida(chamada: ast.Call) -> str | None:
    func = chamada.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr in PROIBIDAS:
        return func.attr
    if func.attr in ("start", "stop"):
        dono = func.value
        if isinstance(dono, ast.Attribute) and dono.attr in OBJETOS_COM_CALLBACK:
            return f"{dono.attr}.{func.attr}"
    return None


@pytest.mark.parametrize("nome", MODULOS)
def test_lock_do_app_nao_envolve_callback(nome):
    infracoes = []
    for bloco in _blocos_com_lock(_carregar(nome)):
        for corpo in bloco.body:
            for no in ast.walk(corpo):
                if isinstance(no, ast.Call):
                    proibida = _chamada_proibida(no)
                    if proibida:
                        infracoes.append(f"{nome}:{no.lineno} chama {proibida}()")

    assert not infracoes, (
        "chamada com callback dentro de `with self._lock:` — "
        "é exatamente o padrão que travou o app:\n  " + "\n  ".join(infracoes)
    )


def test_lock_do_app_e_reentrante():
    """Cinto de segurança: um descuido futuro vira lentidão, não congelamento."""
    fonte = (RAIZ / "transkriptor.pyw").read_text(encoding="utf-8")

    assert "self._lock = threading.RLock()" in fonte


def test_status_nao_pede_o_lock_do_app():
    """`_status` roda nas threads de áudio; não pode disputar `self._lock`."""
    arvore = _carregar("transkriptor.pyw")
    metodos = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef) and no.name == "_status"
    ]

    assert metodos, "_status desapareceu de transkriptor.pyw"
    for metodo in metodos:
        assert not list(_blocos_com_lock(metodo)), "_status voltou a pedir self._lock"
