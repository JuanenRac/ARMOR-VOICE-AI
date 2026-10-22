"""The two-turn policy for spoken commands.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

* An unknown or ambiguous phrase is not accepted.
* the queries, ``silence`` and the lights are accepted at once (the server decides what a ``silence`` by voice is worth: it does not stop a critical alarm from being escalated).
* ``arm`` and ``disarm`` first return a confirmation token and are **not**
  accepted; only a later turn that echoes the service's own valid token for
  that same intent is accepted.

The decision is a recommendation to ARMOR-SERVER, which still authenticates and
authorises the action. Nothing here performs it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .confirmation import VALID, ConfirmationSigner
from .intent import SENSITIVE, SILENCE, parse_intent
from .silence_policy import DOUBLE_TURN, OFF, PIN, PinGuard

NOT_UNDERSTOOD, CONFIRMATION_NEEDED, ACCEPTED, CONFIRMATION_REFUSED = "not-understood", "confirmation-needed", "accepted", "confirmation-refused"
PIN_NEEDED, PIN_REFUSED = "pin-needed", "pin-refused"


@dataclass(frozen=True)
class VoiceDecision:
    accepted: bool
    requires_confirmation: bool
    intent: str | None
    outcome: str = NOT_UNDERSTOOD
    confirmation_token: str | None = None
    reason: str = ""


def evaluate(text: str, signer: ConfirmationSigner, confirmation: str | None = None, subject: str = "", silence_mode: str = OFF, pin: str | None = None,
             pin_guard: PinGuard | None = None) -> VoiceDecision:
    intent = parse_intent(text)
    if intent is None:
        return VoiceDecision(False, False, None, NOT_UNDERSTOOD, reason="the phrase is not one of the known commands")
    if intent == SILENCE and silence_mode == PIN:
        # the PIN is the proof: it is checked here, never stored or reported back
        if pin is None:
            return VoiceDecision(False, False, intent, PIN_NEEDED, reason="silencing needs the PIN")
        verdict = (pin_guard or PinGuard(None)).check("".join(ch for ch in pin if ch.isascii() and ch.isdigit()))
        if verdict == "ok":
            return VoiceDecision(True, False, intent, ACCEPTED)
        return VoiceDecision(False, False, intent, PIN_REFUSED, reason=f"the PIN was refused: {verdict}")
    if intent not in SENSITIVE and not (intent == SILENCE and silence_mode == DOUBLE_TURN):
        return VoiceDecision(True, False, intent, ACCEPTED)
    if confirmation is None:
        return VoiceDecision(False, True, intent, CONFIRMATION_NEEDED, signer.issue(intent, subject), f"say it again with the confirmation within {signer.ttl_s:.0f} s")
    verdict = signer.verify(confirmation, intent, subject)
    if verdict == VALID:
        return VoiceDecision(True, False, intent, ACCEPTED)
    return VoiceDecision(False, False, intent, CONFIRMATION_REFUSED, reason=f"the confirmation was refused: {verdict}")
