# The voice gateway as a service

`python -m armor_voice_ai.service --port 18090 --token-file <file with ARMOR_VOICE_TOKEN=...>` runs the closed gateway of [SAFETY.md](SAFETY.md) as a small HTTP
service for ARMOR-SERVER to ask. It only decides - which of the fifteen commands a phrase is, and the two-turn confirmation of arm and disarm - and never acts: the
server carries out what was accepted, with the session of the person who spoke.

| Route | What it does |
|---|---|
| `GET /healthz` | `{ok, service}`; needs no token |
| `POST /v1/command` | body `{text, language?, confirmation?}` (at most 2 KB), header `X-Armor-Voice-Token`; answers what was understood, `confirmation_token` when a second turn is needed, and `speech` in the language asked for |

It listens on the loopback address only (it refuses another one without `--allow-remote`), compares the token in constant time, never logs what was said, and signs
the confirmations with `ARMOR_VOICE_CONFIRM_SECRET`. On the bench it is installed by `ARMOR-DEVOPS/scripts/install_cm5.sh --with-voice`.
