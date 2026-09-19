# -*- coding: utf-8 -*-
"""FR-13.B3 — inatividade do worker e parada só com lease validado."""
from __future__ import annotations

import re
from typing import Callable

import config as _config
from fila_lock import ProcessIdentityIndeterminate, lease_de_dados, process_matches

ETAPA_MODELO = "model_init"
ETAPA_TRANSCRICAO = "transcribe"
ETAPA_FINAL = "finalize"
PADRAO_STAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
PADRAO_ERRO = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def avaliar_inatividade(
    stage: str | None,
    ocioso_seg: float,
    aviso_seg: float,
    falha_seg: float,
    modelo_init_seg: float,
) -> str:
    """Retorna ok, aviso ou falha. model_init usa orçamento separado."""
    limite = modelo_init_seg if stage == ETAPA_MODELO else falha_seg
    if ocioso_seg >= limite:
        return "falha"
    if ocioso_seg >= aviso_seg:
        return "aviso"
    return "ok"


def pid_do_lease(lease: dict | None) -> int | None:
    if not isinstance(lease, dict):
        return None
    owner = lease.get("owner")
    if not isinstance(owner, dict):
        return None
    try:
        pid = int(owner.get("pid"))
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def encerrar_se_lease_valido(
    lease: dict | None,
    pid_esperado: int | None,
    encerrar: Callable[[], None],
) -> bool:
    """Sinaliza somente o PID que ainda detém o lease validado do job."""
    if pid_esperado is None or int(pid_esperado) <= 0:
        return False
    if pid_do_lease(lease) != int(pid_esperado):
        return False
    try:
        identidade = lease_de_dados(lease).owner
        if not process_matches(identidade):
            return False
    except (ValueError, ProcessIdentityIndeterminate):
        return False
    encerrar()
    return True


def _codigo_erro(erro_seguro: str) -> str:
    codigo = str(erro_seguro)
    return codigo if PADRAO_ERRO.fullmatch(codigo) else "erro_processamento"


def _gravar(fila, dados):
    from fila_processamento import _agora_iso

    dados["revision"] += 1
    dados["atualizado_em"] = _agora_iso()
    fila._salvar(dados)
    return fila._para_job(dados)


def persistir_progresso(fila, job_id: str, stage: str, units: int):
    from fila_processamento import _agora_iso

    if not PADRAO_STAGE.fullmatch(str(stage)):
        raise ValueError("etapa de job inválida")
    if isinstance(units, bool) or not isinstance(units, int) or units < 0:
        raise ValueError("progresso de job inválido")
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        if dados["estado"] != "processing":
            raise RuntimeError("job não está em processamento")
        lease = fila._exigir_lease_do_processo_atual(dados)
        dados["stage"] = stage
        dados["progress_units"] = units
        dados["lease"] = {
            "owner": {
                "pid": lease.owner.pid,
                "created_at_100ns": lease.owner.created_at_100ns,
            },
            "nonce": lease.nonce,
            "acquired_at_utc": lease.acquired_at_utc,
            "heartbeat_at_utc": _agora_iso(),
        }
        return _gravar(fila, dados)


def persistir_aviso(fila, job_id: str, aviso: str):
    codigo = _codigo_erro(aviso)
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        avisos = list(dados.get("warnings") or [])
        if codigo not in avisos:
            avisos.append(codigo)
        dados["warnings"] = avisos
        return _gravar(fila, dados)


def persistir_pedido_cancelamento(fila, job_id: str):
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        if dados["estado"] in {"ready", "failed", "cancelled"}:
            raise RuntimeError("job não pode ser cancelado neste estado")
        dados["cancel_solicitado"] = True
        return _gravar(fila, dados)


def persistir_falha_de_spawn(fila, job_id: str, erro_seguro: str):
    codigo = _codigo_erro(erro_seguro)
    limite = int(_config.WORKER_MAX_TENTATIVAS)
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        if dados["estado"] != "pending":
            return fila._para_job(dados)
        dados["attempt"] = int(dados.get("attempt") or 0) + 1
        dados["erro_seguro"] = codigo
        if dados["attempt"] >= limite:
            dados["estado"] = "failed"
        return _gravar(fila, dados)


def persistir_reabrir_retry(fila, job_id: str, max_tentativas: int | None):
    limite = int(max_tentativas or _config.WORKER_MAX_TENTATIVAS)
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        if dados["estado"] != "failed":
            return fila._para_job(dados)
        if int(dados.get("attempt") or 0) >= limite:
            return fila._para_job(dados)
        dados["estado"] = "pending"
        dados["lease"] = None
        return _gravar(fila, dados)


def persistir_finalizar_supervisor(
    fila,
    job_id: str,
    pid_esperado: int,
    erro_seguro: str,
    *,
    estado: str = "failed",
    max_tentativas: int | None = None,
):
    if estado not in {"failed", "cancelled"}:
        raise ValueError("estado terminal de supervisor inválido")
    if isinstance(pid_esperado, bool) or not isinstance(pid_esperado, int):
        raise ValueError("pid de worker inválido")
    codigo = _codigo_erro(erro_seguro)
    limite = int(max_tentativas or _config.WORKER_MAX_TENTATIVAS)
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        if dados["estado"] != "processing":
            return fila._para_job(dados)
        if pid_do_lease(dados.get("lease")) != pid_esperado:
            raise RuntimeError("lease não pertence ao worker supervisionado")
        attempt = int(dados.get("attempt") or 0)
        if estado == "failed" and attempt < limite:
            dados["estado"] = "pending"
            dados["lease"] = None
        else:
            dados["estado"] = estado
        dados["erro_seguro"] = codigo
        dados["resultado"] = None
        return _gravar(fila, dados)


def persistir_observabilidade(fila, job_id: str, **campos):
    with fila._transacao_job(job_id) as caminho:
        dados = fila._carregar(caminho)
        dados.update(campos)
        return _gravar(fila, dados)


def persistir_worker(fila, job_id: str, pid: int, iniciado_em: str | None):
    from fila_processamento import _agora_iso

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ValueError("pid de worker inválido")
    instante = iniciado_em or _agora_iso()
    if not isinstance(instante, str) or not (1 <= len(instante) <= 80):
        raise ValueError("instante de início inválido")
    return persistir_observabilidade(
        fila, job_id, worker_pid=pid, worker_iniciado_em=instante
    )


def persistir_saida_worker(fila, job_id: str, codigo: int, terminado_em: str | None):
    from fila_processamento import _agora_iso

    if isinstance(codigo, bool) or not isinstance(codigo, int):
        raise ValueError("código de saída inválido")
    if not -(2**31) <= codigo <= 2**31 - 1:
        raise ValueError("código de saída inválido")
    instante = terminado_em or _agora_iso()
    if not isinstance(instante, str) or not (1 <= len(instante) <= 80):
        raise ValueError("instante de término inválido")
    return persistir_observabilidade(
        fila, job_id, worker_codigo_saida=codigo, worker_terminado_em=instante
    )


def recuperar_jobs_interrompidos(fila) -> int:
    import json
    import logging
    import os
    import uuid

    from fila_lock import ProcessIdentityIndeterminate, lease_de_dados, process_matches
    from fila_processamento import PADRAO_ID, _agora_iso

    logger = logging.getLogger(__name__)
    recuperados = 0
    for caminho in sorted(fila.pasta_jobs.glob("*.json")):
        job_id = caminho.stem
        if not PADRAO_ID.fullmatch(job_id):
            continue
        try:
            with fila._transacao_job(job_id) as bloqueado:
                dados = fila._carregar(bloqueado)
                if dados["estado"] != "processing":
                    continue
                lease = dados.get("lease")
                if lease is None:
                    vivo = False
                else:
                    try:
                        vivo = process_matches(lease_de_dados(lease).owner)
                    except ProcessIdentityIndeterminate:
                        vivo = None
                if vivo is True:
                    continue
                if vivo is None:
                    logger.warning(
                        "Lease de job indeterminado; recuperação adiada: %s",
                        bloqueado.name,
                    )
                    continue
                dados["estado"] = "pending"
                dados["lease"] = None
                dados["erro_seguro"] = None
                dados["resultado"] = None
                dados["revision"] += 1
                dados["atualizado_em"] = _agora_iso()
                fila._salvar(dados)
                recuperados += 1
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            destino = caminho.with_suffix(".corrupt")
            if destino.exists():
                destino = caminho.with_suffix(f".{uuid.uuid4().hex}.corrupt")
            try:
                os.replace(caminho, destino)
            except FileNotFoundError:
                continue
            logger.error("Job corrompido movido para quarentena: %s", destino.name)
            continue
    return recuperados
