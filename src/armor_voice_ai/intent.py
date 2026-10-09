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

from .phrases import PHRASES

ARM, DISARM, STATUS, SILENCE = "arm", "disarm", "status", "silence"
#: The commands that *ask* (nothing changes) and those that *do*; the server carries out the second kind with the session of the person who asked.
QUERIES = frozenset({"status", "alarms", "nodes", "cameras", "radar", "solar", "electrical", "network", "time", "help"})
ACTIONS = frozenset({ARM, DISARM, SILENCE, "lights_on", "lights_off"})
ALLOWED = QUERIES | ACTIONS
#: Intents that change the security state and therefore need an explicit confirmation turn.
SENSITIVE = frozenset({ARM, DISARM})
MAX_TEXT_LENGTH = 200

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


# The allow-list: every phrase of phrases.py, normalised with the same function that normalises what is heard (so a phrase written with its accents matches what was said
# without them). Built once, when the module loads.
_PHRASES: dict[str, frozenset[str]] = {}


def _build() -> None:
    for intent, by_language in PHRASES.items():
        _PHRASES[intent] = frozenset(normalize_text(phrase) for phrases in by_language.values() for phrase in phrases)


_build()


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
