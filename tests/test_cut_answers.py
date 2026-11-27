# ARMOR-VOICE-AI - tests/test_cut_answers.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""A server answer cut in the middle, and token and word files saved in another encoding."""
from __future__ import annotations

import argparse
import http.client
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from armor_voice_ai import service, turn  # noqa: E402
from armor_voice_ai.wakeword import load_words  # noqa: E402


class CutAnswerTests(unittest.TestCase):
    def test_a_cut_or_garbled_server_answer_is_server_not_answering(self) -> None:
        link = turn.ServerLink("http://127.0.0.1:1", "t")
        for broken in (http.client.IncompleteRead(b"{", 100), http.client.BadStatusLine("x")):
            with mock.patch.object(turn._OPENER, "open", side_effect=broken):
                with self.assertRaises(turn.TurnError) as stop:
                    link.command("open", "en", None)
                self.assertEqual(stop.exception.code, "server_not_answering")
                link.panic_check("open", "en")   # changes nothing and never raises


class EncodingTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "voice.env"

    def read(self) -> str:
        return service._read_token(argparse.Namespace(token_file=str(self.path)))

    def test_a_token_file_with_a_byte_order_mark_is_read(self) -> None:
        self.path.write_bytes(b"\xef\xbb\xbfARMOR_VOICE_TOKEN=abc\r\n")
        self.assertEqual(self.read(), "abc")

    def test_a_token_file_in_another_encoding_is_a_message(self) -> None:
        for raw in ("ARMOR_VOICE_TOKEN=abc".encode("utf-16"), b"# se\xf1al\nARMOR_VOICE_TOKEN=abc\n"):
            self.path.write_bytes(raw)
            with self.assertRaises(SystemExit) as stop:
                self.read()
            self.assertIn("cannot be read", str(stop.exception))

    def test_a_words_file_with_a_byte_order_mark_is_the_same_as_without_one(self) -> None:
        def outcome(raw: bytes) -> str:
            self.path.write_bytes(raw)
            try:
                return repr(load_words(self.path))
            except ValueError as error:
                return f"refused: {error}"

        self.assertEqual(outcome(b"\xef\xbb\xbf{}"), outcome(b"{}"))


if __name__ == "__main__":
    unittest.main()
