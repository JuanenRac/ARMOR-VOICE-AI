<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  🇫🇷 <b>Français</b> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Intentions vocales hors ligne en huit langues, avec une confirmation que l'appelant ne peut pas falsifier

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Languages-8-00E5FF.svg" alt="Languages">
  <img src="https://img.shields.io/badge/Tests-49%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.2.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Vérification d'honnêteté - ce qui fonctionne aujourd'hui:** Les règles d'intention, les huit langues, la confirmation signée liée à son locuteur, le service local, le point de tour et l'audit sont réels et testés (49 tests), et le serveur interroge le service sur le banc de test CM5. **Aucun moteur de reconnaissance ni de synthèse vocale ne fait partie de ce dépôt** : `/v1/turn` exécute les commandes que vous configurez pour eux, et aucun n'a encore été essayé avec un vrai microphone ; le panneau tactile censé porter l'assistant n'a pas tourné sur une carte.

---

## 📋 En un coup d'œil

| | |
|---|---|
| Version | `0.2.8` |
| Maturité | Établi |
| Tests | 49 (`python -m unittest discover -s tests`) |
| Technologie | Python 3.11+ |
| Sur matériel réel | Tourne comme service sur le banc de test CM5, interrogé par le serveur ; aucun microphone ni moteur vocal n'a été essayé |

## 🎯 Présentation

* **Une liste fermée de quinze commandes :** `status`, `silence`, `arm`, `disarm`, et celles qui interrogent - `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help` - plus allumer et éteindre les lumières, en **huit langues** (anglais, espagnol, allemand, français, italien, japonais, chinois et portugais), après normalisation des accents, de la ponctuation et des politesses. Tout le reste, ou tout ce qui est ambigu, n'est pas compris.
* **Une confirmation émise par le service :** `arm` et `disarm` renvoient un jeton signé au premier tour et ne sont acceptés que lorsqu'un tour suivant le répète pour la même intention en 30 s, **pour le même utilisateur**. L'appelant ne peut pas la falsifier, une confirmation périmée est refusée et les nonces de celles non périmées ne sont jamais oubliés pour faire de la place.
* **Un service HTTP local :** `python -m armor_voice_ai.service` n'écoute que sur l'adresse de boucle locale, exige un jeton et répond à `POST /v1/command` avec la décision dans la langue demandée ; le menu Services du serveur montre quelle version tourne.
* **Un point de tour :** `POST /v1/turn` reçoit un enregistrement, exécute la commande de reconnaissance vocale que vous configurez, passe l'ordre dans le moteur et répond avec un enregistrement fait par la commande de synthèse vocale ; les commandes, l'adresse du serveur et son jeton viennent de l'environnement.
* **Des décisions, pas de l'audio :** avec `--audit-file` chaque décision enregistre l'intention, le résultat et un SHA-256 de la transcription, jamais d'audio ni les mots bruts.
* **Des recommandations seulement :** une commande acceptée est transmise à ARMOR-SERVER, qui l'authentifie et l'autorise toujours ; désarmer à la voix n'est jamais possible sans le PIN de la personne sur un écran.

## 🧩 Rôle dans A.R.M.O.R.

ARMOR-VOICE-AI transforme ce qui est dit en l'une des commandes d'une liste fermée et ne fait jamais rien de lui-même : [ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) l'interroge, puis authentifie et autorise la commande exactement comme un clic dans [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO). Il est destiné à vivre derrière le microphone du panneau mural [ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI) et répond à l'assistant écrit et parlé de l'application Android.

## 📂 Structure du dépôt

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
└── docs/                 SAFETY.md, SERVICE.md
```

## 🛠️ Environnement de développement

**Prérequis:** Python 3.11+ (standard library only), optional: a speech-to-text and a text-to-speech command for `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 49 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

Voir la [sécurité de la voix](docs/SAFETY.md) et le [service](docs/SERVICE.md).

## 🔗 Projets liés

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) est un système de sécurité périmétrique composé de dépôts indépendants. Chacun a sa propre version, ses propres tests et son propre README ; voici la famille :

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contrats de messages, validateurs, vecteurs de conformité et types générés
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware du nœud de terrain pour ESP32-S3 avec trois radars et son propre panneau web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocoles des onduleurs et batteries solaires et messages d'un nœud passerelle
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nœud électrique : compteurs, le message des mesures du réseau et les règles de commutation
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Nœud et centrale d'alarme : zones, armement, temporisations, sirène et PIN, avec ou sans le serveur
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Panneau tactile : l'état du système sur un écran mural, armer et acquitter, et la maison de l'assistant vocal
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - Le réseau local : ses appareils, internet et ce qui change
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinateur central : télémétrie, alarmes, appareils, relevés solaires et caméras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Console web : caméras, radar, alarmes, énergie solaire et concepteur de site 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Client Android de l'opérateur avec radar 2D/3D en direct
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Politique d'inférence visuelle qui explique ses décisions et n'agit jamais
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zones de caméra, masques et règles de détection pour la Jetson Orin NX
* **ARMOR-VOICE-AI** (ce dépôt) - Intentions vocales hors ligne avec une confirmation impossible à falsifier
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Boîtiers, électronique et matrice d'acceptation sur banc
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Déploiement, banc d'essai CM5, sauvegarde et TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulateur de télémétrie hors ligne avec des pannes reproductibles
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Détecte, installe et met à jour les propres dépôts de l'écosystème
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architecture, base de sécurité et matrice des capacités

## 📚 Documentation et communauté

Pour en savoir plus :

* [Matrice des capacités : ce qui est prouvé et ce qui ne l'est pas](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catalogue des projets : versions et dépendances entre les dépôts](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Historique des modifications de ce dépôt](CHANGELOG.md)
* [Licence (GPL-3.0-or-later)](LICENSE)
* Questions, idées et rapports : electrohobby3d@gmail.com

## 👤 AUTEUR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCE

GPL-3.0-or-later - voir [LICENSE](LICENSE).
