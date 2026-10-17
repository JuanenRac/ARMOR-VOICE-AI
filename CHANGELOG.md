# Changelog

All notable changes to this project are documented here.

## [0.2.9] - A confirmation that is understood in every language, and turns that cannot disagree with the panel

- **"Yes" and "no" are recognised the way the commands are:** the spoken answer is normalised (accents, full stops of every script, polite words) before it is compared, so "Yes, please", "Sí, por favor", "はい。" and "是。" confirm, and a "no thanks" cancels. Before only a bare word with ASCII or Spanish punctuation did.
- **The panel and the house agree:** past nine seconds of listening nothing is asked of the server (the panel gives up at twelve), a question that took longer than the panel waits is not remembered, text longer than the server accepts is "I did not hear anything", and the audio of an answer is limited to what the panel can take once it is base64.
- **A speech engine gets a short environment** (PATH, HOME, LANG, TMPDIR, `ARMOR_VOICE_ENGINE_*`), not everything minus the names that look like secrets; a WAVE of an engine that writes to a pipe (no length) is read to the end and one that is not 16 kHz 16-bit mono is refused.
- Two turns at most run at once (a third answers 503), a connection that stops talking is closed after fifteen seconds, a missing length is 411, and a transcript with bytes that are not UTF-8 no longer ends the JSON-lines program.
- **Windows:** the confirmation secret is read from `os.environ` (`os.environb` does not exist there, so the service could not start); a confirmation token cannot be valid for longer than it was issued for.
- The manifest and the documents say what this is: a CM5 service with HTTP and JSON lines (no Wyoming or JSON-RPC), eight languages, speech engines chosen by the installation, and `/v1/turn` documented. Tests: 53 (before 49).

## [0.2.8] - Portuguese, the eighth language

- The voice assistant understands and answers in Portuguese: every command (arm, disarm, status, silence, alarms, nodes, cameras, radar, solar, power, network, time, help, lights on and off), the yes and no of a confirmation and the sentences it says back.
- The tests check that Portuguese arms, disarms, asks and silences like the other languages and that the gateway answers in it.

## [0.2.7] - A turn endpoint with speech to text and text to speech commands, and orders tied to their speaker

- A `/v1/turn` endpoint takes a recording, runs the speech-to-text command, runs the order through the engine and answers with a recording made by the text-to-speech command.
- The commands, the server address and its token are set in the environment and run without the service's own secrets.
- A confirmation belongs to the user who asked for it and is refused for anyone else.
- Tests cover the turn, the engines and the confirmation by subject.

## [0.2.6] - Sturdier confirmation of spoken orders

- The confirmation of a spoken order is harder to replay or confuse, with tests.

## [0.2.5] - Fifteen commands instead of four

- **The package carries its `__version__`** (kept in step with the manifest by the shared version tool), so that the server's Services menu in Studio can show which version of the voice service runs.
- **Ten new commands**, each in the seven languages (3 or 4 phrases per language, `phrases.py`): the ones that *ask* - `alarms` (*how many alarms are there*), `nodes`, `cameras`, `radar` (*is anyone there*), `solar` (*how is the battery*), `electrical` (*how much power am I using*), `network` (*do I have internet*), `time` (*what time is it*) and `help` (*what can I do*) - which change nothing and need no confirmation, and `lights_on` and `lights_off`, which the server carries out with the session of the person. Arm and disarm are still the only ones confirmed in a second turn.
- The phrases now live in one table and are normalised when the module loads with the same function that normalises what is heard, so they cannot drift apart (a test checks that every phrase of every language is understood as its own command, that none means two, and that no half of a phrase is enough). 36 tests.
- **A confirmation that could still be replayed is never forgotten to make room.** The nonces of tokens that have expired are the ones dropped (an expired token is refused on its own); when too many unexpired ones are kept at once, the new token is refused instead of an old nonce being pushed out. A test floods the signer and checks that the first token is still refused as a replay.
- **The package carries its `__version__`**, so that the server's Services menu can show which version of the voice service runs.

## [0.2.4] - A local HTTP service, for the server to ask

- **`python -m armor_voice_ai.service`:** the same closed gateway as a small HTTP service - `POST /v1/command` with `{text, language?, confirmation?}` and `GET /healthz` - that listens on the loopback address only (it refuses to start on another one without `--allow-remote`), wants a token in `X-Armor-Voice-Token` (at least 16 characters, from `ARMOR_VOICE_TOKEN` or a `--token-file`), takes at most 2 KB, never logs what was said and signs the confirmations with `ARMOR_VOICE_CONFIRM_SECRET`. It only decides: ARMOR-SERVER asks it and carries out what is accepted. 5 new tests.

## [0.2.3] - Seven languages, and more polite words in Spanish

- **Phrases in German, French, Italian, Japanese and Chinese** for `arm`, `disarm`, `status` and `silence`, next to English and Spanish. It is still a closed allow-list: a test checks that every phrase is written in its own normal form (or it could never match) and that no phrase means two intents.
- **More polite words** are dropped before a phrase is compared: `oiga`, `venga`, `bueno`, `vale` (Spanish), `bitte` (German), `s'il vous plaît`, `svp` (French), `per favore`, `per piacere` (Italian); a filler alone never makes an unknown phrase known.
- **The answer is spoken in the language asked for:** an optional `language` field of the request (`en`, `es`, `de`, `fr`, `it`, `ja`, `zh`; English when it is absent; anything else is a malformed request). New tests: 7.


## [0.2.2] - What used to go unsaid is now in the log

- **Audit file:** when a decision's line cannot be written, a warning says so (on stderr: stdout is the protocol of the gateway).
- **Confirmation secret:** when `ARMOR_VOICE_CONFIRM_SECRET` is not set and a random one is used, a warning says that the pending confirmations are lost when the process stops.


## [0.2.1]

- A GitHub Actions CI baseline (`.github/workflows/ci.yml`): validates the manifest, the version, CHANGELOG.md's heading, the seven README translations' structure and its own local Markdown links, then runs this project's real build/test through `tools/armor_project_tool.py build-test .` (vendored from ARMOR-COMMON, alongside `tools/armor_ci_validate.py` and `tools/_armor_readme_parity.py`, which do the manifest/docs checking).

## [0.2.0]

- Closed intent allow-list, service-signed single-use confirmation for arm and disarm, and a hash-only audit.
- 20 tests.
