"""The edges of the voice gateway: the line protocol on standard input, the settings of the HTTP service, the link to the server (a stand-in on the loopback) and the engines' limits."""
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from armor_voice_ai import gateway, service
from armor_voice_ai.confirmation import EXPIRED, INVALID, REPLAYED, VALID, WRONG_INTENT, WRONG_SUBJECT, ConfirmationSigner
from armor_voice_ai.turn import CommandEngine, ServerLink, TurnError, TurnService, pcm_from_wav, says, wav_from_pcm


def run_gateway(raw_lines: bytes, *arguments: str) -> list[dict]:
    out = io.StringIO()
    stdin = io.TextIOWrapper(io.BytesIO(raw_lines), encoding="utf-8")
    with mock.patch("sys.stdin", stdin), contextlib.redirect_stdout(out):
        gateway.main(list(arguments))
    return [json.loads(line) for line in out.getvalue().splitlines()]


class LineProtocolTests(unittest.TestCase):
    def test_one_answer_per_line_in_order(self):
        answers = run_gateway(b'{"text":"status"}\n{"text":"open the garage"}\n')
        self.assertEqual([item["accepted"] for item in answers], [True, False])

    def test_bad_input_is_answered_and_the_next_line_still_works(self):
        lines = b'not json\n' + b'{"text":"' + b"x" * 3000 + b'"}\n' + b'{"text":"status"}\n' + b'\xff\xfe\n'
        answers = run_gateway(lines)
        self.assertEqual(answers[0], {"accepted": False, "error": "invalid JSON"})
        self.assertEqual(answers[1], {"accepted": False, "error": "line too long"})
        self.assertEqual(answers[2]["intent"], "status")
        self.assertEqual(answers[3], {"accepted": False, "error": "invalid JSON"})   # bytes that are not UTF-8 are a line, not the end of the program

    def test_a_flag_that_says_it_was_confirmed_is_never_believed_over_the_line_protocol(self):
        (answer,) = run_gateway(b'{"text":"arm the system","confirmed":true}\n')
        self.assertFalse(answer["accepted"])
        self.assertIn("confirmed flag", answer["error"])

    def test_the_two_turns_work_end_to_end_and_the_audit_has_no_words(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / "audit.jsonl"
            first = run_gateway(b'{"text":"arm the system secretphrase"}\n{"text":"arm the system"}\n', "--audit-file", str(audit))
            self.assertEqual(first[1]["outcome"], "confirmation-needed")
            text = audit.read_text(encoding="utf-8")
            self.assertNotIn("secretphrase", text)
            self.assertNotIn("arm the system", text)
            entries = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(len(entries), 2)
            self.assertTrue(all(len(entry["transcript_sha256"]) == 64 for entry in entries))

    def test_each_language_has_all_four_phrases(self):
        for language, table in gateway.SPEECH_BY_LANGUAGE.items():
            self.assertEqual(len(table), 4, language)
            self.assertTrue(all(isinstance(text, str) and text.strip() for text in table.values()), language)

    def test_the_request_fields_are_checked(self):
        signer = ConfirmationSigner(b"s" * 32)
        bad = [{"text": 5}, {"text": "status", "language": "xx"}, {"text": "status", "language": 3}, {"text": "status", "confirmation": 7}, {"text": "status", "subject": "é"},
               {"text": "status", "subject": "x" * 65}, {"text": "status", "subject": 4}, [], "status", None, 5]
        for request in bad:
            self.assertFalse(gateway.handle_request(request, signer)["accepted"], request)

    def test_unknown_language_codes_fall_back_to_the_unrecognised_phrase_only_for_known_languages(self):
        signer = ConfirmationSigner(b"s" * 32)
        answer = gateway.handle_request({"text": "open the garage", "language": "de"}, signer)
        self.assertEqual(answer["speech"], "Befehl nicht erkannt")


class SignerEdgeTests(unittest.TestCase):
    def test_a_short_secret_is_refused_and_a_configured_one_is_used(self):
        with self.assertRaises(ValueError):
            ConfirmationSigner(b"short")
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_CONFIRM_SECRET": "e" * 20}):
            first = ConfirmationSigner()
            second = ConfirmationSigner()
            self.assertEqual(second.verify(first.issue("arm"), "arm"), VALID)    # the same secret in the environment: a token survives a restart
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_CONFIRM_SECRET": ""}):
            with self.assertLogs("armor_voice_ai.confirmation", "WARNING"):
                lonely = ConfirmationSigner()
            self.assertEqual(lonely.verify(first.issue("arm"), "arm"), INVALID)   # a random secret recognises nobody else's tokens

    def test_every_reason_a_token_is_refused(self):
        clock = [1000.0]
        signer = ConfirmationSigner(b"s" * 32, ttl_s=30, now=lambda: clock[0])
        token = signer.issue("arm", "u-1")
        self.assertEqual(signer.verify(token, "disarm", "u-1"), WRONG_INTENT)
        self.assertEqual(signer.verify(token, "arm", "u-2"), WRONG_SUBJECT)
        self.assertEqual(signer.verify(token, "arm", "u-1"), VALID)
        self.assertEqual(signer.verify(token, "arm", "u-1"), REPLAYED)
        late = signer.issue("arm")
        clock[0] += 31
        self.assertEqual(signer.verify(late, "arm"), EXPIRED)
        for garbage in (None, 5, "", "abc", "a.b.c", "é.é", "." , b"bytes"):
            self.assertEqual(signer.verify(garbage, "arm"), INVALID, repr(garbage))

    def test_a_token_that_claims_to_live_longer_than_it_could_have_is_invalid(self):
        clock = [1000.0]
        signer = ConfirmationSigner(b"s" * 32, ttl_s=30, now=lambda: clock[0])
        token = signer.issue("arm")
        clock[0] -= 100          # the clock jumped back: the token would now seem to have 130 s of life
        self.assertEqual(signer.verify(token, "arm"), INVALID)

    def test_a_correctly_signed_body_that_is_not_a_token_is_invalid(self):
        signer = ConfirmationSigner(b"s" * 32)
        import base64
        for payload in (b"not json", b'{"i":"arm"}', b'{"i":"arm","e":"soon","n":"x"}', b"[]"):
            body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
            self.assertEqual(signer.verify(f"{body}.{signer._sign(body)}", "arm"), INVALID, payload)


class StandInServer(BaseHTTPRequestHandler):
    answer: tuple[int, bytes] = (200, b"{}")
    seen: list[dict] = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        StandInServer.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(self.rfile.read(length)), "requested_with": self.headers.get("X-Requested-With")})
        status, payload = StandInServer.answer
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ServerLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), StandInServer)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        StandInServer.seen = []
        StandInServer.answer = (200, b'{"speech":"ok"}')

    def test_the_command_goes_to_the_voice_route_with_the_token_and_the_marker_header(self):
        link = ServerLink(self.url + "/", "operator-token", timeout_s=3)
        self.assertEqual(link.command("status", "es", None), {"speech": "ok"})
        sent = StandInServer.seen[0]
        self.assertEqual((sent["path"], sent["auth"], sent["requested_with"]), ("/api/v1/voice/command", "Bearer operator-token", "armor"))
        self.assertEqual(sent["body"], {"text": "status", "language": "es"})

    def test_a_confirmation_travels_only_when_there_is_one(self):
        link = ServerLink(self.url, "t", timeout_s=3)
        link.command("arm", "en", "tok")
        link.command("arm", "en", "")
        self.assertEqual(StandInServer.seen[0]["body"]["confirmation"], "tok")
        self.assertNotIn("confirmation", StandInServer.seen[1]["body"])

    def test_what_the_server_refuses_is_a_named_bad_gateway(self):
        StandInServer.answer = (403, b'{"error":"forbidden"}')
        with self.assertRaises(TurnError) as caught:
            ServerLink(self.url, "t", timeout_s=3).command("status", "en", None)
        self.assertEqual((caught.exception.status, caught.exception.code), (502, "server_403"))

    def test_a_server_that_is_not_there_or_sends_garbage_is_not_answering(self):
        with self.assertRaises(TurnError) as caught:
            ServerLink("http://127.0.0.1:9", "t", timeout_s=1).command("status", "en", None)
        self.assertEqual(caught.exception.code, "server_not_answering")
        StandInServer.answer = (200, b"<html>")
        with self.assertRaises(TurnError) as caught:
            ServerLink(self.url, "t", timeout_s=3).command("status", "en", None)
        self.assertEqual(caught.exception.code, "server_not_answering")


class EngineEdgeTests(unittest.TestCase):
    def test_an_engine_needs_a_command(self):
        for empty in ("", "   ", []):
            with self.assertRaises(ValueError):
                CommandEngine(empty)

    def test_a_program_that_does_not_exist_or_exits_with_an_error_is_a_failed_engine(self):
        for command in (["no-such-speech-program-armor"], [sys.executable, "-c", "raise SystemExit(3)"]):
            with self.assertRaises(TurnError) as caught:
                CommandEngine(command).run(b"x", "en", 100)
            self.assertEqual((caught.exception.status, caught.exception.code), (502, "engine_failed"))

    def test_an_engine_that_takes_too_long_is_stopped(self):
        engine = CommandEngine([sys.executable, "-c", "import time; time.sleep(30)"], timeout_s=1)
        with self.assertRaises(TurnError) as caught:
            engine.run(b"x", "en", 100)
        self.assertEqual(caught.exception.code, "engine_failed")

    def test_an_answer_bigger_than_the_limit_is_refused(self):
        engine = CommandEngine([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 500)"])
        self.assertEqual(len(engine.run(b"", "en", 500)), 500)
        with self.assertRaises(TurnError):
            engine.run(b"", "en", 499)

    def test_the_command_is_split_without_a_shell(self):
        marker = Path(tempfile.gettempdir()) / "armor-voice-no-shell-marker"
        marker.unlink(missing_ok=True)
        engine = CommandEngine(f"{sys.executable} -c pass ; touch {marker}")
        with contextlib.suppress(TurnError):
            engine.run(b"", "en", 10)
        self.assertFalse(marker.exists())

    def test_the_wave_helpers_reject_what_the_panel_cannot_play(self):
        good = wav_from_pcm(b"\x01\x00" * 100)
        self.assertEqual(pcm_from_wav(good), b"\x01\x00" * 100)
        for bad in (b"", b"RIFF", b"RIFX" + good[4:], good[:8] + b"AVI " + good[12:], good[:20] + (3).to_bytes(2, "little") + good[22:], good[:22] + (2).to_bytes(2, "little") + good[24:],
                    good[:24] + (8000).to_bytes(4, "little") + good[28:], good[:34] + (8).to_bytes(2, "little") + good[36:], good[:36] + b"junk" + good[40:]):
            with self.assertRaises(TurnError, msg=bad[:44]):
                pcm_from_wav(bad)

    def test_words_of_agreement_must_start_the_phrase_not_hide_inside_it(self):
        self.assertTrue(says("yes please", ("yes",), "en"))
        self.assertTrue(says("yes", ("yes",), "en"))
        self.assertFalse(says("eyes", ("yes",), "en"))
        self.assertFalse(says("yesterday", ("yes",), "en"))
        self.assertTrue(says("はいお願いします", ("はい",), "ja"))
        self.assertFalse(says("はいお願いします", ("はい",), "en"))


class ServiceSettingsTests(unittest.TestCase):
    def test_the_token_comes_from_the_file_then_the_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "voice.env"
            path.write_text("OTHER=1\nARMOR_VOICE_TOKEN= " + "f" * 20 + " \n", encoding="utf-8")
            args = mock.Mock(token_file=path)
            self.assertEqual(service._read_token(args), "f" * 20)
            path.write_text("OTHER=1\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                service._read_token(args)
            self.assertIn("ARMOR_VOICE_TOKEN", str(caught.exception))
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_TOKEN": "g" * 20}):
            self.assertEqual(service._read_token(mock.Mock(token_file=None)), "g" * 20)

    def test_the_service_will_not_start_without_a_long_token_or_on_the_network(self):
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_TOKEN": "short"}):
            with self.assertRaises(SystemExit) as caught:
                service.main(["--port", "0"])
            self.assertIn("16 characters", str(caught.exception))
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_TOKEN": "t" * 20}):
            for host in ("0.0.0.0", "192.168.0.5", "example.org"):
                with self.assertRaises(SystemExit, msg=host):
                    service.main(["--host", host])

    def test_the_service_starts_on_loopback_and_stops_cleanly(self):
        started = mock.Mock()
        with mock.patch.dict(os.environ, {"ARMOR_VOICE_TOKEN": "t" * 20}), mock.patch.object(service, "make_server", return_value=started) as made, contextlib.redirect_stderr(io.StringIO()):
            started.server_address = ("127.0.0.1", 18090)
            started.serve_forever.side_effect = KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                service.main([])
        started.server_close.assert_called_once()
        self.assertEqual(made.call_args.args[:3], ("127.0.0.1", 18090, "t" * 20))


class HttpEdgeTests(unittest.TestCase):
    def setUp(self):
        self.turns = TurnService(None, None, None)
        self.server = service.make_server("127.0.0.1", 0, "t" * 24, ConfirmationSigner(b"s" * 32), None, self.turns)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, body, headers):
        import urllib.error
        import urllib.request
        request = urllib.request.Request(self.base + path, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read() or b"{}")

    def test_a_turn_without_a_speech_engine_says_so_instead_of_inventing_a_transcript(self):
        status, body = self.post("/v1/turn", b"\x00\x00" * 100, {"X-Armor-Voice-Token": "t" * 24, "Content-Type": "audio/L16;rate=16000"})
        self.assertEqual((status, body), (501, {"error": "stt_unavailable"}))

    def test_the_length_of_a_command_is_required_and_limited(self):
        headers = {"X-Armor-Voice-Token": "t" * 24, "Content-Type": "application/json"}
        self.assertEqual(self.post("/v1/command", b"", headers)[1], {"accepted": False, "error": "invalid json"})
        status, body = self.post("/v1/command", b"{" + b" " * 5000 + b"}", headers)
        self.assertEqual((status, body["error"]), (413, "line too long"))

    def test_the_token_is_compared_in_constant_time_and_wrong_lengths_are_refused(self):
        for token in ("", "t" * 23, "t" * 25, "T" * 24):
            status, _ = self.post("/v1/command", b'{"text":"status"}', {"X-Armor-Voice-Token": token, "Content-Type": "application/json"})
            self.assertEqual(status, 401, token)

    def test_a_turn_with_no_length_or_an_empty_body_is_refused(self):
        turns = TurnService(CommandEngine([sys.executable, "-c", "print('status')"]), None, lambda *args: {"speech": "ok"})
        server = service.make_server("127.0.0.1", 0, "t" * 24, ConfirmationSigner(b"s" * 32), None, turns)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        import urllib.error
        import urllib.request
        request = urllib.request.Request(base + "/v1/turn", data=b"", method="POST", headers={"X-Armor-Voice-Token": "t" * 24, "Content-Type": "audio/L16;rate=16000"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 411)
        caught.exception.close()
        self.assertTrue(turns.can_hear)


if __name__ == "__main__":
    unittest.main()
