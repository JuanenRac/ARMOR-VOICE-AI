<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  🇺🇸 <b>English</b> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Offline voice intents in eight languages, with a confirmation the caller cannot forge

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Languages-8-00E5FF.svg" alt="Languages">
  <img src="https://img.shields.io/badge/Tests-114%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.3.1-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Honesty check - what runs today:** The intent rules, the eight languages, the signed confirmation tied to its speaker, the local service, the turn endpoint and the audit are real and tested (114 tests), and the server asks the service on the CM5 test bench. **No speech recognition or synthesis engine is part of this repository**: `/v1/turn` runs the commands you configure for them, and none has been tried with a real microphone yet; the touch panel that is meant to carry the assistant has not run on a board.

---

## 📋 At a glance

| | |
|---|---|
| Version | `0.3.1` |
| Maturity | Established |
| Tests | 114 (`python -m unittest discover -s tests`) |
| Stack | Python 3.11+ |
| On real hardware | Running as a service on the CM5 test bench, asked by the server; no microphone or speech engine has been tried |

## 🚦 Project status

Each line is one part of this repository and the light says how far it is today. It is written from what the repository can show (tests, builds, runs), not from what is planned.

🟢 Done and verified · 🟡 Works, with known limits · 🟠 Partly done or not verified yet · 🔴 Not done or not working

| Area | State | What it means here |
|---|---|---|
| Software | 🟡 | The intent rules, the local service and the turn endpoint run as a service on the CM5 test bench, but no speech recognition or synthesis engine is part of the repository: it runs the commands you configure for them. |
| Tests | 🟢 | 114 tests pass (`python -m unittest discover -s tests`): the intent rules, the eight languages, the signed confirmation tied to its speaker, the local service, the turn endpoint and the audit. |
| Hardware | 🔴 | No microphone or speech engine has been tried, and the touch panel that is meant to carry the assistant has not run on a board. |
| Security | 🟡 | The confirmation is signed and tied to its speaker, and the audit is tested on the host; there has been no independent review. |
| Integration | 🟡 | The server asks the service on the CM5 test bench; the voice flow with the touch panel has not run. |
| Documentation | 🟢 | Eight languages and the changelog are up to date. |

## 🎯 Overview

* **A closed allow-list of fifteen commands:** `status`, `silence`, `arm`, `disarm`, and the ones that ask - `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help` - plus switching the lights on and off, in **eight languages** (English, Spanish, German, French, Italian, Japanese, Chinese and Portuguese), after normalising accents, punctuation and polite filler. Anything else, or anything ambiguous, is not understood.
* **A confirmation the service issues:** `arm` and `disarm` return a signed token on the first turn and are accepted only when a later turn echoes it for the same intent within 30 s, **for the same user**. It cannot be forged by the caller, a stale one is refused and the nonces of the unexpired ones are never forgotten to make room.
* **A local HTTP service:** `python -m armor_voice_ai.service` listens on the loopback address only, wants a token and answers `POST /v1/command` with the decision in the language asked for; the server's Services menu shows which version runs.
* **A turn endpoint:** `POST /v1/turn` takes a recording, runs the speech-to-text command you configure, runs the order through the engine and answers with a recording made by the text-to-speech command; the commands, the server address and its token come from the environment.
* **Decisions, not audio:** with `--audit-file` each decision records the intent, the outcome and a SHA-256 of the transcript, never audio or the raw words.
* **Recommendations only:** an accepted command is passed to ARMOR-SERVER, which still authenticates and authorises it; from the wall panel disarming by voice is never possible (the PIN is typed on the screen); from the app it follows the server's `ARMOR_DISARM_PIN` (set it to `required`).

## 🧩 Role in A.R.M.O.R.

ARMOR-VOICE-AI turns what is said into one of a closed list of commands and never does anything by itself: [ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) asks it, then authenticates and authorises the command exactly as it would a click in [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO). It is meant to live behind the microphone of the [ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI) wall panel and answers the written and spoken assistant of the Android app.

## 📂 Repository Structure

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
├── tools/                the shared CI checks (armor_ci_validate.py, armor_project_tool.py, _armor_readme_parity.py)
└── docs/                 SAFETY.md, SERVICE.md, SILENCE_POLICY.md
```

## 🛠️ Development Environment

**Requirements:** Python 3.11+ (standard library only), optional: a speech-to-text and a text-to-speech command for `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 114 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

See [voice safety](docs/SAFETY.md) and the [service](docs/SERVICE.md).

## 🔗 Related Projects

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) is a perimeter-security system made of independent repositories. Each one has its own version, its own tests and its own README; this is the family:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Message contracts, validators, conformance vectors and generated types
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Field-node firmware for ESP32-S3 with three radars and its own web panel
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Solar inverter and battery protocols and the messages of a gateway node
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Electrical node: meters, the message of the network's readings and the rules for switching
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Alarm node and panel: zones, arming, delays, siren and PIN, with the server or without it
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Touch panel: the state of the system on a wall screen, arming and acknowledging, and the home of the voice assistant
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - The local network: its devices, the internet and what changes
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Central coordinator: telemetry, alarms, devices, solar readings and cameras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web console: cameras, radar, alarms, solar energy and the 2D/3D site designer
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Android operator client with a live 2D/3D radar
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone operator client
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Visual inference policy that explains its decisions and never actuates
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Camera zones, masks and detection rules for the Jetson Orin NX
* **ARMOR-VOICE-AI** (this repository) - Offline voice intents with a confirmation that cannot be forged
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Enclosures, electronics and the bench acceptance matrix
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Deployment, the CM5 test bench, backup and TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Offline telemetry simulator with repeatable faults
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detects, installs and updates the ecosystem's own repositories
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architecture, security baseline and the capability matrix

## 📚 Documentation & Community

Where to read more:

* [Capability matrix: what is proven and what is not](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Project catalogue: versions and how the repositories depend on each other](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Changelog of this repository](CHANGELOG.md)
* [License (GPL-3.0-or-later)](LICENSE)
* Questions, ideas and reports: electrohobby3d@gmail.com

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
