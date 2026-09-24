"""Line-oriented local gateway suitable for STT/TTS adapters and tests.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Request  (one JSON object per line):
    {"text": "arm the system"}                          first turn
    {"text": "arm the system", "confirmation": "<token>"}   second turn
Response:
    {"accepted": false, "requires_confirmation": true, "intent": "arm",
     "outcome": "confirmation-needed", "confirmation_token": "...", "speech": "..."}

The caller never states that something was confirmed: it can only echo a token
the service issued. Only the decision is optionally recorded (intent, outcome,
time, and a SHA-256 of the transcript), never audio and never the raw text.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .confirmation import ConfirmationSigner
from .session import ACCEPTED, CONFIRMATION_NEEDED, CONFIRMATION_REFUSED, evaluate

SPEECH = {
    CONFIRMATION_NEEDED: "Please confirm",
    ACCEPTED: "Command accepted",
    CONFIRMATION_REFUSED: "Confirmation refused",
}
MAX_LINE_BYTES = 2048


def handle_request(request: object, signer: ConfirmationSigner, audit: Path | None = None) -> dict[str, object]:
    if not isinstance(request, dict):
        return {"accepted": False, "error": "invalid request shape"}
    if "confirmed" in request:
        return {"accepted": False, "error": "a confirmed flag is not accepted; echo the confirmation token the service issued"}
    if set(request) - {"text", "confirmation"}:
        return {"accepted": False, "error": "invalid request shape"}
    text, confirmation = request.get("text"), request.get("confirmation")
    if not isinstance(text, str) or (confirmation is not None and not isinstance(confirmation, str)):
        return {"accepted": False, "error": "invalid request fields"}
    decision = evaluate(text, signer, confirmation)
    answer = asdict(decision)
    answer["speech"] = SPEECH.get(decision.outcome, "Command not recognised")
    if decision.confirmation_token is None:
        del answer["confirmation_token"]
    if not decision.reason:
        del answer["reason"]
    if audit is not None:
        _record(audit, decision.intent, decision.outcome, text)
    return answer


def _record(path: Path, intent: str | None, outcome: str, text: str) -> None:
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "intent": intent, "outcome": outcome, "transcript_sha256": hashlib.sha256(text.encode()).hexdigest()}
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass  # Recording must never break a spoken command.


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="A.R.M.O.R. voice gateway (JSON lines on stdin and stdout)")
    parser.add_argument("--audit-file", type=Path, help="append one line per decision (no audio, no raw text)")
    args = parser.parse_args(argv)
    signer = ConfirmationSigner()
    for line in sys.stdin:
        if len(line.encode("utf-8", "replace")) > MAX_LINE_BYTES:
            print('{"accepted":false,"error":"line too long"}', flush=True)
            continue
        try:
            print(json.dumps(handle_request(json.loads(line), signer, args.audit_file), separators=(",", ":")), flush=True)
        except json.JSONDecodeError:
            print('{"accepted":false,"error":"invalid JSON"}', flush=True)


if __name__ == "__main__":
    main()
