# The voice gateway as a service

`python -m armor_voice_ai.service --port 18090 --token-file <file with ARMOR_VOICE_TOKEN=...>` runs the closed gateway of [SAFETY.md](SAFETY.md) as a small HTTP
service for ARMOR-SERVER to ask. It only decides - which of the fifteen commands a phrase is, and the two-turn confirmation of arm and disarm - and never acts: the
server carries out what was accepted, with the session of the person who spoke.

| Route | What it does |
|---|---|
| `GET /healthz` | `{ok, service}`; needs no token |
| `POST /v1/command` | body `{text, language?, confirmation?}` (at most 2 KB), header `X-Armor-Voice-Token`; answers what was understood, `confirmation_token` when a second turn is needed, and `speech` in the language asked for |

`POST /v1/turn` (when a speech engine is configured) takes the audio of one turn from the wall panel - body raw 16 kHz 16-bit mono PCM of at most 480 000 bytes, `Content-Type: audio/L16;rate=16000`, `X-Armor-Language`, the same token - and answers `{heard, reply, audio?}`: 411/413 for the length, 415 for the type, 422 for the language, 501 when there is no engine or no server configured, 503 when two turns are already running, 504 when the speech engine took so long that the server was not asked (the panel gives up after twelve seconds; past nine nothing is executed). Settings: `ARMOR_VOICE_STT_COMMAND`, `ARMOR_VOICE_TTS_COMMAND` (programs read from the standard input, run without a shell and with a short environment: PATH, HOME, LANG, TMPDIR and the `ARMOR_VOICE_ENGINE_*` variables), `ARMOR_VOICE_SERVER_URL`, `ARMOR_VOICE_SERVER_TOKEN` and `ARMOR_VOICE_CONFIRM_SECRET`. The wall panel is a device on the network and the service listens on the loopback only: either a proxy of the server forwards the turn, or `--allow-remote` is used behind TLS; the token and the audio must not cross the network in clear.

**The panel.** The server forwards the id of the wall panel that spoke in the header `X-Armor-Panel`; the service sends it back on the command and the panic check, so the server can write down which panel asked. Without the header nothing changes.

**The panic phrase.** Once the audio of a turn is transcribed, and before the words are interpreted, the service shows them to the server with `POST /api/v1/voice/panic-check` (the operator token of the installation, at most three seconds). The server compares them with the phrase of each user and, when its setting `voice.panic_phrase` is on and they match, raises the silent duress alarm; its answer is always the same and the service does not read it, so the turn goes on exactly as it would have and nothing is learnt about a match. A server that lacks the route, refuses it or does not answer changes nothing. The phrase is never kept or logged here.

`POST /v1/speak` (when a text-to-speech program is configured) takes `{text, language}` (at most 300 characters, the same token) and answers `{audio}`: the sentence said by that program, as base64 of 16 kHz 16-bit mono PCM. It is for a wall panel that plays an alarm without having asked anything (ARMOR-SERVER builds the sentence from closed lists and keeps the result): nothing is understood, nothing is carried out and nothing is kept. 501 without a speech program, 502 when it fails or says more than a panel plays, 422 for a request that is not exactly those two fields, 503 when two sentences are already being made.

It listens on the loopback address only (it refuses another one without `--allow-remote`), compares the token in constant time, never logs what was said, and signs
the confirmations with `ARMOR_VOICE_CONFIRM_SECRET`. `armor-voice-service --check-engines` runs each configured speech engine once on a sample (a second of silence for hearing, the word "test" for speaking), prints whether it works, how long it took and what it gave back (never its command line) and stops; it needs no token and exits with 1 when an engine fails or none is set up. On the bench it is installed by `ARMOR-DEVOPS/scripts/install_cm5.sh --with-voice`.

## The wake word in the other languages

`docs/wake_words.example.json` is a `wake_words.json` with a line for each of the eight languages (phrase, model file, threshold). Copy it, point `ARMOR_WAKE_CONFIG` at the copy and `ARMOR_WAKE_MODELS` at the folder of the models, and set `ARMOR_WAKE_WORD=on`. Only the English and Spanish models are meant to exist first; for a language whose model file is missing the service answers `wake_model_missing` instead of guessing, so a word is added by training its model (openWakeWord trains one from synthetic speech) and putting the file in the folder. Nothing is switched on by the file itself.

## Testing without speech engines

`tests/loopback_engine.py tts|stt` can be given as `ARMOR_VOICE_TTS_COMMAND` and `ARMOR_VOICE_STT_COMMAND` in a test or a bench: it turns text into a WAVE that its own `stt` reads back exactly (and silence into no words), so a whole turn runs in every language with no model, microphone or speaker. It proves the road of a turn, never the quality of a real engine.

The models are trained by a person and travel as assets of a release; [WAKE_TRAINING.md](WAKE_TRAINING.md) gives the training routine, the format the service expects, the check of a model (`python -m armor_voice_ai.wake_model_check`) and the helper that prepares the signed assets (`python -m armor_voice_ai.wake_release`).
