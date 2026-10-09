import json
import threading
import unittest
import urllib.error
import urllib.request

from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.service import make_server

TOKEN = "t" * 24


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32))
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, method, path, body=None, token=TOKEN, raw=None):
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json", **({"X-Armor-Voice-Token": token} if token is not None else {})})
        try:
            with urllib.request.urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_the_health_check_needs_no_token(self):
        self.assertEqual(self.call("GET", "/healthz", token=None), (200, {"ok": True, "service": "armor-voice"}))

    def test_a_command_needs_the_token(self):
        self.assertEqual(self.call("POST", "/v1/command", {"text": "status"}, token=None)[0], 401)
        self.assertEqual(self.call("POST", "/v1/command", {"text": "status"}, token="x" * 24)[0], 401)

    def test_the_two_turn_flow_over_http_in_the_language_asked(self):
        status, first = self.call("POST", "/v1/command", {"text": "armer le système", "language": "fr"})
        self.assertEqual((status, first["outcome"], first["speech"]), (200, "confirmation-needed", "Veuillez confirmer"))
        status, second = self.call("POST", "/v1/command", {"text": "armer le système", "language": "fr", "confirmation": first["confirmation_token"]})
        self.assertEqual((status, second["accepted"], second["intent"]), (200, True, "arm"))
        self.assertEqual(self.call("POST", "/v1/command", {"text": "status", "language": "es"})[1]["intent"], "status")

    def test_what_is_not_understood_is_refused_and_a_bad_request_is_not_guessed_at(self):
        status, answer = self.call("POST", "/v1/command", {"text": "open the garage"})
        self.assertEqual((status, answer["accepted"]), (200, False))
        self.assertEqual(self.call("POST", "/v1/command", raw=b"not json")[0], 400)
        self.assertEqual(self.call("POST", "/v1/command", {"text": "x" * 3000})[0], 413)
        self.assertEqual(self.call("POST", "/v1/command", {"text": "status", "extra": 1})[1], {"accepted": False, "error": "invalid request shape"})
        self.assertEqual(self.call("POST", "/nope", {})[0], 404)

    def test_a_short_token_is_not_accepted_and_the_gateway_listens_on_loopback_only(self):
        with self.assertRaises(ValueError):
            make_server("127.0.0.1", 0, "short", ConfirmationSigner(b"s" * 32))
        from armor_voice_ai.service import main
        with self.assertRaises(SystemExit):
            main(["--host", "0.0.0.0", "--port", "0"])


if __name__ == "__main__":
    unittest.main()
