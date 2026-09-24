"""Signed, single-use confirmation tokens for security-changing commands.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

A confirmation is something the *service* issues and later checks, never
something the caller merely claims. The first turn for "arm" returns a token
bound to that intent and to a short expiry; the second turn must echo it. The
token is signed with a secret the caller does not have, so it cannot be forged,
altered, re-targeted to another intent or used after it expired, and it works
once (a replay is refused).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable

CONFIRMATION_VALIDITY_S = 30.0
_USED_LIMIT = 1024

VALID, EXPIRED, INVALID, WRONG_INTENT, REPLAYED = "valid", "expired", "invalid", "wrong-intent", "replayed"


class ConfirmationSigner:
    def __init__(self, secret: bytes | None = None, ttl_s: float = CONFIRMATION_VALIDITY_S, now: Callable[[], float] = time.time) -> None:
        # Without a configured secret a random one is used: pending tokens die with the process, which is the safe failure.
        self._secret = secret or os.environb.get(b"ARMOR_VOICE_CONFIRM_SECRET") or secrets.token_bytes(32)
        if len(self._secret) < 16:
            raise ValueError("the confirmation secret must be at least 16 bytes")
        self._ttl = ttl_s
        self._now = now
        self._used: OrderedDict[str, float] = OrderedDict()

    @property
    def ttl_s(self) -> float:
        return self._ttl

    def _sign(self, body: str) -> str:
        return hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).hexdigest()

    def issue(self, intent: str) -> str:
        payload = {"i": intent, "e": self._now() + self._ttl, "n": secrets.token_hex(8)}
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode("ascii").rstrip("=")
        return f"{body}.{self._sign(body)}"

    def verify(self, token: object, intent: str) -> str:
        """VALID, or the reason the token cannot be used for this intent. A valid token is consumed."""
        if not isinstance(token, str) or token.count(".") != 1:
            return INVALID
        body, _, signature = token.partition(".")
        if not hmac.compare_digest(signature, self._sign(body)):
            return INVALID
        try:
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            bound_intent, expires, nonce = payload["i"], float(payload["e"]), str(payload["n"])
        except (ValueError, KeyError, TypeError):
            return INVALID
        if bound_intent != intent:
            return WRONG_INTENT
        if self._now() > expires:
            return EXPIRED
        if nonce in self._used:
            return REPLAYED
        self._used[nonce] = expires
        while len(self._used) > _USED_LIMIT:
            self._used.popitem(last=False)
        return VALID
