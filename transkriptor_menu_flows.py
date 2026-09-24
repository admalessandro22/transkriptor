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


def _escolher_audio_dialog(items: list[dict]) -> dict | None:
    """Seletor premium para áudio retido — Listbox com busca e detalhes."""
    import tkinter as tk
    from tkinter import ttk

    resultado: dict = {"item": None}
    root = tk.Tk()
    root.withdraw()
    # ttk theme
    try:
        style = ttk.Style(root)
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
    except Exception:
        pass

    dlg = tk.Toplevel(root)
    dlg.title("Transkriptor — Retranscrever áudio")
    dlg.geometry("560x420")
    dlg.minsize(520, 360)
    dlg.attributes("-topmost", True)
    dlg.transient(root)
    dlg.grab_set()
    try:
        dlg.iconbitmap(default=os.path.join(os.path.dirname(__file__), "transkriptor.ico"))
    except Exception:
        pass

    # Centralizar
    dlg.update_idletasks()
    x = (dlg.winfo_screenwidth() - 560) // 2
    y = (dlg.winfo_screenheight() - 420) // 2
    dlg.geometry(f"560x420+{max(0,x)}+{max(0,y)}")

    header = ttk.Frame(dlg, padding=(16, 14, 16, 8))
    header.pack(fill="x")
    ttk.Label(header, text="Áudios retidos", font=("Segoe UI", 11, "bold")).pack(anchor="w")
    ttk.Label(header, text=f"{len(items)} arquivo(s) em transcricoes/audio — selecione um para retranscrever.", font=("Segoe UI", 8), foreground="#6b7280").pack(anchor="w", pady=(2, 0))

    search_var = tk.StringVar()
    search_frame = ttk.Frame(dlg, padding=(16, 0, 16, 8))
    search_frame.pack(fill="x")
    ttk.Label(search_frame, text="Filtrar:", font=("Segoe UI", 8)).pack(side="left")
    entry = ttk.Entry(search_frame, textvariable=search_var, font=("Segoe UI", 9))
    entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
    entry.focus_set()

    list_frame = ttk.Frame(dlg, padding=(16, 0, 16, 0))
    list_frame.pack(fill="both", expand=True)
    lb = tk.Listbox(list_frame, font=("Segoe UI", 9), activestyle="dotbox", selectmode="browse", exportselection=False)
    vsb = ttk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=vsb.set)
    lb.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    # Detalhe
    detail_var = tk.StringVar(value="Selecione um áudio para ver detalhes.")
    detail_lbl = ttk.Label(dlg, textvariable=detail_var, font=("Segoe UI", 8), foreground="#6b7280", padding=(16, 6, 16, 0), wraplength=520, justify="left")
    detail_lbl.pack(fill="x")

    filtrados = list(items)

    def _formatar_item(it: dict) -> str:
        dur = f"{it.get('duracao_seg', 0):.0f}s" if it.get("duracao_seg") else "?"
        return f"{it['mtime']:%d/%m/%Y %H:%M}  ·  {dur}  ·  {it['nome']}"

    def _refresh(*_a):
        q = (search_var.get() or "").strip().lower()
        lb.delete(0, "end")
        filtrados.clear()
        for it in items:
            if q and q not in it["nome"].lower() and q not in it["rotulo"].lower():
                continue
            filtrados.append(it)
            lb.insert("end", _formatar_item(it))
        if filtrados:
            lb.selection_set(0)
            lb.activate(0)
            detail_var.set(filtrados[0]["caminho"])
        else:
            detail_var.set("Nenhum resultado para o filtro.")

    def _on_select(_e=None):
        sel = lb.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(filtrados):
            it = filtrados[idx]
            dur = f"{it.get('duracao_seg', 0):.0f}s" if it.get("duracao_seg") else "?"
            detail_var.set(f"{it['caminho']}  ·  {dur}  ·  {it['mtime']:%d/%m/%Y %H:%M}")

    lb.bind("<<ListboxSelect>>", _on_select)
    lb.bind("<Double-Button-1>", lambda _e: _confirm())
    search_var.trace_add("write", _refresh)
    _refresh()

    btn_frame = ttk.Frame(dlg, padding=(16, 10, 16, 14))
    btn_frame.pack(fill="x")

    def _cancel():
        dlg.grab_release()
        dlg.destroy()
        root.destroy()

    def _confirm():
        sel = lb.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(filtrados):
            resultado["item"] = filtrados[idx]
        dlg.grab_release()
        dlg.destroy()
        root.destroy()

    ttk.Button(btn_frame, text="Cancelar", command=_cancel).pack(side="right")
    ok_btn = ttk.Button(btn_frame, text="Retranscrever", command=_confirm, style="Accent.TButton")
    ok_btn.pack(side="right", padx=(0, 8))
    try:
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
    except Exception:
        pass

    dlg.bind("<Escape>", lambda _e: _cancel())
    dlg.bind("<Return>", lambda _e: _confirm())
    dlg.protocol("WM_DELETE_WINDOW", _cancel)
    root.wait_window(dlg)
    return resultado["item"]


def iniciar_retranscricao_ui(app) -> None:
    """FR-2.5: lista áudios retidos e retranscreve o escolhido em thread."""

    def _ui():
        try:
            from retranscritor import listar_audios, retranscrever

            items = listar_audios(PASTA_AUDIO)
            if not items:
                notificar("Transkriptor", "Nenhum áudio retido em transcricoes/audio.")
                return
            escolhido = None
            try:
                escolhido = _escolher_audio_dialog(items)
            except Exception:
                logger.exception("Falha no diálogo premium, caindo para simpledialog")
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
                try:
                    idx = int(escolha.strip()) - 1
                except ValueError:
                    notificar("Transkriptor", "Número inválido.")
                    return
                if idx < 0 or idx >= len(items):
                    notificar("Transkriptor", "Número inválido.")
                    return
                escolhido = items[idx]
            if not escolhido:
                return
            caminho = escolhido["caminho"]
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


def abrir_central(app, pagina: str = "") -> None:
    """UX-14.C3: abre uma página da Central (inicia o servidor se preciso)."""
    threading.Thread(target=iniciar_assistente_ui, args=(app, pagina), daemon=True).start()


def _registrar_provedores(app) -> None:
    import app_estado_ui
    import central_api

    central_api.registrar_provedor_centroides(
        lambda: getattr(getattr(app, "transcritor", None), "_centroides_por_rotulo_ultima", None)
    )
    app_estado_ui.registrar_provedor(lambda: app_estado_ui.snapshot(app))


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
