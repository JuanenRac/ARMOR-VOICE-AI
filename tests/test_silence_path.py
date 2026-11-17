"""The shared path of a spoken order to silence the alarm (ARMOR-COMMON conformance/voice/silence_path.json), played against the turn service for every confirmation mode."""
import json
import unittest
from pathlib import Path

from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.silence_policy import ChallengeGuard, PinGuard
from armor_voice_ai.turn import TurnService

VECTOR = Path(__file__).resolve().parents[2] / "ARMOR-COMMON" / "conformance" / "voice" / "silence_path.json"
SPEECH = b"\x01\x00" * 8_000
PIN = "4821"
PROOFS = {"yes": "yes", "pin": "4 8 2 1", "challenge": "4 7"}


class Said:
    def __init__(self, *lines):
        self.lines = list(lines)

    def run(self, data, language, limit, deadline=None):
        return self.lines.pop(0).encode("utf-8")


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Server:
    """Answers the first ask as the path says and records every ask."""

    def __init__(self, first_answer):
        self.first_answer = first_answer
        self.asked = []

    def __call__(self, text, language, confirmation):
        self.asked.append((text, confirmation))
        done = {"accepted": True, "executed": True, "intent": "silence", "outcome": "accepted", "speech": "Alarms acknowledged."}
        if self.first_answer == "accepted" or confirmation is not None:
            return done
        answer = {"accepted": False, "executed": False, "intent": "silence", "outcome": "confirmation-needed", "speech": "Say it again to confirm."}
        if self.first_answer == "token":
            answer["confirmation_token"] = "server-token"
        return answer


@unittest.skipUnless(VECTOR.is_file(), "ARMOR-COMMON is not checked out next to this repository")
class SilencePathTests(unittest.TestCase):
    def test_every_path_of_the_shared_vector(self):
        vector = json.loads(VECTOR.read_text(encoding="utf-8"))
        original = vector["original"]
        for path in vector["paths"]:
            with self.subTest(path["name"]):
                clock = Clock()
                signer = ConfirmationSigner(b"s" * 32, now=clock)
                server = Server(path["first_answer"])
                lines = [original] + ([PROOFS[path["proof"]]] if path["proof"] else [])
                service = TurnService(Said(*lines), None, server, now=clock, pin_guard=PinGuard(PIN, now=clock),
                                      challenge_guard=ChallengeGuard(now=clock, draw=lambda: 47), signer=signer)
                policy = {"silence_confirmation": path["mode"]}
                first = service.handle(SPEECH, "en", "panel", policy, path["panel"])
                if path["proof"]:
                    clock.now += 1
                    second = service.handle(SPEECH, "en", "panel", policy, path["panel"])
                    self.assertTrue(first and second)
                self.assertEqual(len(server.asked), len(path["asks"]))
                for (text, confirmation), expected in zip(server.asked, path["asks"], strict=True):
                    self.assertEqual(text, original, "the order that is asked is the one first said, never the proof")
                    kind = expected["confirmation"]
                    if kind == "none":
                        self.assertIsNone(confirmation)
                    elif kind == "server_token":
                        self.assertEqual(confirmation, "server-token")
                    else:
                        self.assertEqual(signer.verify(confirmation, "silence", expected["subject"]), "valid", f"the confirmation is not good for {expected['subject']}")

    def test_the_proof_is_never_kept_as_the_order_for_one_more_confirmation(self):
        """A server that asks for a confirmation after the person's yes gets the ORDER again, not the yes."""
        clock = Clock()
        asked = []

        def server(text, language, confirmation):
            asked.append((text, confirmation))
            if confirmation == "t2":
                return {"accepted": True, "executed": True, "intent": "silence", "outcome": "accepted", "speech": "Done."}
            return {"accepted": False, "executed": False, "intent": "silence", "outcome": "confirmation-needed", "confirmation_token": "t2" if confirmation == "t1" else "t1", "speech": "Once more?"}

        service = TurnService(Said("silence the alarm", "yes", "yes"), None, server, now=clock, signer=ConfirmationSigner(b"s" * 32, now=clock))
        policy = {"silence_confirmation": "double_turn"}
        for _ in range(3):
            service.handle(SPEECH, "en", "panel", policy)
            clock.now += 1
        self.assertTrue(all(text == "silence the alarm" for text, _ in asked), asked)
        self.assertEqual(asked[-1], ("silence the alarm", "t2"))


if __name__ == "__main__":
    unittest.main()
