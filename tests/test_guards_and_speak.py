"""The branches nobody tried: the guards of the PIN and of the spoken number while they are locked, the sentences a panel asks the service to say, and the questions that wait for an answer
and go stale. Every clock is a double and every engine is a one-line script, so nothing waits and nothing is heard."""
import sys
import unittest

from armor_voice_ai.gateway import handle_request
from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.silence_policy import LOCKOUT_S, MAX_PIN_ATTEMPTS, MAX_PIN_DIGITS, MIN_PIN_DIGITS, ChallengeGuard, PinGuard
from armor_voice_ai.turn import MAX_REPLY_AUDIO_BYTES, MAX_SPEAK_CHARS, CommandEngine, TurnError, TurnService

HEADER = ("import struct,sys\n"
          "def wav(pcm):\n"
          "    return b'RIFF'+struct.pack('<I',36+len(pcm))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,16000,32000,2,16)+b'data'+struct.pack('<I',len(pcm))+pcm\n"
          "sys.stdin.buffer.read()\n")


def tts_making(pcm_expression: str) -> CommandEngine:
    return CommandEngine([sys.executable, "-c", HEADER + f"sys.stdout.buffer.write(wav({pcm_expression}))"])


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PinGuardTest(unittest.TestCase):
    def test_a_bad_pin_is_refused_when_the_guard_is_made(self):
        for pin in ("", "123", "1" * (MAX_PIN_DIGITS + 1), "12a4", "١٢٣٤", " 1234", "1234 ", "-1234", "12.34"):
            with self.assertRaises(ValueError, msg=repr(pin)):
                PinGuard(pin)
        for pin in ("1" * MIN_PIN_DIGITS, "9" * MAX_PIN_DIGITS):
            self.assertTrue(PinGuard(pin).configured)
        self.assertFalse(PinGuard(None).configured)

    def test_without_a_pin_every_try_is_unset_and_never_locks(self):
        guard = PinGuard(None)
        for _ in range(MAX_PIN_ATTEMPTS * 3):
            self.assertEqual(guard.check("1234"), "unset")
        self.assertFalse(guard.locked)

    def test_the_wrong_ones_lock_and_the_right_one_is_refused_while_locked_and_works_after(self):
        clock = Clock()
        guard = PinGuard("4821", clock)
        for _ in range(MAX_PIN_ATTEMPTS - 1):
            self.assertEqual(guard.check("0000"), "wrong")
        self.assertFalse(guard.locked)
        self.assertEqual(guard.check("0000"), "locked", "the last wrong try is the one that locks")
        self.assertTrue(guard.locked)
        self.assertEqual(guard.check("4821"), "locked", "even the right PIN is refused while locked")
        clock.now += LOCKOUT_S - 1
        self.assertEqual(guard.check("4821"), "locked")
        clock.now += 2
        self.assertFalse(guard.locked)
        self.assertEqual(guard.check("4821"), "ok")

    def test_a_right_pin_clears_the_count(self):
        guard = PinGuard("4821", Clock())
        for _ in range(5):
            for _ in range(MAX_PIN_ATTEMPTS - 1):
                self.assertEqual(guard.check("1111"), "wrong")
            self.assertEqual(guard.check("4821"), "ok")
        self.assertFalse(guard.locked)

    def test_digits_that_are_not_ascii_or_far_too_long_are_wrong_and_never_raise(self):
        guard = PinGuard("4821", Clock())
        for digits in ("٤٨٢١", "4821\u0000", "4821" * 1000, "", "48 21"):
            self.assertEqual(guard.check(digits), "wrong", repr(digits))
            guard.check("4821")   # a right one in between keeps the count from locking the next try


class ChallengeGuardTest(unittest.TestCase):
    def test_the_number_is_two_digits_and_the_draw_is_used(self):
        self.assertEqual(ChallengeGuard(Clock(), lambda: 42).new_number(), "42")
        for _ in range(200):
            self.assertIn(len(ChallengeGuard().new_number()), (2,))

    def test_the_wrong_ones_lock_and_a_locked_guard_refuses_the_right_number(self):
        clock = Clock()
        guard = ChallengeGuard(clock, lambda: 57)
        for _ in range(MAX_PIN_ATTEMPTS - 1):
            self.assertEqual(guard.check("57", "11"), "wrong")
        self.assertEqual(guard.check("57", "11"), "locked")
        self.assertTrue(guard.locked)
        self.assertEqual(guard.check("57", "57"), "locked")
        clock.now += LOCKOUT_S + 1
        self.assertFalse(guard.locked)
        self.assertEqual(guard.check("57", "57"), "ok")

    def test_a_right_number_clears_the_count_and_odd_text_is_wrong(self):
        guard = ChallengeGuard(Clock(), lambda: 57)
        for _ in range(4):
            for _ in range(MAX_PIN_ATTEMPTS - 1):
                self.assertEqual(guard.check("57", "99"), "wrong")
            self.assertEqual(guard.check("57", "57"), "ok")
        for digits in ("٥٧", "5 7", "057", "", "57\u0000"):
            self.assertEqual(guard.check("57", digits), "wrong", repr(digits))
            guard.check("57", "57")


class SpeakTest(unittest.TestCase):
    def test_without_a_speech_engine_it_is_not_available(self):
        with self.assertRaises(TurnError) as caught:
            TurnService(None, None, lambda *a: {}).speak("alarm", "en")
        self.assertEqual(caught.exception.status, 501)

    def test_an_empty_or_too_long_sentence_is_refused_before_the_engine_runs(self):
        service = TurnService(None, tts_making("b'\\x01\\x00'*800"), lambda *a: {})
        for text in ("", "x" * (MAX_SPEAK_CHARS + 1), "y" * 5000):
            with self.assertRaises(TurnError, msg=text[:10]) as caught:
                service.speak(text, "en")
            self.assertEqual(caught.exception.status, 422)
        self.assertEqual(len(service.speak("x" * MAX_SPEAK_CHARS, "en")), 1600)

    def test_an_engine_that_makes_nothing_too_much_or_a_torn_sample_is_a_failure_not_a_panel_noise(self):
        for expression in ("b''", f"b'\\x01\\x00'*{MAX_REPLY_AUDIO_BYTES // 2 + 1}", "b'\\x01\\x00'*400+b'\\x01'"):
            service = TurnService(None, tts_making(expression), lambda *a: {})
            with self.assertRaises(TurnError, msg=expression) as caught:
                service.speak("alarm", "en")
            self.assertEqual(caught.exception.status, 502, expression)

    def test_an_engine_that_fails_to_run_is_a_failure_too(self):
        service = TurnService(None, CommandEngine([sys.executable, "-c", "import sys; sys.exit(3)"]), lambda *a: {})
        with self.assertRaises(TurnError):
            service.speak("alarm", "en")

    def test_the_audio_of_a_reply_is_left_out_when_it_is_too_long_and_the_words_still_go(self):
        stt = CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'status')"])
        service = TurnService(stt, tts_making(f"b'\\x01\\x00'*{MAX_REPLY_AUDIO_BYTES // 2 + 1}"), lambda text, language, confirmation: {"accepted": True, "speech": "All good."})
        answer = service.handle(b"\x01\x00" * 8000, "en", "panel")
        self.assertEqual((answer["heard"], answer["reply"]), ("status", "All good."))
        self.assertNotIn("audio", answer)


class StaleQuestionTest(unittest.TestCase):
    def test_a_question_that_was_never_answered_is_dropped_when_another_panel_speaks(self):
        clock = Clock()
        stt = CommandEngine([sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'arm the system')"])

        def server(text, language, confirmation):
            if not confirmation:
                return {"accepted": False, "outcome": "confirmation-needed", "speech": "Please confirm", "confirmation_token": "tok"}
            return {"accepted": True, "speech": "System armed."}

        service = TurnService(stt, None, server, now=clock)
        service.handle(b"\x01\x00" * 8000, "en", "kitchen")
        self.assertEqual(list(service._pending), ["kitchen"])
        clock.now += 100_000
        service.handle(b"\x01\x00" * 8000, "en", "garage")
        self.assertEqual(list(service._pending), ["garage"], "the stale question of the other panel is gone")


class GatewayFieldsTest(unittest.TestCase):
    def test_a_pin_that_is_not_text_or_is_too_long_is_refused_as_a_field(self):
        signer = ConfirmationSigner(b"k" * 32)
        for pin in (5, ["1234"], {"a": 1}, "1" * 33, True):
            answer = handle_request({"text": "status", "pin": pin}, signer)
            self.assertEqual(answer, {"accepted": False, "error": "invalid request fields"}, repr(pin))
        for subject in (5, "s" * 65, "sujeto-é", ["x"]):
            answer = handle_request({"text": "status", "subject": subject}, signer)
            self.assertEqual(answer, {"accepted": False, "error": "invalid request fields"}, repr(subject))
        for language in ("xx", "EN", 7, None, ""):
            answer = handle_request({"text": "status", "language": language}, signer)
            self.assertEqual(answer, {"accepted": False, "error": "invalid request fields"}, repr(language))
        for text in (5, None, ["status"]):
            self.assertEqual(handle_request({"text": text}, signer), {"accepted": False, "error": "invalid request fields"}, repr(text))
        for request in ("status", 5, None, [], [{"text": "status"}]):
            self.assertEqual(handle_request(request, signer), {"accepted": False, "error": "invalid request shape"}, repr(request))


if __name__ == "__main__":
    unittest.main()
