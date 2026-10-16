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
    return CommandEngine([sys.executable, "-c", f"import sys; sys.stdin.buffer.read(); print({text!r})"])


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
