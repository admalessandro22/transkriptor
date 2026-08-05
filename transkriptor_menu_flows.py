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
    TIMEOUT_AVISO_GRAVACAO_SEG,
)
from notificador import notificar

logger = logging.getLogger(__name__)

IDYES = 6


def perguntar_continuar_gravacao() -> int:
    """FR-9.D4: Sim/Não com timeout — sem resposta, a gravação continua.

    O toast antes do diálogo não é enfeite: o Windows bloqueia o foco de janelas
    criadas por processos em segundo plano, então a MessageBox pode nascer atrás
    do navegador. O toast garante que o usuário perceba que há algo a responder.
    """
    try:
        import ctypes
        from ctypes import wintypes

        notificar(
            "Transkriptor",
            "Reunião detectada — gravando. Responda se quer manter a gravação.",
        )
        fn = ctypes.windll.user32.MessageBoxTimeoutW
        fn.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.UINT,
            wintypes.WORD,
            wintypes.DWORD,
        ]
        fn.restype = ctypes.c_int
        # YESNO | ICONQUESTION | SETFOREGROUND | TOPMOST
        return int(
            fn(
                None,
                "O Transkriptor detectou uma reunião e já começou a gravar.\n\n"
                "Quer gravar e transcrever esta reunião?\n\n"
                "Sim  — continua gravando e transcreve ao final.\n"
                "Não  — para agora e apaga o que já foi gravado.\n\n"
                f"(Sem resposta em {TIMEOUT_AVISO_GRAVACAO_SEG}s, continua gravando.)",
                "Transkriptor — reunião detectada",
                0x4 | 0x20 | 0x10000 | 0x40000,
                0,
                TIMEOUT_AVISO_GRAVACAO_SEG * 1000,
            )
        )
    except Exception:
        logger.exception("Diálogo de gravação indisponível")
        return IDYES


def rodar_diagnostico_ui(app) -> None:
    """FR-9.C1: responde 'por que não está gravando?' em uma tela."""
    import diagnostico

    app._status("Rodando diagnóstico...")
    try:
        itens = diagnostico.coletar(
            detector=getattr(app, "detector", None),
            modelo_whisper=getattr(app, "modelo_whisper", MODELO_WHISPER),
            capturar_mic=getattr(app, "capturar_mic", True),
            gravando=app._gravando(),
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


def iniciar_retranscricao_ui(app) -> None:
    """FR-2.5: lista áudios retidos e retranscreve o escolhido em thread."""

    def _ui():
        try:
            from retranscritor import listar_audios, retranscrever

            items = listar_audios(PASTA_AUDIO)
            if not items:
                notificar("Transkriptor", "Nenhum áudio retido em transcricoes/audio.")
                return
            import tkinter as tk
            from tkinter import simpledialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            opcoes = "\n".join(f"{i+1}. {it['rotulo']}" for i, it in enumerate(items[:30]))
            escolha = simpledialog.askstring(
                "Retranscrever áudio",
                f"Escolha o número do áudio:\n\n{opcoes}",
                parent=root,
            )
            root.destroy()
            if not escolha:
                return
            idx = int(escolha.strip()) - 1
            if idx < 0 or idx >= len(items):
                notificar("Transkriptor", "Número inválido.")
                return
            caminho = items[idx]["caminho"]
            app._status("Retranscrevendo áudio…")
            notificar("Transkriptor", "Retranscrição iniciada…")

            def _job():
                try:
                    saida = retranscrever(
                        caminho,
                        pasta_saida=PASTA_TRANSCRICOES,
                        diarizar=app.diarizacao_ativa,
                        criptografar=app.criptografar_transcricoes,
                        on_status=app._status,
                        identificar_voz=app.identificar_minha_voz,
                        usar_vozes_conhecidas=True,
                    )
                    notificar(
                        "Transkriptor",
                        f"Retranscrição salva: {os.path.basename(saida) if saida else '?'}",
                    )
                except Exception as e:
                    logger.exception("Retranscrição falhou")
                    notificar("Transkriptor", f"Erro na retranscrição: {e}")

            threading.Thread(target=_job, daemon=True, name="Retranscrever").start()
        except Exception as e:
            logger.exception("Menu retranscrever")
            notificar("Transkriptor", f"Erro: {e}")

    threading.Thread(target=_ui, daemon=True).start()


def iniciar_renomear_falante_ui(app) -> None:
    from renomear_falante_flow import (
        persistir_renomeacao_falante,
        rotulos_falante_disponiveis,
    )
    from config import ARQUIVO_VOZES_CONHECIDAS

    t = app.transcritor
    centroides = getattr(t, "_centroides_por_rotulo_ultima", None) if t else None
    if not centroides:
        notificar(
            "Transkriptor",
            "Transcreva e diarize uma reunião antes de renomear um falante.",
        )
        return

    rotulos = rotulos_falante_disponiveis(centroides)
    if not rotulos:
        notificar("Transkriptor", "Nenhum FALANTE_XX disponível na última diarização.")
        return

    try:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        rotulo = simpledialog.askstring(
            "Renomear falante",
            f"Rótulo a renomear:\n{', '.join(rotulos)}",
            parent=root,
        )
        if not rotulo:
            root.destroy()
            return
        nome = simpledialog.askstring(
            "Renomear falante",
            f"Novo nome para {rotulo.strip().upper()}:",
            parent=root,
        )
        root.destroy()
        if not nome:
            return
        salvo = persistir_renomeacao_falante(
            rotulo, nome, centroides, ARQUIVO_VOZES_CONHECIDAS
        )
        notificar("Transkriptor", f"Voz salva como «{salvo}» para próximas reuniões.")
        app._status(f"Voz conhecida salva: {salvo}")
    except ValueError as e:
        notificar("Transkriptor", str(e))
        app._status(f"Erro ao renomear: {e}")
    except Exception as e:
        logger.exception("Erro ao renomear falante")
        notificar("Transkriptor", f"Erro ao renomear: {e}")
        app._status(f"Erro ao renomear: {e}")


def iniciar_assistente_ui(app) -> None:
    """Inicia o servidor Flask do assistente em segundo plano e abre o navegador."""
    if getattr(app, "_assistente_rodando", False):
        url = getattr(app, "_assistente_url", None)
        token = getattr(app, "_assistente_token", None)
        if url and token:
            _abrir_navegador(url, token)
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
        _abrir_navegador(url, token)
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


def _abrir_navegador(url: str, token: str) -> None:
    import webbrowser

    webbrowser.open(f"{url}?token={token}")
