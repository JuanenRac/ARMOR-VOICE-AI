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
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .confirmation import ConfirmationSigner
from .session import ACCEPTED, CONFIRMATION_NEEDED, CONFIRMATION_REFUSED, evaluate

# What the gateway says back, in the language the caller asks for (`language`, one of these codes; English when none is given).
SPEECH_BY_LANGUAGE = {
    "en": {CONFIRMATION_NEEDED: "Please confirm", ACCEPTED: "Command accepted", CONFIRMATION_REFUSED: "Confirmation refused", "": "Command not recognised"},
    "es": {CONFIRMATION_NEEDED: "Por favor, confirma", ACCEPTED: "Orden aceptada", CONFIRMATION_REFUSED: "Confirmaci\u00f3n rechazada", "": "Orden no reconocida"},
    "de": {CONFIRMATION_NEEDED: "Bitte best\u00e4tigen", ACCEPTED: "Befehl akzeptiert", CONFIRMATION_REFUSED: "Best\u00e4tigung abgelehnt", "": "Befehl nicht erkannt"},
    "fr": {CONFIRMATION_NEEDED: "Veuillez confirmer", ACCEPTED: "Commande accept\u00e9e", CONFIRMATION_REFUSED: "Confirmation refus\u00e9e", "": "Commande non reconnue"},
    "it": {CONFIRMATION_NEEDED: "Conferma, per favore", ACCEPTED: "Comando accettato", CONFIRMATION_REFUSED: "Conferma rifiutata", "": "Comando non riconosciuto"},
    "ja": {CONFIRMATION_NEEDED: "\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044", ACCEPTED: "\u30b3\u30de\u30f3\u30c9\u3092\u53d7\u3051\u4ed8\u3051\u307e\u3057\u305f", CONFIRMATION_REFUSED: "\u78ba\u8a8d\u304c\u62d2\u5426\u3055\u308c\u307e\u3057\u305f", "": "\u30b3\u30de\u30f3\u30c9\u3092\u8a8d\u8b58\u3067\u304d\u307e\u305b\u3093"},
    "zh": {CONFIRMATION_NEEDED: "\u8bf7\u786e\u8ba4", ACCEPTED: "\u547d\u4ee4\u5df2\u63a5\u53d7", CONFIRMATION_REFUSED: "\u786e\u8ba4\u88ab\u62d2\u7edd", "": "\u65e0\u6cd5\u8bc6\u522b\u547d\u4ee4"},
}
SPEECH = SPEECH_BY_LANGUAGE["en"]   # kept for callers of the English table
MAX_LINE_BYTES = 2048


def handle_request(request: object, signer: ConfirmationSigner, audit: Path | None = None) -> dict[str, object]:
    if not isinstance(request, dict):
        return {"accepted": False, "error": "invalid request shape"}
    if "confirmed" in request:
        return {"accepted": False, "error": "a confirmed flag is not accepted; echo the confirmation token the service issued"}
    if set(request) - {"text", "confirmation", "language"}:
        return {"accepted": False, "error": "invalid request shape"}
    text, confirmation, language = request.get("text"), request.get("confirmation"), request.get("language", "en")
    if not isinstance(text, str) or (confirmation is not None and not isinstance(confirmation, str)) or not isinstance(language, str) or language not in SPEECH_BY_LANGUAGE:
        return {"accepted": False, "error": "invalid request fields"}
    decision = evaluate(text, signer, confirmation)
    answer = asdict(decision)
    spoken = SPEECH_BY_LANGUAGE[language]
    answer["speech"] = spoken.get(decision.outcome, spoken[""])
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
    except OSError as error:
        # Recording must never break a spoken command, but a decision that left no trace is said (on stderr: stdout is the protocol).
        logging.getLogger(__name__).warning("the audit line could not be written to %s: %s", path, error)


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
