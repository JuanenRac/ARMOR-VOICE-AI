<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  🇮🇹 <b>Italiano</b> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Intenti vocali offline in otto lingue, con una conferma che chi chiama non può falsificare

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Languages-8-00E5FF.svg" alt="Languages">
  <img src="https://img.shields.io/badge/Tests-83%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.3.0-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Controllo di onestà - cosa funziona oggi:** Le regole di intento, le otto lingue, la conferma firmata legata a chi parla, il servizio locale, l'endpoint di turno e l'audit sono reali e provati (83 test), e il server interroga il servizio sul banco di prova CM5. **Nessun motore di riconoscimento o sintesi vocale fa parte di questo repository**: `/v1/turn` esegue i comandi che configuri per essi, e nessuno è stato ancora provato con un vero microfono; il pannello touch destinato a ospitare l'assistente non ha girato su una scheda.

---

## 📋 In breve

| | |
|---|---|
| Versione | `0.3.0` |
| Maturità | Consolidato |
| Test | 83 (`python -m unittest discover -s tests`) |
| Tecnologia | Python 3.11+ |
| Su hardware reale | Gira come servizio sul banco di prova CM5, interrogato dal server; nessun microfono né motore vocale è stato provato |

## 🎯 Panoramica

* **Un elenco chiuso di quindici comandi:** `status`, `silence`, `arm`, `disarm`, e quelli che chiedono - `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help` - più accendere e spegnere le luci, in **otto lingue** (inglese, spagnolo, tedesco, francese, italiano, giapponese, cinese e portoghese), dopo aver normalizzato accenti, punteggiatura e formule di cortesia. Qualsiasi altra cosa, o qualsiasi cosa ambigua, non è compresa.
* **Una conferma emessa dal servizio:** `arm` e `disarm` restituiscono un token firmato al primo turno e sono accettati solo quando un turno successivo lo ripete per lo stesso intento entro 30 s, **dallo stesso utente**. Chi chiama non può falsificarla, una scaduta è rifiutata e i nonce di quelle non scadute non sono mai dimenticati per fare spazio.
* **Un servizio HTTP locale:** `python -m armor_voice_ai.service` ascolta solo sull'indirizzo di loopback, richiede un token e risponde a `POST /v1/command` con la decisione nella lingua richiesta; il menu Servizi del server mostra quale versione gira.
* **Un endpoint di turno:** `POST /v1/turn` riceve una registrazione, esegue il comando di riconoscimento vocale che configuri, passa l'ordine nel motore e risponde con una registrazione fatta dal comando di sintesi vocale; i comandi, l'indirizzo del server e il suo token vengono dall'ambiente.
* **Decisioni, non audio:** con `--audit-file` ogni decisione registra l'intento, l'esito e uno SHA-256 della trascrizione, mai audio né le parole grezze.
* **Solo raccomandazioni:** un comando accettato è passato ad ARMOR-SERVER, che lo autentica e lo autorizza comunque; dal pannello a muro disinserire a voce non è mai possibile (il PIN si digita sullo schermo); dall'app segue `ARMOR_DISARM_PIN` del server (impostalo su `required`).

## 🧩 Ruolo in A.R.M.O.R.

ARMOR-VOICE-AI trasforma ciò che si dice in uno di un elenco chiuso di comandi e non fa mai nulla da solo: [ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) lo interroga, poi autentica e autorizza il comando esattamente come un clic in [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO). È pensato per vivere dietro il microfono del pannello a muro [ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI) e serve l'assistente scritto e parlato dell'app Android.

## 📂 Struttura del repository

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
└── docs/                 SAFETY.md, SERVICE.md
```

## 🛠️ Ambiente di sviluppo

**Requisiti:** Python 3.11+ (standard library only), optional: a speech-to-text and a text-to-speech command for `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 83 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

Vedi la [sicurezza della voce](docs/SAFETY.md) e il [servizio](docs/SERVICE.md).

## 🔗 Progetti correlati

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) è un sistema di sicurezza perimetrale fatto di repository indipendenti. Ognuno ha la propria versione, i propri test e il proprio README; ecco la famiglia:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratti dei messaggi, validatori, vettori di conformità e tipi generati
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Firmware del nodo di campo per ESP32-S3 con tre radar e un proprio pannello web
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protocolli di inverter e batterie solari e messaggi di un nodo gateway
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Nodo elettrico: contatori, il messaggio delle letture della rete e le regole di manovra
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Nodo e centrale d'allarme: zone, inserimento, ritardi, sirena e PIN, con il server o senza
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Pannello touch: lo stato del sistema su uno schermo a parete, attivare e riconoscere gli allarmi, e la casa dell'assistente vocale
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - La rete locale: i suoi dispositivi, internet e ciò che cambia
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinatore centrale: telemetria, allarmi, dispositivi, letture solari e telecamere
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Console web: telecamere, radar, allarmi, energia solare e progettista del sito 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Client Android dell'operatore con radar 2D/3D in tempo reale
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Politica di inferenza visiva che spiega le sue decisioni e non agisce mai
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zone delle telecamere, maschere e regole di rilevamento per la Jetson Orin NX
* **ARMOR-VOICE-AI** (questo repository) - Intenti vocali offline con una conferma impossibile da falsificare
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Contenitori, elettronica e matrice di accettazione da banco
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Distribuzione, banco di prova CM5, backup e TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulatore di telemetria offline con guasti ripetibili
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Rileva, installa e aggiorna i repository stessi dell'ecosistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architettura, base di sicurezza e matrice delle capacità

## 📚 Documentazione e comunità

Dove leggere di più:

* [Matrice delle capacità: cosa è provato e cosa no](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catalogo dei progetti: versioni e dipendenze tra i repository](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Cronologia delle modifiche di questo repository](CHANGELOG.md)
* [Licenza (GPL-3.0-or-later)](LICENSE)
* Domande, idee e segnalazioni: electrohobby3d@gmail.com

## 👤 AUTORE

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENZA

GPL-3.0-or-later - vedi [LICENSE](LICENSE).
