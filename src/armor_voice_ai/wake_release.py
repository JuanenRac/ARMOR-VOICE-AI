"""Prepares the wake word models for a release: checks each one, writes a manifest of their hashes and has the manifest signed, so that the models travel as assets of the release of this project.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

The models are trained by a person (docs/WAKE_TRAINING.md). What a release carries is each ``.onnx`` file plus ``armor-voice-wake-models-<version>.manifest``, a text file with one
line per model (``language|file|bytes|sha256``), and the signature of that manifest: whoever downloads a model checks its hash against the manifest and the manifest against the
key of the releases. This tool never reads a key: the signer is a program (``~/.armor/sign.mjs`` or ``--signer``) that is asked for the signature of one message and holds the key itself.

  python -m armor_voice_ai.wake_release --models DIR --version 0.3.6 --out OUT_DIR [--words wake_words.json] [--sign] [--signer "node ~/.armor/sign.mjs"]

It stops, writing nothing, when any model fails ``wake_model_check``.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .wake_model_check import check_folder
from .wakeword import WakeWord, load_words, parse_words

VERSION = re.compile(r"^\d+\.\d+\.\d+(\.\d+)?$")
SIGNATURE = re.compile(r"^[0-9a-f]{128}$")
COMPONENT = "voice-wake-models"


def manifest_name(version: str) -> str:
    return f"armor-voice-wake-models-{version}.manifest"


def manifest_text(version: str, entries: list[tuple[str, str, int, str]]) -> str:
    """The manifest: a header line and one ``language|file|bytes|sha256`` line per model, sorted by language."""
    lines = [f"armor-wake-models/1|{version}"] + [f"{language}|{name}|{size}|{digest}" for language, name, size, digest in sorted(entries)]
    return "\n".join(lines) + "\n"


def signed_message(version: str, manifest_sha256: str) -> str:
    """What the signature covers: the hash of the manifest, which in turn names the hash of every model."""
    return f"armor-fw/1|{COMPONENT}|manifest|{version}|{manifest_sha256}"


def default_signer() -> list[str] | None:
    path = Path(os.path.expanduser("~")) / ".armor" / "sign.mjs"
    return ["node", str(path)] if path.is_file() else None


def sign_message(signer: list[str], message: str) -> str:
    result = subprocess.run([*signer, "--message", message], capture_output=True, text=True, check=False)
    signature = result.stdout.strip().lower()
    if result.returncode != 0 or not SIGNATURE.match(signature):
        raise SystemExit("the signer did not give a signature" + (": " + result.stderr.strip()[:200] if result.returncode else ""))
    return signature


def prepare(models: Path, version: str, out: Path, words: dict[str, WakeWord], signer: list[str] | None, sign: bool) -> list[Path]:
    """Checks the models, copies them to ``out`` with the manifest (and its signature when ``sign``) and returns the files to upload."""
    if not VERSION.match(version):
        raise SystemExit(f"{version!r} is not a version of the family (0.3.6 or 0.8.0.1)")
    reports = check_folder(models, words, allow_missing=True)
    present = {language: report for language, report in reports.items() if report.sha256}
    problems = [f"{language}: {problem}" for language, report in reports.items() for problem in report.problems]
    if problems:
        raise SystemExit("a model is not right, nothing was written:\n  " + "\n  ".join(problems))
    if not present:
        raise SystemExit("there is no model in the folder")
    if sign and signer is None:
        raise SystemExit("--sign needs the signer (~/.armor/sign.mjs or --signer)")
    out.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str, int, str]] = []
    files: list[Path] = []
    for language, report in present.items():
        name = Path(words[language].model).name
        shutil.copyfile(models / name, out / name)
        files.append(out / name)
        entries.append((language, name, report.size, report.sha256))
    text = manifest_text(version, entries)
    manifest = out / manifest_name(version)
    manifest.write_bytes(text.encode("utf-8"))
    files.append(manifest)
    if sign and signer is not None:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        signature = out / (manifest.name + ".sig2")
        signature.write_text(sign_message(signer, signed_message(version, digest)) + "\n", encoding="ascii", newline="\n")
        files.append(signature)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wake_release", description="Prepare the wake word models as signed assets of a release.")
    parser.add_argument("--models", required=True, help="the folder with the trained .onnx files")
    parser.add_argument("--version", required=True, help="the version of the release the assets go to")
    parser.add_argument("--out", required=True, help="where the assets are written")
    parser.add_argument("--words", help="wake_words.json (default: the two built-in words)")
    parser.add_argument("--sign", action="store_true", help="ask the signer to sign the manifest (fails without a signer)")
    parser.add_argument("--signer", help="the command of the signer, e.g. \"node ~/.armor/sign.mjs\"")
    arguments = parser.parse_args(argv)
    try:
        words = load_words(Path(arguments.words)) if arguments.words else parse_words(None)
        signer = shlex.split(arguments.signer, posix=True) if arguments.signer else default_signer()
        files = prepare(Path(arguments.models), arguments.version, Path(arguments.out), words, signer, arguments.sign)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    for item in files:
        print(item)
    print(f"upload with: gh release upload v{arguments.version} <the files above> -R JuanenRac/ARMOR-VOICE-AI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
