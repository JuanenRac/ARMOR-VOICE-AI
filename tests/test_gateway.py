import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")
from armor_voice_ai.confirmation import EXPIRED, INVALID, REPLAYED, VALID, WRONG_INTENT, ConfirmationSigner
from armor_voice_ai.gateway import handle_request
from armor_voice_ai.intent import normalize, normalize_text, parse_intent
from armor_voice_ai.session import ACCEPTED, CONFIRMATION_NEEDED, CONFIRMATION_REFUSED, evaluate


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def signer(clock=None):
    return ConfirmationSigner(secret=b"k" * 32, now=clock or Clock())


class IntentTests(unittest.TestCase):
    def test_normalizes_whitespace_case_accents_and_filler(self):
        self.assertEqual(normalize("  STATUS "), "status")
        self.assertEqual(normalize("Please, arm the system!"), "arm")
        self.assertEqual(normalize("Armar el sistema, por favor"), "arm")
        self.assertEqual(normalize("¿Cuál es el estado?"), "status")
        self.assertEqual(normalize_text("ＡＲＭ"), "arm")  # full-width letters from some STT pipelines

    def test_unknown_or_unbounded_phrases_are_not_understood(self):
        for text in ("delete all recordings", "arm and delete", "", "   ", "a" * 500, "rm -rf /", "armed", "disarming now"):
            self.assertIsNone(parse_intent(text), text)
            with self.assertRaises(ValueError):
                normalize(text)
        for value in (None, 5, [], {}):
            self.assertIsNone(parse_intent(value))

    def test_intents_map_in_both_languages(self):
        for text, intent in [("disarm", "disarm"), ("desarmar", "disarm"), ("silence the alarm", "silence"), ("silenciar", "silence")]:
            self.assertEqual(parse_intent(text), intent)


class ConfirmationTests(unittest.TestCase):
    def test_a_token_works_once_for_its_own_intent(self):
        s = signer()
        token = s.issue("arm")
        self.assertEqual(s.verify(token, "arm"), VALID)
        self.assertEqual(s.verify(token, "arm"), REPLAYED)

    def test_a_token_that_could_still_be_replayed_is_never_forgotten_to_make_room(self):
        from armor_voice_ai import confirmation
        clock = Clock()
        s = signer(clock)
        first = s.issue("arm")
        self.assertEqual(s.verify(first, "arm"), VALID)
        # a flood of other tokens used within the same half minute does not push the first one out: it is still refused as a replay
        original_limit = confirmation._USED_LIMIT
        confirmation._USED_LIMIT = 50
        try:
            outcomes = [s.verify(s.issue("arm"), "arm") for _ in range(120)]
            self.assertEqual(outcomes.count(VALID), 49)           # the room that was left
            self.assertEqual(set(outcomes) - {VALID}, {INVALID})   # the others are refused, none replaces a nonce that is still good
            self.assertEqual(s.verify(first, "arm"), REPLAYED)
            # once the tokens have expired their nonces are forgotten, and the room is there again
            clock.now += s.ttl_s + 1
            self.assertEqual(s.verify(s.issue("arm"), "arm"), VALID)
        finally:
            confirmation._USED_LIMIT = original_limit

    def test_a_token_cannot_be_used_for_another_intent(self):
        s = signer()
        self.assertEqual(s.verify(s.issue("arm"), "disarm"), WRONG_INTENT)

    def test_a_token_expires(self):
        clock = Clock()
        s = signer(clock)
        token = s.issue("arm")
        clock.now += s.ttl_s + 1
        self.assertEqual(s.verify(token, "arm"), EXPIRED)

    def test_forged_altered_and_malformed_tokens_are_invalid(self):
        s, other = signer(), ConfirmationSigner(secret=b"z" * 32, now=Clock())
        token = s.issue("arm")
        body, signature = token.split(".")
        for bad in (other.issue("arm"), body + ".0", body[:-2] + "AA." + signature, "x", "", "a.b.c", None, 5, body + "." + "0" * 64):
            self.assertEqual(s.verify(bad, "arm"), INVALID, repr(bad))

    def test_the_secret_must_be_long_enough(self):
        with self.assertRaises(ValueError):
            ConfirmationSigner(secret=b"short")


class ConfirmationHardeningTests(unittest.TestCase):
    def test_a_token_with_characters_outside_ascii_is_refused_not_a_crash(self):
        s = signer()
        for token in ["ñandú.abc", "abc.déf", "😀.😀", "a.bé", "\u0000.\u0000"]:
            self.assertEqual(s.verify(token, "arm"), INVALID, token)

    def test_two_requests_with_the_same_token_at_the_same_time_cannot_both_pass(self):
        import threading
        s = signer()
        token = s.issue("arm")
        results = []
        barrier = threading.Barrier(8)

        def attempt():
            barrier.wait()
            results.append(s.verify(token, "arm"))
        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(VALID), 1, results)
        self.assertEqual(results.count(REPLAYED), 7, results)


class SessionTests(unittest.TestCase):
    def test_status_needs_no_confirmation(self):
        decision = evaluate("status", signer())
        self.assertEqual((decision.accepted, decision.requires_confirmation, decision.outcome), (True, False, ACCEPTED))

    def test_arm_is_not_accepted_on_the_first_turn_and_returns_a_token(self):
        decision = evaluate("arm", signer())
        self.assertEqual((decision.accepted, decision.requires_confirmation, decision.outcome), (False, True, CONFIRMATION_NEEDED))
        self.assertTrue(decision.confirmation_token)

    def test_the_second_turn_with_the_issued_token_is_accepted(self):
        s = signer()
        token = evaluate("arm the system", s).confirmation_token
        self.assertTrue(evaluate("arm", s, token).accepted)

    def test_a_wrong_or_missing_confirmation_never_accepts(self):
        s = signer()
        token = evaluate("arm", s).confirmation_token
        for attempt in ("nonsense", token + "x", None):
            self.assertFalse(evaluate("disarm", s, attempt).accepted)
        self.assertEqual(evaluate("disarm", s, token).outcome, CONFIRMATION_REFUSED)

    def test_an_unknown_phrase_is_refused_outright(self):
        decision = evaluate("erase data", signer())
        self.assertFalse(decision.accepted)
        self.assertIsNone(decision.intent)


class GatewayTests(unittest.TestCase):
    def test_sensitive_intent_needs_confirmation(self):
        answer = handle_request({"text": "arm"}, signer())
        self.assertTrue(answer["requires_confirmation"])
        self.assertIn("confirmation_token", answer)
        self.assertEqual(answer["speech"], "Please confirm")

    def test_unknown_intent_is_rejected(self):
        answer = handle_request({"text": "erase data"}, signer())
        self.assertFalse(answer["accepted"])
        self.assertNotIn("confirmation_token", answer)

    def test_a_caller_cannot_claim_a_confirmation(self):
        answer = handle_request({"text": "arm", "confirmed": True}, signer())
        self.assertFalse(answer["accepted"])
        self.assertIn("not accepted", answer["error"])

    def test_the_full_two_turn_flow(self):
        s = signer()
        token = handle_request({"text": "disarm"}, s)["confirmation_token"]
        done = handle_request({"text": "disarm", "confirmation": token}, s)
        self.assertTrue(done["accepted"])
        self.assertFalse(handle_request({"text": "disarm", "confirmation": token}, s)["accepted"])  # replay

    def test_malformed_requests_are_refused(self):
        for request in ([], "x", {"text": 5}, {"text": "arm", "confirmation": 5}, {"text": "arm", "extra": 1}, {}):
            self.assertFalse(handle_request(request, signer())["accepted"], request)

    def test_the_audit_records_the_decision_but_not_the_words(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "voice.log"
            handle_request({"text": "Arm the system please"}, signer(), audit)
            line = audit.read_text(encoding="utf-8")
            entry = json.loads(line)
            self.assertEqual((entry["intent"], entry["outcome"]), ("arm", "confirmation-needed"))
            self.assertEqual(len(entry["transcript_sha256"]), 64)
            self.assertNotIn("please", line.lower())

    def test_an_unwritable_audit_path_never_breaks_a_command(self):
        answer = handle_request({"text": "status"}, signer(), Path("/nonexistent-dir/voice.log"))
        self.assertTrue(answer["accepted"])


if __name__ == "__main__":
    unittest.main()
