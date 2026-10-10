# Changelog

All notable changes to this project are documented here.

## [0.2.5] - Fifteen commands instead of four

- **The package carries its `__version__`** (kept in step with the manifest by the shared version tool), so that the server's Services menu in Studio can show which version of the voice service runs.
- **Ten new commands**, each in the seven languages (3 or 4 phrases per language, `phrases.py`): the ones that *ask* - `alarms` (*how many alarms are there*), `nodes`, `cameras`, `radar` (*is anyone there*), `solar` (*how is the battery*), `electrical` (*how much power am I using*), `network` (*do I have internet*), `time` (*what time is it*) and `help` (*what can I do*) - which change nothing and need no confirmation, and `lights_on` and `lights_off`, which the server carries out with the session of the person. Arm and disarm are still the only ones confirmed in a second turn.
- The phrases now live in one table and are normalised when the module loads with the same function that normalises what is heard, so they cannot drift apart (a test checks that every phrase of every language is understood as its own command, that none means two, and that no half of a phrase is enough). 36 tests.

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
