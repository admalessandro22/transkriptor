# -*- coding: utf-8 -*-
"""Snapshot de estado da bandeja para a Central (FR-14.D1).

Lê atributos do `AppTranskriptor` sem pedir `self._lock` (regra da regressão
de 2026-08-07: nada que possa bloquear roda no caminho de leitura) e nunca
inclui conteúdo de fala, nomes de participantes, tokens ou caminhos pessoais.
A única leitura de disco é a última reunião pelo índice de metadados.
"""
from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from config import PASTA_TRANSCRICOES, VERSAO
from estado_icone import resolver_estado_icone

ESTADOS = ("aguardando", "gravando", "processando", "separando_vozes", "pausado", "erro")
ROTULOS = {
    "aguardando": "Aguardando reunião",
    "gravando": "Gravando",
    "processando": "Processando reunião",
    "separando_vozes": "Separando vozes",
    "pausado": "Pausado",
    "erro": "Erro",
}
_DO_ICONE = {
    "erro": "erro",
    "diarizando": "separando_vozes",
    "transcrevendo": "gravando",
    "processando": "processando",
    "aguardando": "aguardando",
    "pausado": "pausado",
}
CAMPOS = ("estado", "rotulo", "fontes", "processamento", "protecao", "ultima_reuniao", "versao", "gerado_em")


@dataclass(frozen=True)
class SnapshotEstado:
    estado: str
    rotulo: str
    fontes: tuple[str, ...]
    processamento: str | None
    protecao: str
    ultima_reuniao: dict | None
    versao: str
    gerado_em: str

    def como_dict(self) -> dict:
        dados = asdict(self)
        dados["fontes"] = list(self.fontes)
        return dados


_PROVEDOR: Callable[[], SnapshotEstado] | None = None


def registrar_provedor(fn: Callable[[], SnapshotEstado] | None) -> None:
    global _PROVEDOR
    _PROVEDOR = fn


def provedor_atual() -> Callable[[], SnapshotEstado] | None:
    return _PROVEDOR


def _protecao() -> str:
    try:
        from politica_privacidade import modo_efetivo

        return str(modo_efetivo().value)
    except Exception:  # noqa: BLE001 — estado nunca cai por política
        return "compatible"


def ultima_reuniao(indice: Path | None = None) -> dict | None:
    """Metadados da reunião mais recente pelo índice; nunca abre conteúdo."""
    try:
        from indice_transcricoes import listar_reunioes

        caminho = indice or Path(PASTA_TRANSCRICOES) / "indice.json"
        pagina, _ = listar_reunioes(caminho, cursor=None, limit=1)
    except Exception:  # noqa: BLE001 — índice ausente ou inválido não derruba o estado
        return None
    if not pagina:
        return None
    resumo = pagina[0]
    estado = {"pronto": "Pronta", "parcial": "Parcial", "falhou": "Falhou"}.get(str(resumo.quality_state), str(resumo.quality_state))
    return {"meeting_id": resumo.meeting_id, "started_at": resumo.started_at, "estado": estado}


def _fontes(app) -> tuple[str, ...]:
    detector = getattr(app, "detector", None)
    fontes = getattr(detector, "fontes_da_reuniao", None) or []
    return tuple(str(f) for f in fontes)


def snapshot(app, agora: float | None = None, indice: Path | None = None) -> SnapshotEstado:
    """Estado atual da bandeja; só atributos já em memória, sem lock."""
    transcritor = getattr(app, "transcritor", None)
    estado_icone, _titulo = resolver_estado_icone(
        transcritor,
        bool(getattr(app, "deteccao_ativa", True)),
        em_erro=bool(getattr(app, "_em_erro", False)),
        instante_erro=getattr(app, "_instante_erro", None),
        agora=agora,
        processando=getattr(app, "_estado_processamento", None) == "Processando",
    )
    estado = _DO_ICONE.get(estado_icone, "aguardando")
    processamento = getattr(app, "_estado_processamento", None)
    return SnapshotEstado(
        estado=estado,
        rotulo=ROTULOS[estado],
        fontes=_fontes(app) if estado == "gravando" else (),
        processamento=str(processamento) if processamento else None,
        protecao=_protecao(),
        ultima_reuniao=ultima_reuniao(indice),
        versao=VERSAO,
        gerado_em=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )


def validar_snapshot(dados: Mapping) -> list[str]:
    """Campos fora do contrato ou valores suspeitos (caminhos, tokens); lista vazia = ok."""
    problemas = []
    extras = set(dados) - set(CAMPOS)
    if extras:
        problemas.append(f"campos fora do contrato: {sorted(extras)}")
    faltando = set(CAMPOS) - set(dados)
    if faltando:
        problemas.append(f"campos ausentes: {sorted(faltando)}")
    if dados.get("estado") not in ESTADOS:
        problemas.append(f"estado desconhecido: {dados.get('estado')!r}")
    texto = " ".join(str(v) for v in dados.values())
    for suspeito in ("\\Users\\", "/Users/", "token", "C:\\", "AppData"):
        if suspeito.lower() in texto.lower():
            problemas.append(f"valor suspeito no snapshot: {suspeito}")
    return problemas
