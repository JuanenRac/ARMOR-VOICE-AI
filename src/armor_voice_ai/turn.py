"""One spoken turn: audio in, the answer (text and, when there is a speech engine, audio) out.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

The panel of the house (ARMOR-HMI) sends what the microphones heard to `POST /v1/turn` and plays what comes back. This module is the middle of that: the speech engine turns the audio into
words (STT), the words are given to ARMOR-SERVER's own voice route - the one that decides, holds the two-turn confirmation and carries out what was accepted, in the audit trail -
and the answer is turned into audio (TTS) when an engine for it is configured.

Nothing here understands speech or says it by itself: the engines are programs the installation chooses (whisper.cpp or Vosk for hearing, Piper for speaking, anything that reads
standard input and writes standard output) and they are given in the environment, without a shell. Without an engine the turn says so (`stt_unavailable`) instead of inventing a transcript.

The panel has no keyboard, so the confirmation of "arm the system" is spoken: the service remembers the question it asked this client for half a minute and takes the next turn that
says yes (in the language of the panel) as the confirmation, and the next that says no as a refusal. Disarming is never done from here: it needs the PIN of a person, and a PIN is not said aloud.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from shlex import split as shell_split

MAX_AUDIO_BYTES = 480_000          # fifteen seconds of 16 kHz, 16-bit mono
MAX_REPLY_AUDIO_BYTES = 200_000    # what the panel accepts to play (it takes at most 256 KB of answer in all)
ENGINE_TIMEOUT_S = 25.0
PENDING_VALIDITY_S = 30.0

YES = {"en": ("yes", "yeah", "confirm", "do it"), "es": ("sí", "si", "confirmo", "adelante", "vale"), "de": ("ja", "bestätige", "mach das"), "fr": ("oui", "confirme", "vas-y"),
       "it": ("sì", "si", "conferma", "vai"), "ja": ("はい", "ええ", "確認"), "zh": ("是", "是的", "确认", "好")}
NO = {"en": ("no", "cancel", "stop"), "es": ("no", "cancela", "cancelar"), "de": ("nein", "abbrechen"), "fr": ("non", "annule"), "it": ("no", "annulla"), "ja": ("いいえ", "キャンセル"), "zh": ("不", "不要", "取消")}
DISARM_REFUSED = {"en": "Disarming needs your PIN: do it on the screen.", "es": "Para desarmar hace falta tu PIN: hazlo en la pantalla.", "de": "Zum Entschärfen brauchst du deine PIN: mach es auf dem Bildschirm.",
                  "fr": "Pour désarmer il faut votre PIN : faites-le sur l'écran.", "it": "Per disarmare serve il tuo PIN: fallo sullo schermo.", "ja": "解除には PIN が必要です。画面で操作してください。", "zh": "撤防需要 PIN，请在屏幕上操作。"}
CANCELLED = {"en": "Cancelled.", "es": "Cancelado.", "de": "Abgebrochen.", "fr": "Annulé.", "it": "Annullato.", "ja": "キャンセルしました。", "zh": "已取消。"}
NOTHING_HEARD = {"en": "I did not hear anything.", "es": "No he oído nada.", "de": "Ich habe nichts gehört.", "fr": "Je n'ai rien entendu.", "it": "Non ho sentito nulla.", "ja": "聞き取れませんでした。", "zh": "没有听到内容。"}


class TurnError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


class CommandEngine:
    """A speech engine that is a program: the input goes to its standard input and the result comes from its standard output. No shell, a time limit and a size limit."""

    def __init__(self, command: str | list[str], timeout_s: float = ENGINE_TIMEOUT_S) -> None:
        self._argv = list(command) if isinstance(command, list) else shell_split(command)
        if not self._argv:
            raise ValueError("an engine needs a command")
        self._timeout = timeout_s

    @staticmethod
    def _environment(language: str) -> dict[str, str]:
        """What the engine is given to run with: the usual environment without any secret (the tokens of this service and of the server are not for a speech program), and the language."""
        kept = {key: value for key, value in os.environ.items() if not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "KEY"))}
        kept["ARMOR_VOICE_LANGUAGE"] = language
        return kept

    def run(self, data: bytes, language: str, limit: int) -> bytes:
        try:
            done = subprocess.run(self._argv, input=data, capture_output=True, timeout=self._timeout, check=False, env=self._environment(language))
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TurnError(502, "engine_failed") from error
        if done.returncode != 0 or len(done.stdout) > limit:
            raise TurnError(502, "engine_failed")
        return done.stdout


def wav_from_pcm(pcm: bytes, rate: int = 16_000) -> bytes:
    """A RIFF/WAVE header in front of 16-bit mono PCM, which is what the speech engines read."""
    size = len(pcm)
    header = (b"RIFF" + (36 + size).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
              + rate.to_bytes(4, "little") + (rate * 2).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + size.to_bytes(4, "little"))
    return header + pcm


def pcm_from_wav(wav: bytes) -> bytes:
    """The samples of a WAVE file made by a text-to-speech engine (16-bit mono is what the panel plays): the data chunk, found by walking the chunks."""
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise TurnError(502, "engine_failed")
    position = 12
    while position + 8 <= len(wav):
        name, size = wav[position:position + 4], int.from_bytes(wav[position + 4:position + 8], "little")
        if name == b"data":
            return wav[position + 8:position + 8 + size]
        position += 8 + size + (size & 1)
    raise TurnError(502, "engine_failed")


@dataclass
class ServerLink:
    """ARMOR-SERVER's route for written and spoken commands, with the operator token of the installation."""
    url: str
    token: str
    timeout_s: float = 8.0

    def command(self, text: str, language: str, confirmation: str | None) -> dict[str, object]:
        body: dict[str, object] = {"text": text, "language": language}
        if confirmation:
            body["confirmation"] = confirmation
        request = urllib.request.Request(self.url.rstrip("/") + "/api/v1/voice/command", data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}", "X-Requested-With": "armor"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as reply:  # noqa: S310 - the address is the installation's own
                return json.loads(reply.read(65_536).decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            error.close()
            raise TurnError(502, f"server_{error.code}") from error
        except (OSError, ValueError) as error:
            raise TurnError(502, "server_not_answering") from error


class TurnService:
    def __init__(self, stt: CommandEngine | None, tts: CommandEngine | None, server: ServerLink | Callable[[str, str, str | None], dict[str, object]] | None,
                 now: Callable[[], float] = time.time) -> None:
        self._stt, self._tts, self._now = stt, tts, now
        self._ask = server.command if isinstance(server, ServerLink) else server
        self._pending: dict[str, tuple[str, str, float]] = {}
        self._lock = threading.Lock()

    @property
    def can_hear(self) -> bool:
        return self._stt is not None and self._ask is not None

    def handle(self, pcm: bytes, language: str, client: str) -> dict[str, object]:
        if self._stt is None:
            raise TurnError(501, "stt_unavailable")
        if self._ask is None:
            raise TurnError(501, "server_not_configured")
        if not pcm or len(pcm) > MAX_AUDIO_BYTES or len(pcm) % 2:
            raise TurnError(413 if len(pcm) > MAX_AUDIO_BYTES else 400, "bad_audio")
        heard = self._stt.run(wav_from_pcm(pcm), language, 4_096).decode("utf-8", "replace").strip()[:400]
        if not heard:
            return self._answer("", NOTHING_HEARD[language], language)
        words = heard.lower().strip(" .,!?¡¿")
        pending = self._take_pending(client)
        if pending is not None:
            original, token = pending
            if words in NO.get(language, ()):
                return self._answer(heard, CANCELLED[language], language)
            if words in YES.get(language, ()):
                return self._finish(heard, self._ask(original, language, token), language, client)
            # anything else is a new command: the question that was waiting is dropped
        return self._finish(heard, self._ask(heard, language, None), language, client)

    def _finish(self, heard: str, answer: dict[str, object], language: str, client: str) -> dict[str, object]:
        if answer.get("intent") == "disarm":
            return self._answer(heard, DISARM_REFUSED[language], language)
        token = answer.get("confirmation_token")
        if isinstance(token, str) and token:
            with self._lock:
                self._pending[client] = (heard, token, self._now() + PENDING_VALIDITY_S)
        return self._answer(heard, str(answer.get("speech") or ""), language)

    def _take_pending(self, client: str) -> tuple[str, str] | None:
        with self._lock:
            held = self._pending.pop(client, None)
            for key in [key for key, (_text, _token, until) in self._pending.items() if until < self._now()]:
                del self._pending[key]
        if held is None or held[2] < self._now():
            return None
        return held[0], held[1]

    def _answer(self, heard: str, reply: str, language: str) -> dict[str, object]:
        result: dict[str, object] = {"heard": heard, "reply": reply}
        if self._tts is not None and reply:
            try:
                audio = pcm_from_wav(self._tts.run(reply.encode("utf-8"), language, MAX_REPLY_AUDIO_BYTES * 2))
                if len(audio) <= MAX_REPLY_AUDIO_BYTES:
                    result["audio"] = base64.b64encode(audio).decode("ascii")
            except TurnError:
                pass   # the words still go; a speech engine that failed does not take the answer with it
        return result
