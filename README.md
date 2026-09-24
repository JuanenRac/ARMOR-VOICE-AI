<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">🇺🇸 <b>English</b> | <a href="README_spa.md">🇪🇸 Español</a></p>

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

## 1. 🛠️ OVERVIEW

* **A closed allow-list:** `status`, `silence`, `arm` and `disarm`, in English and Spanish, after normalising accents, punctuation and polite filler. Anything else, or anything ambiguous, is not understood.
* **A confirmation the service issues:** `arm` and `disarm` return a signed token on the first turn and are accepted only when a later turn echoes it for the same intent within 30 s. It cannot be forged, retargeted, reused or sent as a plain `confirmed: true` (that is refused).
* **Decisions, not audio:** with `--audit-file` each decision records the intent, the outcome and a SHA-256 of the transcript, never audio or the raw words.
* **Recommendations only:** an accepted command is passed to ARMOR-SERVER, which still authenticates and authorises it.

---

## 2. 🔧 BUILD & RUN

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
```

See [voice safety](docs/SAFETY.md).

---

## 📂 DIRECTORY STRUCTURE

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   intent, confirmation, session, gateway
├── tests/
└── docs/SAFETY.md
```

---

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
