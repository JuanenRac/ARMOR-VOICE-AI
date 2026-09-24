"""Speech-to-intent: a closed allow-list, never a free-form command.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Speech recognition output is untrusted text. It is normalised (Unicode NFKC,
lower case, punctuation and polite filler removed) and must then equal one of a
small set of known phrases in English or Spanish. Anything else, including any
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

_PHRASES: dict[str, frozenset[str]] = {
    ARM: frozenset({"arm", "arm system", "arm the system", "armar", "armar sistema", "armar el sistema", "activar alarma", "activa la alarma"}),
    DISARM: frozenset({"disarm", "disarm system", "disarm the system", "desarmar", "desarmar sistema", "desarmar el sistema", "desactivar alarma", "desactiva la alarma"}),
    STATUS: frozenset({"status", "system status", "what is the status", "estado", "estado del sistema", "cual es el estado"}),
    SILENCE: frozenset({"silence", "silence alarm", "silence the alarm", "silenciar", "silenciar alarma", "silenciar la alarma"}),
}
_FILLER = re.compile(r"\b(please|kindly|could you|can you|would you|hey|armor|por favor|oye|puedes|podrias)\b")
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
