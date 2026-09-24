# -*- coding: utf-8 -*-
"""Sobe o Flask real da Central em 127.0.0.1 para a medição de primeira renderização (T-14.F2).

    TRANSKRIPTOR_TOKEN=<token> python docs/sdd/v1.9/evidencias/T-14.F2/servidor_medicao.py <porta>

Não abre navegador, não registra bandeja (APIs de estado/config respondem 503,
como numa Central aberta sem o app) e liga a galeria. Encerra com Ctrl+C/kill.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
os.environ.setdefault("TRANSKRIPTOR_GALERIA", "1")

import assistente  # noqa: E402

if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5077
    print(f"pronto em http://127.0.0.1:{porta}", flush=True)
    assistente.app.run(host="127.0.0.1", port=porta, debug=False, use_reloader=False, threaded=True)
