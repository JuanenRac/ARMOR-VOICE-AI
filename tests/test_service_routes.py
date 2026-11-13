"""The routes of the HTTP service that the happy path does not reach: a header that is not a number, a body that is shorter than it promised, a service that is busy, the speech and wake
routes with and without their engines, and the start-up checks of the settings (the check of the engines, a wrong PIN, a wake word that cannot start)."""
import contextlib
import io
import json
import os
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loopback_engine
from armor_voice_ai import service, wakeword
from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.turn import MAX_AUDIO_BYTES, MAX_SPEAK_CHARS, CommandEngine, TurnService, pcm_from_wav
from armor_voice_ai.wakeword import MAX_CHUNK_BYTES, WakeService, parse_words

TOKEN = "t" * 24
ENGINE = str(Path(loopback_engine.__file__).resolve())
AUDIO = "audio/L16;rate=16000"


def frames(count: int) -> bytes:
    return struct.pack("<h", 100) * (wakeword.FRAME_SAMPLES * count)


class Quiet:
    """A detector that never hears the word."""

    def predict(self, frame, model):
        return 0.0


def raw(port: int, path: str, headers: dict[str, str], body: bytes = b"", method: str = "POST", half_close: bool = False) -> tuple[int, dict]:
    """One request written by hand, so that a header can be wrong and a body can be shorter than the length it promised."""
    lines = [f"{method} {path} HTTP/1.1", "Host: 127.0.0.1", "Connection: close", *(f"{key}: {value}" for key, value in headers.items())]
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body)
        if half_close:
            connection.shutdown(socket.SHUT_WR)
        reply = b""
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                break
            reply += chunk
    head, _, payload = reply.partition(b"\r\n\r\n")
    return int(head.split(b" ")[1]), (json.loads(payload) if payload else {})


class Running:
    def __init__(self, test: unittest.TestCase, turns=None, wake=None):
        self.server = service.make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), None, turns, None, wake)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        test.addCleanup(self.server.server_close)
        test.addCleanup(self.server.shutdown)

    def post(self, path, headers=None, body=b"", **extra):
        return raw(self.port, path, {"X-Armor-Voice-Token": TOKEN, "Content-Length": str(len(body)), **(headers or {})}, body, **extra)


def engines() -> TurnService:
    return TurnService(CommandEngine([sys.executable, ENGINE, "stt"]), CommandEngine([sys.executable, ENGINE, "tts"]), lambda *args: {"speech": "ok"})


class WithoutEnginesTests(unittest.TestCase):
    def setUp(self):
        self.running = Running(self)

    def test_an_unknown_path_is_not_found_for_a_reader_too(self):
        self.assertEqual(raw(self.running.port, "/nope", {}, method="GET"), (404, {"error": "not found"}))

    def test_a_turn_with_a_wrong_language_is_refused_and_without_an_engine_it_is_not_available(self):
        self.assertEqual(self.running.post("/v1/turn", {"X-Armor-Language": "xx"})[0], 422)
        self.assertEqual(self.running.post("/v1/turn", {"Content-Type": AUDIO}, b"\x00\x00"), (501, {"error": "stt_unavailable"}))

    def test_speaking_and_the_wake_word_are_not_available_without_their_parts(self):
        self.assertEqual(self.running.post("/v1/speak", {}, b"{}"), (501, {"error": "tts_unavailable"}))
        self.assertEqual(self.running.post("/v1/wake", {"Content-Type": AUDIO}, frames(1)), (403, {"error": "wake_disabled"}))

    def test_a_command_with_a_length_that_is_not_a_number_is_a_missing_length(self):
        status, body = self.running.post("/v1/command", {"Content-Type": "application/json", "Content-Length": "abc"})
        self.assertEqual((status, body["error"]), (411, "length required"))


class EnginesTests(unittest.TestCase):
    def setUp(self):
        self.running = Running(self, engines())

    def test_a_turn_is_refused_for_the_wrong_kind_of_audio_a_missing_length_and_a_length_that_is_not_a_number(self):
        self.assertEqual(self.running.post("/v1/turn", {"Content-Type": "application/json"}, b"x")[0], 415)
        self.assertEqual(self.running.post("/v1/turn", {"Content-Type": AUDIO, "Content-Length": "abc"})[0], 411)
        self.assertEqual(self.running.post("/v1/turn", {"Content-Type": AUDIO}, b"")[0], 411)

    def test_a_body_that_never_arrives_is_thrown_away_without_waiting_and_the_refusal_says_why(self):
        # it promised more than the limit and sent a few bytes, then closed its side: the service reads what there is, finds nothing more and answers 413
        status, body = self.running.post("/v1/turn", {"Content-Type": AUDIO, "Content-Length": str(MAX_AUDIO_BYTES + 1)}, b"\x00" * 10, half_close=True)
        self.assertEqual((status, body), (413, {"error": "bad audio length"}))

    def test_a_connection_that_breaks_while_the_refused_body_is_read_does_not_stop_the_service(self):
        with mock.patch.object(self.running.server, "handle_error"):
            with socket.create_connection(("127.0.0.1", self.running.port), timeout=5) as connection:
                head = f"POST /v1/turn HTTP/1.1\r\nHost: x\r\nX-Armor-Voice-Token: {TOKEN}\r\nContent-Type: {AUDIO}\r\nContent-Length: {MAX_AUDIO_BYTES + 1}\r\n\r\n"
                connection.sendall(head.encode("ascii") + b"\x00" * 10)
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))   # closing now resets the connection
            self.assertEqual(raw(self.running.port, "/healthz", {}, method="GET")[0], 200)

    def test_a_whole_turn_over_http_hears_and_answers_with_the_policy_of_the_server(self):
        pcm = pcm_from_wav(loopback_engine.encode("status"))
        status, body = self.running.post("/v1/turn", {"Content-Type": AUDIO, "X-Armor-Language": "en", "X-Armor-Client": "panel-1", "X-Armor-Panel": "p", "X-Armor-Policy": '{"silence_confirmation": "off"}'}, pcm)
        self.assertEqual(status, 200)
        self.assertEqual(body["heard"], "status")

    def test_speaking_refuses_what_is_not_a_sentence_with_its_language_and_says_it_otherwise(self):
        post = self.running.post
        self.assertEqual(post("/v1/speak", {"Content-Length": "abc"})[0], 411)
        self.assertEqual(post("/v1/speak", {}, b"")[0], 411)
        status, _ = post("/v1/speak", {"Content-Length": str(MAX_SPEAK_CHARS * 4 + 201)}, b"", half_close=True)
        self.assertEqual(status, 413)
        self.assertEqual(post("/v1/speak", {}, b"not json")[1], {"error": "invalid json"})
        self.assertEqual(post("/v1/speak", {}, b"\xff\xfe")[1], {"error": "invalid json"})
        for shape in ({"text": "hi"}, {"text": 5, "language": "en"}, {"text": "hi", "language": "xx"}, {"text": "hi", "language": "en", "x": 1}, ["a"]):
            self.assertEqual(post("/v1/speak", {}, json.dumps(shape).encode())[1], {"error": "invalid request shape"}, shape)
        status, body = post("/v1/speak", {}, json.dumps({"text": "The system is armed.", "language": "en"}).encode())
        self.assertEqual(status, 200)
        self.assertTrue(body["audio"])

    def test_a_service_that_is_already_speaking_twice_says_busy_instead_of_starting_a_third_program(self):
        class Full:
            def acquire(self, blocking=False):
                return False

            def release(self):
                raise AssertionError("nothing was taken")

        with mock.patch.object(threading, "BoundedSemaphore", return_value=Full()):
            busy = Running(self, engines())
        self.assertEqual(busy.post("/v1/turn", {"Content-Type": AUDIO}, b"\x00\x00" * 10), (503, {"error": "busy"}))
        self.assertEqual(busy.post("/v1/speak", {}, json.dumps({"text": "hi", "language": "en"}).encode()), (503, {"error": "busy"}))


class WakeRouteTests(unittest.TestCase):
    def setUp(self):
        self.running = Running(self, None, WakeService(Quiet(), parse_words(None, generic=False)))

    def test_a_chunk_is_listened_to_and_every_wrong_request_is_named(self):
        post = self.running.post
        status, body = post("/v1/wake", {"Content-Type": AUDIO, "X-Armor-Language": "en", "X-Armor-Client": "p"}, frames(2))
        self.assertEqual((status, body["wake"]), (200, False))
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO, "X-Armor-Language": "xx"}, frames(1))[0], 422)
        self.assertEqual(post("/v1/wake", {"Content-Type": "text/plain"}, frames(1))[0], 415)
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO, "Content-Length": "abc"})[0], 411)
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO}, b"")[0], 411)
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO, "Content-Length": str(MAX_CHUNK_BYTES + 1)}, b"", half_close=True)[0], 413)
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO, "X-Armor-Language": "fr"}, frames(1)), (422, {"error": "no_wake_word_for_language"}))
        self.assertEqual(post("/v1/wake", {"Content-Type": AUDIO}, b"\x00" * 3), (422, {"error": "bad_audio_chunk"}))
        self.assertEqual(raw(self.running.port, "/v1/wake", {"Content-Type": AUDIO, "Content-Length": "2"}, b"\x00\x00")[0], 401)


class StartUpTests(unittest.TestCase):
    def run_main(self, env: dict[str, str], *arguments: str) -> tuple[int | str | None, str]:
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                service.main(list(arguments))
            except SystemExit as stop:
                return stop.code, out.getvalue()
        return None, out.getvalue()

    def clean(self, **extra: str) -> dict[str, str]:
        base = {key: "" for key in ("ARMOR_VOICE_STT_COMMAND", "ARMOR_VOICE_TTS_COMMAND", "ARMOR_VOICE_SILENCE_PIN", "ARMOR_WAKE_WORD", "ARMOR_WAKE_MODELS", "ARMOR_WAKE_CONFIG", "ARMOR_VOICE_SERVER_URL", "ARMOR_VOICE_SERVER_TOKEN")}
        return {**base, "ARMOR_VOICE_TOKEN": TOKEN, **extra}

    def test_checking_the_engines_prints_the_report_and_stops_with_the_verdict(self):
        working = self.clean(ARMOR_VOICE_STT_COMMAND=f'"{sys.executable}" "{ENGINE}" stt', ARMOR_VOICE_TTS_COMMAND=f'"{sys.executable}" "{ENGINE}" tts')
        code, printed = self.run_main(working, "--check-engines")
        self.assertEqual(code, 0)
        self.assertEqual([row["engine"] for row in json.loads(printed)], ["stt", "tts"])
        code, printed = self.run_main(self.clean(), "--check-engines")
        self.assertEqual(code, 1)
        self.assertNotIn(sys.executable, printed)

    def test_a_pin_that_is_not_digits_stops_the_start_without_printing_it(self):
        code, _ = self.run_main(self.clean(ARMOR_VOICE_SILENCE_PIN="abc-secret"), "--port", "0")
        self.assertIn("ARMOR_VOICE_SILENCE_PIN is not valid", str(code))
        self.assertNotIn("abc-secret", str(code))

    def test_a_wake_word_that_cannot_start_stops_the_start_and_one_that_can_is_given_to_the_server(self):
        with tempfile_json({"en": {"phrase": "hey armor", "model": "m.onnx", "threshold": 0.6}}) as good, tempfile_text("not json") as bad:
            code, _ = self.run_main(self.clean(ARMOR_WAKE_WORD="on", ARMOR_WAKE_CONFIG=bad), "--port", "0")
            self.assertIn("the wake word cannot start", str(code))
            started = mock.Mock()
            started.server_address = ("127.0.0.1", 1)
            started.serve_forever.side_effect = KeyboardInterrupt
            detector = mock.Mock()
            with mock.patch.object(service, "OpenWakeWordDetector", detector), mock.patch.object(service, "make_server", return_value=started) as made:
                with self.assertRaises(KeyboardInterrupt):
                    self.run_main(self.clean(ARMOR_WAKE_WORD="ON", ARMOR_WAKE_CONFIG=good, ARMOR_WAKE_MODELS=str(Path(good).parent)), "--port", "0")
            self.assertIsInstance(made.call_args.args[-1], WakeService)
            detector.assert_called_once()


@contextlib.contextmanager
def tempfile_text(content: str):
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "wake.json"
        path.write_text(content, encoding="utf-8")
        yield str(path)


def tempfile_json(content: dict):
    return tempfile_text(json.dumps(content))


if __name__ == "__main__":
    unittest.main()
