# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- **A routine to train, check and release the wake word models:** `docs/WAKE_TRAINING.md` gives the training steps for the eight languages, the file the service expects (name from `wake_words.json`, 8 KiB to 8 MiB, ONNX with an input of `[batch, 16, 96]` and an output of `[batch, 1]`, weights inside the file) and the release routine. `python -m armor_voice_ai.wake_model_check` verifies a model or a whole folder against `wake_words.json` reading the file with the standard library only, and `python -m armor_voice_ai.wake_release` checks the models, writes a manifest of their hashes and has it signed by the signer of the releases (it never reads a key), so the models can be added to the release as signed assets. 18 tests build models in memory, including a wrong name, a wrong shape, a truncated file, an external weight and a signer that fails.

## [0.3.5] - The CI checks the coverage floor of this repository: a workflow of its own runs `tools/coverage_check.py` on every push and fails when the lines or the branches covered by the tests fall under the numbers of `docs/coverage_threshold.json` (

- **The CI checks the coverage floor of this repository:** a workflow of its own runs `tools/coverage_check.py` on every push and fails when the lines or the branches covered by the tests fall under the numbers of `docs/coverage_threshold.json` (the shared workflow checks a floor only where there is a `package.json`).

- **The service has a coverage floor, and its routes are tested to the edge:** `docs/coverage_threshold.json` holds the least the tests may cover (lines and branches) and `tools/coverage_check.py` runs the tests with coverage and fails under it. The new tests (`tests/test_service_routes.py`) reach the paths the happy path does not: a length header that is not a number, a body shorter than it promised, a service that is busy, the speech and wake routes with and without their parts, the check of the engines, a wrong PIN and a wake word that cannot start. The service module now has 99 % of its lines covered (it had 87 %).

- **An example `wake_words.json` for the eight languages:** `docs/wake_words.example.json` names a phrase, a model file and a threshold for English, Spanish, German, French, Italian, Japanese, Chinese and Portuguese (Portugal), and `docs/SERVICE.md` explains how to use it; a language whose model file is not there answers `wake_model_missing`, and the whole feature stays off unless `ARMOR_WAKE_WORD=on`. Two tests read the example through the same parser as the service, and four more run the openWakeWord detector with stand-in modules (library missing, model missing, a model loaded once, no score).

- **The README and the table of settings say how the wake word is switched on:** `POST /v1/wake` (its headers, its answer and the 403 it gives while it is off), `ARMOR_WAKE_WORD`, `ARMOR_WAKE_MODELS` and `ARMOR_WAKE_CONFIG` are in the eight languages, and the limits section no longer says there is no wake word.
- **A wake word that runs on this machine:** `POST /v1/wake` takes up to two seconds of 16 kHz mono 16-bit audio from a panel and answers whether the wake word ended in it (two 80 ms frames in a row over the threshold, then two seconds of quiet, per panel; no audio is kept). The detector is openWakeWord, loaded only when asked for (no account, no key, no cloud). It is OFF unless the service starts with `ARMOR_WAKE_WORD=on` (403 `wake_disabled` otherwise). The word is a setting: `wake_words.json` (`ARMOR_WAKE_CONFIG`) gives, for each of the eight languages, the phrase, the model file and the threshold (0.3 to 0.99); "hey armor" in English and "oye armor" in Spanish are the defaults, and a word for another language is added by training a model and writing one line. A line that is not valid is refused whole. 17 tests with a scripted detector.

- **Stand-in speech engines for the tests and the bench:** `tests/loopback_engine.py` is a speech-to-text and a text-to-speech command that recognise and say nothing a person could hear (every byte of the text is a block of samples, so a clip it makes reads back exactly and silence reads back as no words). A whole turn - the panel audio, the engine commands, the server voice route and the audio of the answer - now runs in the tests in all eight languages without a model, a microphone or a speaker. A green run proves the plumbing, not how well a real engine hears a voice.
- **The wall panel that spoke is handed back to the server:** `POST /v1/turn` reads the header `X-Armor-Panel` (the node id of the panel, as the server forwards it) and sends it on the `/api/v1/voice/command` and `/api/v1/voice/panic-check` calls, so that what a panel asked is written down as that panel. An id that is not a plain node id is dropped, and a turn without one carries none (the value lives only in that request). Two tests.

## [0.3.4] - The launchers find the shared repository through ARMORCOMMONDIR: build, build-test, test and run (.sh and .bat) use the folder named by that variable when it is set and the sibling ARMOR-COMMON folder otherwise, so a checkout... (and 3 more changes)

- **The launchers find the shared repository through `ARMOR_COMMON_DIR`:** `build`, `build-test`, `test` and `run` (`.sh` and `.bat`) use the folder named by that variable when it is set and the sibling `ARMOR-COMMON` folder otherwise, so a checkout with another layout builds without changing a file.
- **The transcript of a spoken turn is shown to the server before it is interpreted, so that the server can look for a panic phrase:** `ServerLink.panic_check` calls `POST /api/v1/voice/panic-check` with the operator token and the text just transcribed (three seconds at most); the answer is never read, so the service cannot tell a match from a miss, and a server that does not have the route, that refuses or that does not answer changes nothing in the turn. Whether anything is looked for is the server's setting `voice.panic_phrase` (off by default). Four tests.
- **One matrix of risk by intent:** `intent.RISK` says for every intent whether it asks or does, which confirmation it needs (none, the signed one, or the one the silence policy chooses), whether a PIN is the proof and whether the wall panel may carry it out; the sensitive set and the refusal of disarming from the panel read it instead of naming intents by hand.
- Tests: 134 (before 130): the matrix, punctuation of Japanese and Chinese transcripts, a spoken reply of 199,000 bytes (words only) and one of 190,000 (with audio), and an engine cut short by the turn budget.

## [0.3.3] - A silence mode with a number that is shown and not said, an audit that no longer keeps a reversible digest, a check of the speech engines before they are needed and the voiced marks of Japanese kept

- **The audit no longer keeps a digest that can be reversed:** the line of each decision carries `transcript_hmac`, an HMAC-SHA-256 of the words keyed by `ARMOR_VOICE_AUDIT_KEY` (or by a key of the run), instead of a plain SHA-256 that a dictionary of the known phrases would reverse; `ARMOR_VOICE_AUDIT_TRANSCRIPT` chooses `hmac` (the default), `sha256` (the old field) or `none`.
- **The voiced marks of Japanese are no longer dropped when the words are compared:** "ば" and "は" stay different words (only the accents of the other scripts are removed).
- **The speech engines can be tried before they are needed:** `--check-engines` runs each configured engine once on a sample and prints whether it works, how long it took and what it gave back.
- **A silence mode with a number that is shown, not said:** the policy `silence_confirmation: "challenge"` makes the first "silence" ask for a number of two digits that appears in the answer (`challenge`) for the screen of the panel and is not in the spoken reply; only that number, said within 20 seconds from the same panel, passes the command on. A loudspeaker or somebody outside the house cannot know it. Three wrong numbers in a row lock silencing by voice for five minutes for every panel, a number is good once, and a panel that cannot show it cannot silence by voice in this mode. The text route (`/v1/command`) has no screen and asks for the signed confirmation in this mode, never less. The new sentences are in the eight languages. Nothing changes unless the server sends the new value.
- Tests: 130 (before 118).

## [0.3.2] - The service can say a sentence out loud on request, the lights of Project status follow the evidence of the manifest and the pictures of the README from shared tools

- **The lights of Project status follow the evidence of the manifest:** the manifest says how far the repository has been shown to work (`evidence`: `host-test`, `simulator`, `bench` or `field`) and the validator fails when a light is above what that evidence and the maturity allow (`tools/status_lights.py`), so a green that never ran on real hardware cannot come back.
- **The service can say a sentence out loud on request:** `POST /v1/speak` takes `{text, language}` (300 characters at most, the same token) and answers the sentence made by the text-to-speech program as 16 kHz 16-bit mono PCM; ARMOR-SERVER uses it to hand the wall panel an alarm said aloud. It understands nothing, carries out nothing and keeps nothing; without the program it answers 501. Tests: 118 (before 114).
- **The layout of the README is checked in the CI:** the validator runs the shared `tools/universal_readme_check.py` and fails when the README differs from the universal layout.
- **The pictures of the README come from shared tools:** `tools/make_architecture.py` draws `images/architecture.svg` from `docs/architecture.json` and `tools/make_structure.py` draws the Repository Structure (the text tree and the animated picture) from `docs/structure.json`; both measure every text, and `--check` fails when a picture, its description or the code it points to disagree. They are vendored from ARMOR-COMMON like the shared CI checks.

## [0.3.1] - Silencing by voice can require a PIN or a second turn

- **Silencing by voice can require a PIN or a second turn:** a policy sent by the server (`policy.silence_confirmation`: `off` by default, `pin` or `double_turn`; the `X-Armor-Policy` header on `/v1/turn`, a `policy` field on `/v1/command`) makes the first "silence" ask for the spoken PIN or for a yes. Without a policy nothing changes; an unreadable one counts as the second turn. The PIN (`ARMOR_VOICE_SILENCE_PIN`) is spoken in the eight languages, compared in constant time, never logged, kept or echoed back, three wrong ones lock silencing for every panel for five minutes, and with no PIN set up it fails closed. The contract is in `docs/SILENCE_POLICY.md`. Tests: 114 (before 83).
- The repository has a security policy, a code of conduct, a contributing guide and a support file.
- The banner follows the animated style of the ecosystem banners, with the name, the kind and the technologies of the project.
- SAFETY.md lists the fifteen intents (ten that ask, five that do) with their confirmation, names Portuguese among the languages, and has a section on the wall-panel turn (`/v1/turn`): untrusted text, size and time limits, spoken confirmation only for arming, nothing kept, loopback only and no identity of the speaker yet.

## [0.3.0] - Each panel keeps its own question when it comes through the server

- The question a panel was asked is remembered under the name the server gives it (`X-Armor-Client`, sent by the voice route of ARMOR-SERVER that the wall panel uses), not under the address the request came from, which for every panel is the server's own. Without the header it is the address, as before. Tests: 54 (before 53).

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
