#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gate NFR-10.C2 — uma reunião de verdade, do alto-falante ao `.txt`.

Nenhum dublê. Toca fala pelo alto-falante, captura pelo loopback com o
`Transcritor` real, encerra, enfileira e roda o Whisper de verdade até sair um
`.txt` legível. É o gate que faltava: em 2026-08-07, 380 testes passavam com o
produto incapaz de gravar um único frame.

    python scripts/gate_reuniao_real.py                  # ~25 s, modelo auto
    python scripts/gate_reuniao_real.py --segundos 600   # gate longo (10 min)
    python scripts/gate_reuniao_real.py --sem-audio      # já tem WAV, só o resto

Escreve tudo numa pasta temporária: não toca nas transcrições do usuário.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

FRASE = (
    "Bom dia a todos. Esta é uma reunião de teste do Transkriptor. "
    "Vamos revisar o cronograma do projeto e definir os próximos passos. "
    "O relatório final fica pronto na sexta-feira."
)

OK, FALHA = "OK  ", "FALHA"
_resultados: list[tuple[str, bool, str]] = []


def etapa(nome: str, ok: bool, detalhe: str = "") -> bool:
    _resultados.append((nome, ok, detalhe))
    print(f"[{OK if ok else FALHA}] {nome}" + (f" — {detalhe}" if detalhe else ""))
    return ok


def falar_em_voz_alta(frase: str, repeticoes: int) -> subprocess.Popen | None:
    """Toca fala pelo alto-falante padrão — é o que o loopback vai capturar."""
    texto = " ".join([frase] * repeticoes).replace("'", "")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "try { $s.SelectVoice('Microsoft Maria') } catch {} "
        "$s.Rate = 0; "
        f"$s.Speak('{texto}')"
    )
    try:
        return subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:  # noqa: BLE001
        print(f"  (sem TTS: {e})")
        return None


def checar_loopback() -> bool:
    from audio_utils import testar_loopback

    resultado = testar_loopback()
    return etapa(
        "Loopback do sistema disponível",
        bool(resultado.get("ok")),
        str(resultado.get("dispositivo") or resultado.get("motivo") or ""),
    )


def isolar_pastas(pasta: Path) -> None:
    """Mantém o gate fora das transcrições do usuário.

    `Transcritor._preservar_audios` move o WAV para `transcricao_core.PASTA_AUDIO`
    — reexportado justamente para ser trocado assim. Sem isto, o gate deposita
    áudio de teste na pasta real e a fila recusa o arquivo por estar fora dela.
    """
    import config
    import transcricao_core

    audio = pasta / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    config.PASTA_TRANSCRICOES = str(pasta)
    config.PASTA_AUDIO = str(audio)
    transcricao_core.PASTA_AUDIO = str(audio)


def gravar_reuniao(pasta: Path, segundos: int, modelo: str, com_audio: bool):
    """Roda o Transcritor real pelo tempo pedido e devolve (caminho_saida, wav)."""
    from transcricao_core import Transcritor

    status: list[str] = []
    transcritor = Transcritor(
        modelo=modelo,
        idioma="pt",
        pasta_saida=str(pasta),
        diarizar_ao_final=False,
        on_status=status.append,
        capturar_mic=False,
        identificar_voz=False,
        criptografar=False,
        processar_ao_vivo=False,  # é assim que o app grava reuniões (FR-10.C1)
    )

    voz = falar_em_voz_alta(FRASE, max(1, segundos // 12)) if com_audio else None
    inicio = time.monotonic()
    transcritor.start()
    etapa("Captura iniciada sem travar", True, f"{time.monotonic() - inicio:.1f}s")

    try:
        while time.monotonic() - inicio < segundos:
            time.sleep(1.0)
            metricas = transcritor.metricas_captura()
            if metricas["frames_gravados"] and int(time.monotonic() - inicio) % 5 == 0:
                print(
                    f"      {int(time.monotonic() - inicio):3d}s "
                    f"frames={metricas['frames_gravados']:,} "
                    f"falhas={metricas['falhas_captura']}"
                )
    finally:
        if voz is not None:
            with contextlib.suppress(Exception):
                voz.terminate()

    metricas = transcritor.metricas_captura()
    etapa(
        "Áudio realmente capturado",
        metricas["frames_gravados"] > 0,
        f"{metricas['frames_gravados']:,} frames, "
        f"{metricas['falhas_captura']} falha(s) de captura",
    )

    inicio_stop = time.monotonic()
    caminho = transcritor.stop()
    etapa("stop() retornou sem travar", True, f"{time.monotonic() - inicio_stop:.1f}s")
    return caminho, list(transcritor.audios_preservados)


def checar_wav(caminhos: list[str]) -> str | None:
    principal = next((c for c in caminhos if not c.endswith("_mic.wav")), None)
    if not etapa("WAV preservado", bool(principal), principal or "nenhum"):
        return None
    tamanho = os.path.getsize(principal)
    if not etapa("WAV não está vazio", tamanho > 1024, f"{tamanho:,} bytes"):
        return None
    try:
        with wave.open(principal, "rb") as w:
            quadros, taxa = w.getnframes(), w.getframerate()
        etapa(
            "Header do WAV válido",
            quadros > 0,
            f"{quadros / taxa:.1f}s a {taxa} Hz",
        )
    except Exception as e:  # noqa: BLE001
        etapa("Header do WAV válido", False, str(e))
        return None
    return principal


def processar(pasta: Path, wav: str, mic: str | None, base: str) -> Path | None:
    from fila_processamento import FilaProcessamento
    from processador_reuniao import processar_job

    fila = FilaProcessamento(str(pasta))
    job_id = fila.enfileirar(
        wav, mic, base, {"origem": "gate", "diarizar": False, "idioma": "pt"}
    )
    etapa("Job enfileirado", fila.obter(job_id).estado == "pending", job_id)

    inicio = time.monotonic()
    try:
        resultado = processar_job(job_id, fila=fila)
    except Exception as e:  # noqa: BLE001
        etapa("Whisper processou o job", False, f"{type(e).__name__}: {e}")
        return None
    etapa(
        "Whisper processou o job",
        fila.obter(job_id).estado == "ready",
        f"{time.monotonic() - inicio:.0f}s",
    )
    return Path(resultado)


def checar_texto(caminho: Path | None) -> bool:
    if not etapa("Transcrição .txt criada", bool(caminho and caminho.is_file()),
                 str(caminho or "")):
        return False
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    corpo = [
        linha
        for linha in texto.splitlines()
        if linha.strip() and not linha.startswith("===")
    ]
    etapa("Transcrição tem conteúdo", bool(corpo), f"{len(corpo)} linha(s)")
    print("\n----- transcrição -----")
    print(texto.strip()[:1200])
    print("-----------------------\n")
    return bool(corpo)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segundos", type=int, default=25)
    parser.add_argument("--modelo", default="auto")
    parser.add_argument("--sem-audio", action="store_true")
    parser.add_argument("--manter", action="store_true", help="não apagar a pasta")
    args = parser.parse_args(argv)

    pasta = Path(tempfile.mkdtemp(prefix="gate_transkriptor_"))
    print(f"Gate de reunião real — {args.segundos}s, modelo {args.modelo}")
    print(f"Pasta de trabalho: {pasta}\n")

    try:
        isolar_pastas(pasta)
        checar_loopback()
        caminho_saida, audios = gravar_reuniao(
            pasta, args.segundos, args.modelo, not args.sem_audio
        )
        wav = checar_wav(audios)
        if wav:
            mic = next((c for c in audios if c.endswith("_mic.wav")), None)
            base = Path(caminho_saida or wav).stem.replace("_audio", "")
            checar_texto(processar(pasta, wav, mic, base))
    finally:
        if args.manter:
            print(f"Pasta preservada: {pasta}")
        else:
            shutil.rmtree(pasta, ignore_errors=True)

    falhas = [n for n, ok, _ in _resultados if not ok]
    print("=" * 60)
    if falhas:
        print(f"GATE REPROVADO — {len(falhas)} etapa(s): {', '.join(falhas)}")
        return 1
    print(f"GATE APROVADO — {len(_resultados)} etapas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
