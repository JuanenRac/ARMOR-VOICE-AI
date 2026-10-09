"""The voice gateway as a small local HTTP service.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

The same closed gateway as the JSON-lines one (gateway.py): a request is `{"text", "language"?, "confirmation"?}` and the answer says what was understood, whether it needs
a confirmation (a signed token to echo back) and what to say. This only decides - it understands a phrase and holds the two-turn confirmation of the sensitive ones; it
never arms anything itself: whoever calls it (ARMOR-SERVER) carries out what was accepted, with the session of the person who spoke.

It listens on the loopback address only (so nothing on the network can reach it), wants a token in `X-Armor-Voice-Token`, takes at most 2 KB, and answers JSON. A request that
is not valid is refused, never guessed at.

    python -m armor_voice_ai.service --port 18090 --token-file /opt/armor/etc/armor.voice.env
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .confirmation import ConfirmationSigner
from .gateway import MAX_LINE_BYTES, handle_request

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def make_server(host: str, port: int, token: str, signer: ConfirmationSigner, audit: Path | None = None) -> ThreadingHTTPServer:
    """A server that answers `POST /v1/command` and `GET /healthz`; call serve_forever() on it."""
    if len(token) < 16:
        raise ValueError("the token must be at least 16 characters")

    class Handler(BaseHTTPRequestHandler):
        server_version = "armor-voice"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:   # noqa: A002 - the name is the one of the base class
            return   # what was said is never written to a log

        def _send(self, status: int, payload: dict[str, object]) -> None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            sent = self.headers.get("X-Armor-Voice-Token", "")
            return hmac.compare_digest(sent.encode("utf-8"), token.encode("utf-8"))

        def do_GET(self) -> None:   # noqa: N802
            if self.path == "/healthz":
                return self._send(200, {"ok": True, "service": "armor-voice"})
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:   # noqa: N802
            if self.path != "/v1/command":
                return self._send(404, {"error": "not found"})
            if not self._authorized():
                return self._send(401, {"error": "unauthorized"})
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_LINE_BYTES:
                self.close_connection = True
                return self._send(413, {"accepted": False, "error": "line too long" if length > MAX_LINE_BYTES else "length required"})
            raw = self.rfile.read(length)
            try:
                request = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return self._send(400, {"accepted": False, "error": "invalid json"})
            self._send(200, handle_request(request, signer, audit))

    return ThreadingHTTPServer((host, port), Handler)


def _read_token(args: argparse.Namespace) -> str:
    if args.token_file:
        for line in Path(args.token_file).read_text(encoding="utf-8").splitlines():
            if line.startswith("ARMOR_VOICE_TOKEN="):
                return line.split("=", 1)[1].strip()
        raise SystemExit(f"{args.token_file} has no ARMOR_VOICE_TOKEN= line")
    return os.environ.get("ARMOR_VOICE_TOKEN", "")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="A.R.M.O.R. voice gateway as a local HTTP service")
    parser.add_argument("--host", default="127.0.0.1", help="the address to listen on (loopback only unless --allow-remote)")
    parser.add_argument("--port", type=int, default=18090)
    parser.add_argument("--token-file", type=Path, help="a file with a line ARMOR_VOICE_TOKEN=...; else the environment variable of the same name")
    parser.add_argument("--audit-file", type=Path, help="append one line per decision (no audio, no raw text)")
    parser.add_argument("--allow-remote", action="store_true", help="listen on a non-loopback address (not recommended)")
    args = parser.parse_args(argv)
    if args.host not in LOOPBACK and not args.allow_remote:
        raise SystemExit("refusing to listen on a non-loopback address without --allow-remote")
    token = _read_token(args)
    if len(token) < 16:
        raise SystemExit("a token of at least 16 characters is needed (ARMOR_VOICE_TOKEN)")
    server = make_server(args.host, args.port, token, ConfirmationSigner(), args.audit_file)
    print(f"armor-voice listening on {args.host}:{server.server_address[1]}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
