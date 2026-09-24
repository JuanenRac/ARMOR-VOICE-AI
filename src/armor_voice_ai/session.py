"""The two-turn policy for spoken commands.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

* An unknown or ambiguous phrase is not accepted.
* ``status`` and ``silence`` are accepted at once.
* ``arm`` and ``disarm`` first return a confirmation token and are **not**
  accepted; only a later turn that echoes the service's own valid token for
  that same intent is accepted.

The decision is a recommendation to ARMOR-SERVER, which still authenticates and
authorises the action. Nothing here performs it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .confirmation import VALID, ConfirmationSigner
from .intent import SENSITIVE, parse_intent

NOT_UNDERSTOOD, CONFIRMATION_NEEDED, ACCEPTED, CONFIRMATION_REFUSED = "not-understood", "confirmation-needed", "accepted", "confirmation-refused"


@dataclass(frozen=True)
class VoiceDecision:
    accepted: bool
    requires_confirmation: bool
    intent: str | None
    outcome: str = NOT_UNDERSTOOD
    confirmation_token: str | None = None
    reason: str = ""


def evaluate(text: str, signer: ConfirmationSigner, confirmation: str | None = None) -> VoiceDecision:
    intent = parse_intent(text)
    if intent is None:
        return VoiceDecision(False, False, None, NOT_UNDERSTOOD, reason="the phrase is not one of the known commands")
    if intent not in SENSITIVE:
        return VoiceDecision(True, False, intent, ACCEPTED)
    if confirmation is None:
        return VoiceDecision(False, True, intent, CONFIRMATION_NEEDED, signer.issue(intent), f"say it again with the confirmation within {signer.ttl_s:.0f} s")
    verdict = signer.verify(confirmation, intent)
    if verdict == VALID:
        return VoiceDecision(True, False, intent, ACCEPTED)
    return VoiceDecision(False, False, intent, CONFIRMATION_REFUSED, reason=f"the confirmation was refused: {verdict}")
