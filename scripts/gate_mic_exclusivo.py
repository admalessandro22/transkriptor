#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gate C2 — frase humana exclusiva no mic vs. loopback (DU-12, uso único autorizado).

Toca uma frase pelo alto-falante (loopback) enquanto o usuário fala outra
frase exclusiva no microfone. Transcreve as duas fontes com o Whisper real e
exige o texto das duas — não só energia RMS.
"""
from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

FRASE_LOOPBACK = (
    "Bom dia a todos. Esta é uma reunião de teste do Transkriptor. "
    "Vamos revisar o cronograma do projeto e definir os próximos passos."
)
FRASE_MIC = "A minha frase exclusiva do microfone e jabuticaba amarela noventa e tres"


def falar_loopback(frase: str, repeticoes: int) -> subprocess.Popen | None:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segundos", type=int, default=45)
    parser.add_argument("--manter", action="store_true")
    args = parser.parse_args(argv)

    pasta = Path(tempfile.mkdtemp(prefix="gate_mic_c2_"))
    print(f"Gate mic exclusivo — {args.segundos}s")
    print(f"Pasta: {pasta}")
    print(f"FRASE DO LOOPBACK (alto-falante): {FRASE_LOOPBACK}")
    print(f"SUA FRASE NO MICROFONE (fale alto, 3x quando pedido): {FRASE_MIC}\n")

    import config
    import transcricao_core

    audio = pasta / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    config.PASTA_TRANSCRICOES = str(pasta)
    config.PASTA_AUDIO = str(audio)
    transcricao_core.PASTA_AUDIO = str(audio)

    from transcricao_core import Transcritor

    status: list[str] = []
    t = Transcritor(
        modelo="auto",
        idioma="pt",
        pasta_saida=str(pasta),
        diarizar_ao_final=False,
        on_status=status.append,
        capturar_mic=True,
        identificar_voz=False,
        criptografar=False,
        processar_ao_vivo=False,
    )
    voz = falar_loopback(FRASE_LOOPBACK, max(1, args.segundos // 12))
    t.start()
    inicio = time.monotonic()
    marcas = {5: "(1/3) FALE AGORA no microfone!", 15: "(2/3) FALE AGORA!", 25: "(3/3) FALE AGORA!"}
    avisados = set()
    try:
        while time.monotonic() - inicio < args.segundos:
            time.sleep(0.5)
            decorrido = int(time.monotonic() - inicio)
            for marco, msg in marcas.items():
                if decorrido >= marco and marco not in avisados:
                    print(f"  [{decorrido}s] {msg} -> {FRASE_MIC}")
                    avisados.add(marco)
            if decorrido % 10 == 0:
                m = t.metricas_captura()
                print(f"  [{decorrido}s] frames={m['frames_gravados']:,}")
    finally:
        if voz is not None:
            with contextlib.suppress(Exception):
                voz.terminate()
    m = t.metricas_captura()
    print(f"Captura: frames={m['frames_gravados']:,} falhas={m['falhas_captura']}")
    caminho = t.stop()
    print(f"stop OK -> {caminho}")
    preservados = list(getattr(t, "audios_preservados", []) or [])
    caminho_mic = next(
        (a for a in preservados if str(a).endswith("_mic.wav")),
        getattr(t, "_caminho_wav_mic_salvo", None),
    )
    print(f"mic: {caminho_mic}")
    try:
        from audio_reader import AudioSource, iter_audio
        import numpy as np

        janelas = [
            float(np.sqrt((c.samples ** 2).mean())) if c.samples.size else 0.0
            for c in iter_audio(Path(str(caminho_mic)), AudioSource.MICROPHONE, 5.0)
        ]
        pico = max(janelas) if janelas else 0.0
        print(f"mic RMS por janela de 5s: {[round(v, 4) for v in janelas]}")
        print(f"mic pico RMS: {pico:.4f} (voz real costuma passar de 0.05)")
    except Exception as e:  # noqa: BLE001
        print(f"mic RMS indisponivel: {type(e).__name__}")

    from retranscritor import retranscrever

    saida = retranscrever(
        preservados[0] if preservados else str(caminho),
        caminho_mic=str(caminho_mic) if caminho_mic else None,
        pasta_saida=str(pasta),
        nome_base_saida="gate-mic-exclusivo",
        idioma="pt",
        diarizar=False,
    )
    texto = Path(saida).read_text(encoding="utf-8")
    print("---- TXT ----")
    print(texto)
    print("-------------")
    ok_mic = "jabuticaba" in texto.lower()
    ok_lb = "cronograma" in texto.lower() or "sexta" in texto.lower()
    print(f"[{'OK  ' if ok_mic else 'FALHA'}] frase exclusiva do mic (jabuticaba)")
    print(f"[{'OK  ' if ok_lb else 'FALHA'}] frase do loopback (cronograma/sexta)")
    if args.manter:
        print(f"Pasta preservada: {pasta}")
    else:
        shutil.rmtree(pasta, ignore_errors=True)
    if ok_mic and ok_lb:
        print("GATE MIC APROVADO")
        return 0
    print("GATE MIC REPROVADO")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
