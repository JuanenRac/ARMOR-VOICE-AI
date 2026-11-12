import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from armor_voice_ai import wake_model_check as check
from armor_voice_ai import wake_release as release
from armor_voice_ai.wakeword import parse_words

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "wake_words.example.json"


# A tiny protocol buffer writer, just enough to build the parts of an ONNX model that the check reads.
def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field(number, payload):
    if isinstance(payload, int):
        return varint(number << 3) + varint(payload)
    if isinstance(payload, str):
        payload = payload.encode()
    return varint(number << 3 | 2) + varint(len(payload)) + payload


def value_info(name, dims):
    shape = b"".join(field(1, field(1, d) if isinstance(d, int) else field(2, d)) for d in dims)
    return field(1, name) + field(2, field(1, field(1, 1) + field(2, shape)))


def model(inputs=(("x", [1, 16, 96]),), outputs=(("y", [1, 1]),), initializers=(), padding=9000):
    graph = b"".join(field(11, value_info(n, d)) for n, d in inputs) + b"".join(field(12, value_info(n, d)) for n, d in outputs)
    graph += b"".join(field(5, i) for i in initializers) + field(2, "g")
    return field(1, 8) + field(7, graph) + field(8, b"\x00" * padding)


def names(path_folder):
    return sorted(p.name for p in path_folder.iterdir())


class ShapeTests(unittest.TestCase):
    def test_a_good_model_passes_with_batch_one_or_open(self):
        for batch in (1, "batch"):
            report = check.check_bytes(model(inputs=(("x", [batch, 16, 96]),), outputs=(("y", [batch, 1]),)), "hey_armor_en.onnx", "hey_armor_en.onnx")
            self.assertTrue(report.ok, report.problems)
            self.assertEqual(len(report.sha256), 64)

    def test_wrong_shapes_are_refused(self):
        cases = {
            "input window": model(inputs=(("x", [1, 8, 96]),)),
            "input features": model(inputs=(("x", [1, 16, 40]),)),
            "input rank": model(inputs=(("x", [1, 16]),)),
            "batch": model(inputs=(("x", [4, 16, 96]),)),
            "output last": model(outputs=(("y", [1, 2]),)),
            "output rank": model(outputs=(("y", [1]),)),
            "two inputs": model(inputs=(("x", [1, 16, 96]), ("z", [1, 16, 96]))),
            "no outputs": model(outputs=()),
        }
        for label, content in cases.items():
            with self.subTest(label):
                self.assertFalse(check.check_bytes(content, "a_b.onnx", None).ok)

    def test_weights_listed_as_inputs_do_not_count_as_inputs(self):
        weight = field(8, "w") + field(1, 1)
        content = model(inputs=(("x", [1, 16, 96]), ("w", [10, 10])), initializers=(weight,))
        self.assertTrue(check.check_bytes(content, "a_b.onnx", None).ok)

    def test_external_weights_are_refused(self):
        external = field(8, "w") + field(14, 1)
        report = check.check_bytes(model(initializers=(external,)), "a_b.onnx", None)
        self.assertTrue(any("external" in p for p in report.problems))

    def test_not_an_onnx_file(self):
        for content in (b"x" * 9000, b"\xff" * 9000, field(1, 8) + b"\x00" * 9000, field(7, b"\x0a\xff\x7f") + b"\x00" * 9000):
            with self.subTest(content[:6]):
                self.assertFalse(check.check_bytes(content, "a_b.onnx", None).ok)

    def test_truncated_and_odd_protobuf(self):
        good = model()
        self.assertFalse(check.check_bytes(good[:-5], "a_b.onnx", None).ok)
        for bad in (b"\x80", b"\x80" * 12, b"\x00\x01", b"\x0b\x01", b"\x09\x01", b"\x0d\x01", b"\x12\x05ab"):
            with self.subTest(bad):
                with self.assertRaises(check.ProtoError):
                    check.fields(bad)
        self.assertEqual(check.fields(b"\x09" + b"\x00" * 8 + b"\x0d" + b"\x00" * 4)[0][1], 1)

    def test_dims_of_a_value_without_a_tensor(self):
        self.assertIsNone(check.dims_of(field(1, "x")))
        self.assertIsNone(check.dims_of(field(1, "x") + field(2, field(2, b""))))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.words = parse_words(EXAMPLE.read_text(encoding="utf-8"))

    def write(self, name, content=None):
        path = self.dir / name
        path.write_bytes(model() if content is None else content)
        return path

    def test_name_size_and_hash(self):
        path = self.write("hey_armor_en.onnx")
        self.assertTrue(check.check_file(path, self.words["en"]).ok)
        wrong = self.write("other.onnx")
        self.assertTrue(any("wake_words.json names" in p for p in check.check_file(wrong, self.words["en"]).problems))
        self.assertTrue(any("under the least" in p for p in check.check_file(self.write("tiny_en.onnx", b"x" * 100), None).problems))
        self.assertTrue(any("over the most" in p for p in check.check_bytes(b"x" * (check.MAX_BYTES + 1), "big.onnx", None).problems))
        self.assertTrue(any("file name" in p for p in check.check_bytes(model(), "Bad Name.onnx", None).problems))
        report = check.check_file(path, None)
        self.assertTrue(check.check_file(path, None, report.sha256.upper()).ok)
        self.assertTrue(any("sha256" in p for p in check.check_file(path, None, "0" * 64).problems))
        self.assertFalse(check.check_file(self.dir / "missing.onnx", None).ok)

    def test_folder_checks_every_language(self):
        self.write("hey_armor_en.onnx")
        self.write("oye_armor_es.onnx")
        reports = check.check_folder(self.dir, self.words, allow_missing=True)
        self.assertEqual(sorted(reports), sorted(self.words))
        self.assertTrue(all(r.ok for r in reports.values()))
        self.assertTrue(reports["en"].sha256 and not reports["de"].sha256)
        strict = check.check_folder(self.dir, self.words, allow_missing=False)
        self.assertTrue(strict["de"].problems and strict["en"].ok)

    def test_two_languages_cannot_share_a_model(self):
        words = parse_words(json.dumps({"en": {"phrase": "hey armor", "model": "same.onnx"}, "es": {"phrase": "oye armor", "model": "same.onnx"}}))
        self.write("same.onnx")
        reports = check.check_folder(self.dir, words, allow_missing=False)
        self.assertTrue(reports["en"].ok)
        self.assertTrue(any("every language needs a model of its own" in p for p in reports["es"].problems))

    def test_the_example_words_all_pass_the_name_rule(self):
        for word in self.words.values():
            self.assertRegex(Path(word.model).name, check.MODEL_NAME)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_main(self, module, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = module.main(list(args))
            except SystemExit as stop:
                code = stop.code
        return code, out.getvalue(), err.getvalue()

    def test_check_a_file_and_a_folder(self):
        (self.dir / "hey_armor_en.onnx").write_bytes(model())
        code, out, _ = self.run_main(check, str(self.dir / "hey_armor_en.onnx"), "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("en: ok", out)
        code, out, _ = self.run_main(check, "--folder", str(self.dir), "--words", str(EXAMPLE))
        self.assertEqual(code, 1)
        self.assertIn("es: BAD", out)
        code, out, _ = self.run_main(check, "--folder", str(self.dir), "--words", str(EXAMPLE), "--allow-missing")
        self.assertEqual(code, 0)
        self.assertIn("not there (allowed)", out)

    def test_bad_arguments(self):
        self.assertEqual(self.run_main(check)[0], 2)
        self.assertEqual(self.run_main(check, "x.onnx", "--language", "xx")[0], 2)
        (self.dir / "words.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.run_main(check, "--folder", str(self.dir), "--words", str(self.dir / "words.json"))[0], 1)

    def test_release_assets_are_written_and_signed(self):
        models = self.dir / "models"
        models.mkdir()
        (models / "hey_armor_en.onnx").write_bytes(model())
        (models / "oye_armor_es.onnx").write_bytes(model(padding=9100))
        signer = self.dir / "signer.py"
        signer.write_text("import sys\nassert sys.argv[1] == '--message'\nprint(('ab' * 64))\n", encoding="utf-8")
        out = self.dir / "out"
        command = f'"{sys.executable}" "{signer.as_posix()}"'
        code, text, _ = self.run_main(release, "--models", str(models), "--version", "0.3.6", "--out", str(out), "--sign", "--signer", command)
        self.assertEqual(code, 0, text)
        self.assertEqual(names(out), ["armor-voice-wake-models-0.3.6.manifest", "armor-voice-wake-models-0.3.6.manifest.sig2", "hey_armor_en.onnx", "oye_armor_es.onnx"])
        lines = (out / "armor-voice-wake-models-0.3.6.manifest").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "armor-wake-models/1|0.3.6")
        self.assertEqual([line.split("|")[0] for line in lines[1:]], ["en", "es"])
        self.assertEqual(lines[1].split("|")[3], check.check_file(models / "hey_armor_en.onnx", None).sha256)
        self.assertIn("gh release upload v0.3.6", text)

    def test_nothing_is_written_when_a_model_is_wrong_or_the_signer_is_missing(self):
        models = self.dir / "models"
        models.mkdir()
        out = self.dir / "out"
        (models / "hey_armor_en.onnx").write_bytes(b"x" * 20000)
        code, _, err = self.run_main(release, "--models", str(models), "--version", "0.3.6", "--out", str(out))
        self.assertNotEqual(code, 0)
        self.assertFalse(out.exists())
        (models / "hey_armor_en.onnx").write_bytes(model())
        for version in ("v1", "1.2"):
            self.assertNotEqual(self.run_main(release, "--models", str(models), "--version", version, "--out", str(out))[0], 0)
        self.assertNotEqual(self.run_main(release, "--models", str(self.dir / "empty"), "--version", "0.3.6", "--out", str(out))[0], 0)
        empty = self.dir / "empty2"
        empty.mkdir()
        self.assertNotEqual(self.run_main(release, "--models", str(empty), "--version", "0.3.6", "--out", str(out))[0], 0)
        os.environ.pop("ARMOR_NO_SIGNER", None)
        words = parse_words(None)
        with self.assertRaises(SystemExit):
            release.prepare(models, "0.3.6", out, words, None, True)
        self.assertFalse(out.exists())

    def test_a_signer_that_gives_nothing_stops_the_release(self):
        bad = self.dir / "bad.py"
        bad.write_text("print('nope')\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            release.sign_message([sys.executable, str(bad)], "m")
        failing = self.dir / "fail.py"
        failing.write_text("import sys\nsys.stderr.write('no key')\nsys.exit(3)\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            release.sign_message([sys.executable, str(failing)], "m")

    def test_the_default_signer_is_the_one_of_the_home_folder_when_it_exists(self):
        home = self.dir / "home"
        (home / ".armor").mkdir(parents=True)
        previous = {key: os.environ.get(key) for key in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(home)
        try:
            self.assertIsNone(release.default_signer())
            (home / ".armor" / "sign.mjs").write_text("", encoding="utf-8")
            self.assertEqual(release.default_signer()[0], "node")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_manifest_format_is_stable(self):
        text = release.manifest_text("0.3.6", [("es", "b.onnx", 2, "bb"), ("en", "a.onnx", 1, "aa")])
        self.assertEqual(text, "armor-wake-models/1|0.3.6\nen|a.onnx|1|aa\nes|b.onnx|2|bb\n")
        self.assertEqual(release.signed_message("0.3.6", "cc"), "armor-fw/1|voice-wake-models|manifest|0.3.6|cc")


if __name__ == "__main__":
    unittest.main()
