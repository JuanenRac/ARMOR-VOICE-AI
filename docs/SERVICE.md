# The voice gateway as a service

`python -m armor_voice_ai.service --port 18090 --token-file <file with ARMOR_VOICE_TOKEN=...>` runs the closed gateway of [SAFETY.md](SAFETY.md) as a small HTTP
service for ARMOR-SERVER to ask. It only decides - which of the fifteen commands a phrase is, and the two-turn confirmation of arm and disarm - and never acts: the
server carries out what was accepted, with the session of the person who spoke.

| Route | What it does |
|---|---|
| `GET /healthz` | `{ok, service}`; needs no token |
| `POST /v1/command` | body `{text, language?, confirmation?}` (at most 2 KB), header `X-Armor-Voice-Token`; answers what was understood, `confirmation_token` when a second turn is needed, and `speech` in the language asked for |

`POST /v1/turn` (when a speech engine is configured) takes the audio of one turn from the wall panel - body raw 16 kHz 16-bit mono PCM of at most 480 000 bytes, `Content-Type: audio/L16;rate=16000`, `X-Armor-Language`, the same token - and answers `{heard, reply, audio?}`: 411/413 for the length, 415 for the type, 422 for the language, 501 when there is no engine or no server configured, 503 when two turns are already running, 504 when the speech engine took so long that the server was not asked (the panel gives up after twelve seconds; past nine nothing is executed). Settings: `ARMOR_VOICE_STT_COMMAND`, `ARMOR_VOICE_TTS_COMMAND` (programs read from the standard input, run without a shell and with a short environment: PATH, HOME, LANG, TMPDIR and the `ARMOR_VOICE_ENGINE_*` variables), `ARMOR_VOICE_SERVER_URL`, `ARMOR_VOICE_SERVER_TOKEN` and `ARMOR_VOICE_CONFIRM_SECRET`. The wall panel is a device on the network and the service listens on the loopback only: either a proxy of the server forwards the turn, or `--allow-remote` is used behind TLS; the token and the audio must not cross the network in clear.

It listens on the loopback address only (it refuses another one without `--allow-remote`), compares the token in constant time, never logs what was said, and signs
the confirmations with `ARMOR_VOICE_CONFIRM_SECRET`. On the bench it is installed by `ARMOR-DEVOPS/scripts/install_cm5.sh --with-voice`.
