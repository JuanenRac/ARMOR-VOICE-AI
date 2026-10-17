import json
import sys
import threading
import unittest
import urllib.error
import urllib.request

from armor_voice_ai.confirmation import ConfirmationSigner, INVALID, VALID, WRONG_SUBJECT
from armor_voice_ai.service import make_server
from armor_voice_ai.turn import CommandEngine, TurnError, TurnService, pcm_from_wav, wav_from_pcm

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
