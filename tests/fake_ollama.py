# -*- coding: utf-8 -*-
"""Servidor Ollama falso em thread (NFR-4.1)."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class FakeOllama:
    def __init__(
        self,
        modelos: list[str] | None = None,
        context_length: int = 8192,
        chat_reply: str = "resposta fake",
    ):
        self.modelos = modelos or ["llama-fake"]
        self.context_length = context_length
        self.chat_reply = chat_reply
        self.requests: list[dict[str, Any]] = []
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.url = ""

    def start(self) -> str:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _read_json(self):
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0:
                    return {}
                return json.loads(self.rfile.read(n).decode("utf-8"))

            def do_GET(self):
                parent.requests.append({"method": "GET", "path": self.path})
                if self.path.startswith("/api/tags"):
                    body = {
                        "models": [{"name": m} for m in parent.modelos],
                    }
                    self._json(200, body)
                elif self.path.startswith("/api/show"):
                    self._json(
                        200,
                        {
                            "model_info": {
                                "llama.context_length": parent.context_length,
                            },
                            "parameters": f"num_ctx {parent.context_length}",
                        },
                    )
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self):
                dados = self._read_json()
                parent.requests.append(
                    {"method": "POST", "path": self.path, "body": dados}
                )
                if self.path.startswith("/api/show"):
                    self._json(
                        200,
                        {
                            "model_info": {
                                "general.architecture": "llama",
                                "llama.context_length": parent.context_length,
                            },
                            "parameters": f"num_ctx {parent.context_length}",
                        },
                    )
                    return
                if self.path.startswith("/api/chat"):
                    # NDJSON stream
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson")
                    self.end_headers()
                    chunk = {
                        "message": {"role": "assistant", "content": parent.chat_reply},
                        "done": False,
                    }
                    self.wfile.write((json.dumps(chunk) + "\n").encode("utf-8"))
                    done = {
                        "message": {"role": "assistant", "content": ""},
                        "done": True,
                    }
                    self.wfile.write((json.dumps(done) + "\n").encode("utf-8"))
                    return
                self._json(404, {"error": "not found"})

            def _json(self, code, obj):
                raw = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        port = self._httpd.server_address[1]
        self.url = f"http://127.0.0.1:{port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
