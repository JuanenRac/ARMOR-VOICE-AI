import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from armor_voice_ai.intent import ACTIONS, ALLOWED, QUERIES, RISK, SENSITIVE, allowed_from_panel, parse_intent
from armor_voice_ai.confirmation import ConfirmationSigner, VALID, WRONG_SUBJECT
from armor_voice_ai.service import make_server
from armor_voice_ai.turn import CommandEngine, ServerLink, TurnError, TurnService, check_engines, pcm_from_wav, wav_from_pcm

TOKEN = "t" * 24
SPEECH = b"\x01\x00" * 8_000     # half a second of "audio"


class FakeServer:
    """What ARMOR-SERVER's voice route would answer, and what it was asked."""

    def __init__(self):
        self.asked = []

    def __call__(self, text, language, confirmation):
        self.asked.append((text, language, confirmation))
        if text.startswith("arm") and not confirmation:
            return {"accepted": False, "intent": "arm", "outcome": "confirmation-needed", "speech": "Please confirm", "confirmation_token": "tok-1"}
        if text.startswith("arm"):
            return {"accepted": True, "executed": True, "intent": "arm", "outcome": "accepted", "speech": "System armed."}
        if text.startswith("disarm"):
            return {"accepted": False, "intent": "disarm", "outcome": "confirmation-needed", "speech": "Please confirm", "confirmation_token": "tok-2"}
        return {"accepted": True, "executed": True, "intent": "status", "outcome": "accepted", "speech": "The system is armed."}


def engine_saying(text: str) -> CommandEngine:
    return CommandEngine([sys.executable, "-c", f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({text!r}.encode('utf-8'))"])


class TurnTests(unittest.TestCase):
    def service(self, heard="status", server=None, tts=None):
        server = server or FakeServer()
        return TurnService(engine_saying(heard), tts, server), server

    def test_what_is_heard_is_asked_of_the_server_and_its_words_come_back(self):
        service, server = self.service("status")
        answer = service.handle(SPEECH, "en", "panel")
        self.assertEqual(answer, {"heard": "status", "reply": "The system is armed."})
        self.assertEqual(server.asked, [("status", "en", None)])

    def test_a_spoken_yes_confirms_the_question_that_was_asked_and_a_no_cancels_it(self):
        server = FakeServer()
        first = TurnService(engine_saying("arm the system"), None, server)
        self.assertEqual(first.handle(SPEECH, "en", "panel")["reply"], "Please confirm")
        first._stt = engine_saying("yes")
        self.assertEqual(first.handle(SPEECH, "en", "panel")["reply"], "System armed.")
        self.assertEqual(server.asked[-1], ("arm the system", "en", "tok-1"))
        # the question is closed: a second yes confirms nothing
        self.assertEqual(first.handle(SPEECH, "en", "panel")["reply"], "The system is armed.")
        first._stt = engine_saying("arm the system"); first.handle(SPEECH, "en", "panel")
        first._stt = engine_saying("no")
        self.assertEqual(first.handle(SPEECH, "en", "panel")["reply"], "Cancelled.")

    def test_a_confirmation_is_for_the_client_that_was_asked(self):
        server = FakeServer()
        service = TurnService(engine_saying("arm the system"), None, server)
        service.handle(SPEECH, "en", "panel-1")
        service._stt = engine_saying("yes")
        service.handle(SPEECH, "en", "panel-2")
        self.assertEqual(server.asked[-1], ("yes", "en", None), "the yes of another client is just words")

    def test_a_confirmation_in_any_language_with_courtesy_or_full_stops_is_understood(self):
        cases = [("en", "Yes, please.", True), ("es", "Sí, por favor", True), ("fr", "Oui, vas-y !", True), ("ja", "はい。", True), ("zh", "是。", True), ("de", "Ja.", True),
                 ("en", "No thanks", False), ("es", "No.", False), ("ja", "いいえ。", False)]
        for language, said, confirms in cases:
            server = FakeServer()
            service = TurnService(engine_saying("arm the system"), None, server)
            service.handle(SPEECH, language, "panel")
            service._stt = engine_saying(said)
            answer = service.handle(SPEECH, language, "panel")
            if confirms:
                self.assertEqual(server.asked[-1][2], "tok-1", (language, said))
            else:
                self.assertNotEqual(server.asked[-1][2], "tok-1", (language, said))
                self.assertIn(answer["reply"], ("Cancelled.", "Cancelado.", "キャンセルしました。") + ("The system is armed.",), (language, said))

    def test_a_turn_that_is_too_slow_asks_nothing_of_the_server_and_long_noise_is_not_a_command(self):
        from armor_voice_ai import turn as turns
        server = FakeServer()
        service = TurnService(engine_saying("x" * 300), None, server)
        self.assertEqual(service.handle(SPEECH, "en", "panel")["reply"], "I did not hear anything.")
        self.assertEqual(server.asked, [])
        slow = TurnService(engine_saying("status"), None, server)
        original = turns.TURN_BUDGET_S
        turns.TURN_BUDGET_S = -1.0
        try:
            with self.assertRaises(TurnError) as caught:
                slow.handle(SPEECH, "en", "panel")
        finally:
            turns.TURN_BUDGET_S = original
        self.assertEqual(caught.exception.status, 504)
        self.assertEqual(server.asked, [])

    def test_the_client_a_pending_question_belongs_to_can_be_named_by_the_server(self):
        server = FakeServer()
        service = TurnService(engine_saying("arm the system"), None, server)
        httpd = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), None, service)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            def post(client):
                request = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/v1/turn", data=SPEECH, method="POST",
                                                 headers={"X-Armor-Voice-Token": TOKEN, "Content-Type": "audio/L16;rate=16000", "X-Armor-Language": "en", "X-Armor-Client": client})
                return json.loads(urllib.request.urlopen(request, timeout=10).read())
            self.assertEqual(post("panel-1")["reply"], "Please confirm")
            service._stt = engine_saying("yes")
            post("panel-2")
            self.assertEqual(server.asked[-1][2], None, "another panel's yes confirms nothing")
            post("panel-1")
            self.assertEqual(server.asked[-1][2], "tok-1")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_the_wave_of_an_engine_is_checked_and_a_pipe_wave_is_read_to_the_end(self):
        samples = b"\x02\x00" * 100
        good = wav_from_pcm(samples)
        self.assertEqual(pcm_from_wav(good), samples)
        unknown_length = good[:40] + (0).to_bytes(4, "little") + good[44:]
        self.assertEqual(pcm_from_wav(unknown_length), samples)
        streaming = good[:40] + (0xFFFFFFFF).to_bytes(4, "little") + good[44:]
        self.assertEqual(pcm_from_wav(streaming), samples)
        wrong_rate = wav_from_pcm(samples, rate=22_050)
        with self.assertRaises(TurnError):
            pcm_from_wav(wrong_rate)

    def test_the_check_of_the_engines_says_what_works_without_showing_their_commands(self):
        tts_code = "import sys; sys.stdout.buffer.write(bytes.fromhex(%r))" % wav_from_pcm(b"\x01\x00" * 8_000).hex()
        good_tts = CommandEngine([sys.executable, "-c", tts_code])
        good_stt = CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); print('arm the system')"])
        report = check_engines(good_stt, good_tts)
        self.assertEqual([item["engine"] for item in report], ["stt", "tts"])
        self.assertTrue(all(item["ok"] for item in report))
        self.assertEqual(report[0]["text_chars"], 14)
        self.assertEqual((report[1]["audio_seconds"], report[1]["fits_a_turn"]), (0.5, True))
        self.assertNotIn(sys.executable, json.dumps(report))
        bad_tts = CommandEngine([sys.executable, "-c", "print('not a wave')"])
        broken = check_engines(None, bad_tts)
        self.assertEqual(broken[0], {"engine": "stt", "configured": False})
        self.assertFalse(broken[1]["ok"])
        self.assertEqual(check_engines(None, None), [{"engine": "stt", "configured": False}, {"engine": "tts", "configured": False}])

    def test_an_engine_is_given_no_secret_it_was_not_meant_to_have(self):
        import os
        os.environ["ARMOR_PGPASS_HINT"] = "x"; os.environ["MY_AUTH_COOKIE"] = "y"; os.environ["ARMOR_VOICE_ENGINE_MODEL"] = "small"
        try:
            kept = CommandEngine._environment("en")
        finally:
            del os.environ["ARMOR_PGPASS_HINT"], os.environ["MY_AUTH_COOKIE"], os.environ["ARMOR_VOICE_ENGINE_MODEL"]
        self.assertNotIn("ARMOR_PGPASS_HINT", kept)
        self.assertNotIn("MY_AUTH_COOKIE", kept)
        self.assertEqual(kept["ARMOR_VOICE_ENGINE_MODEL"], "small")
        self.assertEqual(kept["ARMOR_VOICE_LANGUAGE"], "en")

    def test_one_matrix_says_what_each_intent_is_worth(self):
        self.assertEqual(set(RISK), set(ALLOWED))
        for name in QUERIES:
            self.assertEqual((RISK[name].kind, RISK[name].confirmation), ("query", "none"))
        for name in ACTIONS:
            self.assertEqual(RISK[name].kind, "action")
        self.assertEqual(SENSITIVE, {"arm", "disarm"})
        self.assertEqual(RISK["silence"].confirmation, "policy")
        self.assertTrue(RISK["disarm"].pin_required)
        self.assertFalse(allowed_from_panel("disarm"))
        self.assertTrue(allowed_from_panel("arm") and allowed_from_panel("status"))
        self.assertFalse(allowed_from_panel("something-new") or allowed_from_panel(None))

    def test_the_punctuation_of_a_transcript_in_japanese_and_chinese_does_not_hide_a_command(self):
        for said in ("状態。", "「状態」", "システムの状態！", "状态！", "状态？", "状态，"):
            self.assertEqual(parse_intent(said), "status", said)
        self.assertEqual(parse_intent("Yes please"), None)   # a courtesy is never a command by itself

    def test_a_spoken_reply_of_199000_bytes_goes_as_words_only_and_one_of_190000_goes_with_audio(self):
        for size, has_audio in ((199_000, False), (190_000, True)):
            wav = wav_from_pcm(b"\x02\x00" * (size // 2))
            with tempfile.TemporaryDirectory() as folder:   # a WAVE this size does not fit on a command line
                path = Path(folder) / "reply.wav"
                path.write_bytes(wav)
                tts = CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(open(sys.argv[1], 'rb').read())", str(path)])
                service, _ = self.service("status", tts=tts)
                answer = service.handle(SPEECH, "en", "panel")
            self.assertEqual("audio" in answer, has_audio, size)
            self.assertEqual(answer["reply"], "The system is armed.")

    def test_an_engine_without_a_secret_in_its_environment_still_runs_and_a_long_engine_is_cut_short_by_the_turn_budget(self):
        service, server = self.service("status")
        slow = CommandEngine([sys.executable, "-c", "import time; time.sleep(30)"], timeout_s=30.0)
        service._stt = slow
        started = time.monotonic()
        with self.assertRaises(TurnError) as raised:
            service.handle(SPEECH, "en", "panel")
        self.assertEqual(raised.exception.code, "engine_failed")
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(server.asked, [])

    def test_disarming_is_never_done_from_here(self):
        service, server = self.service("disarm the system")
        answer = service.handle(SPEECH, "es", "panel")
        self.assertIn("PIN", answer["reply"])
        self.assertTrue(all(call[2] is None for call in server.asked))

    def test_no_engine_no_server_and_bad_audio_are_said(self):
        with self.assertRaises(TurnError) as raised:
            TurnService(None, None, FakeServer()).handle(SPEECH, "en", "panel")
        self.assertEqual(raised.exception.code, "stt_unavailable")
        with self.assertRaises(TurnError) as raised:
            TurnService(engine_saying("x"), None, None).handle(SPEECH, "en", "panel")
        self.assertEqual(raised.exception.code, "server_not_configured")
        service, _ = self.service()
        for bad in (b"", b"\x01", b"\x00\x00" * 300_000):
            with self.assertRaises(TurnError):
                service.handle(bad, "en", "panel")

    def test_a_failing_engine_is_an_error_and_silence_is_an_answer(self):
        broken = TurnService(CommandEngine([sys.executable, "-c", "import sys; sys.exit(3)"]), None, FakeServer())
        with self.assertRaises(TurnError) as raised:
            broken.handle(SPEECH, "en", "panel")
        self.assertEqual(raised.exception.code, "engine_failed")
        quiet = TurnService(engine_saying(""), None, FakeServer())
        self.assertEqual(quiet.handle(SPEECH, "es", "panel")["reply"], "No he oído nada.")

    def test_the_speech_of_an_engine_goes_back_as_audio(self):
        tts = CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(bytes.fromhex(" + repr(wav_from_pcm(b"\x02\x00" * 10).hex()) + "))"])
        service, _ = self.service("status", tts=tts)
        answer = service.handle(SPEECH, "en", "panel")
        self.assertIn("audio", answer)

    def test_wave_headers_round_trip(self):
        pcm = b"\x05\x00\x06\x00"
        self.assertEqual(pcm_from_wav(wav_from_pcm(pcm)), pcm)


class PanicCheckTests(unittest.TestCase):
    """The transcript goes to the server's panic route BEFORE it is interpreted; what comes back is not read, and a failure there never changes the turn."""

    def test_the_transcript_is_checked_before_the_server_is_asked_and_the_turn_is_unchanged(self):
        events = []
        server = FakeServer()
        service = TurnService(engine_saying("the blue heron flies"), None, lambda *a: events.append("command") or server(*a), panic_check=lambda text, language: events.append(("panic", text, language)))
        answer = service.handle(SPEECH, "en", "panel")
        self.assertEqual(events, [("panic", "the blue heron flies", "en"), "command"])
        self.assertEqual(answer["heard"], "the blue heron flies")

    def test_a_check_that_fails_changes_nothing(self):
        def broken(text, language):
            raise RuntimeError("down")
        service = TurnService(engine_saying("status"), None, FakeServer(), panic_check=broken)
        self.assertEqual(service.handle(SPEECH, "en", "panel"), {"heard": "status", "reply": "The system is armed."})

    def test_nothing_is_checked_when_nothing_was_heard(self):
        seen = []
        service = TurnService(engine_saying(""), None, FakeServer(), panic_check=lambda *a: seen.append(a))
        service.handle(SPEECH, "en", "panel")
        self.assertEqual(seen, [])

    def test_the_link_asks_the_route_with_the_operator_token_and_ignores_every_answer(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from armor_voice_ai.turn import ServerLink
        seen = []
        status = [200]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                seen.append((self.path, self.headers.get("Authorization"), json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(status[0])
                self.send_header("Content-Length", "11")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            link = ServerLink(f"http://127.0.0.1:{httpd.server_address[1]}", "o" * 24)
            for code in (200, 401, 404, 429):   # a match, a refusal, an old server and the rate limit all look the same from here
                status[0] = code
                self.assertIsNone(link.panic_check("the blue heron flies at midnight", "en"))
            self.assertEqual(seen[0], ("/api/v1/voice/panic-check", "Bearer " + "o" * 24, {"text": "the blue heron flies at midnight", "language": "en"}))
            self.assertEqual(len(seen), 4)
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertIsNone(ServerLink("http://127.0.0.1:9", "o" * 24).panic_check("x y z", "en"))   # nobody listening: still nothing raised


class PanelHeaderTests(unittest.TestCase):
    """The wall panel that spoke is handed back to the server on the command and on the panic check, and only a well-formed id is."""

    def run_turn(self, panel):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                seen.append((self.path, self.headers.get("X-Armor-Panel")))
                body = b'{"reply":"ok","intent":"status"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            service = TurnService(engine_saying("status"), None, ServerLink(f"http://127.0.0.1:{httpd.server_address[1]}", "o" * 24))
            service.handle(SPEECH, "en", "panel", None, panel)
            service.handle(SPEECH, "en", "panel")   # a turn with no panel afterwards carries none: nothing leaks between turns
        finally:
            httpd.shutdown()
            httpd.server_close()
        return seen

    def test_the_panel_goes_back_on_both_routes_and_does_not_leak(self):
        seen = self.run_turn("hmi-kitchen")
        self.assertEqual(seen[:2], [("/api/v1/voice/panic-check", "hmi-kitchen"), ("/api/v1/voice/command", "hmi-kitchen")])
        self.assertTrue(all(panel is None for _path, panel in seen[2:]))

    def test_a_malformed_panel_is_dropped(self):
        seen = self.run_turn("../x y")
        self.assertTrue(seen and all(panel is None for _path, panel in seen))


class SpeakTests(unittest.TestCase):
    """The sentence of an alarm said out loud (`/v1/speak`): the speech engine and nothing else."""

    PCM = b"\x02\x00" * 400

    @staticmethod
    def saying(pcm: bytes) -> CommandEngine:
        return CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(bytes.fromhex(" + repr(wav_from_pcm(pcm).hex()) + "))"])

    def start(self, tts):
        server = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), turns=TurnService(None, tts, None))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    @staticmethod
    def post(base, body, token=TOKEN, raw=None):
        data = raw if raw is not None else json.dumps(body).encode()
        request = urllib.request.Request(base + "/v1/speak", data=data, method="POST", headers={"Content-Type": "application/json", **({"X-Armor-Voice-Token": token} if token else {})})
        try:
            with urllib.request.urlopen(request, timeout=10) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_a_sentence_comes_back_as_samples(self):
        base = self.start(self.saying(self.PCM))
        status, answer = self.post(base, {"text": "Critical alarm. Electrical.", "language": "en"})
        self.assertEqual(status, 200)
        import base64
        self.assertEqual(base64.b64decode(answer["audio"]), self.PCM)

    def test_it_needs_the_token_a_closed_request_and_a_speech_engine(self):
        base = self.start(self.saying(self.PCM))
        self.assertEqual(self.post(base, {"text": "x", "language": "en"}, token=None)[0], 401)
        self.assertEqual(self.post(base, {"text": "x", "language": "en"}, token="w" * 24)[0], 401)
        self.assertEqual(self.post(base, {"text": "x", "language": "xx"})[0], 422)
        self.assertEqual(self.post(base, {"text": "x", "language": "en", "extra": 1})[0], 422)
        self.assertEqual(self.post(base, {"text": 5, "language": "en"})[0], 422)
        self.assertEqual(self.post(base, None, raw=b"not json")[0], 400)
        self.assertEqual(self.post(base, {"text": "y" * 301, "language": "en"})[0], 422)
        self.assertEqual(self.post(base, {"text": "y" * 2000, "language": "en"})[0], 413)
        self.assertEqual(self.post(self.start(None), {"text": "x", "language": "en"}), (501, {"error": "tts_unavailable"}))

    def test_an_engine_that_fails_or_says_too_much_is_an_error_and_not_a_sound(self):
        failing = CommandEngine([sys.executable, "-c", "import sys; sys.exit(2)"])
        self.assertEqual(self.post(self.start(failing), {"text": "x", "language": "en"}), (502, {"error": "engine_failed"}))
        long_one = self.saying(b"\x01\x00" * 100_000)
        self.assertEqual(self.post(self.start(long_one), {"text": "x", "language": "en"}), (502, {"error": "engine_failed"}))
        with self.assertRaises(TurnError):
            TurnService(None, self.saying(self.PCM), None).speak("", "en")

    def test_the_speech_engine_gets_the_sentence_and_no_secret(self):
        probe = CommandEngine([sys.executable, "-c", "import sys, os; sys.stdin.buffer.read(); sys.stdout.buffer.write(bytes.fromhex(" + repr(wav_from_pcm(self.PCM).hex()) + ")) if not os.environ.get('ARMOR_VOICE_TOKEN') else sys.exit(9)"])
        os.environ["ARMOR_VOICE_TOKEN"] = "secret-value-1234567890"
        self.addCleanup(os.environ.pop, "ARMOR_VOICE_TOKEN", None)
        self.assertEqual(self.post(self.start(probe), {"text": "x", "language": "en"})[0], 200)


class SubjectTests(unittest.TestCase):
    def test_a_token_is_good_only_for_the_person_who_asked(self):
        signer = ConfirmationSigner(b"s" * 32)
        token = signer.issue("arm", "u-1")
        self.assertEqual(signer.verify(token, "arm", "u-2"), WRONG_SUBJECT)
        self.assertEqual(signer.verify(token, "arm", "u-1"), VALID)
        self.assertEqual(signer.verify(signer.issue("arm"), "arm"), VALID, "no subject, as before")
        self.assertEqual(signer.verify(signer.issue("arm", "u-1"), "arm", ""), WRONG_SUBJECT)


class RouteTests(unittest.TestCase):
    def setUp(self):
        turns = TurnService(engine_saying("status"), None, FakeServer())
        self.server = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), None, turns)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, body, token=TOKEN, content_type="audio/L16;rate=16000", language="en"):
        headers = {"Content-Type": content_type, "X-Armor-Language": language, **({"X-Armor-Voice-Token": token} if token else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + "/v1/turn", data=body, method="POST", headers=headers), timeout=10) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_a_turn_over_http_needs_the_token_the_audio_type_and_a_known_language(self):
        self.assertEqual(self.post(SPEECH)[0], 200)
        self.assertEqual(self.post(SPEECH, token=None)[0], 401)
        self.assertEqual(self.post(SPEECH, token="x" * 24)[0], 401)
        self.assertEqual(self.post(SPEECH, content_type="application/json")[0], 415)
        self.assertEqual(self.post(SPEECH, language="xx")[0], 422)
        self.assertEqual(self.post(b"\x00" * 500_000)[0], 413)


if __name__ == "__main__":
    unittest.main()
