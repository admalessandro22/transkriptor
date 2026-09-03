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


def _renomear_dialog(rotulos: list[str]) -> tuple[str | None, str | None]:
    """Diálogo premium: Combobox + Entry validados, com dica."""
    import tkinter as tk
    from tkinter import ttk

    resultado: dict = {"rotulo": None, "nome": None}
    root = tk.Tk()
    root.withdraw()
    try:
        style = ttk.Style(root)
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
    except Exception:
        pass

    dlg = tk.Toplevel(root)
    dlg.title("Transkriptor — Renomear falante")
    dlg.geometry("420x220")
    dlg.minsize(400, 210)
    dlg.attributes("-topmost", True)
    dlg.transient(root)
    dlg.grab_set()
    try:
        dlg.iconbitmap(default=os.path.join(os.path.dirname(__file__), "transkriptor.ico"))
    except Exception:
        pass
    dlg.update_idletasks()
    x = (dlg.winfo_screenwidth() - 420) // 2
    y = (dlg.winfo_screenheight() - 220) // 2
    dlg.geometry(f"420x220+{max(0,x)}+{max(0,y)}")

    frm = ttk.Frame(dlg, padding=(16, 14, 16, 10))
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Renomear falante", font=("Segoe UI", 11, "bold")).pack(anchor="w")
    ttk.Label(frm, text="O nome será usado para reconhecer esta voz nas próximas reuniões.", font=("Segoe UI", 8), foreground="#6b7280").pack(anchor="w", pady=(2, 10))

    ttk.Label(frm, text="Falante detectado", font=("Segoe UI", 8, "bold")).pack(anchor="w")
    rotulo_var = tk.StringVar(value=rotulos[0] if rotulos else "")
    cb = ttk.Combobox(frm, textvariable=rotulo_var, values=rotulos, state="readonly", font=("Segoe UI", 9))
    cb.pack(fill="x", pady=(4, 10))

    ttk.Label(frm, text="Novo nome", font=("Segoe UI", 8, "bold")).pack(anchor="w")
    nome_var = tk.StringVar()
    entry = ttk.Entry(frm, textvariable=nome_var, font=("Segoe UI", 9))
    entry.pack(fill="x", pady=(4, 0))
    entry.focus_set()

    hint = ttk.Label(frm, text="Ex.: Maria Silva, João — evite só iniciais.", font=("Segoe UI", 8), foreground="#6b7280")
    hint.pack(anchor="w", pady=(4, 0))

    erro_var = tk.StringVar(value="")
    erro_lbl = ttk.Label(frm, textvariable=erro_var, font=("Segoe UI", 8), foreground="#ef4444")
    erro_lbl.pack(anchor="w", pady=(4, 0))

    btns = ttk.Frame(dlg, padding=(16, 0, 16, 14))
    btns.pack(fill="x")

    def _cancel():
        dlg.grab_release()
        dlg.destroy()
        root.destroy()

    def _ok():
        nome = (nome_var.get() or "").strip()
        if not nome:
            erro_var.set("Digite um nome válido.")
            entry.focus_set()
            return
        if len(nome) < 2:
            erro_var.set("Nome muito curto.")
            return
        resultado["rotulo"] = rotulo_var.get().strip()
        resultado["nome"] = nome
        dlg.grab_release()
        dlg.destroy()
        root.destroy()

    ttk.Button(btns, text="Cancelar", command=_cancel).pack(side="right")
    ttk.Button(btns, text="Salvar", command=_ok, style="Accent.TButton").pack(side="right", padx=(0, 8))
    try:
        ttk.Style().configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
    except Exception:
        pass

    dlg.bind("<Escape>", lambda _e: _cancel())
    dlg.bind("<Return>", lambda _e: _ok())
    cb.bind("<Return>", lambda _e: entry.focus_set())
    dlg.protocol("WM_DELETE_WINDOW", _cancel)
    root.wait_window(dlg)
    if resultado["rotulo"] and resultado["nome"]:
        return resultado["rotulo"], resultado["nome"]
    return None, None


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
        try:
            rotulo, nome = _renomear_dialog(rotulos)
        except Exception:
            logger.exception("Falha no diálogo premium renomear, fallback simpledialog")
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
        if not rotulo or not nome:
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
