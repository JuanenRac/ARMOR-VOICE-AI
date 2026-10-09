<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  🇩🇪 <b>Deutsch</b> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### Offline-Sprachabsichten mit einer Bestätigung, die der Aufrufer nicht fälschen kann

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Maturity-functional%20baseline-00E5FF.svg" alt="Maturity">
</p>

---

**Ehrlichkeitsprüfung - was heute läuft:** Die Absichtsregeln, die signierte Bestätigung und das Audit sind real und getestet (36 Tests). **Eine Spracherkennungs- oder Synthese-Engine ist noch nicht Teil dieses Repositorys.**

---

## 🎯 Überblick

* **Eine geschlossene Erlaubnisliste:** fünfzehn Befehle - `arm`, `disarm`, `status`, `silence`, `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help`, `lights_on` und `lights_off` -, auf Englisch, Spanisch, Deutsch, Französisch, Italienisch, Japanisch und Chinesisch (und die Antwort wird in der gewünschten Sprache gesprochen), nach Normalisierung von Akzenten, Satzzeichen und Höflichkeitsfloskeln. Alles andere oder Mehrdeutige wird nicht verstanden.
* **Eine vom Dienst ausgestellte Bestätigung:** `arm` und `disarm` liefern im ersten Schritt ein signiertes Token und werden nur akzeptiert, wenn ein späterer Schritt es für dieselbe Absicht innerhalb von 30 s zurückgibt. Es lässt sich nicht fälschen, umlenken, wiederverwenden oder durch ein einfaches `confirmed: true` ersetzen (wird abgelehnt).
* **Entscheidungen, kein Audio:** mit `--audit-file` hält jede Entscheidung Absicht, Ergebnis und einen SHA-256 des Transkripts fest, nie Audio oder die rohen Wörter.
* **Nur Empfehlungen:** ein akzeptierter Befehl wird an ARMOR-SERVER weitergegeben, der ihn weiterhin authentifiziert und autorisiert.
* **Ein kleiner Dienst, keine Engine:** `armor-voice` lauscht auf `127.0.0.1:18090` auf den Text, den der Server ihm gibt (in der Android-App getippt oder von der Spracherkennung des Telefons gehört), und antwortet mit dem Urteil; siehe [der Dienst](docs/SERVICE.md). Der Server führt jeden akzeptierten Befehl mit der Sitzung der sprechenden Person aus.

## 📂 Struktur des Repositorys

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway, service
├── tests/
└── docs/SAFETY.md, SERVICE.md
```

## 🛠️ Entwicklungsumgebung

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
```

Siehe die [Sprachsicherheit](docs/SAFETY.md).

## 🔗 Verwandte Projekte

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) ist ein Perimeter-Sicherheitssystem aus unabhängigen Repositorys. Jedes hat eine eigene Version, eigene Tests und ein eigenes README; hier ist die Familie:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Nachrichtenverträge, Validierer, Konformitätsvektoren und generierte Typen
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Feldknoten-Firmware für ESP32-S3 mit drei Radaren und eigenem Web-Panel
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protokolle für Solar-Wechselrichter und -Batterien und die Nachrichten eines Gateway-Knotens
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Elektroknoten: Zähler, die Nachricht der Netzmesswerte und die Regeln fürs Schalten
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Touch-Panel: der Systemzustand auf einem Wandbildschirm, Scharf- und Quittieren sowie das Zuhause des Sprachassistenten
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - Das lokale Netzwerk: seine Geräte, das Internet und was sich ändert
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Zentraler Koordinator: Telemetrie, Alarme, Geräte, Solarmesswerte und Kameras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web-Konsole: Kameras, Radar, Alarme, Solarenergie und 2D/3D-Standortdesigner
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Android-Bedienclient mit Live-Radar in 2D/3D
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Visuelle Inferenzrichtlinie, die ihre Entscheidungen erklärt und nie handelt
* **ARMOR-VOICE-AI** (dieses Repository) - Offline-Sprachabsichten mit einer nicht fälschbaren Bestätigung
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Gehäuse, Elektronik und die Abnahmematrix am Prüfstand
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Bereitstellung, CM5-Prüfstand, Backup und TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Offline-Telemetriesimulator mit wiederholbaren Fehlern
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Erkennt, installiert und aktualisiert die eigenen Repositories des Ökosystems
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architektur, Sicherheitsgrundlage und die Fähigkeitsmatrix

## 📚 Dokumentation und Community

Hier gibt es mehr zu lesen:

* [Fähigkeitsmatrix: was belegt ist und was nicht](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Projektkatalog: Versionen und wie die Repositorys voneinander abhängen](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Änderungsverlauf dieses Repositorys](CHANGELOG.md)
* [Lizenz (GPL-3.0-or-later)](LICENSE)
* Fragen, Ideen und Meldungen: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LIZENZ

GPL-3.0-or-later - siehe [LICENSE](LICENSE).
