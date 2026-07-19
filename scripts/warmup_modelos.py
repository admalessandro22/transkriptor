# -*- coding: utf-8 -*-
"""Warm-up opcional de modelos Whisper e ECAPA (FR-7.4)."""
from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("warmup")


def main():
    try:
        from config import MODELO_WHISPER, MODELO_VOZ_FONTE, resolver_device_whisper, DEVICE_WHISPER
        from config import resolver_modelo_whisper  # type: ignore
    except Exception:
        resolver_modelo_whisper = None

    try:
        import torch

        tem_cuda = torch.cuda.is_available()
        vram = 0.0
        if tem_cuda:
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    except Exception:
        tem_cuda = False
        vram = 0.0

    if resolver_modelo_whisper:
        modelo, device, ctype = resolver_modelo_whisper(tem_cuda, vram)
    else:
        modelo, device, ctype = "small" if not tem_cuda else "medium", (
            "cuda" if tem_cuda else "cpu"
        ), "int8"

    log.info("Baixando Whisper %s (%s, %s)...", modelo, device, ctype)
    try:
        from faster_whisper import WhisperModel

        WhisperModel(modelo, device=device, compute_type=ctype)
        log.info("Whisper pronto.")
    except Exception as e:
        log.warning("Whisper warm-up falhou: %s — tentando small/cpu", e)
        try:
            from faster_whisper import WhisperModel

            WhisperModel("small", device="cpu", compute_type="int8")
        except Exception as e2:
            log.error("Falha Whisper: %s", e2)
            return 1

    log.info("Baixando encoder de voz %s...", MODELO_VOZ_FONTE if "MODELO_VOZ_FONTE" in dir() else "ECAPA")
    try:
        from speechbrain.inference.speaker import EncoderClassifier
        from config import MODELO_VOZ_FONTE, DIR_MODELO_VOZ
        import os

        os.makedirs(DIR_MODELO_VOZ, exist_ok=True)
        EncoderClassifier.from_hparams(
            source=MODELO_VOZ_FONTE,
            savedir=DIR_MODELO_VOZ,
            run_opts={"device": "cpu"},
        )
        log.info("Encoder de voz pronto.")
    except Exception as e:
        log.warning("Warm-up de voz opcional falhou: %s", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
