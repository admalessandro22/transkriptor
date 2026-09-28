# -*- coding: utf-8 -*-
"""Exclusão completa de uma reunião (pedido do usuário, 24/09/2026).

Apaga tudo o que pertence à reunião — manifesto, falas, transcrições (.txt,
.tkpt, _diarizado), áudio, sessão de gravação, eventos do Meet, resumo da IA,
job e entrada do índice — e nada além:

- só nomes exatos, nunca curinga de prefixo (`…_16h05` é prefixo de
  `…_16h05_Reuniao_X`, outra reunião);
- todo caminho é resolvido e precisa ficar dentro de `transcricoes/`;
- DU-11: o plano mostrado ao usuário é o executado — `plano_id` é o hash da
  lista exata; se algo mudou entre confirmar e excluir, a exclusão é recusada;
- reunião em processamento não é excluída;
- execução em duas fases: tudo vai para `.lixeira_exclusao/` (mesmo disco,
  rename), o índice é atualizado e só então a área é apagada; falha no meio
  devolve cada item ao lugar.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

LIXEIRA = ".lixeira_exclusao"
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_SESSAO = re.compile(r"[A-Za-z0-9-]{8,64}")
_SUFIXO_MANIFESTO = ".resultado.json"
_SUFIXOS_TRANSCRICAO = (".txt", ".tkpt", "_diarizado.txt", "_diarizado.tkpt")
_SUFIXOS_AUDIO = ("_audio.wav", "_audio.wav.enc", "_mic.wav", "_mic.wav.enc")
_EM_ANDAMENTO = {"pending", "processing"}


class ReuniaoNaoEncontrada(LookupError):
    pass


class ExclusaoBloqueada(RuntimeError):
    """Reunião ainda em processamento."""


class PlanoDivergente(RuntimeError):
    """Os arquivos mudaram desde a confirmação; mostre o plano de novo."""


@dataclass(frozen=True)
class Item:
    caminho: str          # relativo a transcricoes/, com "/"
    categoria: str
    bytes: int
    pasta: bool


@dataclass(frozen=True)
class Plano:
    meeting_id: str
    itens: tuple[Item, ...]
    bytes_total: int
    plano_id: str

    def como_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "plano_id": self.plano_id,
            "bytes_total": self.bytes_total,
            "itens": [{"caminho": i.caminho, "categoria": i.categoria, "bytes": i.bytes, "pasta": i.pasta}
                      for i in self.itens],
        }


def _dentro(raiz: Path, alvo: Path) -> bool:
    try:
        alvo.resolve().relative_to(raiz.resolve())
        return True
    except (OSError, ValueError):
        return False


def _relativo(raiz: Path, valor: object) -> Path | None:
    """Caminho do job/manifesto: só relativo, sem '..', dentro da raiz."""
    if not isinstance(valor, str) or not valor or os.path.isabs(valor) or ".." in Path(valor).parts:
        return None
    alvo = raiz / valor
    return alvo if _dentro(raiz, alvo) else None


def _tamanho(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _categoria(rel: str) -> str:
    if rel.startswith(("audio/", "sessoes/")):
        return "Áudio"
    if rel.startswith("eventos_privados/"):
        return "Eventos do Meet"
    if rel.startswith("resumos/"):
        return "Resumo"
    if rel.startswith(".jobs_processamento/"):
        return "Controle de processamento"
    return "Transcrição"


def _manifesto(raiz: Path, meeting_id: str) -> Path | None:
    for caminho in sorted(raiz.glob("*" + _SUFIXO_MANIFESTO)):
        try:
            if json.loads(caminho.read_text(encoding="utf-8")).get("meeting_id") == meeting_id:
                return caminho
        except (OSError, ValueError, AttributeError):
            continue
    return None


def _ler_json(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def planejar(raiz: Path, meeting_id: str) -> Plano:
    raiz = Path(raiz)
    if not isinstance(meeting_id, str) or not _ID.fullmatch(meeting_id):
        raise ReuniaoNaoEncontrada("reunião inválida")
    job_path = raiz / ".jobs_processamento" / f"{meeting_id}.json"
    job = _ler_json(job_path)
    if job.get("estado") in _EM_ANDAMENTO:
        raise ExclusaoBloqueada("a reunião ainda está sendo processada")
    manifesto = _manifesto(raiz, meeting_id)
    if manifesto is None and not job:
        raise ReuniaoNaoEncontrada("reunião não encontrada")

    alvos: set[Path] = set()
    if manifesto is not None:
        alvos.add(manifesto)
        dados = _ler_json(manifesto)
        seg = _relativo(raiz, (dados.get("segments_ref") or {}).get("relative_path"))
        if seg is not None:
            alvos.add(seg)
        for exp in dados.get("exports") or []:
            if isinstance(exp, dict) and (p := _relativo(raiz, exp.get("relative_path"))) is not None:
                alvos.add(p)
    bases = {b for b in (
        manifesto.name[: -len(_SUFIXO_MANIFESTO)] if manifesto is not None else None,
        job.get("base_saida") if isinstance(job.get("base_saida"), str) else None,
    ) if b and "/" not in b and "\\" not in b and ".." not in b}
    for base in bases:
        alvos.update(raiz / f"{base}{s}" for s in _SUFIXOS_TRANSCRICAO)
        alvos.update(raiz / "audio" / f"{base}{s}" for s in _SUFIXOS_AUDIO)
    for chave in ("audio", "mic", "resultado", "manifesto_resultado"):
        if (p := _relativo(raiz, job.get(chave))) is not None:
            alvos.add(p)
    pasta_resultados = raiz / "resultados"
    if pasta_resultados.is_dir():
        alvos.update(p for p in pasta_resultados.iterdir() if p.name.split(".", 1)[0] == meeting_id)
    alvos.add(raiz / "resumos" / f"{meeting_id}.resumo")
    if job:
        alvos.add(job_path)
    alvos.add(raiz / ".jobs_processamento" / ".locks" / f"{meeting_id}.lock")
    sessao = (job.get("sessao") or {}).get("session_id") if isinstance(job.get("sessao"), dict) else None
    if isinstance(sessao, str) and _SESSAO.fullmatch(sessao):
        alvos.add(raiz / "sessoes" / sessao)
        alvos.add(raiz / "eventos_privados" / sessao)

    itens = []
    for alvo in alvos:
        if not alvo.exists() or not _dentro(raiz, alvo) or LIXEIRA in alvo.parts:
            continue
        rel = alvo.resolve().relative_to(raiz.resolve()).as_posix()
        itens.append(Item(rel, _categoria(rel), _tamanho(alvo), alvo.is_dir()))
    itens.sort(key=lambda i: (i.categoria, i.caminho))
    assinatura = "\n".join(f"{i.caminho}|{int(i.pasta)}|{i.bytes}" for i in itens)
    plano_id = hashlib.sha256(f"{meeting_id}\n{assinatura}".encode("utf-8")).hexdigest()
    return Plano(meeting_id, tuple(itens), sum(i.bytes for i in itens), plano_id)


def _mover(origem: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    os.replace(origem, destino)


def _tirar_do_indice(raiz: Path, meeting_id: str) -> dict | None:
    """Remove a entrada; devolve a entrada antiga para restaurar em caso de falha."""
    from indice_transcricoes import _carregar_indice, _salvar_indice

    indice = raiz / "indice.json"
    reunioes = _carregar_indice(indice)
    antiga = reunioes.pop(meeting_id, None)
    if antiga is not None:
        _salvar_indice(indice, reunioes)
    return antiga


def excluir(raiz: Path, meeting_id: str, plano_id: str) -> Plano:
    """Executa exatamente o plano confirmado; sem volta depois de concluir."""
    raiz = Path(raiz)
    plano = planejar(raiz, meeting_id)
    if plano.plano_id != plano_id:
        raise PlanoDivergente("os arquivos da reunião mudaram; confirme de novo")
    shutil.rmtree(raiz / LIXEIRA, ignore_errors=True)  # restos de exclusões já concluídas
    area = raiz / LIXEIRA / f"{meeting_id}-{int(time.time() * 1000)}"
    movidos: list[tuple[Path, Path]] = []
    try:
        for item in plano.itens:
            origem = raiz / item.caminho
            destino = area / item.caminho
            _mover(origem, destino)
            movidos.append((origem, destino))
        _tirar_do_indice(raiz, meeting_id)
    except Exception:
        for origem, destino in reversed(movidos):
            try:
                _mover(destino, origem)
            except OSError:
                logger.error("Exclusão de reunião: não foi possível restaurar um item.", exc_info=True)
        shutil.rmtree(area, ignore_errors=True)
        raise
    shutil.rmtree(raiz / LIXEIRA, ignore_errors=True)
    if (raiz / LIXEIRA).exists():
        logger.warning("Exclusão de reunião: restos em %s serão apagados na próxima exclusão.", LIXEIRA)
    logger.info("Reunião excluída: %d item(ns).", len(plano.itens))
    return plano
