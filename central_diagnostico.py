# -*- coding: utf-8 -*-
"""Diagnóstico e retranscrição pela Central (FR-14.D3).

Reutiliza `diagnostico.coletar/salvar_relatorio/exportar_diagnostico` e
`retranscritor.listar_audios/retranscrever`; a bandeja registrada em
`central_config` fornece detector, transcritor e preferências. Sem bandeja,
cada rota responde 503 explicando; nomes de áudio são validados contra a
própria lista (nunca um caminho vindo do cliente).
"""
from __future__ import annotations

import logging
import threading

from flask import Blueprint, Response, jsonify, request

from config import IDIOMA, MEET_CONVITE_SEG, MODELO_WHISPER, PASTA_AUDIO, PASTA_TRANSCRICOES

bp = Blueprint("central_diagnostico", __name__)
logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_ULTIMOS_ITENS: list[dict] = []
_RETRANSCRICAO = {"em_curso": False, "nome": None}


def _app():
    import central_config

    return central_config.app_registrado()


def _sem_bandeja():
    return jsonify({"erro": "indisponível: o aplicativo da bandeja não está ligado a esta Central"}), 503


@bp.route("/api/diagnostico", methods=["POST"])
def api_diagnostico():
    """Roda as checagens reais (áudio, detecção, modelo) e salva o relatório .txt como antes."""
    import diagnostico

    app = _app()
    if app is None:
        return _sem_bandeja()
    if not _LOCK.acquire(blocking=False):
        return jsonify({"erro": "Diagnóstico já em execução. Aguarde o resultado."}), 409
    try:
        itens = diagnostico.coletar(
            detector=getattr(app, "detector", None),
            modelo_whisper=getattr(app, "modelo_whisper", MODELO_WHISPER),
            capturar_mic=getattr(app, "capturar_mic", True),
            gravando=bool(getattr(app, "_gravando", lambda: False)()),
            transcritor=getattr(app, "transcritor", None),
            idiomas_meet=getattr(getattr(app, "meet_bridge", None), "idiomas_meet", None),
            idioma_transcricao=IDIOMA,
            descartes_meet=getattr(getattr(app, "meet_bridge", None), "contador_descarte_rajada", 0),
            saude_meet=getattr(getattr(app, "meet_bridge", None), "saude_meet", None),
        )
        caminho = diagnostico.salvar_relatorio(diagnostico.formatar_texto(itens))
    except Exception as exc:  # noqa: BLE001 — a falha vira item visível, não 500 mudo
        logger.exception("Diagnóstico pela Central falhou")
        return jsonify({"erro": f"O diagnóstico falhou: {exc.__class__.__name__}. Veja o log."}), 500
    finally:
        _LOCK.release()
    _ULTIMOS_ITENS[:] = list(itens)
    erros, avisos = diagnostico.resumir(itens)
    import os

    return jsonify({"itens": itens, "erros": erros, "avisos": avisos, "relatorio": os.path.basename(caminho)})


@bp.route("/api/diagnostico/exportar")
def api_diagnostico_exportar():
    """Relatório sem PII do último diagnóstico (T-13.E4)."""
    import diagnostico

    if not _ULTIMOS_ITENS:
        return jsonify({"erro": "Rode o diagnóstico antes de exportar."}), 404
    texto = diagnostico.exportar_diagnostico(list(_ULTIMOS_ITENS))
    resposta = Response(texto, mimetype="text/plain")
    resposta.charset = "utf-8"
    resposta.headers["Content-Disposition"] = 'attachment; filename="diagnostico-transkriptor.txt"'
    return resposta


def _audios() -> list[dict]:
    from retranscritor import listar_audios

    saida = []
    for item in listar_audios(PASTA_AUDIO):
        saida.append({
            "nome": item["nome"],
            "mtime": item["mtime"].isoformat(timespec="minutes") if hasattr(item["mtime"], "isoformat") else str(item["mtime"]),
            "duracao_seg": round(float(item.get("duracao_seg") or 0.0), 1),
        })
    return saida


@bp.route("/api/audios-retidos")
def api_audios_retidos():
    try:
        return jsonify(_audios())
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao listar áudios retidos")
        return jsonify({"erro": "Não foi possível listar os áudios retidos."}), 500


@bp.route("/api/acoes/retranscrever", methods=["POST"])
def api_retranscrever():
    from retranscritor import listar_audios, retranscrever

    app = _app()
    if app is None:
        return _sem_bandeja()
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", ""))
    alvo = next((i for i in listar_audios(PASTA_AUDIO) if i["nome"] == nome), None)
    if alvo is None:
        return jsonify({"erro": "Áudio não encontrado na lista de retidos."}), 400
    if _RETRANSCRICAO["em_curso"]:
        return jsonify({"erro": "Já existe uma retranscrição em andamento. Aguarde terminar."}), 409
    _RETRANSCRICAO.update(em_curso=True, nome=nome)
    status = getattr(app, "_status", lambda _m: None)

    def _job():
        try:
            status("Retranscrevendo áudio…")
            retranscrever(
                alvo["caminho"], pasta_saida=PASTA_TRANSCRICOES,
                diarizar=getattr(app, "diarizacao_ativa", True),
                criptografar=getattr(app, "criptografar_transcricoes", True),
                on_status=status,
                identificar_voz=getattr(app, "identificar_minha_voz", False),
                usar_vozes_conhecidas=True,
            )
            status("Retranscrição concluída.")
        except Exception:  # noqa: BLE001
            logger.exception("Retranscrição pela Central falhou")
            status("Retranscrição falhou. Veja o log.")
        finally:
            _RETRANSCRICAO.update(em_curso=False, nome=None)

    threading.Thread(target=_job, daemon=True, name="Retranscrever-Central").start()
    return jsonify({"aceito": True, "nome": nome}), 202


@bp.route("/api/acoes/pareamento", methods=["POST"])
def api_pareamento():
    """Emite um convite de uso único para a extensão do Meet (pairing.html).

    O convite nasce no `Pareador` da ponte e vale MEET_CONVITE_SEG segundos;
    antes desta rota ele era gerado no arranque e nunca mostrado. O código não
    é registrado em log (o sanitizador já o redige, mas nem chega lá).
    """
    app = _app()
    if app is None:
        return _sem_bandeja()
    pareador = getattr(getattr(app, "meet_bridge", None), "pareador", None)
    if pareador is None:
        return jsonify({"erro": "Ponte do Meet desligada: ative 'Identificar nomes do Meet' em Configurações e tente de novo."}), 503
    codigo = pareador.gerar_convite()
    app.convite_pareamento_meet = codigo
    return jsonify({
        "codigo": codigo,
        "validade_seg": int(MEET_CONVITE_SEG),
        "ponte_ativa": bool(getattr(app, "usar_nomes_meet", False)),
    })


@bp.route("/api/acoes/retranscrever")
def api_retranscrever_estado():
    return jsonify({"em_curso": _RETRANSCRICAO["em_curso"], "nome": _RETRANSCRICAO["nome"]})
