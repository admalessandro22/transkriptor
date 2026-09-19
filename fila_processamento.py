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
from fila_lock import (
    ProcessIdentityIndeterminate,
    current_process_identity,
    job_lock,
    lease_de_dados,
    process_matches,
)
from resultado_reuniao import validar_manifesto_para_job
logger = logging.getLogger(__name__)

ESTADOS = {"pending", "processing", "ready", "failed"}
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

    def _registrar_observabilidade(self, job_id: str, **campos) -> Job:
        """Atualiza somente metadados do worker, sem mudar o estado do job."""
        with self._transacao_job(job_id) as caminho:
            dados = self._carregar(caminho)
            dados.update(campos)
            dados["revision"] += 1
            dados["atualizado_em"] = _agora_iso()
            self._salvar(dados)
            return self._para_job(dados)

    def registrar_worker(
        self, job_id: str, pid: int, iniciado_em: str | None = None
    ) -> Job:
        """Persiste o PID e o instante de início sem registrar áudio ou texto."""
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("pid de worker inválido")
        instante = iniciado_em or _agora_iso()
        if not isinstance(instante, str) or not (1 <= len(instante) <= 80):
            raise ValueError("instante de início inválido")
        return self._registrar_observabilidade(
            job_id,
            worker_pid=pid,
            worker_iniciado_em=instante,
        )

    def registrar_saida_worker(
        self,
        job_id: str,
        codigo: int,
        terminado_em: str | None = None,
    ) -> Job:
        """Persiste o código de saída, mantendo o estado funcional do job."""
        if isinstance(codigo, bool) or not isinstance(codigo, int):
            raise ValueError("código de saída inválido")
        if not -(2**31) <= codigo <= 2**31 - 1:
            raise ValueError("código de saída inválido")
        instante = terminado_em or _agora_iso()
        if not isinstance(instante, str) or not (1 <= len(instante) <= 80):
            raise ValueError("instante de término inválido")
        return self._registrar_observabilidade(
            job_id,
            worker_codigo_saida=codigo,
            worker_terminado_em=instante,
        )

    def _lease_tem_proprietario_vivo(self, dados: dict) -> bool | None:
        """True=vivo, False=ausente/legado, None=identidade indeterminada."""
        lease = dados.get("lease")
        if lease is None:
            return False
        try:
            return process_matches(lease_de_dados(lease).owner)
        except ProcessIdentityIndeterminate:
            return None

    def _quarentenar_corrompido(self, caminho: Path) -> None:
        destino = caminho.with_suffix(".corrupt")
        if destino.exists():
            destino = caminho.with_suffix(f".{uuid.uuid4().hex}.corrupt")
        try:
            os.replace(caminho, destino)
        except FileNotFoundError:
            return
        logger.error("Job corrompido movido para quarentena: %s", destino.name)

    def recuperar_interrompidos(self) -> int:
        recuperados = 0
        for caminho in sorted(self.pasta_jobs.glob("*.json")):
            job_id = caminho.stem
            if not PADRAO_ID.fullmatch(job_id):
                continue
            try:
                with self._transacao_job(job_id) as bloqueado:
                    dados = self._carregar(bloqueado)
                    if dados["estado"] != "processing":
                        continue
                    vivo = self._lease_tem_proprietario_vivo(dados)
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
                    self._salvar(dados)
                    recuperados += 1
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                self._quarentenar_corrompido(caminho)
                continue
        return recuperados


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
