"""Speech-to-intent: a closed allow-list, never a free-form command.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Speech recognition output is untrusted text. It is normalised (Unicode NFKC,
lower case, punctuation and polite filler removed) and must then equal one of a
small set of known phrases in English, Spanish, German, French, Italian, Japanese or Chinese. Anything else, including any
phrase that could mean two different intents, is not understood. The text is
never forwarded as a shell or device command.
"""

from __future__ import annotations

import re
import unicodedata

ARM, DISARM, STATUS, SILENCE = "arm", "disarm", "status", "silence"
ALLOWED = frozenset({ARM, DISARM, STATUS, SILENCE})
#: Intents that change the security state and therefore need an explicit confirmation turn.
SENSITIVE = frozenset({ARM, DISARM})
MAX_TEXT_LENGTH = 200

# Every phrase is written already normalised (lower case, no accents, no punctuation): test_every_phrase_is_its_own_normal_form checks it, and that no phrase
# means two different intents.
_PHRASES: dict[str, frozenset[str]] = {
    ARM: frozenset({
        "arm", "arm system", "arm the system", "armar", "armar sistema", "armar el sistema", "arma el sistema", "activar alarma", "activa la alarma",
        "scharfschalten", "alarm scharfschalten", "system scharfschalten", "das system scharfschalten",
        "armer", "armer le systeme", "armer l alarme", "activer l alarme",
        "armare", "armare il sistema", "attivare l allarme", "attiva l allarme",
        "警備開始", "警備を開始", "警備を開始して", "布防", "系统布防", "开启警戒",
    }),
    DISARM: frozenset({
        "disarm", "disarm system", "disarm the system", "desarmar", "desarmar sistema", "desarmar el sistema", "desarma el sistema", "desactivar alarma", "desactiva la alarma",
        "entscharfen", "alarm entscharfen", "system entscharfen", "das system entscharfen",
        "desarmer", "desarmer le systeme", "desarmer l alarme", "desactiver l alarme",
        "disarmare", "disarmare il sistema", "disattivare l allarme", "disattiva l allarme",
        "警備解除", "警備を解除", "警備を解除して", "撤防", "系统撤防", "解除警戒",
    }),
    STATUS: frozenset({
        "status", "system status", "what is the status", "estado", "estado del sistema", "cual es el estado",
        "systemstatus", "wie ist der status", "statut", "etat du systeme", "quel est l etat", "stato", "stato del sistema", "qual e lo stato",
        "状態", "システムの状態", "状态", "系统状态",
    }),
    SILENCE: frozenset({
        "silence", "silence alarm", "silence the alarm", "silenciar", "silenciar alarma", "silenciar la alarma", "silencia la alarma",
        "stummschalten", "alarm stummschalten", "den alarm stummschalten",
        "silence alarme", "faire taire l alarme", "silenzio", "silenzia", "silenzia l allarme", "silenzia allarme",
        "警報を止めて", "警報停止", "消音", "静音报警",
    }),
}
# Polite words and ways of calling the assistant that are dropped before the phrase is compared (whole words only). Japanese and Chinese are written without
# spaces, so they have no filler: their phrases are listed with and without the polite ending.
_FILLER = re.compile(
    r"\b(please|kindly|could you|can you|would you|hey|armor|"
    r"por favor|oye|oiga|venga|bueno|vale|puedes|podrias|"
    r"bitte|kannst du|konntest du|"
    r"s il vous plait|s il te plait|svp|stp|"
    r"per favore|per piacere|ehi)\b"
)
_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_text(text: str) -> str:
    """Canonical form of a transcript: NFKC, lower case, no accents, punctuation or filler."""
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text).lower())
    without_accents = "".join(char for char in folded if not unicodedata.combining(char))
    cleaned = _FILLER.sub(" ", _PUNCTUATION.sub(" ", without_accents))
    return " ".join(cleaned.split())


def parse_intent(text: object) -> str | None:
    """The intent a transcript means, or None when it is not one of the known phrases."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_LENGTH:
        return None
    normalized = normalize_text(text)
    matches = {intent for intent, phrases in _PHRASES.items() if normalized in phrases}
    return next(iter(matches)) if len(matches) == 1 else None


def normalize(text: str) -> str:
    """The intent name for a transcript; raises ValueError when it is not allowed."""
    intent = parse_intent(text)
    if intent is None:
        raise ValueError("intent is not allowed")
    return intent
