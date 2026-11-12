"""Two edges of the turn that the main tests of the turn do not reach: a speech engine that fails must not take the written answer with it, and the questions that wait for a spoken yes are
forgotten when their time is over (also those of other clients, whenever anybody asks)."""
import sys
import unittest

from armor_voice_ai.turn import CommandEngine, TurnService

SPEECH = b"\x01\x00" * 8_000   # half a second of "audio"


def engine_saying(text: str) -> CommandEngine:
    return CommandEngine([sys.executable, "-c", f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({text!r}.encode('utf-8'))"])


def status_server(text, language, confirmation):
    return {"accepted": True, "executed": True, "intent": "status", "outcome": "accepted", "speech": "The system is armed."}


class SpeechEngineFailureTests(unittest.TestCase):
    def test_a_speech_engine_that_does_not_give_a_wave_still_lets_the_words_go(self):
        broken = CommandEngine([sys.executable, "-c", "print('not a wave')"])
        service = TurnService(engine_saying("status"), broken, status_server)
        answer = service.handle(SPEECH, "en", "panel")
        self.assertEqual(answer["heard"], "status")
        self.assertEqual(answer["reply"], "The system is armed.")
        self.assertNotIn("audio", answer)   # the speech failed, the answer did not

    def test_a_speech_engine_that_exits_with_an_error_also_lets_the_words_go(self):
        failing = CommandEngine([sys.executable, "-c", "import sys; sys.exit(3)"])
        service = TurnService(engine_saying("status"), failing, status_server)
        answer = service.handle(SPEECH, "en", "panel")
        self.assertEqual(answer["reply"], "The system is armed.")
        self.assertNotIn("audio", answer)


class WaitingQuestionsTests(unittest.TestCase):
    def test_taking_the_waiting_question_of_one_client_forgets_the_expired_ones_of_the_others(self):
        service = TurnService(engine_saying("status"), None, status_server)
        now = service._now()
        service._silence_wait["old"] = ("silence the siren", "all", now - 1.0)
        service._silence_wait["fresh"] = ("silence the siren", "all", now + 300.0)
        service._silence_wait["asking"] = ("silence the siren", "all", now + 300.0)
        taken = service._take_silence_wait("asking")
        self.assertIsNotNone(taken)                    # the one that asked gets its own question
        self.assertNotIn("old", service._silence_wait)   # an expired question of another client is dropped
        self.assertIn("fresh", service._silence_wait)    # a live one stays
        self.assertNotIn("asking", service._silence_wait)

    def test_a_question_that_expired_is_not_given_back(self):
        service = TurnService(engine_saying("status"), None, status_server)
        service._silence_wait["late"] = ("silence the siren", "all", service._now() - 5.0)
        self.assertIsNone(service._take_silence_wait("late"))
        self.assertNotIn("late", service._silence_wait)


if __name__ == "__main__":
    unittest.main()
