"""Checks a trained wake word model before it is trusted: its name, its size and the shape of its network, read from the file with nothing but the standard library.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

A model for the wake word is trained by a person (docs/WAKE_TRAINING.md) and is a file that the service later loads, so it is looked at before it goes anywhere:

* the file name is the one ``wake_words.json`` names for that language (a model under another name would never be loaded, or would be loaded for the wrong language);
* the size is in a sane range (an empty file or a file of hundreds of megabytes is not an openWakeWord classifier);
* the file is an ONNX model whose graph has one input of shape ``[batch, 16, 96]`` (sixteen frames of the 96 features of the embedding model) and one output of shape ``[batch, 1]``,
  where the batch is 1 or left open, and that keeps its weights inside the file (no external data file the service would not find).

Nothing is run and no library is imported: the ONNX file is a protocol buffer and only the few fields needed are read, with every length checked against the bytes that are there.

  python -m armor_voice_ai.wake_model_check MODEL.onnx --language es [--words wake_words.json] [--sha256 HEX]
  python -m armor_voice_ai.wake_model_check --folder MODELS_DIR [--words wake_words.json] [--allow-missing]

It exits with 0 when everything checked is right and with 1 when anything is not.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .wakeword import WakeWord, load_words, parse_words

MIN_BYTES = 8 * 1024
MAX_BYTES = 8 * 1024 * 1024
#: What an openWakeWord classifier takes: a window of this many embedding frames, each with this many features.
INPUT_WINDOW = 16
INPUT_FEATURES = 96
MODEL_NAME = re.compile(r"^[a-z0-9][a-z0-9_]{1,60}\.onnx$")
#: ONNX ``TensorProto.DataLocation`` value of a tensor that lives in another file.
EXTERNAL = 1


class ProtoError(ValueError):
    """The bytes are not a protocol buffer that fits in the file."""


def read_varint(data: bytes, position: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if position >= len(data):
            raise ProtoError("a number runs past the end of the file")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
        if shift > 63:
            raise ProtoError("a number is too long")


def fields(data: bytes) -> list[tuple[int, int, object]]:
    """Every field of one message as ``(number, wire type, value)``: an integer for a varint, bytes for the rest."""
    found: list[tuple[int, int, object]] = []
    position = 0
    while position < len(data):
        key, position = read_varint(data, position)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ProtoError("a field has the number 0")
        if wire == 0:
            value, position = read_varint(data, position)
            found.append((number, wire, value))
        elif wire == 1 or wire == 5:
            size = 8 if wire == 1 else 4
            if position + size > len(data):
                raise ProtoError("a fixed field runs past the end of the file")
            found.append((number, wire, data[position:position + size]))
            position += size
        elif wire == 2:
            size, position = read_varint(data, position)
            if position + size > len(data):
                raise ProtoError("a field is longer than the bytes that are left")
            found.append((number, wire, data[position:position + size]))
            position += size
        else:
            raise ProtoError(f"a field has the wire type {wire}, which a model does not use")
    return found


def messages(data: bytes, number: int) -> list[bytes]:
    return [value for n, wire, value in fields(data) if n == number and wire == 2 and isinstance(value, bytes)]


def dims_of(value_info: bytes) -> list[int | None] | None:
    """The shape of a graph input or output (``None`` for a dimension that is open or named), or ``None`` when it is not a tensor with a shape."""
    for type_proto in messages(value_info, 2):
        for tensor in messages(type_proto, 1):
            for shape in messages(tensor, 2):
                result: list[int | None] = []
                for dim in messages(shape, 1):
                    fixed = [value for n, wire, value in fields(dim) if n == 1 and wire == 0]
                    result.append(int(fixed[0]) if fixed and isinstance(fixed[0], int) else None)
                return result
    return None


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sha256: str = ""
    size: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems


def check_shape(model: bytes, report: Report) -> None:
    try:
        top = fields(model)
        graphs = [value for n, wire, value in top if n == 7 and wire == 2 and isinstance(value, bytes)]
        if len(graphs) != 1:
            report.problems.append("the file is not an ONNX model (no graph)")
            return
        graph = graphs[0]
        inputs, outputs = messages(graph, 11), messages(graph, 12)
        initializers = messages(graph, 5)
        if any(value == EXTERNAL for tensor in initializers for n, wire, value in fields(tensor) if n == 14 and wire == 0):
            report.problems.append("a weight lives in an external data file: the model must keep its weights inside the file")
        # A graph input may also list the weights (older exporters do); the ones that count are those that no initializer provides.
        named = {text for tensor in initializers for n, wire, text in fields(tensor) if n == 8 and wire == 2 and isinstance(text, bytes)}
        real_inputs = [item for item in inputs if not any(n == 1 and wire == 2 and value in named for n, wire, value in fields(item))]
        if len(real_inputs) != 1 or len(outputs) != 1:
            report.problems.append(f"the graph must have one input and one output, it has {len(real_inputs)} and {len(outputs)}")
            return
        shape_in, shape_out = dims_of(real_inputs[0]), dims_of(outputs[0])
        if shape_in is None or len(shape_in) != 3 or shape_in[1:] != [INPUT_WINDOW, INPUT_FEATURES] or shape_in[0] not in (None, 1):
            report.problems.append(f"the input must be [batch, {INPUT_WINDOW}, {INPUT_FEATURES}] with a batch of 1 or open, it is {shape_in}")
        if shape_out is None or len(shape_out) != 2 or shape_out[1] != 1 or shape_out[0] not in (None, 1):
            report.problems.append(f"the output must be [batch, 1] with a batch of 1 or open, it is {shape_out}")
    except ProtoError as error:
        report.problems.append(f"the file is not a readable ONNX model: {error}")


def check_bytes(content: bytes, file_name: str, expected_name: str | None) -> Report:
    report = Report(sha256=hashlib.sha256(content).hexdigest(), size=len(content))
    if not MODEL_NAME.match(file_name):
        report.problems.append(f"the file name {file_name!r} must be lower case letters, digits and '_' ending in .onnx")
    if expected_name is not None and file_name != expected_name:
        report.problems.append(f"the file is called {file_name!r} but wake_words.json names {expected_name!r} for this language")
    if len(content) < MIN_BYTES:
        report.problems.append(f"the file has {len(content)} bytes, under the least of {MIN_BYTES}")
    elif len(content) > MAX_BYTES:
        report.problems.append(f"the file has {len(content)} bytes, over the most of {MAX_BYTES}")
    else:
        check_shape(content, report)
    return report


def check_file(path: Path, word: WakeWord | None, sha256: str | None = None) -> Report:
    """The checks of one model file; ``word`` is the line of ``wake_words.json`` for its language (``None`` skips the name check)."""
    expected = Path(word.model).name if word is not None else None
    if not path.is_file():
        report = Report()
        report.problems.append(f"{path} is not a file")
        return report
    report = check_bytes(path.read_bytes(), path.name, expected)
    if sha256 is not None and sha256.lower() != report.sha256:
        report.problems.append(f"the sha256 is {report.sha256}, not the {sha256.lower()} that was expected")
    return report


def check_folder(folder: Path, words: dict[str, WakeWord], allow_missing: bool) -> dict[str, Report]:
    """The report of the model of each language of ``words`` found in ``folder``; a model that is not there is a problem unless ``allow_missing``. A model name used by two languages is a problem."""
    reports: dict[str, Report] = {}
    seen: dict[str, str] = {}
    for language in sorted(words):
        name = Path(words[language].model).name
        report = Report()
        if name in seen:
            report.problems.append(f"{name!r} is the model of {seen[name]} too: every language needs a model of its own")
        seen.setdefault(name, language)
        path = folder / name
        if not path.is_file():
            if allow_missing:
                report.notes.append("not there (allowed)")
            else:
                report.problems.append(f"{name} is not in {folder}")
        else:
            checked = check_file(path, words[language])
            report.problems += checked.problems
            report.sha256, report.size = checked.sha256, checked.size
        reports[language] = report
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wake_model_check", description="Check a trained wake word model (name, size, network shape).")
    parser.add_argument("model", nargs="?", help="the .onnx file to check")
    parser.add_argument("--language", help="the language of the model (needed with a file)")
    parser.add_argument("--folder", help="check the model of every language of the words file found in this folder")
    parser.add_argument("--words", help="wake_words.json (default: the two built-in words)")
    parser.add_argument("--sha256", help="the hash the file is expected to have")
    parser.add_argument("--allow-missing", action="store_true", help="with --folder: a language without a model is not a problem")
    arguments = parser.parse_args(argv)
    try:
        words = load_words(Path(arguments.words)) if arguments.words else parse_words(None)
    except (OSError, ValueError) as error:
        print(f"wake_words.json: {error}", file=sys.stderr)
        return 1
    if bool(arguments.model) == bool(arguments.folder):
        parser.error("give one model file with --language, or --folder")
    if arguments.folder:
        reports = check_folder(Path(arguments.folder), words, arguments.allow_missing)
    else:
        if arguments.language not in words:
            parser.error("--language must be one of the languages of the words file: " + ", ".join(sorted(words)))
        reports = {arguments.language: check_file(Path(arguments.model), words[arguments.language], arguments.sha256)}
    bad = False
    for language, report in reports.items():
        state = "ok" if report.ok else "BAD"
        detail = f"{report.size} bytes sha256 {report.sha256}" if report.sha256 else "; ".join(report.notes)
        print(f"{language}: {state} {detail}".rstrip())
        for problem in report.problems:
            print(f"  - {problem}")
        bad = bad or not report.ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
