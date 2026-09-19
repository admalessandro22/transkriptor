# -*- coding: utf-8 -*-
"""Fila durável e atômica para pós-processamento de reuniões."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config as _config
from fila_lock import current_process_identity, job_lock, lease_de_dados
from resultado_reuniao import validar_manifesto_para_job

logger = logging.getLogger(__name__)

ESTADOS = {"pending", "processing", "ready", "failed", "cancelled"}
PADRAO_STAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
CHAVES_METADADOS = {
    "origem",
    "inicio_iso",
    "fim_iso",
    "duracao_seg",
    "diarizar",
    "identificar_voz",
    "criptografar",
    "modelo",
    "idioma",
    "lacuna_estimada_seg",
    "titulo_reuniao",
}
PADRAO_ID = re.compile(r"^[a-f0-9]{32}$")
PADRAO_BASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
PADRAO_ERRO = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Job:
    id: str
    estado: str
    audio: str
    mic: str | None
    base_saida: str
    metadados: dict
    resultado: str | None
    erro_seguro: str | None
    criado_em: str
    atualizado_em: str
    revision: int = 0
    lease: dict | None = None
    schema_version: int = 1
    manifesto_resultado: str | None = None
    worker_pid: int | None = None
    worker_iniciado_em: str | None = None
    worker_terminado_em: str | None = None
    worker_codigo_saida: int | None = None
    stage: str | None = None
    progress_units: int = 0
    attempt: int = 0
    warnings: tuple[str, ...] = ()
    cancel_solicitado: bool = False


class FilaProcessamento:
    def __init__(self, pasta_transcricoes: str, pasta_jobs: str | None = None):
        self.pasta_transcricoes = Path(pasta_transcricoes).resolve()
        self.pasta_transcricoes.mkdir(parents=True, exist_ok=True)
        self.pasta_jobs = Path(
            pasta_jobs or self.pasta_transcricoes / ".jobs_processamento"
        ).resolve()
        if not self.pasta_jobs.is_relative_to(self.pasta_transcricoes):
            raise ValueError("pasta de jobs deve ficar dentro de transcricoes")
        self.pasta_jobs.mkdir(parents=True, exist_ok=True)
        self.pasta_locks = self.pasta_jobs / ".locks"
        self.pasta_locks.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def caminho_job(self, job_id: str) -> Path:
        if not PADRAO_ID.fullmatch(str(job_id)):
            raise ValueError("id de job inválido")
        return self.pasta_jobs / f"{job_id}.json"

    def _caminho_lock(self, job_id: str) -> Path:
        if not PADRAO_ID.fullmatch(str(job_id)):
            raise ValueError("id de job inválido")
        return self.pasta_locks / f"{job_id}.lock"

    @contextmanager
    def _transacao_job(self, job_id: str):
        """Serializa RMW no processo e entre processos para um job."""
        with self._lock:
            with job_lock(self._caminho_lock(job_id)):
                yield self.caminho_job(job_id)

    def _relativo_validado(self, caminho: str | None) -> str | None:
        if caminho is None:
            return None
        resolvido = Path(caminho).resolve(strict=True)
        if not resolvido.is_file() or not resolvido.is_relative_to(
            self.pasta_transcricoes
        ):
            raise ValueError("arquivo deve ficar dentro de transcricoes")
        return resolvido.relative_to(self.pasta_transcricoes).as_posix()

    def _absoluto_validado(self, relativo: str | None) -> str | None:
        if relativo is None:
            return None
        caminho = (self.pasta_transcricoes / relativo).resolve()
        if not caminho.is_relative_to(self.pasta_transcricoes):
            raise ValueError("path inválido no job")
        return str(caminho)

    def _metadados_seguros(self, metadados: dict | None) -> dict:
        seguros = {}
        for chave, valor in dict(metadados or {}).items():
            if chave not in CHAVES_METADADOS:
                continue
            if isinstance(valor, (bool, int, float)) or valor is None:
                seguros[chave] = valor
            elif isinstance(valor, str) and len(valor) <= 80:
                seguros[chave] = valor
        return seguros

    def _salvar(self, dados: dict) -> None:
        if dados.get("estado") not in ESTADOS:
            raise ValueError("estado de job inválido")
        if not isinstance(dados.get("revision"), int) or dados["revision"] < 0:
            raise ValueError("revisão de job inválida")
        if dados.get("schema_version") not in {1, 2}:
            raise ValueError("versão de job inválida")
        dados["schema_version"] = 2
        destino = self.caminho_job(dados["id"])
        fd, temporario = tempfile.mkstemp(
            prefix=f"{dados['id']}_", suffix=".tmp", dir=str(self.pasta_jobs)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
                json.dump(dados, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
                arquivo.write("\n")
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, destino)
            temporario = None
        finally:
            if temporario and os.path.isfile(temporario):
                try:
                    os.remove(temporario)
                except OSError:
                    pass

    def _carregar(self, caminho: Path) -> dict:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or dados.get("estado") not in ESTADOS:
            raise ValueError("job inválido")
        dados.setdefault("revision", 0)
        dados.setdefault("lease", None)
        dados.setdefault("schema_version", 1)
        dados.setdefault("manifesto_resultado", None)
        dados.setdefault("stage", None)
        dados.setdefault("progress_units", 0)
        dados.setdefault("attempt", 0)
        dados.setdefault("warnings", [])
        dados.setdefault("cancel_solicitado", False)
        if not isinstance(dados["progress_units"], int) or dados["progress_units"] < 0:
            raise ValueError("progresso de job inválido")
        if not isinstance(dados["attempt"], int) or dados["attempt"] < 0:
            raise ValueError("tentativa de job inválida")
        if dados["stage"] is not None and not PADRAO_STAGE.fullmatch(str(dados["stage"])):
            raise ValueError("etapa de job inválida")
        if dados["cancel_solicitado"] not in {True, False}:
            raise ValueError("cancelamento de job inválido")
        if not isinstance(dados["revision"], int) or dados["revision"] < 0:
            raise ValueError("revisão de job inválida")
        if dados["lease"] is not None:
            lease_de_dados(dados["lease"])
        if dados["schema_version"] not in {1, 2}:
            raise ValueError("versão de job inválida")
        if dados["manifesto_resultado"] is not None and not isinstance(
            dados["manifesto_resultado"], str
        ):
            raise ValueError("manifesto de job inválido")
        return dados

    def _para_job(self, dados: dict) -> Job:
        return Job(
            id=dados["id"],
            estado=dados["estado"],
            audio=self._absoluto_validado(dados["audio"]),
            mic=self._absoluto_validado(dados.get("mic")),
            base_saida=dados["base_saida"],
            metadados=dict(dados.get("metadados") or {}),
            resultado=self._absoluto_validado(dados.get("resultado")),
            erro_seguro=dados.get("erro_seguro"),
            criado_em=dados["criado_em"],
            atualizado_em=dados["atualizado_em"],
            revision=dados["revision"],
            lease=dict(dados["lease"]) if dados["lease"] is not None else None,
            schema_version=dados["schema_version"],
            manifesto_resultado=self._absoluto_validado(dados["manifesto_resultado"]),
            worker_pid=dados.get("worker_pid"),
            worker_iniciado_em=dados.get("worker_iniciado_em"),
            worker_terminado_em=dados.get("worker_terminado_em"),
            worker_codigo_saida=dados.get("worker_codigo_saida"),
            stage=dados.get("stage"),
            progress_units=int(dados.get("progress_units") or 0),
            attempt=int(dados.get("attempt") or 0),
            warnings=tuple(dados.get("warnings") or ()),
            cancel_solicitado=bool(dados.get("cancel_solicitado")),
        )

    def enfileirar(
        self,
        audio: str,
        mic: str | None,
        base_saida: str,
        metadados: dict | None,
    ) -> str:
        if not PADRAO_BASE.fullmatch(str(base_saida)):
            raise ValueError("base de saída inválida")
        agora = _agora_iso()
        job_id = uuid.uuid4().hex
        dados = {
            "id": job_id,
            "estado": "pending",
            "audio": self._relativo_validado(audio),
            "mic": self._relativo_validado(mic),
            "base_saida": base_saida,
            "metadados": self._metadados_seguros(metadados),
            "resultado": None,
            "erro_seguro": None,
            "criado_em": agora,
            "atualizado_em": agora,
            "revision": 0,
            "lease": None,
            "schema_version": 2,
            "manifesto_resultado": None,
            "stage": None,
            "progress_units": 0,
            "attempt": 0,
            "warnings": [],
            "cancel_solicitado": False,
        }
        with self._lock:
            self._salvar(dados)
        return job_id

    def obter(self, job_id: str) -> Job:
        with self._transacao_job(job_id) as caminho:
            return self._para_job(self._carregar(caminho))

    def listar(self, estado: str | None = None) -> list[Job]:
        if estado is not None and estado not in ESTADOS:
            raise ValueError("estado de job inválido")
        jobs = []
        with self._lock:
            for caminho in self.pasta_jobs.glob("*.json"):
                try:
                    job = self._para_job(self._carregar(caminho))
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    logger.warning("Job inválido ignorado na fila: %s", caminho.name)
                    continue
                if estado is None or job.estado == estado:
                    jobs.append(job)
        return sorted(jobs, key=lambda job: (job.criado_em, job.id))

    def quantidade(self, estado: str | None = None) -> int:
        return len(self.listar(estado))

    def reivindicar_proximo(self) -> Job | None:
        for caminho in sorted(self.pasta_jobs.glob("*.json")):
            job_id = caminho.stem
            if not PADRAO_ID.fullmatch(job_id):
                continue
            try:
                with self._transacao_job(job_id) as bloqueado:
                    dados = self._carregar(bloqueado)
                    if dados["estado"] != "pending":
                        continue
                    return self._reivindicar_dados(dados)
            except FileNotFoundError:
                continue
        return None

    def reivindicar(self, job_id: str) -> Job:
        """Marca um job pending específico para o subprocesso solicitado."""
        with self._transacao_job(job_id) as caminho:
            dados = self._carregar(caminho)
            if dados["estado"] != "pending":
                raise RuntimeError("job não está pendente")
            return self._reivindicar_dados(dados)

    def _reivindicar_dados(self, dados: dict) -> Job:
        agora = _agora_iso()
        owner = current_process_identity()
        dados["estado"] = "processing"
        dados["attempt"] = int(dados.get("attempt") or 0) + 1
        dados["cancel_solicitado"] = bool(dados.get("cancel_solicitado"))
        dados["lease"] = {
            "owner": {
                "pid": owner.pid,
                "created_at_100ns": owner.created_at_100ns,
            },
            "nonce": uuid.uuid4().hex,
            "acquired_at_utc": agora,
            "heartbeat_at_utc": agora,
        }
        dados["revision"] += 1
        dados["atualizado_em"] = agora
        self._salvar(dados)
        return self._para_job(dados)

    def _alterar_estado(self, job_id: str, estado: str, **campos) -> Job:
        with self._transacao_job(job_id) as caminho:
            dados = self._carregar(caminho)
            if dados["estado"] != "processing":
                raise RuntimeError("job não está em processamento")
            self._exigir_lease_do_processo_atual(dados)
            dados.update(campos)
            dados["estado"] = estado
            dados["revision"] += 1
            dados["atualizado_em"] = _agora_iso()
            self._salvar(dados)
            return self._para_job(dados)

    def _exigir_lease_do_processo_atual(self, dados: dict):
        lease = lease_de_dados(dados.get("lease"))
        if lease.owner != current_process_identity():
            raise RuntimeError("lease não pertence ao processo atual")
        return lease

    def renovar_lease(self, job_id: str) -> Job:
        """Registra atividade do proprietário sem trocar o lease do job."""
        with self._transacao_job(job_id) as caminho:
            dados = self._carregar(caminho)
            if dados["estado"] != "processing":
                raise RuntimeError("job não está em processamento")
            lease = self._exigir_lease_do_processo_atual(dados)
            dados["lease"] = {
                "owner": {
                    "pid": lease.owner.pid,
                    "created_at_100ns": lease.owner.created_at_100ns,
                },
                "nonce": lease.nonce,
                "acquired_at_utc": lease.acquired_at_utc,
                "heartbeat_at_utc": _agora_iso(),
            }
            dados["revision"] += 1
            dados["atualizado_em"] = _agora_iso()
            self._salvar(dados)
            return self._para_job(dados)

    def concluir(self, job_id: str, resultado: str, manifesto_resultado: str) -> Job:
        relativo = self._relativo_validado(resultado)
        with self._transacao_job(job_id) as caminho:
            dados = self._carregar(caminho)
            if dados["estado"] != "processing":
                raise RuntimeError("job não está em processamento")
            self._exigir_lease_do_processo_atual(dados)
            fontes = [Path(self._absoluto_validado(dados["audio"]))]
            if dados.get("mic"):
                fontes.append(Path(self._absoluto_validado(dados["mic"])))
            relativo_manifesto = validar_manifesto_para_job(
                resultado=Path(resultado),
                manifesto=Path(manifesto_resultado),
                fontes_audio=fontes,
                raiz=self.pasta_transcricoes,
            )
            dados["estado"] = "ready"
            dados["resultado"] = relativo
            dados["manifesto_resultado"] = relativo_manifesto
            dados["erro_seguro"] = None
            dados["revision"] += 1
            dados["atualizado_em"] = _agora_iso()
            self._salvar(dados)
            return self._para_job(dados)

    def falhar(self, job_id: str, erro_seguro: str) -> Job:
        codigo = str(erro_seguro)
        if not PADRAO_ERRO.fullmatch(codigo):
            codigo = "erro_processamento"
        return self._alterar_estado(
            job_id, "failed", erro_seguro=codigo, resultado=None
        )

    def registrar_progresso(self, job_id: str, stage: str, units: int) -> Job:
        from worker_liveness import persistir_progresso

        return persistir_progresso(self, job_id, stage, units)

    def registrar_aviso(self, job_id: str, aviso: str) -> Job:
        from worker_liveness import persistir_aviso

        return persistir_aviso(self, job_id, aviso)

    def solicitar_cancelamento(self, job_id: str) -> Job:
        from worker_liveness import persistir_pedido_cancelamento

        return persistir_pedido_cancelamento(self, job_id)

    def cancelar(self, job_id: str) -> Job:
        return self._alterar_estado(
            job_id,
            "cancelled",
            erro_seguro="cancelado",
            resultado=None,
            manifesto_resultado=None,
        )

    def registrar_falha_de_spawn(self, job_id: str, erro_seguro: str) -> Job:
        from worker_liveness import persistir_falha_de_spawn

        return persistir_falha_de_spawn(self, job_id, erro_seguro)

    def reabrir_se_retry(
        self, job_id: str, max_tentativas: int | None = None
    ) -> Job:
        from worker_liveness import persistir_reabrir_retry

        return persistir_reabrir_retry(self, job_id, max_tentativas)

    def finalizar_por_supervisor(
        self, job_id: str, pid_esperado: int, erro_seguro: str, **kwargs
    ) -> Job:
        from worker_liveness import persistir_finalizar_supervisor

        return persistir_finalizar_supervisor(
            self, job_id, pid_esperado, erro_seguro, **kwargs
        )

    def registrar_worker(
        self, job_id: str, pid: int, iniciado_em: str | None = None
    ) -> Job:
        from worker_liveness import persistir_worker

        return persistir_worker(self, job_id, pid, iniciado_em)

    def registrar_saida_worker(
        self,
        job_id: str,
        codigo: int,
        terminado_em: str | None = None,
    ) -> Job:
        from worker_liveness import persistir_saida_worker

        return persistir_saida_worker(self, job_id, codigo, terminado_em)

    def recuperar_interrompidos(self) -> int:
        from worker_liveness import recuperar_jobs_interrompidos

        return recuperar_jobs_interrompidos(self)


_fila_padrao_instancia: FilaProcessamento | None = None


def fila_padrao() -> FilaProcessamento:
    global _fila_padrao_instancia
    pasta = str(Path(_config.PASTA_TRANSCRICOES).resolve())
    if (
        _fila_padrao_instancia is None
        or str(_fila_padrao_instancia.pasta_transcricoes) != pasta
    ):
        _fila_padrao_instancia = FilaProcessamento(pasta)
    return _fila_padrao_instancia


def enfileirar(audio, mic, base_saida, metadados) -> str:
    return fila_padrao().enfileirar(audio, mic, base_saida, metadados)


def reivindicar_proximo() -> Job | None:
    return fila_padrao().reivindicar_proximo()


def concluir(job_id, resultado, manifesto_resultado) -> Job:
    return fila_padrao().concluir(job_id, resultado, manifesto_resultado)


def falhar(job_id, erro_seguro) -> Job:
    return fila_padrao().falhar(job_id, erro_seguro)


def recuperar_interrompidos() -> int:
    return fila_padrao().recuperar_interrompidos()
