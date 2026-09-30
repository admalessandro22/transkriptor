# -*- coding: utf-8 -*-
"""Fluxos de menu da bandeja: retranscrever, renomear, assistente."""

from __future__ import annotations

import logging
import os
import threading

from config import (
    MODELO_WHISPER,
    PASTA_AUDIO,
    PASTA_TRANSCRICOES,
)
from notificador import notificar

logger = logging.getLogger(__name__)

def iniciar_retranscricao_ui(app) -> None:
    """UX-14.D3: a lista de áudios retidos e a retranscrição vivem na Central."""
    abrir_central(app, "diagnostico")


def rodar_diagnostico_ui(app) -> None:
    """FR-9.C1: responde 'por que não está gravando?' em uma tela (agora a Central).

    Mantém o relatório .txt salvo e aberto para quem prefere o arquivo.
    """
    import diagnostico

    abrir_central(app, "diagnostico")

    app._status("Rodando diagnóstico...")
    try:
        itens = diagnostico.coletar(
            detector=getattr(app, "detector", None),
            modelo_whisper=getattr(app, "modelo_whisper", MODELO_WHISPER),
            capturar_mic=getattr(app, "capturar_mic", True),
            gravando=app._gravando(),
            transcritor=getattr(app, "transcritor", None),
        )
        texto = diagnostico.formatar_texto(itens)
        caminho = diagnostico.salvar_relatorio(texto)
    except Exception as e:
        logger.exception("Diagnóstico falhou")
        app._status(f"Erro no diagnóstico: {e}")
        notificar("Transkriptor", f"Diagnóstico falhou: {e}")
        return
    erros, avisos = diagnostico.resumir(itens)
    app._status(f"Diagnóstico: {erros} erro(s), {avisos} aviso(s).")
    notificar(
        "Transkriptor",
        f"Diagnóstico: {erros} erro(s), {avisos} aviso(s). Relatório aberto.",
    )
    try:
        os.startfile(caminho)
    except Exception:
        logger.warning("Não foi possível abrir o relatório de diagnóstico.")


def abrir_central(app, pagina: str = "") -> None:
    """UX-14.C3: abre uma página da Central (inicia o servidor se preciso)."""
    threading.Thread(target=iniciar_assistente_ui, args=(app, pagina), daemon=True).start()


def abrir_primeiro_uso_se_preciso(app, abrir=abrir_central) -> bool:
    """T-15.E3: na primeira vez, a Central abre no assistente de primeiros passos."""
    import config_user

    if config_user.carregar().get("assistente_inicial_concluido"):
        return False
    try:
        abrir(app, "primeiro-uso")
    except Exception:  # noqa: BLE001 — conveniência: nunca pode derrubar a bandeja
        logger.warning("Primeiros passos não abriram; siga pelo menu da bandeja.", exc_info=True)
        return False
    return True


def _registrar_provedores(app) -> None:
    import app_estado_ui
    import central_config

    app_estado_ui.registrar_provedor(lambda: app_estado_ui.snapshot(app))
    central_config.registrar_app(app)


def iniciar_assistente_ui(app, pagina: str = "") -> None:
    """Inicia o servidor Flask do assistente em segundo plano e abre o navegador."""
    if getattr(app, "_assistente_rodando", False):
        url = getattr(app, "_assistente_url", None)
        token = getattr(app, "_assistente_token", None)
        if url and token:
            _abrir_navegador(url, token, pagina)
            app._status(f"Assistente já aberto — reabrindo navegador em {url}")
        else:
            app._status("Assistente já está aberto.")
        return
    app._assistente_rodando = True
    app._status("Abrindo assistente de reunião...")
    try:
        import importlib

        assistente = importlib.import_module("assistente")
        porta = assistente.porta_livre()
        url = f"http://127.0.0.1:{porta}"
        import logging as _lg

        _lg.getLogger("werkzeug").setLevel(_lg.WARNING)
        thread = assistente.iniciar_servidor_em_thread(assistente.app, "127.0.0.1", porta)
        if not assistente.aguardar_servidor(url, timeout=10):
            app._status("Erro: assistente não respondeu. Verifique o log.")
            app._assistente_rodando = False
            return
        token = assistente.obter_token_sessao()
        app._assistente_url = url
        app._assistente_token = token
        _registrar_provedores(app)
        _abrir_navegador(url, token, pagina)
        app._status(f"Assistente rodando em {url}")
        thread.join()
    except RuntimeError as e:
        app._status(f"Erro ao abrir assistente: {e}")
        logger.error("Erro porta_livre: %s", e)
    except Exception as e:
        app._status(f"Erro no assistente: {e}")
        logger.exception("Erro no assistente")
    finally:
        app._assistente_rodando = False
        app._assistente_url = None
        app._assistente_token = None


from central_janela import _abrir_navegador  # noqa: E402,F401 — usado por iniciar_assistente_ui
