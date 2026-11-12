import json
import struct
import threading
import unittest
import urllib.error
import urllib.request

from armor_voice_ai import wakeword
from armor_voice_ai.confirmation import ConfirmationSigner
from armor_voice_ai.service import make_server
from armor_voice_ai.wakeword import FRAME_BYTES, MAX_CHUNK_BYTES, WakeError, WakeService, parse_words, peak_score

TOKEN = "t" * 24


def frames(count, loud=False):
    value = 30000 if loud else 100
    return struct.pack("<h", value) * (wakeword.FRAME_SAMPLES * count)


class Scripted:
    """A detector that answers from a list, one score for each frame it is given, and remembers which model it was asked for."""

    def __init__(self, scores):
        self.scores, self.models, self.frames = list(scores), [], 0

    def predict(self, frame, model):
        self.models.append(model)
        self.frames += 1
        return self.scores.pop(0) if self.scores else 0.0


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class WordsTests(unittest.TestCase):
    def test_the_defaults_are_english_and_spanish_with_their_own_models(self):
        words = parse_words(None)
        self.assertEqual(sorted(words), ["en", "es"])
        self.assertEqual((words["en"].phrase, words["es"].phrase), ("hey armor", "oye armor"))
        self.assertNotEqual(words["en"].model, words["es"].model)

    def test_another_language_is_one_line_and_the_threshold_may_be_given(self):
        words = parse_words(json.dumps({"de": {"phrase": "hallo armor", "model": "models/hallo_armor.onnx", "threshold": 0.7}}))
        self.assertEqual((words["de"].phrase, words["de"].threshold), ("hallo armor", 0.7))

    def test_a_line_that_is_not_valid_is_refused_whole(self):
        good = {"phrase": "hey armor", "model": "m.onnx", "threshold": 0.6}
        for bad in (
            {"xx": good},                                   # not a language of the family
            {"en": {**good, "extra": 1}},                   # a key that does not exist
            {"en": {**good, "phrase": "x"}},                # too short
            {"en": {**good, "phrase": "y" * 41}},           # too long
            {"en": {**good, "model": "../../etc/passwd"}},  # outside its folder
            {"en": {**good, "model": ""}},
            {"en": {**good, "threshold": 0.1}},             # would listen to everything
            {"en": {**good, "threshold": 1.0}},             # would listen to nothing
            {"en": {**good, "threshold": True}},
            {"en": {**good, "threshold": "0.6"}},
            {"en": "hey armor"},
            {},
            [],
        ):
            with self.assertRaises(ValueError, msg=str(bad)):
                parse_words(json.dumps(bad))
        with self.assertRaises(ValueError):
            parse_words("not json")


class ServiceLogicTests(unittest.TestCase):
    def make(self, scores, cooldown=2.0):
        detector, clock = Scripted(scores), Clock()
        return WakeService(detector, parse_words(None), cooldown, clock), detector, clock

    def test_two_frames_in_a_row_over_the_threshold_wake_the_panel(self):
        service, detector, _ = self.make([0.1, 0.9, 0.95])
        answer = service.process(frames(3), "en", "panel-1")
        self.assertEqual((answer["wake"], answer["word"], answer["frames"]), (True, "hey armor", 3))
        self.assertEqual(answer["score"], 0.95)
        self.assertEqual(set(detector.models), {"hey_armor_en.onnx"})

    def test_one_frame_alone_does_not_wake_and_the_streak_is_broken_by_a_low_frame(self):
        service, _, _ = self.make([0.9, 0.1, 0.9, 0.1])
        self.assertFalse(service.process(frames(4), "en", "p")["wake"])

    def test_the_streak_goes_on_between_two_chunks(self):
        service, _, _ = self.make([0.9, 0.9])
        self.assertFalse(service.process(frames(1), "en", "p")["wake"])
        self.assertTrue(service.process(frames(1), "en", "p")["wake"])

    def test_after_a_wake_the_panel_is_quiet_for_the_cooldown_and_then_listens_again(self):
        service, _, clock = self.make([0.9] * 20, cooldown=2.0)
        self.assertTrue(service.process(frames(2), "en", "p")["wake"])
        self.assertFalse(service.process(frames(4), "en", "p")["wake"], "the same word is one wake")
        clock.now += 2.5
        self.assertTrue(service.process(frames(2), "en", "p")["wake"])

    def test_a_partial_frame_waits_for_the_rest_and_nothing_is_kept_of_the_audio_after_a_frame(self):
        service, detector, _ = self.make([0.0, 0.0])
        half = FRAME_BYTES // 2
        self.assertEqual(service.process(b"\x01\x00" * (half // 2), "en", "p")["frames"], 0)
        self.assertEqual(detector.frames, 0)
        self.assertEqual(service.process(b"\x01\x00" * (half // 2) + b"\x02\x00" * (half // 2), "en", "p")["frames"], 1)

    def test_each_panel_has_its_own_streak(self):
        service, _, _ = self.make([0.9, 0.0, 0.0, 0.9])
        service.process(frames(1), "en", "a")
        self.assertFalse(service.process(frames(1), "en", "b")["wake"])
        self.assertFalse(service.process(frames(1), "en", "b")["wake"])
        self.assertTrue(service.process(frames(1), "en", "a")["wake"])

    def test_a_language_without_a_word_and_bad_chunks_are_refused(self):
        service, _, _ = self.make([])
        for pcm, language, status, code in ((frames(1), "fr", 422, "no_wake_word_for_language"), (b"", "en", 422, "bad_audio_chunk"), (b"\x00" * 3, "en", 422, "bad_audio_chunk"),
                                            (b"\x00" * (MAX_CHUNK_BYTES + 2), "en", 413, "bad_audio_chunk")):
            with self.assertRaises(WakeError) as caught:
                service.process(pcm, language, "p")
            self.assertEqual((caught.exception.status, caught.exception.code), (status, code))
        self.assertEqual(service.languages, ["en", "es"])

    def test_the_spanish_word_uses_its_own_model_and_threshold(self):
        words = parse_words(json.dumps({"es": {"phrase": "oye armor", "model": "es.onnx", "threshold": 0.8}}))
        detector = Scripted([0.7, 0.7, 0.85, 0.85])
        service = WakeService(detector, words)
        self.assertFalse(service.process(frames(2), "es", "p")["wake"], "0.7 is under the 0.8 of this word")
        self.assertTrue(service.process(frames(2), "es", "p")["wake"])
        self.assertEqual(set(detector.models), {"es.onnx"})

    def test_the_panels_remembered_are_bounded_and_one_can_be_forgotten(self):
        service, _, clock = self.make([])
        for number in range(wakeword.MAX_SESSIONS + 10):
            clock.now += 1
            service.process(frames(1), "en", f"panel-{number}")
        self.assertLessEqual(len(service._panels), wakeword.MAX_SESSIONS)
        service.forget("panel-70")
        service.forget("nobody")

    def test_a_cooldown_out_of_range_is_refused(self):
        for bad in (-1, 31):
            with self.assertRaises(ValueError):
                WakeService(Scripted([]), parse_words(None), bad)

    def test_the_stand_in_detector_hears_loudness_only(self):
        self.assertEqual(peak_score(b""), 0.0)
        self.assertGreater(peak_score(frames(1, loud=True)), 0.9)
        self.assertLess(peak_score(frames(1)), 0.01)

    def test_without_the_openwakeword_package_the_detector_says_so(self):
        try:
            import openwakeword  # noqa: F401
        except ImportError:
            with self.assertRaises(WakeError) as caught:
                wakeword.OpenWakeWordDetector()
            self.assertEqual((caught.exception.status, caught.exception.code), (501, "wake_detector_unavailable"))


class WakeRouteTests(unittest.TestCase):
    def start(self, wake):
        server = make_server("127.0.0.1", 0, TOKEN, ConfirmationSigner(b"s" * 32), None, None, None, wake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close()))
        return f"http://127.0.0.1:{server.server_address[1]}"

    def post(self, base, pcm, language="en", token=TOKEN, content_type="audio/L16;rate=16000"):
        request = urllib.request.Request(base + "/v1/wake", data=pcm, method="POST", headers={"Content-Type": content_type, "X-Armor-Language": language, "X-Armor-Voice-Token": token, "X-Armor-Client": "panel-9"})
        try:
            with urllib.request.urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_it_is_off_unless_the_service_was_started_with_the_word_on(self):
        base = self.start(None)
        self.assertEqual(self.post(base, frames(1)), (403, {"error": "wake_disabled"}))

    def test_a_wake_comes_back_as_json_and_a_bad_request_is_refused(self):
        base = self.start(WakeService(Scripted([0.9, 0.9]), parse_words(None)))
        self.assertEqual(self.post(base, frames(1), token="wrong")[0], 401)
        self.assertEqual(self.post(base, frames(1), language="xx")[0], 422)
        self.assertEqual(self.post(base, frames(1), content_type="text/plain")[0], 415)
        self.assertEqual(self.post(base, b"")[0], 411)
        self.assertEqual(self.post(base, b"\x00" * (MAX_CHUNK_BYTES + 2))[0], 413)
        self.assertEqual(self.post(base, frames(1), language="fr")[1], {"error": "no_wake_word_for_language"})
        status, body = self.post(base, frames(2))
        self.assertEqual((status, body["wake"], body["word"]), (200, True, "hey armor"))


class ExampleWordsFileTests(unittest.TestCase):
    def test_the_example_file_names_a_word_for_each_of_the_eight_languages(self):
        from pathlib import Path
        from armor_voice_ai.gateway import SPEECH_BY_LANGUAGE
        path = Path(__file__).resolve().parent.parent / "docs" / "wake_words.example.json"
        words = parse_words(path.read_text(encoding="utf-8"))
        self.assertEqual(set(words), set(SPEECH_BY_LANGUAGE))
        self.assertEqual(len(words), 8)
        self.assertEqual(len({word.model for word in words.values()}), 8)
        self.assertEqual((words["en"].phrase, words["es"].phrase), ("hey armor", "oye armor"))

    def test_a_language_without_a_line_is_refused_not_guessed(self):
        words = parse_words('{"en": {"phrase": "hey armor", "model": "m.onnx"}}')
        self.assertEqual(set(words), {"en"})
        self.assertEqual(words["en"].threshold, 0.6)


class OpenWakeWordDetectorTests(unittest.TestCase):
    """The detector of openWakeWord with stand-in modules: nothing is installed on the machine that runs the tests."""

    def fake_modules(self, scores):
        import types
        loaded = []

        class Model:
            def __init__(self, wakeword_models, inference_framework):
                loaded.append((wakeword_models, inference_framework))

            def predict(self, samples):
                return scores

        numpy = types.SimpleNamespace(int16="int16", frombuffer=lambda frame, dtype: (len(frame), dtype))
        modules = {"numpy": numpy, "openwakeword": types.ModuleType("openwakeword"), "openwakeword.model": types.SimpleNamespace(Model=Model)}
        return modules, loaded

    def test_without_the_library_it_says_the_detector_is_unavailable(self):
        import sys
        from unittest import mock
        with mock.patch.dict(sys.modules, {"openwakeword": None, "openwakeword.model": None}):
            with self.assertRaises(WakeError) as caught:
                wakeword.OpenWakeWordDetector()
        self.assertEqual((caught.exception.status, caught.exception.code), (501, "wake_detector_unavailable"))

    def test_a_model_that_is_not_in_the_folder_is_said_not_guessed(self):
        import sys
        import tempfile
        from pathlib import Path
        from unittest import mock
        modules, loaded = self.fake_modules({"hey": 0.9})
        with mock.patch.dict(sys.modules, modules), tempfile.TemporaryDirectory() as folder:
            detector = wakeword.OpenWakeWordDetector(Path(folder))
            with self.assertRaises(WakeError) as caught:
                detector.predict(frames(1), "missing.onnx")
        self.assertEqual((caught.exception.status, caught.exception.code), (501, "wake_model_missing"))
        self.assertEqual(loaded, [])

    def test_a_model_is_loaded_once_from_the_folder_and_the_best_score_is_returned(self):
        import sys
        import tempfile
        from pathlib import Path
        from unittest import mock
        modules, loaded = self.fake_modules({"a": 0.2, "b": 0.8})
        with mock.patch.dict(sys.modules, modules), tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "hey.onnx").write_bytes(b"model")
            detector = wakeword.OpenWakeWordDetector(Path(folder))
            self.assertEqual(detector.predict(frames(1), "hey.onnx"), 0.8)
            self.assertEqual(detector.predict(frames(1), "hey.onnx"), 0.8)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0][1], "onnx")

    def test_a_model_that_gives_no_score_counts_as_silence(self):
        import sys
        import tempfile
        from pathlib import Path
        from unittest import mock
        modules, _ = self.fake_modules({})
        with mock.patch.dict(sys.modules, modules), tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "hey.onnx").write_bytes(b"model")
            self.assertEqual(wakeword.OpenWakeWordDetector(Path(folder)).predict(frames(1), "hey.onnx"), 0.0)


if __name__ == "__main__":
    unittest.main()
