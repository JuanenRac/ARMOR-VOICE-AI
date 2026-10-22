import json
import logging
import threading
import unittest
import urllib.request

from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.gateway import handle_request
from armor_voice_ai.service import make_server
from armor_voice_ai.silence_policy import (DOUBLE_TURN, LOCKOUT_S, MAX_PIN_ATTEMPTS, OFF, PIN, PinGuard, mode_from_header, mode_from_policy, spoken_digits)
from armor_voice_ai.intent import normalize_text
from armor_voice_ai.turn import TurnService

SPEECH = b"\x01\x00" * 8_000
TOKEN = "t" * 24
SECRET_PIN = "4821"


class Said:
    """A speech engine that hears the next thing on a list."""

    def __init__(self, *lines):
        self.lines = list(lines)

    def run(self, data, language, limit, deadline=None):
        return self.lines.pop(0).encode("utf-8")


class Server:
    def __init__(self):
        self.asked = []

    def __call__(self, text, language, confirmation):
        self.asked.append((text, confirmation))
        return {"accepted": True, "executed": True, "intent": "silence", "outcome": "accepted", "speech": "Alarms acknowledged."}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def turns(*heard, guard=None, clock=None):
    server = Server()
    clock = clock or Clock()
    return TurnService(Said(*heard), None, server, now=clock, pin_guard=guard or PinGuard(SECRET_PIN, now=clock)), server, clock


class PolicyParsingTests(unittest.TestCase):
    def test_a_missing_policy_is_off_and_a_known_mode_is_kept(self):
        self.assertEqual(mode_from_policy(None), OFF)
        self.assertEqual(mode_from_policy({}), OFF)
        self.assertEqual(mode_from_policy({"silence_confirmation": "off"}), OFF)
        self.assertEqual(mode_from_policy({"silence_confirmation": "pin"}), PIN)
        self.assertEqual(mode_from_policy({"silence_confirmation": "double_turn"}), DOUBLE_TURN)
        self.assertEqual(mode_from_header(None), OFF)
        self.assertEqual(mode_from_header('{"silence_confirmation":"pin"}'), PIN)

    def test_a_policy_that_is_there_but_broken_never_switches_the_protection_off(self):
        for broken in ({"silence_confirmation": "maybe"}, {"silence_confirmation": 3}, "pin", ["pin"], 7):
            self.assertEqual(mode_from_policy(broken), DOUBLE_TURN, broken)
        self.assertEqual(mode_from_header("{not json"), DOUBLE_TURN)
        self.assertEqual(mode_from_header('{"silence_confirmation":"' + "x" * 400 + '"}'), DOUBLE_TURN)


class OffTests(unittest.TestCase):
    def test_without_a_policy_silence_is_accepted_at_once(self):
        service, server, _ = turns("silence the alarm")
        answer = service.handle(SPEECH, "en", "panel")
        self.assertEqual(answer["reply"], "Alarms acknowledged.")
        self.assertEqual(server.asked, [("silence the alarm", None)])

    def test_off_asked_for_is_the_same(self):
        service, server, _ = turns("silence the alarm")
        service.handle(SPEECH, "en", "panel", {"silence_confirmation": "off"})
        self.assertEqual(len(server.asked), 1)


class DoubleTurnTests(unittest.TestCase):
    policy = {"silence_confirmation": "double_turn"}

    def test_the_first_turn_asks_and_the_server_is_not_asked(self):
        service, server, _ = turns("silence the alarm")
        answer = service.handle(SPEECH, "en", "panel", self.policy)
        self.assertIn("yes", answer["reply"])
        self.assertEqual(server.asked, [])

    def test_a_yes_in_time_passes_the_silence_on(self):
        service, server, _ = turns("silence the alarm", "yes please")
        service.handle(SPEECH, "en", "panel", self.policy)
        answer = service.handle(SPEECH, "en", "panel", self.policy)
        self.assertEqual(answer["reply"], "Alarms acknowledged.")
        self.assertEqual(server.asked, [("silence the alarm", None)])

    def test_a_no_cancels_and_a_late_yes_does_nothing(self):
        service, server, _ = turns("silence the alarm", "no")
        service.handle(SPEECH, "en", "panel", self.policy)
        self.assertEqual(service.handle(SPEECH, "en", "panel", self.policy)["reply"], "Cancelled.")
        self.assertEqual(server.asked, [])
        late, server, clock = turns("silence the alarm", "yes")
        late.handle(SPEECH, "en", "panel", self.policy)
        clock.now += 60
        late.handle(SPEECH, "en", "panel", self.policy)   # the "yes" is now a command on its own, which is not one
        self.assertEqual([call for call in server.asked if call[0] == "silence the alarm"], [])

    def test_the_confirmation_belongs_to_the_panel_that_was_asked(self):
        service, server, _ = turns("silence the alarm", "yes")
        service.handle(SPEECH, "en", "panel-1", self.policy)
        service.handle(SPEECH, "en", "panel-2", self.policy)
        self.assertEqual([call for call in server.asked if call[0] == "silence the alarm"], [])

    def test_it_works_in_the_other_languages(self):
        for language, first, yes in (("es", "silenciar la alarma", "sí"), ("de", "alarm stummschalten", "ja"), ("pt", "silenciar o alarme", "sim"), ("fr", "silence alarme", "oui"), ("it", "silenzia allarme", "sì"), ("ja", "警報停止", "はい"), ("zh", "消音", "是")):
            service, server, _ = turns(first, yes)
            service.handle(SPEECH, language, "panel", self.policy)
            if server.asked:
                self.fail(f"{language}: the server was asked before the confirmation")
            service.handle(SPEECH, language, "panel", self.policy)
            self.assertEqual(len(server.asked), 1, language)

    def test_other_commands_are_not_slowed_down(self):
        service, server, _ = turns("status")
        service.handle(SPEECH, "en", "panel", self.policy)
        self.assertEqual(len(server.asked), 1)


class PinTests(unittest.TestCase):
    policy = {"silence_confirmation": "pin"}

    def ask(self, *heard, guard=None):
        service, server, clock = turns("silence the alarm", *heard, guard=guard)
        first = service.handle(SPEECH, "en", "panel", self.policy)
        return service, server, clock, first

    def test_the_first_turn_asks_for_the_pin_and_asks_nothing_of_the_server(self):
        _, server, _, first = self.ask()
        self.assertIn("PIN", first["reply"])
        self.assertEqual(server.asked, [])

    def test_the_right_pin_spoken_as_words_or_digits_passes_the_silence_on(self):
        for said in ("four eight two one", "4 8 2 1", "my pin is 4821", "4821"):
            service, server, _, _ = self.ask(said)
            answer = service.handle(SPEECH, "en", "panel", self.policy)
            self.assertEqual(answer["reply"], "Alarms acknowledged.", said)
            self.assertEqual(server.asked, [("silence the alarm", None)], said)

    def test_the_pin_is_never_echoed_back(self):
        service, _, _, _ = self.ask("four eight two one")
        self.assertEqual(service.handle(SPEECH, "en", "panel", self.policy)["heard"], "")
        service, _, _, _ = self.ask("nine nine nine nine")
        self.assertEqual(service.handle(SPEECH, "en", "panel", self.policy)["heard"], "")

    def test_a_wrong_pin_does_nothing_and_says_so(self):
        service, server, _, _ = self.ask("one two three four")
        answer = service.handle(SPEECH, "en", "panel", self.policy)
        self.assertIn("not right", answer["reply"])
        self.assertEqual(server.asked, [])

    def test_three_wrong_pins_lock_every_panel_even_for_the_right_pin_until_the_time_is_up(self):
        clock = Clock()
        guard = PinGuard(SECRET_PIN, now=clock)
        lines = ["silence the alarm"] + ["1 1 1 1", "silence the alarm"] * (MAX_PIN_ATTEMPTS - 1) + ["1 1 1 1", "silence the alarm", "4 8 2 1"]
        service, server, _ = turns(*lines, guard=guard, clock=clock)
        service.handle(SPEECH, "en", "a", self.policy)
        for _ in range(MAX_PIN_ATTEMPTS - 1):
            service.handle(SPEECH, "en", "a", self.policy)    # wrong
            service.handle(SPEECH, "en", "a", self.policy)    # silence again
        locked = service.handle(SPEECH, "en", "a", self.policy)   # the third wrong one
        self.assertIn("locked", locked["reply"])
        again = service.handle(SPEECH, "en", "b", self.policy)    # another panel asks to silence
        self.assertIn("locked", again["reply"])
        self.assertEqual(server.asked, [])
        clock.now += LOCKOUT_S + 1
        self.assertFalse(guard.locked)

    def test_the_lock_comes_off_after_the_time_and_the_right_pin_works_again(self):
        clock = Clock()
        guard = PinGuard(SECRET_PIN, now=clock)
        for _ in range(MAX_PIN_ATTEMPTS):
            guard.check("0000")
        self.assertEqual(guard.check(SECRET_PIN), "locked")
        clock.now += LOCKOUT_S + 1
        self.assertEqual(guard.check(SECRET_PIN), "ok")

    def test_a_right_pin_clears_the_count_of_wrong_ones(self):
        guard = PinGuard(SECRET_PIN)
        guard.check("0000")
        guard.check("0000")
        self.assertEqual(guard.check(SECRET_PIN), "ok")
        self.assertEqual(guard.check("0000"), "wrong")

    def test_without_a_pin_set_up_nothing_is_silenced_by_voice(self):
        service, server, _ = turns("silence the alarm", guard=PinGuard(None))
        answer = service.handle(SPEECH, "en", "panel", self.policy)
        self.assertIn("not set up", answer["reply"])
        self.assertEqual(server.asked, [])

    def test_something_that_is_not_a_pin_is_a_new_command(self):
        service, server, _, _ = self.ask("status")
        service.handle(SPEECH, "en", "panel", self.policy)
        self.assertEqual(server.asked, [("status", None)])

    def test_a_no_cancels(self):
        service, server, _, _ = self.ask("cancel")
        self.assertEqual(service.handle(SPEECH, "en", "panel", self.policy)["reply"], "Cancelled.")
        self.assertEqual(server.asked, [])

    def test_the_pin_never_reaches_the_log(self):
        with self.assertLogs(level=logging.DEBUG) as captured:
            logging.getLogger("probe").debug("keep the capture open")
            service, _, _, _ = self.ask("four eight two one")
            service.handle(SPEECH, "en", "panel", self.policy)
        self.assertNotIn(SECRET_PIN, "\n".join(captured.output))
        with self.assertRaises(ValueError) as refused:
            PinGuard("12")
        self.assertNotIn("12", str(refused.exception).replace("4 to 12", ""))

    def test_a_pin_must_be_four_to_twelve_digits(self):
        for bad in ("123", "1" * 13, "12a4", "１２３４"):
            with self.assertRaises(ValueError):
                PinGuard(bad)


class SpokenDigitsTests(unittest.TestCase):
    def digits(self, text, language):
        return spoken_digits(normalize_text(text), language)

    def test_digit_words_in_every_language(self):
        cases = {"en": "one two three four", "es": "uno dos tres cuatro", "de": "eins zwei drei vier", "fr": "un deux trois quatre", "it": "uno due tre quattro", "pt": "um dois três quatro"}
        for language, text in cases.items():
            self.assertEqual(self.digits(text, language), "1234", language)
        self.assertEqual(self.digits("fünf sechs sieben acht neun null", "de"), "567890")

    def test_chinese_and_japanese_numerals_and_fullwidth_digits(self):
        self.assertEqual(self.digits("一二三四", "zh"), "1234")
        self.assertEqual(self.digits("いち に さん よん", "ja"), "1234")
        self.assertEqual(self.digits("１２３４", "en"), "1234")


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.signer = ConfirmationSigner(b"s" * 32)

    def test_no_policy_keeps_the_old_behaviour(self):
        self.assertTrue(handle_request({"text": "silence"}, self.signer)["accepted"])

    def test_double_turn_needs_the_token_of_the_service(self):
        first = handle_request({"text": "silence", "policy": {"silence_confirmation": "double_turn"}}, self.signer)
        self.assertFalse(first["accepted"])
        self.assertTrue(first["requires_confirmation"])
        second = handle_request({"text": "silence", "confirmation": first["confirmation_token"], "policy": {"silence_confirmation": "double_turn"}}, self.signer)
        self.assertTrue(second["accepted"])

    def test_pin_needs_the_right_pin_and_counts_the_wrong_ones(self):
        guard = PinGuard(SECRET_PIN)
        policy = {"silence_confirmation": "pin"}
        self.assertEqual(handle_request({"text": "silence", "policy": policy}, self.signer, None, guard)["outcome"], "pin-needed")
        self.assertEqual(handle_request({"text": "silence", "policy": policy, "pin": "0000"}, self.signer, None, guard)["outcome"], "pin-refused")
        self.assertTrue(handle_request({"text": "silence", "policy": policy, "pin": SECRET_PIN}, self.signer, None, guard)["accepted"])
        for _ in range(MAX_PIN_ATTEMPTS):
            handle_request({"text": "silence", "policy": policy, "pin": "0000"}, self.signer, None, guard)
        self.assertFalse(handle_request({"text": "silence", "policy": policy, "pin": SECRET_PIN}, self.signer, None, guard)["accepted"])

    def test_the_pin_is_not_in_the_audit_line_and_not_in_the_answer(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / "audit.log"
            answer = handle_request({"text": "silence", "policy": {"silence_confirmation": "pin"}, "pin": SECRET_PIN}, self.signer, audit, PinGuard(SECRET_PIN))
            self.assertNotIn(SECRET_PIN, json.dumps(answer))
            self.assertNotIn(SECRET_PIN, audit.read_text(encoding="utf-8"))

    def test_a_broken_policy_is_the_second_turn_not_nothing(self):
        self.assertFalse(handle_request({"text": "silence", "policy": "pin"}, self.signer)["accepted"])

    def test_the_other_commands_are_not_affected(self):
        self.assertTrue(handle_request({"text": "status", "policy": {"silence_confirmation": "pin"}}, self.signer)["accepted"])


class HttpPolicyTests(unittest.TestCase):
    def test_the_policy_header_of_a_turn_is_read(self):
        asked = Server()
        service = TurnService(Said("silence the alarm", "silence the alarm"), None, asked, pin_guard=PinGuard(SECRET_PIN))
        server = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), None, service, service.pin_guard)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"

            def post(policy):
                headers = {"Content-Type": "audio/L16;rate=16000", "X-Armor-Voice-Token": TOKEN, "X-Armor-Language": "en", "X-Armor-Client": "panel"}
                if policy is not None:
                    headers["X-Armor-Policy"] = policy
                with urllib.request.urlopen(urllib.request.Request(base + "/v1/turn", data=SPEECH, method="POST", headers=headers), timeout=10) as reply:
                    return json.loads(reply.read())

            self.assertIn("PIN", post('{"silence_confirmation":"pin"}')["reply"])
            self.assertEqual(asked.asked, [])
            self.assertEqual(post(None)["reply"], "Alarms acknowledged.")   # no header: off, as before
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
