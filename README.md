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
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### Offline voice intents with a confirmation the caller cannot forge

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Maturity-functional%20baseline-00E5FF.svg" alt="Maturity">
</p>

---

**Honesty check - what runs today:** The intent rules, the signed confirmation and the audit are real and tested (20 tests). **No speech recognition or synthesis engine is part of this repository yet.**

---

## 🎯 Overview

* **A closed allow-list:** `status`, `silence`, `arm` and `disarm`, in English and Spanish, after normalising accents, punctuation and polite filler. Anything else, or anything ambiguous, is not understood.
* **A confirmation the service issues:** `arm` and `disarm` return a signed token on the first turn and are accepted only when a later turn echoes it for the same intent within 30 s. It cannot be forged, retargeted, reused or sent as a plain `confirmed: true` (that is refused).
* **Decisions, not audio:** with `--audit-file` each decision records the intent, the outcome and a SHA-256 of the transcript, never audio or the raw words.
* **Recommendations only:** an accepted command is passed to ARMOR-SERVER, which still authenticates and authorises it.

## 📂 Repository Structure

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   intent, confirmation, session, gateway
├── tests/
└── docs/SAFETY.md
```

## 🛠️ Development Environment

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
```

See [voice safety](docs/SAFETY.md).

## 🔗 Related Projects

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) is a perimeter-security system made of independent repositories. Each one has its own version, its own tests and its own README; this is the family:

* **[ARMOR-COMMON](../ARMOR-COMMON)** - Message contracts, validators, conformance vectors and generated types
* **[ARMOR-RADAR](../ARMOR-RADAR)** - Field-node firmware for ESP32-S3 with three radars and its own web panel
* **[ARMOR-SOLAR](../ARMOR-SOLAR)** - Solar inverter and battery protocols and the messages of a gateway node
* **[ARMOR-ELECTRICAL](../ARMOR-ELECTRICAL)** - Electrical node: meters, the message of the network's readings and the rules for switching
* **[ARMOR-NETWORK](../ARMOR-NETWORK)** - The local network: its devices, the internet and what changes
* **[ARMOR-SERVER](../ARMOR-SERVER)** - Central coordinator: telemetry, alarms, devices, solar readings and cameras
* **[ARMOR-STUDIO](../ARMOR-STUDIO)** - Web console: cameras, radar, alarms, solar energy and the 2D/3D site designer
* **[ARMOR-ANDROID-CONTROL](../ARMOR-ANDROID-CONTROL)** - Android operator client with a live 2D/3D radar
* **[ARMOR-SERVER-AI](../ARMOR-SERVER-AI)** - Visual inference policy that explains its decisions and never actuates
* **ARMOR-VOICE-AI** (this repository) - Offline voice intents with a confirmation that cannot be forged
* **[ARMOR-HARDWARE](../ARMOR-HARDWARE)** - Enclosures, electronics and the bench acceptance matrix
* **[ARMOR-DEVOPS](../ARMOR-DEVOPS)** - Deployment, the CM5 test bench, backup and TLS
* **[ARMOR-SIMULATOR](../ARMOR-SIMULATOR)** - Offline telemetry simulator with repeatable faults
* **[ARMOR-UPDATER](../ARMOR-UPDATER)** - Detects, installs and updates the ecosystem's own repositories
* **[ARMOR-DOCS](../ARMOR-DOCS)** - Architecture, security baseline and the capability matrix

## 📚 Documentation & Community

Where to read more:

* [Capability matrix: what is proven and what is not](../ARMOR-DOCS/docs/CAPABILITY_MATRIX.md)
* [Project catalogue: versions and how the repositories depend on each other](../ARMOR-DOCS/docs/PROJECT_CATALOG.md)
* [Changelog of this repository](CHANGELOG.md)
* [License (GPL-3.0-or-later)](LICENSE)
* Questions, ideas and reports: electrohobby3d@gmail.com

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
