import unittest

from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.gateway import SPEECH_BY_LANGUAGE, handle_request
from armor_voice_ai.intent import ARM, DISARM, SILENCE, STATUS, _PHRASES, normalize_text, parse_intent
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


if __name__ == "__main__":
    unittest.main()
