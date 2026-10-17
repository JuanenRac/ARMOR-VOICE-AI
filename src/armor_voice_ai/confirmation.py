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
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable

CONFIRMATION_VALIDITY_S = 30.0
_USED_LIMIT = 1024

VALID, EXPIRED, INVALID, WRONG_INTENT, REPLAYED, WRONG_SUBJECT = "valid", "expired", "invalid", "wrong-intent", "replayed", "wrong-subject"


class ConfirmationSigner:
    def __init__(self, secret: bytes | None = None, ttl_s: float = CONFIRMATION_VALIDITY_S, now: Callable[[], float] = time.time) -> None:
        # Without a configured secret a random one is used: pending tokens die with the process, which is the safe failure.
        configured = os.environ.get("ARMOR_VOICE_CONFIRM_SECRET")    # (os.environb does not exist on Windows)
        self._secret = secret or (configured.encode("utf-8") if configured else None)
        if not self._secret:
            self._secret = secrets.token_bytes(32)
            logging.getLogger(__name__).warning("ARMOR_VOICE_CONFIRM_SECRET is not set: a random secret is used and the pending confirmations are lost when the process stops")
        if len(self._secret) < 16:
            raise ValueError("the confirmation secret must be at least 16 bytes")
        self._ttl = ttl_s
        self._now = now
        self._used: OrderedDict[str, float] = OrderedDict()
        # The server answers several requests at once: checking that a nonce is new and recording it must be one step, or two requests with the same token both pass.
        self._lock = threading.Lock()

    @property
    def ttl_s(self) -> float:
        return self._ttl

    def _sign(self, body: str) -> str:
        return hmac.new(self._secret, body.encode("ascii"), hashlib.sha256).hexdigest()

    def issue(self, intent: str, subject: str = "") -> str:
        """A token for this intent, and for the person who asked (`subject`, as the caller names them): a token asked for by one person is not good for another."""
        payload = {"i": intent, "e": self._now() + self._ttl, "n": secrets.token_hex(8), "s": subject}
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode("ascii").rstrip("=")
        return f"{body}.{self._sign(body)}"

    def verify(self, token: object, intent: str, subject: str = "") -> str:
        """VALID, or the reason the token cannot be used for this intent. A valid token is consumed."""
        # Only ASCII can be a token; anything else is refused before it reaches the signature code (a character outside ASCII used to make it raise and cut the connection).
        if not isinstance(token, str) or not token.isascii() or token.count(".") != 1:
            return INVALID
        body, _, signature = token.partition(".")
        if not hmac.compare_digest(signature.encode("ascii"), self._sign(body).encode("ascii")):
            return INVALID
        try:
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            bound_intent, expires, nonce, bound_subject = payload["i"], float(payload["e"]), str(payload["n"]), str(payload.get("s", ""))
        except (ValueError, KeyError, TypeError):
            return INVALID
        if bound_intent != intent:
            return WRONG_INTENT
        if not hmac.compare_digest(bound_subject.encode("utf-8"), subject.encode("utf-8")):
            return WRONG_SUBJECT
        if self._now() > expires:
            return EXPIRED
        if expires - self._now() > self._ttl + 5.0:
            return INVALID   # a token cannot live longer than it was ever issued for (a clock that jumped back would stretch it)
        # The nonces of tokens that have expired are of no use any more (an expired token is refused on its own), so they are what is forgotten; one that could still be replayed is
        # NEVER pushed out to make room. When there are too many of those at once, the new token is refused rather than the old one forgotten.
        with self._lock:
            now = self._now()
            for old in [key for key, until in self._used.items() if until < now]:
                del self._used[old]
            if nonce in self._used:
                return REPLAYED
            if len(self._used) >= _USED_LIMIT:
                return INVALID
            self._used[nonce] = expires
        return VALID
