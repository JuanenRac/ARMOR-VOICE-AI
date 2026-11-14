import io
import json
import socket
import threading
import unittest

from armor_voice_ai.intent import ACTIONS, QUERIES, parse_intent
from armor_voice_ai.phrases import PHRASES
from armor_voice_ai.turn import TurnError
from armor_voice_ai.wyoming import (
    ACTION_REFUSED,
    LANGUAGES,
    NOT_UNDERSTOOD,
    SERVER_UNAVAILABLE,
    Handler,
    WyomingError,
    make_server,
    read_event,
    write_event,
)


def stream_of(*lines: bytes) -> io.BytesIO:
    return io.BytesIO(b"".join(lines))


def phrase_of(intent: str, language: str = "en") -> str:
    return next(iter(PHRASES[intent][language]))


class Asker:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.asked = reply, error, []

    def __call__(self, text, language, confirmation):
        self.asked.append((text, language, confirmation))
        if self.error:
            raise self.error
        return self.reply


class EventFramingTests(unittest.TestCase):
    def test_a_header_with_its_data_inside_is_read(self):
        event = read_event(stream_of(b'{"type":"transcript","data":{"text":"time"}}\n'))
        self.assertEqual(event, ("transcript", {"text": "time"}))

    def test_data_that_follows_the_header_is_merged(self):
        extra = b'{"language":"es"}'
        header = json.dumps({"type": "transcript", "data": {"text": "hora"}, "data_length": len(extra)}).encode() + b"\n"
        self.assertEqual(read_event(stream_of(header, extra)), ("transcript", {"text": "hora", "language": "es"}))

    def test_a_payload_is_read_and_dropped(self):
        header = b'{"type":"audio-chunk","payload_length":4}\n'
        stream = stream_of(header, b"abcd", b'{"type":"describe"}\n')
        self.assertEqual(read_event(stream), ("audio-chunk", {}))
        self.assertEqual(read_event(stream), ("describe", {}))

    def test_the_end_of_the_connection_is_none(self):
        self.assertIsNone(read_event(stream_of()))

    def test_bad_events_are_refused(self):
        for raw in [b"not json\n", b"[1]\n", b'{"data":{}}\n', b'{"type":"x","data":[1]}\n', b'{"type":"x","data_length":-1}\n', b'{"type":"x","data_length":999999}\n',
                    b'{"type":"x","payload_length":9999999}\n', b'{"type":"x","payload_length":true}\n', b'{"type":"x","data_length":5}\n{"a"', b'{"type":"x","payload_length":9}\nabc',
                    b'{"type":"x","data_length":2}\n[]', b'{"type":"describe"}', b"\xff\xfe\n", b"x" * 5000 + b"\n"]:
            with self.subTest(raw=raw[:30]), self.assertRaises(WyomingError):
                read_event(stream_of(raw))

    def test_an_event_is_written_as_one_line(self):
        out = io.BytesIO()
        write_event(out, "handled", {"text": "Es la una"})
        self.assertEqual(json.loads(out.getvalue()), {"type": "handled", "data": {"text": "Es la una"}})
        self.assertEqual(out.getvalue().count(b"\n"), 1)


class HandlerTests(unittest.TestCase):
    def test_describe_lists_one_handler_in_the_eight_languages(self):
        (kind, data), = Handler(None, version="1").handle(("describe", {}))
        self.assertEqual(kind, "info")
        self.assertEqual(data["handle"][0]["models"][0]["languages"], list(LANGUAGES))
        self.assertEqual(sorted(LANGUAGES), sorted(["en", "es", "de", "fr", "it", "ja", "zh", "pt"]))

    def test_a_query_is_asked_to_the_server_and_its_speech_is_the_answer(self):
        asker = Asker({"speech": "It is one o'clock", "intent": "time"})
        (kind, data), = Handler(asker).handle(("transcript", {"text": phrase_of("time")}))
        self.assertEqual((kind, data["text"]), ("handled", "It is one o'clock"))
        self.assertEqual(asker.asked[0][1:], ("en", None))   # never with a confirmation

    def test_the_language_of_the_event_picks_the_language_of_the_ask(self):
        asker = Asker({"speech": "Ok"})
        Handler(asker).handle(("transcript", {"text": phrase_of("time", "pt"), "language": "pt-PT"}))
        self.assertEqual(asker.asked[0][1], "pt")
        Handler(asker, "de").handle(("transcript", {"text": phrase_of("time", "de"), "language": "xx"}))
        self.assertEqual(asker.asked[1][1], "de")

    def test_an_action_is_never_asked_to_the_server(self):
        for intent in sorted(ACTIONS):
            asker = Asker({"speech": "done"})
            (kind, data), = Handler(asker).handle(("transcript", {"text": phrase_of(intent)}))
            with self.subTest(intent=intent):
                self.assertEqual((kind, data["text"]), ("handled", ACTION_REFUSED["en"]))
                self.assertEqual(asker.asked, [])

    def test_words_that_are_not_a_command_are_not_handled(self):
        asker = Asker({"speech": "x"})
        for text in ["tell me a joke", "", "x" * 500, None, 5]:
            with self.subTest(text=text):
                (kind, data), = Handler(asker).handle(("transcript", {"text": text}))
                self.assertEqual((kind, data["text"]), ("not-handled", NOT_UNDERSTOOD["en"]))
        self.assertEqual(asker.asked, [])

    def test_a_server_that_fails_or_is_missing_is_not_handled(self):
        phrase = phrase_of("time")
        for ask in [Asker(error=TurnError(502, "server_not_answering")), Asker(error=OSError("down")), Asker(error=ValueError("bad")), None]:
            (kind, data), = Handler(ask).handle(("transcript", {"text": phrase}))
            self.assertEqual((kind, data["text"]), ("not-handled", SERVER_UNAVAILABLE["en"]))
        for reply in [{}, {"speech": ""}, {"speech": 5}]:
            (kind, _), = Handler(Asker(reply)).handle(("transcript", {"text": phrase}))
            self.assertEqual(kind, "not-handled")

    def test_other_events_are_ignored(self):
        self.assertEqual(Handler(None).handle(("audio-chunk", {})), [])

    def test_every_query_is_asked_in_every_language(self):
        for intent in sorted(QUERIES):
            for language in LANGUAGES:
                text = phrase_of(intent, language)
                self.assertEqual(parse_intent(text), intent)
                asker = Asker({"speech": "ok"})
                (kind, _), = Handler(asker).handle(("transcript", {"text": text, "language": language}))
                with self.subTest(intent=intent, language=language):
                    self.assertEqual(kind, "handled")

    def test_the_fixed_texts_exist_in_the_eight_languages(self):
        for table in (NOT_UNDERSTOOD, ACTION_REFUSED, SERVER_UNAVAILABLE):
            self.assertEqual(sorted(table), sorted(LANGUAGES))
            self.assertTrue(all(isinstance(value, str) and value for value in table.values()))


class ServerTests(unittest.TestCase):
    def test_it_refuses_a_public_address_unless_allowed(self):
        with self.assertRaises(ValueError):
            make_server("0.0.0.0", 0, Handler(None))

    def test_a_connection_gets_its_answers(self):
        server = make_server("127.0.0.1", 0, Handler(Asker({"speech": "One o'clock"}), version="9"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
                reader = client.makefile("rb")
                client.sendall(b'{"type":"describe"}\n')
                self.assertEqual(json.loads(reader.readline())["type"], "info")
                client.sendall(json.dumps({"type": "transcript", "data": {"text": phrase_of("time")}}).encode() + b"\n")
                self.assertEqual(json.loads(reader.readline()), {"type": "handled", "data": {"text": "One o'clock"}})
                client.sendall(b"garbage\n")
                self.assertEqual(reader.readline(), b"")   # a bad event closes the connection
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
