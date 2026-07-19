#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI para transcrição de reuniões — wrapper fino sobre Transcritor."""
import argparse, os, time
import soundcard as sc
from config import MODELO_WHISPER, IDIOMA, CHUNK_SEGUNDOS, PASTA_TRANSCRICOES
from transcricao_core import Transcritor


def main():
    p = argparse.ArgumentParser(description="Transcreve audio de reunioes para .txt (offline, gratis).")
    p.add_argument("--modelo", default=MODELO_WHISPER, choices=["tiny", "base", "small", "medium", "large-v3"])
    p.add_argument("--idioma", default=IDIOMA, help="Use 'auto' para detectar.")
    p.add_argument("--chunk", type=float, default=CHUNK_SEGUNDOS)
    p.add_argument("--dispositivo", default="", help="Nome/id do alto-falante (loopback).")
    p.add_argument("--listar", action="store_true", help="Lista dispositivos de saida e sai.")
    args = p.parse_args()

    if args.listar:
        print("Dispositivos de saida de audio disponiveis:")
        for s in sc.all_speakers():
            marca = " (padrao)" if s == sc.default_speaker() else ""
            print(f"  - {s}{marca}")
        return

    on_status = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    t = Transcritor(modelo=args.modelo, idioma=args.idioma, pasta_saida=PASTA_TRANSCRICOES,
                    dispositivo=args.dispositivo, chunk=args.chunk, diarizar_ao_final=False, on_status=on_status)
    print("=" * 60, "\n  Transcritor de Reunioes - Whisper local\n", "=" * 60, sep="")
    print(f"Modelo: {args.modelo} | Idioma: {args.idioma} | Bloco: {args.chunk}s | Dispositivo: {args.dispositivo or '(padrao)'}")
    t.start()
    print("\n>>> Gravando. Ctrl+C para parar e salvar. <<<\n", flush=True)
    try:
        while t.rodando:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        caminho = t.stop()
        if caminho:
            print(f"\n[OK] Salvo em: {os.path.abspath(caminho)}")


if __name__ == "__main__":
    main()
