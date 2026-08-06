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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config as _config


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
        self._lock = threading.Lock()

    def caminho_job(self, job_id: str) -> Path:
        if not PADRAO_ID.fullmatch(str(job_id)):
            raise ValueError("id de job inválido")
        return self.pasta_jobs / f"{job_id}.json"

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
        }
        with self._lock:
            self._salvar(dados)
        return job_id

    def obter(self, job_id: str) -> Job:
        with self._lock:
            return self._para_job(self._carregar(self.caminho_job(job_id)))

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
        with self._lock:
            for caminho in sorted(self.pasta_jobs.glob("*.json")):
                claim = caminho.with_suffix(".claim")
                try:
                    fd = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.close(fd)
                except FileExistsError:
                    continue
                try:
                    dados = self._carregar(caminho)
                    if dados["estado"] != "pending":
                        continue
                    dados["estado"] = "processing"
                    dados["atualizado_em"] = _agora_iso()
                    self._salvar(dados)
                    return self._para_job(dados)
                finally:
                    claim.unlink(missing_ok=True)
        return None

    def reivindicar(self, job_id: str) -> Job:
        """Marca um job pending específico para o subprocesso solicitado."""
        caminho = self.caminho_job(job_id)
        claim = caminho.with_suffix(".claim")
        try:
            fd = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError as exc:
            raise RuntimeError("job já reivindicado") from exc
        try:
            with self._lock:
                dados = self._carregar(caminho)
                if dados["estado"] != "pending":
                    raise RuntimeError("job não está pendente")
                dados["estado"] = "processing"
                dados["atualizado_em"] = _agora_iso()
                self._salvar(dados)
                return self._para_job(dados)
        finally:
            claim.unlink(missing_ok=True)

    def _alterar_estado(self, job_id: str, estado: str, **campos) -> Job:
        with self._lock:
            caminho = self.caminho_job(job_id)
            dados = self._carregar(caminho)
            if dados["estado"] != "processing":
                raise RuntimeError("job não está em processamento")
            dados.update(campos)
            dados["estado"] = estado
            dados["atualizado_em"] = _agora_iso()
            self._salvar(dados)
            return self._para_job(dados)

    def concluir(self, job_id: str, resultado: str) -> Job:
        relativo = self._relativo_validado(resultado)
        return self._alterar_estado(
            job_id, "ready", resultado=relativo, erro_seguro=None
        )

    def falhar(self, job_id: str, erro_seguro: str) -> Job:
        codigo = str(erro_seguro)
        if not PADRAO_ERRO.fullmatch(codigo):
            codigo = "erro_processamento"
        return self._alterar_estado(
            job_id, "failed", erro_seguro=codigo, resultado=None
        )

    def recuperar_interrompidos(self) -> int:
        recuperados = 0
        with self._lock:
            for claim in self.pasta_jobs.glob("*.claim"):
                claim.unlink(missing_ok=True)
            for caminho in sorted(self.pasta_jobs.glob("*.json")):
                dados = self._carregar(caminho)
                if dados["estado"] != "processing":
                    continue
                dados["estado"] = "pending"
                dados["erro_seguro"] = None
                dados["resultado"] = None
                dados["atualizado_em"] = _agora_iso()
                self._salvar(dados)
                recuperados += 1
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


def concluir(job_id, resultado) -> Job:
    return fila_padrao().concluir(job_id, resultado)


def falhar(job_id, erro_seguro) -> Job:
    return fila_padrao().falhar(job_id, erro_seguro)


def recuperar_interrompidos() -> int:
    return fila_padrao().recuperar_interrompidos()
