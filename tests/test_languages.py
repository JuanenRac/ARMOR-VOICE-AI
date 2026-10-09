import unittest

from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.gateway import SPEECH_BY_LANGUAGE, handle_request
from armor_voice_ai.intent import ACTIONS, ALLOWED, ARM, DISARM, QUERIES, SENSITIVE, SILENCE, STATUS, _PHRASES, normalize_text, parse_intent
from armor_voice_ai.phrases import LANGUAGES, PHRASES
from armor_voice_ai.session import ACCEPTED, CONFIRMATION_NEEDED, CONFIRMATION_REFUSED

SECRET = b"s" * 32


class LanguageTests(unittest.TestCase):
    def test_every_phrase_is_its_own_normal_form(self):
        for intent, phrases in _PHRASES.items():
            for phrase in phrases:
                self.assertEqual(normalize_text(phrase), phrase, f"{intent}: {phrase!r} is not written in normal form, so it could never match")

    def test_no_phrase_means_two_intents(self):
        seen: dict[str, str] = {}
        for intent, phrases in _PHRASES.items():
            for phrase in phrases:
                self.assertNotIn(phrase, seen, f"{phrase!r} is both {seen.get(phrase)} and {intent}")
                seen[phrase] = intent

    def test_each_language_arms_disarms_asks_and_silences(self):
        said = {
            "de": ("Bitte, das System scharfschalten!", "Das System entschärfen", "Wie ist der Status?", "Alarm stummschalten"),
            "fr": ("S'il vous plaît, armer le système", "Désarmer l'alarme", "Quel est l'état ?", "Faire taire l'alarme"),
            "it": ("Per favore, armare il sistema", "Disattiva l'allarme", "Qual è lo stato?", "Silenzia l'allarme"),
            "ja": ("警備開始", "警備解除", "システムの状態", "警報停止"),
            "zh": ("布防", "撤防", "系统状态", "消音"),
            "es": ("Oiga, armar el sistema", "Bueno, desarma el sistema por favor", "¿Cuál es el estado?", "Silencia la alarma"),
        }
        for language, (arm, disarm, status, silence) in said.items():
            self.assertEqual([parse_intent(arm), parse_intent(disarm), parse_intent(status), parse_intent(silence)], [ARM, DISARM, STATUS, SILENCE], language)

    def test_a_filler_word_never_makes_an_unknown_phrase_known(self):
        for text in ("bitte", "per favore", "oiga", "armar la puerta", "bueno", "svp stp"):
            self.assertIsNone(parse_intent(text), text)

    def test_the_gateway_answers_in_the_language_asked(self):
        signer = ConfirmationSigner(SECRET)
        first = handle_request({"text": "armer le système", "language": "fr"}, signer)
        self.assertEqual(first["outcome"], CONFIRMATION_NEEDED)
        self.assertEqual(first["speech"], SPEECH_BY_LANGUAGE["fr"][CONFIRMATION_NEEDED])
        second = handle_request({"text": "armer le système", "language": "fr", "confirmation": first["confirmation_token"]}, signer)
        self.assertEqual((second["outcome"], second["speech"]), (ACCEPTED, "Commande acceptée"))
        self.assertEqual(handle_request({"text": "blah", "language": "de"}, signer)["speech"], "Befehl nicht erkannt")
        self.assertEqual(handle_request({"text": "arm"}, signer)["speech"], "Please confirm")   # English when none is asked

    def test_every_language_says_every_outcome(self):
        self.assertEqual(sorted(SPEECH_BY_LANGUAGE), ["de", "en", "es", "fr", "it", "ja", "zh"])
        for language, table in SPEECH_BY_LANGUAGE.items():
            for outcome in (CONFIRMATION_NEEDED, ACCEPTED, CONFIRMATION_REFUSED, ""):
                self.assertTrue(table[outcome].strip(), f"{language} {outcome!r}")

    def test_an_unknown_language_is_a_malformed_request(self):
        signer = ConfirmationSigner(SECRET)
        for bad in ("xx", 3, None, ["en"]):
            self.assertEqual(handle_request({"text": "status", "language": bad}, signer), {"accepted": False, "error": "invalid request fields"})


class EveryCommandTests(unittest.TestCase):
    def test_every_command_is_said_in_every_language_and_is_understood_as_itself(self):
        self.assertEqual(set(PHRASES), set(ALLOWED))
        for intent, by_language in PHRASES.items():
            self.assertEqual(tuple(by_language), LANGUAGES, intent)
            for language, phrases in by_language.items():
                self.assertGreaterEqual(len(phrases), 2, f"{intent} {language}")
                for phrase in phrases:
                    self.assertEqual(parse_intent(phrase), intent, f"{language}: {phrase!r}")

    def test_the_commands_that_ask_and_those_that_do_are_told_apart_and_only_arm_and_disarm_are_confirmed(self):
        self.assertFalse(QUERIES & ACTIONS)
        self.assertEqual(SENSITIVE, {ARM, DISARM})
        self.assertGreaterEqual(len(ALLOWED), 15)

    def test_what_is_heard_with_polite_words_and_without_accents_is_understood(self):
        for heard, intent in (("Por favor, ¿qué hora es?", "time"), ("oiga cuantas alarmas hay", "alarms"), ("Hey, turn on the lights please", "lights_on"), ("Quel est l'état des caméras ?", None),
                              ("état des caméras", "cameras"), ("Wie viel Strom verbrauche ich?", "electrical"), ("什么", None), ("電気を消して", "lights_off")):
            self.assertEqual(parse_intent(heard), intent, heard)

    def test_a_phrase_that_is_part_of_a_command_is_not_enough(self):
        for heard in ("lights", "turn the lights", "alarm", "estado de", "open the garage", "ayuda por favor ahora"):
            self.assertIsNone(parse_intent(heard), heard)


if __name__ == "__main__":
    unittest.main()