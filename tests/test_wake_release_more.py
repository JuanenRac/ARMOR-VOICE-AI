"""The two ways out of the release tool that nobody took: a release without a signature (the manifest alone, as the manual step expects) and a file the tool cannot read."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from armor_voice_ai import wake_release as release
from test_wake_models import model, names


def run_main(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = release.main(list(arguments))
    return code, out.getvalue(), err.getvalue()


class ReleaseWaysOutTest(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.dir = Path(holder.name)
        self.models = self.dir / "models"
        self.models.mkdir()
        (self.models / "hey_armor_en.onnx").write_bytes(model())

    def test_without_sign_the_models_and_the_manifest_are_written_and_no_signature(self):
        out = self.dir / "out"
        code, text, _ = run_main("--models", str(self.models), "--version", "0.3.6", "--out", str(out))
        self.assertEqual(code, 0, text)
        self.assertEqual(names(out), ["armor-voice-wake-models-0.3.6.manifest", "hey_armor_en.onnx"])

    def test_a_signer_that_is_given_but_not_asked_for_is_not_run(self):
        marker = self.dir / "ran"
        signer = self.dir / "signer.py"
        signer.write_text(f"open({str(marker)!r}, 'w').close()\nprint('ab' * 64)\n", encoding="utf-8")
        out = self.dir / "out"
        code, _, _ = run_main("--models", str(self.models), "--version", "0.3.6", "--out", str(out), "--signer", f'python "{signer.as_posix()}"')
        self.assertEqual(code, 0)
        self.assertFalse(marker.exists())
        self.assertFalse(any(name.endswith(".sig2") for name in names(out)))

    def test_a_words_file_that_cannot_be_read_is_a_message_and_not_a_trace(self):
        code, text, err = run_main("--models", str(self.models), "--version", "0.3.6", "--out", str(self.dir / "out"), "--words", str(self.dir / "no_such_words.json"))
        self.assertEqual(code, 1)
        self.assertEqual(text, "")
        self.assertTrue(err.strip())
        self.assertNotIn("Traceback", err)
        self.assertFalse((self.dir / "out").exists())


if __name__ == "__main__":
    unittest.main()
