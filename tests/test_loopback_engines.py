"""The stand-in speech engines (tests/loopback_engine.py) and a whole spoken turn through them, in every language, without a model, a microphone or a speaker."""
import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loopback_engine
from armor_voice_ai.phrases import LANGUAGES
from armor_voice_ai.turn import NOTHING_HEARD, CommandEngine, TurnService, check_engines, pcm_from_wav

ENGINE = str(Path(loopback_engine.__file__).resolve())
SAID = {"en": "status", "es": "estado del sistema", "de": "Systemstatus", "fr": "état du système", "it": "stato del sistema", "ja": "システムの状態", "zh": "系统状态", "pt": "estado do sistema"}
ANSWER = {"en": "The system is armed.", "es": "El sistema está armado.", "de": "Das System ist scharf.", "fr": "Le système est armé.", "it": "Il sistema è inserito.", "ja": "システムは警戒中です。", "zh": "系统已布防。", "pt": "O sistema está armado."}


def stt() -> CommandEngine:
    return CommandEngine([sys.executable, ENGINE, "stt"])


def tts() -> CommandEngine:
    return CommandEngine([sys.executable, ENGINE, "tts"])


class LoopbackEngineTests(unittest.TestCase):
    def test_a_clip_reads_back_as_the_words_it_was_made_from_in_every_language(self):
        for language in LANGUAGES:
            for text in (SAID[language], ANSWER[language], NOTHING_HEARD[language]):
                self.assertEqual(loopback_engine.decode(loopback_engine.encode(text)), text, language)

    def test_silence_and_noise_read_as_no_words(self):
        self.assertEqual(loopback_engine.decode(loopback_engine.wave(bytes(32_000))), "")
        self.assertEqual(loopback_engine.decode(loopback_engine.wave(b"\x07\x01" * 4_000)), "")
        self.assertEqual(loopback_engine.decode(b"not a wave"), "")

    def test_the_engines_pass_the_check_of_the_service(self):
        report = check_engines(stt(), tts())
        self.assertEqual([row["ok"] for row in report], [True, True])
        self.assertEqual(report[0]["text_chars"], 0)          # a second of silence is no words
        self.assertTrue(report[1]["fits_a_turn"])

    def test_a_whole_turn_hears_asks_and_speaks_in_every_language(self):
        for language in LANGUAGES:
            asked = []

            def server(text, lang, confirmation, language=language, asked=asked):
                asked.append((text, lang, confirmation))
                return {"accepted": True, "executed": True, "intent": "status", "outcome": "accepted", "speech": ANSWER[language]}

            turns = TurnService(stt(), tts(), server)
            heard_audio = pcm_from_wav(loopback_engine.encode(SAID[language]))
            result = turns.handle(heard_audio, language, "panel")
            self.assertEqual(result["heard"], SAID[language], language)
            self.assertEqual(result["reply"], ANSWER[language], language)
            self.assertEqual(len(asked), 1, language)
            spoken = loopback_engine.decode(loopback_engine.wave(base64.b64decode(str(result["audio"]))))
            self.assertEqual(spoken, ANSWER[language], language)

    def test_silence_in_a_turn_is_answered_with_that_nothing_was_heard(self):
        turns = TurnService(stt(), tts(), lambda *args: {"speech": "never asked"})
        result = turns.handle(bytes(16_000), "pt", "panel")
        self.assertEqual(result["reply"], NOTHING_HEARD["pt"])


if __name__ == "__main__":
    unittest.main()
