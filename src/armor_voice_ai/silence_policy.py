"""What it takes to silence the alarms by voice: nothing (the default), a spoken PIN, or a second confirming turn.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

The installation chooses the strictness in ARMOR-SERVER (`voice.silence_confirmation`) and the server passes it on as `policy: {"silence_confirmation": "off" | "pin" | "double_turn"}`
(a JSON field of `/v1/command`, the header `X-Armor-Policy` of `/v1/turn`). A policy that is missing means `off`, exactly as before. A policy that is there but cannot be read, or names
a mode this service does not know, is taken as `double_turn`: a broken setting never switches a protection off.

* `off`: "silence" is accepted at once.
* `double_turn`: the first "silence" is not carried out; the service asks to say yes, and only a yes within a few seconds is passed on.
* `pin`: the first "silence" is not carried out; the service asks for the PIN, spoken digit by digit (or as digits), and only the right PIN is passed on. The PIN is set in the
  environment of this service (`ARMOR_VOICE_SILENCE_PIN`), is compared in constant time, is never written to a log or to the audit file, and is not echoed back in `heard`. Three
  wrong PINs lock silencing by voice, for every panel, for five minutes. With the mode `pin` and no PIN set up nothing is silenced by voice (it fails closed).
"""

from __future__ import annotations

import hmac
import json
import threading
import time
import unicodedata
from collections.abc import Callable

OFF, DOUBLE_TURN, PIN = "off", "double_turn", "pin"
MODES = (OFF, DOUBLE_TURN, PIN)
MAX_POLICY_BYTES = 256
#: How long the service waits for the yes or for the PIN after asking.
DOUBLE_TURN_VALIDITY_S = 15.0
PIN_VALIDITY_S = 20.0
MAX_PIN_ATTEMPTS = 3
LOCKOUT_S = 300.0
MIN_PIN_DIGITS, MAX_PIN_DIGITS = 4, 12


def mode_from_policy(policy: object) -> str:
    """The silence mode a policy asks for: `off` when there is none, `double_turn` when it is there but unreadable or unknown."""
    if policy is None:
        return OFF
    if not isinstance(policy, dict):
        return DOUBLE_TURN
    value = policy.get("silence_confirmation", OFF)
    return value if isinstance(value, str) and value in MODES else DOUBLE_TURN


def mode_from_header(raw: str | None) -> str:
    """The same, from the `X-Armor-Policy` header of a turn (a JSON object); no header is `off`."""
    if raw is None or raw == "":
        return OFF
    if len(raw.encode("utf-8", "replace")) > MAX_POLICY_BYTES:
        return DOUBLE_TURN
    try:
        return mode_from_policy(json.loads(raw))
    except ValueError:
        return DOUBLE_TURN


# ---- the spoken PIN -------------------------------------------------------------------------------------------------------------------------------

#: Digit words per language, as `normalize_text` leaves them (lower case, no accents). A word that is not here is ignored when a PIN is read, so "my PIN is one two three four" works.
_WORDS: dict[str, dict[str, str]] = {
    "en": {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"},
    "es": {"cero": "0", "uno": "1", "un": "1", "dos": "2", "tres": "3", "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9"},
    "de": {"null": "0", "eins": "1", "ein": "1", "zwei": "2", "drei": "3", "vier": "4", "funf": "5", "sechs": "6", "sieben": "7", "acht": "8", "neun": "9"},
    "fr": {"zero": "0", "un": "1", "une": "1", "deux": "2", "trois": "3", "quatre": "4", "cinq": "5", "six": "6", "sept": "7", "huit": "8", "neuf": "9"},
    "it": {"zero": "0", "uno": "1", "un": "1", "due": "2", "tre": "3", "quattro": "4", "cinque": "5", "sei": "6", "sette": "7", "otto": "8", "nove": "9"},
    "pt": {"zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5", "seis": "6", "sete": "7", "oito": "8", "nove": "9"},
    "ja": {"zero": "0", "rei": "0", "ichi": "1", "ni": "2", "san": "3", "yon": "4", "shi": "4", "go": "5", "roku": "6", "nana": "7", "shichi": "7", "hachi": "8", "kyu": "9", "ku": "9",
           "ゼロ": "0", "れい": "0", "いち": "1", "に": "2", "さん": "3", "よん": "4", "し": "4", "ご": "5", "ろく": "6", "なな": "7", "しち": "7", "はち": "8", "きゅう": "9", "く": "9"},
    "zh": {},
}
_CJK = {"零": "0", "〇": "0", "一": "1", "二": "2", "两": "2", "兩": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}


def spoken_digits(words: str, language: str) -> str:
    """The digits in what was heard (already normalised): digit characters of any script, the digit words of the language, and the Chinese/Japanese numerals. Anything else is skipped."""
    table = _WORDS.get(language, {})
    digits: list[str] = []
    for token in words.split():
        if token in table:
            digits.append(table[token])
            continue
        for char in token:
            if char in _CJK:
                digits.append(_CJK[char])
            else:
                value = unicodedata.digit(char, None)
                if value is not None:
                    digits.append(str(value))
    return "".join(digits)


class PinGuard:
    """The PIN that silences by voice, and the limit on guesses. One guard serves every panel: a client name is chosen by the caller, so a count per name could be walked around."""

    def __init__(self, pin: str | None, now: Callable[[], float] = time.monotonic) -> None:
        if pin is not None and (not pin.isascii() or not pin.isdigit() or not MIN_PIN_DIGITS <= len(pin) <= MAX_PIN_DIGITS):
            raise ValueError(f"the PIN must be {MIN_PIN_DIGITS} to {MAX_PIN_DIGITS} digits")
        self._pin = pin
        self._now = now
        self._failures = 0
        self._locked_until = 0.0
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return self._pin is not None

    @property
    def locked(self) -> bool:
        with self._lock:
            return self._now() < self._locked_until

    def check(self, digits: str) -> str:
        """`ok`, `wrong`, `locked` or `unset`. A right PIN clears the count; the third wrong one locks for LOCKOUT_S. While locked even the right PIN is refused."""
        with self._lock:
            if self._pin is None:
                return "unset"
            if self._now() < self._locked_until:
                return "locked"
            if hmac.compare_digest(digits.encode("ascii", "replace"), self._pin.encode("ascii")):
                self._failures = 0
                return "ok"
            self._failures += 1
            if self._failures >= MAX_PIN_ATTEMPTS:
                self._failures = 0
                self._locked_until = self._now() + LOCKOUT_S
                return "locked"
            return "wrong"


# ---- what is said ---------------------------------------------------------------------------------------------------------------------------------

ASK_YES = {"en": "Say yes to silence the alarms.", "es": "Di sí para silenciar las alarmas.", "de": "Sag Ja, um die Alarme stummzuschalten.", "fr": "Dites oui pour couper le son des alarmes.",
           "it": "Di' sì per silenziare gli allarmi.", "ja": "アラームを消音するには「はい」と言ってください。", "zh": "说“是”即可静音警报。", "pt": "Diga sim para silenciar os alarmes."}
ASK_PIN = {"en": "Say your PIN to silence the alarms.", "es": "Di tu PIN para silenciar las alarmas.", "de": "Nenne deine PIN, um die Alarme stummzuschalten.", "fr": "Dites votre PIN pour couper le son des alarmes.",
           "it": "Di' il tuo PIN per silenziare gli allarmi.", "ja": "アラームを消音するには PIN を言ってください。", "zh": "请说出 PIN 以静音警报。", "pt": "Diga o seu PIN para silenciar os alarmes."}
WRONG_PIN = {"en": "That PIN is not right.", "es": "Ese PIN no es correcto.", "de": "Diese PIN ist nicht richtig.", "fr": "Ce PIN n'est pas le bon.", "it": "Questo PIN non è corretto.",
             "ja": "PIN が正しくありません。", "zh": "PIN 不正确。", "pt": "Esse PIN não está correto."}
LOCKED = {"en": "Silencing by voice is locked for a while: use the screen.", "es": "Silenciar por voz está bloqueado un rato: usa la pantalla.", "de": "Stummschalten per Sprache ist für eine Weile gesperrt: nutze den Bildschirm.",
          "fr": "Couper le son par la voix est bloqué un moment : utilisez l'écran.", "it": "Silenziare a voce è bloccato per un po': usa lo schermo.", "ja": "音声での消音は一時的にロックされています。画面で操作してください。",
          "zh": "语音静音已被暂时锁定，请在屏幕上操作。", "pt": "Silenciar por voz está bloqueado durante algum tempo: use o ecrã."}
NO_PIN_SET = {"en": "Silencing by voice needs a PIN that is not set up: use the screen.", "es": "Silenciar por voz necesita un PIN que no está configurado: usa la pantalla.",
              "de": "Zum Stummschalten per Sprache ist eine PIN nötig, die nicht eingerichtet ist: nutze den Bildschirm.", "fr": "Couper le son par la voix demande un PIN qui n'est pas configuré : utilisez l'écran.",
              "it": "Per silenziare a voce serve un PIN che non è configurato: usa lo schermo.", "ja": "音声での消音には PIN が必要ですが、設定されていません。画面で操作してください。",
              "zh": "语音静音需要 PIN，但尚未设置，请在屏幕上操作。", "pt": "Silenciar por voz precisa de um PIN que não está configurado: use o ecrã."}
