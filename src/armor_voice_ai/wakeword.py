"""The wake word of the wall panel: a small detector that runs on this machine and says when the word was spoken, so the panel starts listening for a command.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Nothing leaves the machine: the detector is openWakeWord (an open source model that runs on the processor, no account, no key, no cloud), loaded only when it is asked for. The word
is a setting, not code: ``wake_words.json`` names, for each of the eight languages, the phrase, the model file and the threshold, so a word in a language the family has no model for
yet is added by training one (openWakeWord trains a model from synthetic speech) and writing one line. English ("hey armor") and Spanish ("oye armor") are the first two.

It is OFF unless ``ARMOR_WAKE_WORD=on`` is in the environment of the service, and the server only passes audio to it while the security option ``voice.wake_word`` is on. It only decides
whether the word was said: it keeps no audio (a frame is looked at and dropped), it never carries out a command, and it adds nothing to what the turn service already does after the
panel wakes up.
"""

from __future__ import annotations

import json
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .gateway import SPEECH_BY_LANGUAGE

#: openWakeWord looks at 80 ms of 16 kHz mono 16-bit audio at a time.
FRAME_SAMPLES = 1280
FRAME_BYTES = FRAME_SAMPLES * 2
#: A chunk from the panel is at most two seconds (25 frames): the panel sends what it heard since the last call, not a recording.
MAX_CHUNK_BYTES = FRAME_BYTES * 25
#: The most panels remembered at once; the one idle for longest is forgotten first.
MAX_SESSIONS = 64
MIN_THRESHOLD, MAX_THRESHOLD = 0.3, 0.99

DEFAULT_WORDS: dict[str, dict[str, object]] = {
    "en": {"phrase": "hey armor", "model": "hey_armor_en.onnx", "threshold": 0.6},
    "es": {"phrase": "oye armor", "model": "oye_armor_es.onnx", "threshold": 0.6},
}


class WakeError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


class Detector(Protocol):
    def predict(self, frame: bytes, model: str) -> float:
        """The score from 0 to 1 that the word of ``model`` ends in this 80 ms frame."""


@dataclass(frozen=True)
class WakeWord:
    language: str
    phrase: str
    model: str
    threshold: float


def parse_words(text: str | None) -> dict[str, WakeWord]:
    """The words of the file ``wake_words.json`` (``{"en": {"phrase", "model", "threshold"}, ...}``), or the two defaults when there is no file. A line that is not valid is refused whole,
    never half used: a wrong threshold would make the panel listen to everything or to nothing."""
    data: object = DEFAULT_WORDS if text is None else json.loads(text)
    if not isinstance(data, dict) or not data:
        raise ValueError("the wake words must be an object with a line for at least one language")
    words: dict[str, WakeWord] = {}
    for language, entry in data.items():
        if language not in SPEECH_BY_LANGUAGE:
            raise ValueError(f"{language!r} is not a language of the family")
        if not isinstance(entry, dict) or set(entry) - {"phrase", "model", "threshold"}:
            raise ValueError(f"{language}: a line has phrase, model and threshold, nothing else")
        phrase, model, threshold = entry.get("phrase"), entry.get("model"), entry.get("threshold", 0.6)
        if not isinstance(phrase, str) or not 2 <= len(phrase.strip()) <= 40:
            raise ValueError(f"{language}: the phrase must be 2 to 40 characters")
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or ".." in Path(model).parts or "\x00" in model:
            raise ValueError(f"{language}: the model must be a file name or a path without '..'")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not MIN_THRESHOLD <= float(threshold) <= MAX_THRESHOLD:
            raise ValueError(f"{language}: the threshold must be a number from {MIN_THRESHOLD} to {MAX_THRESHOLD}")
        words[language] = WakeWord(language, phrase.strip(), model.strip(), float(threshold))
    return words


def load_words(path: Path | None) -> dict[str, WakeWord]:
    return parse_words(path.read_text(encoding="utf-8") if path is not None else None)


class OpenWakeWordDetector:
    """The detector of openWakeWord, imported only when it is built so that a machine without it (or with the switch off) never needs it."""

    def __init__(self, model_folder: Path | None = None) -> None:
        try:
            import numpy  # noqa: PLC0415 - optional dependency, loaded on demand
            from openwakeword.model import Model  # type: ignore[import-not-found]  # noqa: PLC0415
        except ImportError as error:
            raise WakeError(501, "wake_detector_unavailable") from error
        self._numpy, self._Model, self._folder, self._models, self._lock = numpy, Model, model_folder, {}, threading.Lock()

    def predict(self, frame: bytes, model: str) -> float:
        with self._lock:
            loaded = self._models.get(model)
            if loaded is None:
                path = (self._folder / model) if self._folder is not None and not Path(model).is_absolute() else Path(model)
                if not path.is_file():
                    raise WakeError(501, "wake_model_missing")
                loaded = self._models[model] = self._Model(wakeword_models=[str(path)], inference_framework="onnx")
            samples = self._numpy.frombuffer(frame, dtype=self._numpy.int16)
            scores = loaded.predict(samples)
            return float(max(scores.values())) if scores else 0.0


class _Panel:
    __slots__ = ("pending", "streak", "quiet_until", "seen")

    def __init__(self) -> None:
        self.pending, self.streak, self.quiet_until, self.seen = b"", 0, 0.0, 0.0


class WakeService:
    """Frames in, the word out. A panel wakes when two frames in a row (160 ms) score over the threshold, and then stays quiet for ``cooldown_s`` so one word is one wake."""

    def __init__(self, detector: Detector, words: dict[str, WakeWord], cooldown_s: float = 2.0, clock: Callable[[], float] = time.monotonic) -> None:
        if cooldown_s < 0 or cooldown_s > 30:
            raise ValueError("the cooldown must be between 0 and 30 seconds")
        self._detector, self._words, self._cooldown, self._clock = detector, words, cooldown_s, clock
        self._panels: dict[str, _Panel] = {}
        self._lock = threading.Lock()

    @property
    def languages(self) -> list[str]:
        return sorted(self._words)

    def process(self, pcm: bytes, language: str, client: str) -> dict[str, object]:
        word = self._words.get(language)
        if word is None:
            raise WakeError(422, "no_wake_word_for_language")
        if not pcm or len(pcm) % 2 or len(pcm) > MAX_CHUNK_BYTES:
            raise WakeError(413 if len(pcm) > MAX_CHUNK_BYTES else 422, "bad_audio_chunk")
        now = self._clock()
        with self._lock:
            panel = self._panels.get(client)
            if panel is None:
                if len(self._panels) >= MAX_SESSIONS:
                    del self._panels[min(self._panels, key=lambda key: self._panels[key].seen)]
                panel = self._panels[client] = _Panel()
            panel.seen = now
            data = panel.pending + pcm
            frames, panel.pending = [data[i:i + FRAME_BYTES] for i in range(0, len(data) - len(data) % FRAME_BYTES, FRAME_BYTES)], data[len(data) - len(data) % FRAME_BYTES:]
            best, woke = 0.0, False
            for frame in frames:
                score = self._detector.predict(frame, word.model)
                best = max(best, score)
                if now < panel.quiet_until:
                    panel.streak = 0
                    continue
                panel.streak = panel.streak + 1 if score >= word.threshold else 0
                if panel.streak >= 2:
                    woke, panel.streak, panel.quiet_until = True, 0, now + self._cooldown
        return {"wake": woke, "word": word.phrase if woke else None, "score": round(best, 3), "frames": len(frames)}

    def forget(self, client: str) -> None:
        with self._lock:
            self._panels.pop(client, None)


def peak_score(frame: bytes) -> float:
    """A stand-in detector for tests and for a bench without a model: the loudness of the frame from 0 to 1. It hears no word, only a shout; the name says so."""
    count = len(frame) // 2
    return max((abs(value) for value in struct.unpack(f"<{count}h", frame[:count * 2])), default=0) / 32768 if count else 0.0
