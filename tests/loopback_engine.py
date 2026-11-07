"""A stand-in for the two speech engines, for the bench and the tests: it recognises no speech and says nothing a person could hear.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

    python loopback_engine.py tts   text on the standard input -> a 16 kHz, 16-bit, mono WAVE on the standard output
    python loopback_engine.py stt   a WAVE made by `tts` on the standard input -> the text on the standard output

The "audio" is a code: every byte of the text becomes a block of constant samples, so the clip a `tts` run makes is a recording that `stt` reads back exactly, and a second of silence
(what the engines are checked with) reads back as no words, like a real recogniser on a quiet room. It lets the whole road of a spoken turn - the panel's audio, the service, the
engine commands, the server's voice route and the audio of the answer - run in a continuous integration job, in every language, with no model, no microphone and no speaker.
A green run says the plumbing works; it says nothing about how well a real engine hears a real voice.
"""

from __future__ import annotations

import struct
import sys

BLOCK = 80          # samples per byte (5 ms at 16 kHz)
SCALE = 250         # one step of the byte is this much of the 16-bit range
MARK = 30_000       # the first block of a clip, so a clip that is not one of ours reads as no words


def wave(pcm: bytes, rate: int = 16_000) -> bytes:
    size = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + size) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", size) + pcm)


def samples_of(wav: bytes) -> list[int]:
    at = wav.find(b"data")
    if wav[:4] != b"RIFF" or at < 0:
        return []
    body = wav[at + 8:]
    return list(struct.unpack("<%dh" % (len(body) // 2), body[: len(body) // 2 * 2]))


def encode(text: str) -> bytes:
    """The clip that says `text`: a mark block, then one block per byte of its UTF-8."""
    samples = [MARK] * BLOCK
    for byte in text.encode("utf-8"):
        samples.extend([(byte - 128) * SCALE] * BLOCK)
    return wave(struct.pack("<%dh" % len(samples), *samples))


def decode(wav: bytes) -> str:
    """The words of a clip made by `encode`; a clip that is not one (silence, noise) has none."""
    samples = samples_of(wav)
    blocks = [samples[i:i + BLOCK] for i in range(0, len(samples) - BLOCK + 1, BLOCK)]
    if not blocks or any(abs(value - MARK) > 1 for value in blocks[0]):
        return ""
    data = bytearray()
    for block in blocks[1:]:
        byte = round(sum(block) / len(block) / SCALE) + 128
        if not 0 <= byte <= 255:
            return ""
        data.append(byte)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("tts", "stt"):
        print("usage: loopback_engine.py tts|stt", file=sys.stderr)
        return 2
    data = sys.stdin.buffer.read()
    if argv[1] == "tts":
        sys.stdout.buffer.write(encode(data.decode("utf-8", "replace")))
    else:
        sys.stdout.buffer.write(decode(data).encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
