# -*- coding: utf-8 -*-
"""Retenção de áudio somente após resultado íntegro e confirmação explícita."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from artefatos import sha256_arquivo
from config import RETENCAO_AUDIO_DIAS
from resultado_reuniao import StageState, carregar_manifesto, validar_manifesto


logger = logging.getLogger(__name__)


def _agora_utc(agora: datetime | None) -> datetime:
    if agora is None:
        return datetime.now(timezone.utc)
    if agora.tzinfo is None:
        return agora.replace(tzinfo=timezone.utc)
    return agora.astimezone(timezone.utc)


def _estado_job(job: object) -> str | None:
    if isinstance(job, dict):
        return job.get("estado")
    return getattr(job, "estado", None)


def _audio_job(job: object) -> str | None:
    if isinstance(job, dict):
        return job.get("audio")
    return getattr(job, "audio", None)


def _job_dependente(audio: Path, jobs: Iterable[object]) -> bool:
    alvo = audio.resolve(strict=True)
    for job in jobs:
        if _estado_job(job) not in {"pending", "processing"}:
            continue
        caminho = _audio_job(job)
        if not isinstance(caminho, str):
            continue
        try:
            if Path(caminho).resolve(strict=True) == alvo:
                return True
        except OSError:
            continue
    return False


def pode_expirar(
    audio: Path,
    jobs: Iterable[object],
    manifesto: Path,
    agora: datetime,
    *,
    dias: int = RETENCAO_AUDIO_DIAS,
) -> bool:
    """Só libera uma fonte com manifesto revalidado e sem trabalho dependente."""
    if isinstance(dias, bool) or not isinstance(dias, int) or dias < 0:
        raise ValueError("dias de retenção inválidos")
    try:
        audio_resolvido = Path(audio).resolve(strict=True)
        caminho_manifesto = Path(manifesto).resolve(strict=True)
    except OSError:
        return False
    raiz = caminho_manifesto.parent
    if not validar_manifesto(caminho_manifesto, raiz):
        return False
    try:
        resultado = carregar_manifesto(caminho_manifesto)
        criado_em = datetime.fromisoformat(resultado.created_at.replace("Z", "+00:00"))
    except (OSError, ValueError):
        return False
    if (
        resultado.stage_status.get("stt") is not StageState.COMPLETE
        or "stt_sem_fala" in resultado.warnings
        or sha256_arquivo(audio_resolvido) not in resultado.source_audio_hashes
        or _job_dependente(audio_resolvido, jobs)
    ):
        return False
    if criado_em.tzinfo is None:
        return False
    return _agora_utc(agora) >= criado_em.astimezone(timezone.utc) + timedelta(days=dias)


def _audios(pasta_audio: Path) -> list[Path]:
    if not pasta_audio.is_dir():
        return []
    return sorted(
        caminho
        for caminho in pasta_audio.iterdir()
        if caminho.is_file()
        and (caminho.name.lower().endswith(".wav") or caminho.name.lower().endswith(".wav.enc"))
    )


def _jobs_persistidos(pasta_transcricoes: Path) -> list[object]:
    try:
        from fila_processamento import FilaProcessamento

        return FilaProcessamento(str(pasta_transcricoes)).listar()
    except Exception:
        logger.warning("Não foi possível ler jobs para retenção", exc_info=True)
        return []


def inventariar_audios_vencidos(
    pasta_audio: Path,
    pasta_transcricoes: Path,
    *,
    jobs: Iterable[object] | None = None,
    agora: datetime | None = None,
    dias: int = RETENCAO_AUDIO_DIAS,
) -> tuple[list[str], list[str]]:
    """Retorna candidatos e bloqueados; não remove nenhum arquivo."""
    raiz = Path(pasta_transcricoes).resolve()
    fontes = _audios(Path(pasta_audio))
    jobs_efetivos = list(_jobs_persistidos(raiz) if jobs is None else jobs)
    manifestos = sorted(raiz.glob("*.resultado.json")) if raiz.is_dir() else []
    elegiveis: list[str] = []
    bloqueados: list[str] = []
    instante = _agora_utc(agora)
    for audio in fontes:
        if any(
            pode_expirar(audio, jobs_efetivos, manifesto, instante, dias=dias)
            for manifesto in manifestos
        ):
            elegiveis.append(str(audio))
        else:
            bloqueados.append(str(audio))
    return elegiveis, bloqueados


def _tem_manifesto_associado(audio: str, raiz: Path) -> bool:
    """Distingue uma fonte ainda no prazo de uma fonte sem resultado íntegro."""
    try:
        hash_audio = sha256_arquivo(Path(audio).resolve(strict=True))
    except OSError:
        return False
    for caminho_manifesto in raiz.glob("*.resultado.json"):
        if not validar_manifesto(caminho_manifesto, raiz):
            continue
        try:
            if hash_audio in carregar_manifesto(caminho_manifesto).source_audio_hashes:
                return True
        except (OSError, ValueError):
            continue
    return False


def aplicar_exclusao_confirmada(
    candidatos: Iterable[str | Path],
    *,
    pasta_audio: Path,
    confirmados: Iterable[str | Path],
    dry_run: bool = True,
) -> list[str]:
    """Aplica somente paths confirmados que continuam sob a pasta inventariada."""
    try:
        raiz_audio = Path(pasta_audio).resolve(strict=True)
    except OSError:
        return []
    if not raiz_audio.is_dir():
        return []
    confirmacoes: set[Path] = set()
    for confirmado in confirmados:
        try:
            confirmacoes.add(Path(confirmado).resolve(strict=True))
        except OSError:
            continue
    selecionados: list[Path] = []
    for candidato in candidatos:
        try:
            caminho = Path(candidato).resolve(strict=True)
        except OSError:
            continue
        if not caminho.is_file() or not caminho.is_relative_to(raiz_audio):
            continue
        try:
            from recuperacao_sessao import sob_recuperacao_ativa

            if sob_recuperacao_ativa(caminho):
                continue
        except Exception:  # noqa: BLE001 — guarda indisponível não libera
            continue
        if caminho in confirmacoes and caminho not in selecionados:
            selecionados.append(caminho)
    if dry_run:
        return [str(caminho) for caminho in selecionados]
    removidos: list[str] = []
    for caminho in selecionados:
        try:
            caminho.unlink()
            removidos.append(str(caminho))
        except OSError:
            logger.warning("Falha ao remover áudio confirmado: %s", caminho.name)
    return removidos


def limpar_audios_vencidos(
    pasta_audio: str,
    pasta_transcricoes: str,
    dias: int = RETENCAO_AUDIO_DIAS,
    agora: datetime | None = None,
    *,
    jobs: Iterable[object] | None = None,
    confirmados: Iterable[str | Path] = (),
    dry_run: bool = True,
) -> tuple[list[str], list[str]]:
    """Compatibilidade: por padrão apenas inventaria, sem exclusão automática."""
    elegiveis, bloqueados = inventariar_audios_vencidos(
        Path(pasta_audio),
        Path(pasta_transcricoes),
        jobs=jobs,
        agora=agora,
        dias=dias,
    )
    removidos = aplicar_exclusao_confirmada(
        elegiveis,
        pasta_audio=Path(pasta_audio),
        confirmados=confirmados,
        dry_run=dry_run,
    )
    orfaos = [
        caminho
        for caminho in bloqueados
        if not _tem_manifesto_associado(caminho, Path(pasta_transcricoes).resolve())
    ]
    if not dry_run:
        orfaos.extend(caminho for caminho in elegiveis if caminho not in removidos)
    return removidos if not dry_run else [], orfaos
