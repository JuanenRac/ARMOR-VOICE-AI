"""A Wyoming "handle" service over the closed list of commands, for Home Assistant's Assist.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Wyoming is the small protocol Home Assistant's voice assistant uses to talk to its parts: one JSON line per event (`type`, `data`, and optionally `data_length` and
`payload_length` for bytes that follow), over a TCP connection. This module answers the events of an intent handler:

    describe     ->  info         what this service is (one handler, the eight languages)
    transcript   ->  handled      the words were one of the QUERIES of the closed list and the server answered them; `text` is what to say
                     not-handled  the words were not understood, the server is not set up or did not answer

Nothing new is understood here: the words are given to the same `parse_intent` as everything else and only the commands that ASK (`intent.QUERIES`) go on to the server; a command
that DOES something (arm, disarm, silence, the lights) is never carried out from here, and the answer says to use the app or the panel. There is no token in the protocol, so it
listens on the loopback address only (unless `--allow-remote`) and it is OFF unless `ARMOR_VOICE_WYOMING=on`: an installation that wants Assist on another machine puts its own tunnel
in front. Audio is not accepted (a payload is read and thrown away up to a limit); what was said is never written to a log.

    ARMOR_VOICE_WYOMING=on python -m armor_voice_ai.wyoming --port 10400
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socketserver
import threading
from collections.abc import Callable

from .gateway import SPEECH_BY_LANGUAGE
from .intent import MAX_TEXT_LENGTH, QUERIES, RISK, parse_intent
from .turn import ServerLink, TurnError

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
DEFAULT_PORT = 10400
MAX_HEADER_BYTES = 4096        # one event line
MAX_DATA_BYTES = 8192          # the extra JSON that may follow the header
MAX_PAYLOAD_BYTES = 65_536     # bytes that follow; never used, read and dropped
MAX_EVENTS_PER_CONNECTION = 50
CONNECTION_TIMEOUT_S = 15.0
MAX_CONNECTIONS = 4
LANGUAGES = tuple(SPEECH_BY_LANGUAGE)

# What is said when the answer is not the server's own, in the eight languages (Portuguese of Portugal).
NOT_UNDERSTOOD = {"en": "I did not understand that.", "es": "No lo he entendido.", "de": "Das habe ich nicht verstanden.", "fr": "Je n'ai pas compris.", "it": "Non ho capito.",
                  "ja": "理解できませんでした。", "zh": "没有听懂。", "pt": "Não percebi."}
ACTION_REFUSED = {"en": "I only answer questions here: do that in the app or on the panel.", "es": "Aquí solo respondo preguntas: hazlo en la app o en el panel.",
                  "de": "Hier beantworte ich nur Fragen: mach das in der App oder am Panel.", "fr": "Ici je réponds seulement aux questions : fais-le dans l'application ou sur le panneau.",
                  "it": "Qui rispondo solo alle domande: fallo nell'app o sul pannello.", "ja": "ここでは質問にだけ答えます。アプリかパネルで操作してください。",
                  "zh": "这里只回答问题：请在应用或面板上操作。", "pt": "Aqui só respondo a perguntas: faça-o na aplicação ou no painel."}
SERVER_UNAVAILABLE = {"en": "The house does not answer right now.", "es": "La casa no responde ahora mismo.", "de": "Das Haus antwortet gerade nicht.", "fr": "La maison ne répond pas pour le moment.",
                      "it": "La casa non risponde in questo momento.", "ja": "今は家から応答がありません。", "zh": "家里暂时没有回应。", "pt": "A casa não responde neste momento."}

Event = tuple[str, dict[str, object]]
Ask = Callable[[str, str, str | None], dict[str, object]]


class WyomingError(Exception):
    """An event that cannot be read: the connection is closed."""


def read_event(stream: io.BufferedIOBase) -> Event | None:
    """The next event of a connection, or None at its end. A payload that follows is read and dropped; an event that is too long or not JSON raises WyomingError."""
    line = stream.readline(MAX_HEADER_BYTES + 1)
    if not line:
        return None
    if len(line) > MAX_HEADER_BYTES or not line.endswith(b"\n"):
        raise WyomingError("header too long")
    try:
        header = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise WyomingError("header is not JSON") from error
    if not isinstance(header, dict) or not isinstance(header.get("type"), str):
        raise WyomingError("header has no type")
    data = header.get("data", {})
    if not isinstance(data, dict):
        raise WyomingError("data is not an object")
    data_length, payload_length = header.get("data_length", 0), header.get("payload_length", 0)
    if not isinstance(data_length, int) or isinstance(data_length, bool) or not 0 <= data_length <= MAX_DATA_BYTES:
        raise WyomingError("bad data_length")
    if not isinstance(payload_length, int) or isinstance(payload_length, bool) or not 0 <= payload_length <= MAX_PAYLOAD_BYTES:
        raise WyomingError("bad payload_length")
    if data_length:
        raw = stream.read(data_length)
        if len(raw) != data_length:
            raise WyomingError("data cut short")
        try:
            extra = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise WyomingError("data is not JSON") from error
        if not isinstance(extra, dict):
            raise WyomingError("data is not an object")
        data = {**data, **extra}
    if payload_length and len(stream.read(payload_length)) != payload_length:
        raise WyomingError("payload cut short")
    return header["type"], data


def write_event(stream: io.BufferedIOBase, event_type: str, data: dict[str, object] | None = None) -> None:
    """One event as a header line; the data travels inside it."""
    body: dict[str, object] = {"type": event_type}
    if data:
        body["data"] = data
    stream.write(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")
    stream.flush()


def info_data(version: str) -> dict[str, object]:
    """What `describe` is answered with: one handler, the eight languages."""
    attribution = {"name": "A.R.M.O.R.", "url": ""}
    return {"handle": [{"name": "armor-voice", "description": "Questions to the A.R.M.O.R. house, from a closed list", "attribution": attribution, "installed": True, "version": version,
                        "models": [{"name": "armor-closed-queries", "description": "The questions of the closed list of commands", "attribution": attribution, "installed": True,
                                    "languages": list(LANGUAGES), "version": version}]}]}


class Handler:
    """What the service does with one event; no sockets, so it is tried without a network."""

    def __init__(self, ask: Ask | None, default_language: str = "en", version: str = "0") -> None:
        self._ask = ask
        self._language = default_language if default_language in SPEECH_BY_LANGUAGE else "en"
        self._version = version

    def language_of(self, data: dict[str, object]) -> str:
        value = data.get("language")
        if isinstance(value, str):
            code = value.lower().replace("_", "-").split("-")[0]   # "pt-PT", "es_ES"
            if code in SPEECH_BY_LANGUAGE:
                return code
        return self._language

    def handle(self, event: Event) -> list[Event]:
        event_type, data = event
        if event_type == "describe":
            return [("info", info_data(self._version))]
        if event_type != "transcript":
            return []   # events of other kinds (ping, audio) are not for a handler
        language = self.language_of(data)
        text = data.get("text")
        if not isinstance(text, str) or len(text) > MAX_TEXT_LENGTH:
            return [("not-handled", {"text": NOT_UNDERSTOOD[language]})]
        intent = parse_intent(text)
        if intent is None:
            return [("not-handled", {"text": NOT_UNDERSTOOD[language]})]
        if intent not in QUERIES or RISK[intent].kind != "query":
            return [("handled", {"text": ACTION_REFUSED[language]})]   # never carried out from here
        if self._ask is None:
            return [("not-handled", {"text": SERVER_UNAVAILABLE[language]})]
        try:
            answer = self._ask(text, language, None)
        except (TurnError, OSError, ValueError):
            return [("not-handled", {"text": SERVER_UNAVAILABLE[language]})]
        speech = answer.get("speech") if isinstance(answer, dict) else None
        if not isinstance(speech, str) or not speech.strip():
            return [("not-handled", {"text": NOT_UNDERSTOOD[language]})]
        return [("handled", {"text": speech[:300]})]


def make_server(host: str, port: int, handler: Handler, allow_remote: bool = False) -> socketserver.ThreadingTCPServer:
    """A server for the events; call serve_forever() on it. A non-loopback address is refused unless it is allowed."""
    if host not in LOOPBACK and not allow_remote:
        raise ValueError("the Wyoming service listens on the loopback address only")
    slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    class Connection(socketserver.StreamRequestHandler):
        timeout = CONNECTION_TIMEOUT_S

        def handle(self) -> None:
            if not slots.acquire(blocking=False):
                return   # too many connections: this one is closed
            try:
                for _ in range(MAX_EVENTS_PER_CONNECTION):
                    try:
                        event = read_event(self.rfile)
                    except (WyomingError, OSError):
                        return
                    if event is None:
                        return
                    for kind, data in handler.handle(event):
                        write_event(self.wfile, kind, data)
            finally:
                slots.release()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    return Server((host, port), Connection)


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("armor-voice-ai")
    except Exception:  # noqa: BLE001 - a checkout that is not installed has no version to tell
        return "0"


def main() -> None:
    parser = argparse.ArgumentParser(description="A.R.M.O.R. voice: a Wyoming handler for Home Assistant's Assist (off unless ARMOR_VOICE_WYOMING=on)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--language", default="en", help="the language used when the event does not say one")
    parser.add_argument("--allow-remote", action="store_true", help="listen on a non-loopback address (the protocol has no token: not recommended)")
    args = parser.parse_args()
    if os.environ.get("ARMOR_VOICE_WYOMING", "").strip().lower() != "on":
        raise SystemExit("the Wyoming service is off: set ARMOR_VOICE_WYOMING=on to start it")
    url, token = os.environ.get("ARMOR_VOICE_SERVER_URL", ""), os.environ.get("ARMOR_VOICE_SERVER_TOKEN", "")
    ask = ServerLink(url, token).command if url and token else None
    server = make_server(args.host, args.port, Handler(ask, args.language, _version()), args.allow_remote)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
