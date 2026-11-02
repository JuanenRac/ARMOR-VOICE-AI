"""Speech-to-intent: a closed allow-list, never a free-form command.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Speech recognition output is untrusted text. It is normalised (Unicode NFKC,
lower case, punctuation and polite filler removed) and must then equal one of a
small set of known phrases in English, Spanish, German, French, Italian, Portuguese, Japanese or Chinese. Anything else, including any
phrase that could mean two different intents, is not understood. The text is
never forwarded as a shell or device command.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .phrases import PHRASES

ARM, DISARM, STATUS, SILENCE = "arm", "disarm", "status", "silence"
#: The commands that *ask* (nothing changes) and those that *do*; the server carries out the second kind with the session of the person who asked.
QUERIES = frozenset({"status", "alarms", "nodes", "cameras", "radar", "solar", "electrical", "network", "time", "help"})
ACTIONS = frozenset({ARM, DISARM, SILENCE, "lights_on", "lights_off"})
ALLOWED = QUERIES | ACTIONS


@dataclass(frozen=True)
class IntentRisk:
    """What a spoken intent is worth, in one place: whether it only asks or does something, which confirmation it needs, whether a PIN is the proof and whether the wall panel may carry it out."""
    kind: str                  # "query" (nothing changes) or "action" (the server carries it out)
    confirmation: str          # "none", "signed" (a token echoed back) or "policy" (the server's silence policy chooses)
    pin_required: bool         # a PIN, typed on a screen, is the proof (never said aloud)
    allowed_from_panel: bool   # whether the panel's voice turn may carry it out


#: The single matrix of risk by intent. session.py (the text route) and turn.py (the panel turn) both read it, so no intent is special-cased by name elsewhere.
RISK: dict[str, IntentRisk] = {
    **{name: IntentRisk("query", "none", False, True) for name in sorted(QUERIES)},
    ARM: IntentRisk("action", "signed", False, True),
    DISARM: IntentRisk("action", "signed", True, False),
    SILENCE: IntentRisk("action", "policy", False, True),
    "lights_on": IntentRisk("action", "none", False, True),
    "lights_off": IntentRisk("action", "none", False, True),
}
#: Intents that change the security state and therefore need an explicit signed confirmation turn.
SENSITIVE = frozenset(name for name, risk in RISK.items() if risk.confirmation == "signed")


def allowed_from_panel(intent: object) -> bool:
    """Whether the voice turn of the wall panel may carry out this intent; an intent that is not in the matrix is not allowed."""
    risk = RISK.get(intent) if isinstance(intent, str) else None
    return risk is not None and risk.allowed_from_panel
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
_KANA_MARKS = frozenset("\u3099\u309a")


def normalize_text(text: str) -> str:
    """Canonical form of a transcript: NFKC, lower case, no accents, punctuation or filler."""
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text).lower())
    # The voiced marks of kana (U+3099, U+309A) are part of the letter ("ば" is not "は"): only the accents of the other scripts are dropped.
    without_accents = unicodedata.normalize("NFC", "".join(char for char in folded if char in _KANA_MARKS or not unicodedata.combining(char)))
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
