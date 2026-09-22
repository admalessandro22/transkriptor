"""Manifesto canônico mínimo do resultado de uma reunião."""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Sequence

import config
from artefatos import ArtifactRef, criar_referencia, referencia_integra, sha256_arquivo


VERSAO_MANIFESTO = 1
NOME_PENDENTE = "Identificação pendente"
VERSAO_SEGMENTOS = 1
_PADRAO_LINHA_TXT = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] .+: .+$")


class StageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ResultManifest:
    meeting_id: str
    schema_version: int
    source_audio_hashes: tuple[str, ...]
    participants_ref: ArtifactRef | None
    segments_ref: ArtifactRef
    stage_status: Mapping[str, StageState]
    warnings: tuple[str, ...]
    exports: tuple[ArtifactRef, ...]
    created_at: str
    pipeline_version: str


@dataclass(frozen=True)
class SegmentoResultado:
    segment_id: str
    start_ms: int
    end_ms: int
    audio_source: str
    text: str
    speaker_cluster_id: str
    overlap: bool = False
    assignment: Mapping[str, object] | None = None


def _agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _referencia_para_dict(referencia: ArtifactRef) -> dict[str, object]:
    return {
        "relative_path": referencia.relative_path,
        "format": referencia.format,
        "schema_version": referencia.schema_version,
        "sha256": referencia.sha256,
        "size_bytes": referencia.size_bytes,
    }


def _referencia_de_dict(dados: object) -> ArtifactRef:
    if not isinstance(dados, dict):
        raise ValueError("referência de artefato inválida")
    try:
        referencia = ArtifactRef(
            relative_path=dados["relative_path"],
            format=dados["format"],
            schema_version=dados["schema_version"],
            sha256=dados["sha256"],
            size_bytes=dados["size_bytes"],
        )
    except KeyError as exc:
        raise ValueError("referência de artefato incompleta") from exc
    if (
        not isinstance(referencia.relative_path, str)
        or not isinstance(referencia.format, str)
        or isinstance(referencia.schema_version, bool)
        or not isinstance(referencia.schema_version, int)
        or isinstance(referencia.size_bytes, bool)
        or not isinstance(referencia.size_bytes, int)
        or not isinstance(referencia.sha256, str)
    ):
        raise ValueError("referência de artefato inválida")
    return referencia


def _instante_valido(valor: str) -> bool:
    if not isinstance(valor, str) or not valor:
        return False
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _manifesto_para_dict(manifesto: ResultManifest) -> dict[str, object]:
    return {
        "meeting_id": manifesto.meeting_id,
        "schema_version": manifesto.schema_version,
        "source_audio_hashes": list(manifesto.source_audio_hashes),
        "participants_ref": (
            _referencia_para_dict(manifesto.participants_ref)
            if manifesto.participants_ref is not None
            else None
        ),
        "segments_ref": _referencia_para_dict(manifesto.segments_ref),
        "stage_status": {
            chave: estado.value for chave, estado in manifesto.stage_status.items()
        },
        "warnings": list(manifesto.warnings),
        "exports": [_referencia_para_dict(ref) for ref in manifesto.exports],
        "created_at": manifesto.created_at,
        "pipeline_version": manifesto.pipeline_version,
    }


def _validar_estrutura(manifesto: ResultManifest) -> None:
    if not isinstance(manifesto, ResultManifest):
        raise ValueError("manifesto inválido")
    if manifesto.schema_version != VERSAO_MANIFESTO:
        raise ValueError("versão de manifesto inválida")
    if not isinstance(manifesto.meeting_id, str) or not manifesto.meeting_id:
        raise ValueError("identificador de reunião inválido")
    if not manifesto.source_audio_hashes or any(
        not isinstance(hash_audio, str)
        or len(hash_audio) != 64
        or any(caractere not in "0123456789abcdef" for caractere in hash_audio)
        for hash_audio in manifesto.source_audio_hashes
    ):
        raise ValueError("hash de áudio inválido")
    if not manifesto.stage_status or any(
        not isinstance(chave, str) or not chave or not isinstance(estado, StageState)
        for chave, estado in manifesto.stage_status.items()
    ):
        raise ValueError("estado de estágio inválido")
    if not all(isinstance(aviso, str) and aviso for aviso in manifesto.warnings):
        raise ValueError("aviso de manifesto inválido")
    if not manifesto.exports or not _instante_valido(manifesto.created_at):
        raise ValueError("manifesto incompleto")
    if not isinstance(manifesto.pipeline_version, str) or not manifesto.pipeline_version:
        raise ValueError("versão de pipeline inválida")


def _manifesto_de_dict(dados: object) -> ResultManifest:
    if not isinstance(dados, dict):
        raise ValueError("manifesto inválido")
    try:
        stage_bruto = dados["stage_status"]
        if not isinstance(stage_bruto, dict):
            raise ValueError("estágio de manifesto inválido")
        manifesto = ResultManifest(
            meeting_id=dados["meeting_id"],
            schema_version=dados["schema_version"],
            source_audio_hashes=tuple(dados["source_audio_hashes"]),
            participants_ref=(
                _referencia_de_dict(dados["participants_ref"])
                if dados["participants_ref"] is not None
                else None
            ),
            segments_ref=_referencia_de_dict(dados["segments_ref"]),
            stage_status={
                chave: StageState(valor) for chave, valor in stage_bruto.items()
            },
            warnings=tuple(dados["warnings"]),
            exports=tuple(_referencia_de_dict(ref) for ref in dados["exports"]),
            created_at=dados["created_at"],
            pipeline_version=dados["pipeline_version"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("manifesto inválido") from exc
    _validar_estrutura(manifesto)
    return manifesto


def salvar_manifesto(caminho: Path, manifesto: ResultManifest) -> None:
    _validar_estrutura(manifesto)
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(
        prefix=f"{destino.stem}_", suffix=".tmp", dir=str(destino.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(_manifesto_para_dict(manifesto), arquivo, ensure_ascii=False, sort_keys=True)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario:
            try:
                Path(temporario).unlink(missing_ok=True)
            except OSError:
                pass


def carregar_manifesto(caminho: Path) -> ResultManifest:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return _manifesto_de_dict(dados)


def validar_manifesto(caminho: Path, raiz: Path) -> bool:
    """Verifica estrutura, paths confinados e integridade de todos os refs."""
    try:
        raiz_resolvida = Path(raiz).resolve(strict=True)
        caminho_resolvido = Path(caminho).resolve(strict=True)
        if not caminho_resolvido.is_file() or not caminho_resolvido.is_relative_to(
            raiz_resolvida
        ):
            return False
        manifesto = carregar_manifesto(caminho_resolvido)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    referencias: list[ArtifactRef] = [manifesto.segments_ref, *manifesto.exports]
    if manifesto.participants_ref is not None:
        referencias.append(manifesto.participants_ref)
    if not all(referencia_integra(referencia, raiz_resolvida) for referencia in referencias):
        return False
    if manifesto.segments_ref.format == "application/vnd.transkriptor.segments+json":
        try:
            carregar_segmentos(raiz_resolvida / manifesto.segments_ref.relative_path)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
    return True


def validar_manifesto_para_job(
    *,
    resultado: Path,
    manifesto: Path,
    fontes_audio: Sequence[Path],
    raiz: Path,
) -> str:
    """Vincula resultado/manifesto às fontes antes de o job ficar pronto."""
    raiz_resolvida = Path(raiz).resolve(strict=True)
    resultado_resolvido = Path(resultado).resolve(strict=True)
    manifesto_resolvido = Path(manifesto).resolve(strict=True)
    if (
        not resultado_resolvido.is_file()
        or not resultado_resolvido.is_relative_to(raiz_resolvida)
        or not manifesto_resolvido.is_file()
        or not manifesto_resolvido.is_relative_to(raiz_resolvida)
        or not validar_manifesto(manifesto_resolvido, raiz_resolvida)
    ):
        raise ValueError("manifesto de resultado inválido")
    resultado_manifesto = carregar_manifesto(manifesto_resolvido)
    if any(
        sha256_arquivo(Path(fonte).resolve(strict=True))
        not in resultado_manifesto.source_audio_hashes
        for fonte in fontes_audio
    ):
        raise ValueError("manifesto não corresponde ao áudio do job")
    relativo_resultado = resultado_resolvido.relative_to(raiz_resolvida).as_posix()
    referencias = [resultado_manifesto.segments_ref, *resultado_manifesto.exports]
    if not any(ref.relative_path == relativo_resultado for ref in referencias):
        raise ValueError("manifesto não referencia o resultado do job")
    return manifesto_resolvido.relative_to(raiz_resolvida).as_posix()


def _exportacao_tem_fala(caminho: Path) -> bool:
    """Reconhece a linha de ausência legada sem expor texto em logs."""
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.startswith("[") or "]" not in linha:
            continue
        conteudo = linha.split("]", 1)[1].strip()
        if conteudo and conteudo != "(nenhuma fala reconhecida)":
            return True
    return False


def criar_manifesto_inicial(
    *,
    meeting_id: str,
    resultado: Path,
    fontes_audio: Sequence[Path],
    raiz: Path,
    created_at: str | None = None,
) -> ResultManifest:
    """Representa o TXT legado como artefato rastreável até D7 estruturar segmentos."""
    resultado_resolvido = Path(resultado).resolve(strict=True)
    raiz_resolvida = Path(raiz).resolve(strict=True)
    referencia = criar_referencia(
        resultado_resolvido,
        raiz_resolvida,
        format="text/plain; charset=utf-8",
        schema_version=1,
    )
    tem_fala = _exportacao_tem_fala(resultado_resolvido)
    return ResultManifest(
        meeting_id=meeting_id,
        schema_version=VERSAO_MANIFESTO,
        source_audio_hashes=tuple(
            sha256_arquivo(Path(fonte).resolve(strict=True)) for fonte in fontes_audio
        ),
        participants_ref=None,
        segments_ref=referencia,
        stage_status={"stt": StageState.COMPLETE if tem_fala else StageState.PARTIAL},
        warnings=() if tem_fala else ("stt_sem_fala",),
        exports=(referencia,),
        created_at=created_at or _agora_utc(),
        pipeline_version=config.VERSAO,
    )


def criar_manifesto_estruturado(
    *, meeting_id: str, segmentos: Path, resultado: Path,
    fontes_audio: Sequence[Path], raiz: Path, warnings: Sequence[str] = (),
    diarizacao_solicitada: bool = False,
) -> ResultManifest:
    """Referencia o JSON canônico e seu TXT derivado, ambos já persistidos."""
    raiz = Path(raiz).resolve(strict=True)
    ref_json = criar_referencia(Path(segmentos), raiz, format="application/vnd.transkriptor.segments+json", schema_version=1)
    ref_txt = criar_referencia(Path(resultado), raiz, format="text/plain; charset=utf-8", schema_version=1)
    tem_segmentos = bool(carregar_segmentos(segmentos)["segmentos"])
    avisos = tuple(warnings) + (() if tem_segmentos else ("stt_sem_fala",))
    return ResultManifest(
        meeting_id=meeting_id,
        schema_version=VERSAO_MANIFESTO,
        source_audio_hashes=tuple(sha256_arquivo(Path(fonte).resolve(strict=True)) for fonte in fontes_audio),
        participants_ref=None,
        segments_ref=ref_json,
        stage_status={
            "stt": StageState.COMPLETE if tem_segmentos else StageState.PARTIAL,
            "diarizacao": (
                StageState.SKIPPED if not diarizacao_solicitada else
                StageState.PARTIAL if "diarizacao_falhou" in avisos or "segment_alignment_failed" in avisos else
                StageState.COMPLETE
            ),
        },
        warnings=avisos,
        exports=(ref_txt,),
        created_at=_agora_utc(),
        pipeline_version=config.VERSAO,
    )


def _manifesto_da_edicao(caminho_segmentos: Path):
    caminho_segmentos = Path(caminho_segmentos).resolve(strict=True)
    raiz = caminho_segmentos.parent.parent
    relativo = caminho_segmentos.relative_to(raiz).as_posix()
    encontrados = []
    for candidato in raiz.glob("*.resultado.json"):
        try:
            manifesto = carregar_manifesto(candidato)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if manifesto.segments_ref.relative_path == relativo and manifesto.segments_ref.format == "application/vnd.transkriptor.segments+json":
            encontrados.append((candidato, manifesto))
    if not encontrados:
        return None  # JSON avulso sem exportação vinculada
    if len(encontrados) != 1:
        raise ValueError("resultado associado a múltiplos manifestos")
    return encontrados[0]


def validar_exportacao_antes_edicao(caminho_segmentos: Path) -> None:
    encontrado = _manifesto_da_edicao(caminho_segmentos)
    if encontrado is None:
        return
    _caminho_manifesto, manifesto = encontrado
    raiz = Path(caminho_segmentos).resolve(strict=True).parent.parent
    refs_txt = [ref for ref in manifesto.exports if ref.format == "text/plain; charset=utf-8"]
    if (len(refs_txt) != 1 or not referencia_integra(refs_txt[0], raiz)
            or not referencia_integra(manifesto.segments_ref, raiz)):
        raise ValueError("TXT alterado fora da revisão; exportação preservada")


def atualizar_exportacao_apos_edicao(caminho_segmentos: Path) -> None:
    """Atualiza TXT e refs da reunião editada sem tocar exportação alheia."""
    encontrado = _manifesto_da_edicao(caminho_segmentos)
    if encontrado is None:
        return
    caminho_manifesto, manifesto = encontrado
    caminho_segmentos = Path(caminho_segmentos).resolve(strict=True)
    raiz = caminho_segmentos.parent.parent
    refs_txt = [ref for ref in manifesto.exports if ref.format == "text/plain; charset=utf-8"]
    if len(refs_txt) != 1 or not referencia_integra(refs_txt[0], raiz):
        raise ValueError("TXT alterado fora da revisão; exportação preservada")
    caminho_txt = (raiz / refs_txt[0].relative_path).resolve(strict=True)
    dados = carregar_segmentos(caminho_segmentos)
    texto = exportar_txt(dados["segmentos"], dados["mapeamento"])
    fd, temporario = tempfile.mkstemp(prefix=f"{caminho_txt.stem}_", suffix=".tmp", dir=str(caminho_txt.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho_txt)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)
    novo_json = criar_referencia(caminho_segmentos, raiz, format=manifesto.segments_ref.format, schema_version=manifesto.segments_ref.schema_version)
    novo_txt = criar_referencia(caminho_txt, raiz, format=refs_txt[0].format, schema_version=refs_txt[0].schema_version)
    exports = tuple(novo_txt if ref == refs_txt[0] else ref for ref in manifesto.exports)
    salvar_manifesto(caminho_manifesto, replace(manifesto, segments_ref=novo_json, exports=exports))


# Reexportações D7 (implementação em resultado_edicao para o limite de linhas).
from resultado_edicao import (
    NOME_PENDENTE,
    VERSAO_SEGMENTOS,
    SegmentoResultado,
    aplicar_correcao,
    carregar_segmentos,
    desfazer_correcao,
    exportar_txt,
    format_segment_txt,
    salvar_segmentos,
)


def resultado_global(manifesto: ResultManifest) -> str:
    """Estado global honesto: parcial nunca se apresenta como completo."""
    estados = {str(e.value if isinstance(e, StageState) else e) for e in manifesto.stage_status.values()}
    if not estados:
        return StageState.FAILED.value
    if estados == {"complete"}:
        return StageState.COMPLETE.value
    if "failed" in estados:
        return StageState.FAILED.value
    return StageState.PARTIAL.value
