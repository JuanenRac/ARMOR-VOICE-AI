<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  🇪🇸 <b>Español</b> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Órdenes de voz sin conexión en ocho idiomas, con una confirmación que quien llama no puede falsificar

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

**Comprobación de honestidad - qué funciona hoy:** Las reglas de intención, los ocho idiomas, la confirmación firmada ligada a quien habla, el servicio local, el punto de turno y la auditoría son reales y están probados (114 tests), y el servidor pregunta al servicio en el banco de pruebas de la CM5. **Ningún motor de reconocimiento ni de síntesis de voz forma parte de este repositorio**: `/v1/turn` ejecuta los comandos que configures para ellos, y ninguno se ha probado todavía con un micrófono real; el panel táctil pensado para llevar al asistente no ha corrido en una placa.

---

## 📋 De un vistazo

| | |
|---|---|
| Versión | `0.3.1` |
| Madurez | Establecido |
| Tests | 114 (`python -m unittest discover -s tests`) |
| Tecnología | Python 3.11+ |
| En hardware real | Corriendo como servicio en el banco de pruebas de la CM5, consultado por el servidor; no se ha probado ningún micrófono ni motor de voz |

## 🚦 Estado del proyecto

Cada línea es una parte de este repositorio y la luz dice hasta dónde llega hoy. Se escribe con lo que el repositorio puede demostrar (pruebas, compilaciones, ejecuciones), no con lo previsto.

🟢 Hecho y verificado · 🟡 Funciona, con límites conocidos · 🟠 Hecho a medias o sin verificar · 🔴 Sin hacer o sin funcionar

| Área | Estado | Qué significa aquí |
|---|---|---|
| Software | 🟡 | Las reglas de intención, el servicio local y el punto de turno funcionan como servicio en el banco de pruebas CM5, pero ningún motor de reconocimiento o síntesis de voz forma parte del repositorio: ejecuta las órdenes que configures para ellos. |
| Pruebas | 🟢 | Pasan 114 pruebas (`python -m unittest discover -s tests`): las reglas de intención, los ocho idiomas, la confirmación firmada ligada a su hablante, el servicio local, el punto de turno y la auditoría. |
| Hardware | 🔴 | No se ha probado ningún micrófono ni motor de voz, y el panel táctil que debe llevar el asistente no ha funcionado en una placa. |
| Seguridad | 🟡 | La confirmación va firmada y ligada a su hablante, y la auditoría está probada en el host; no ha habido una revisión independiente. |
| Integración | 🟡 | El servidor consulta el servicio en el banco de pruebas CM5; el flujo de voz con el panel táctil no se ha ejecutado. |
| Documentación | 🟢 | Ocho idiomas y el historial de cambios están al día. |

## 🎯 Descripción general

* **Una lista cerrada de quince comandos:** `status`, `silence`, `arm`, `disarm`, y los que preguntan - `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help` - más encender y apagar las luces, en **ocho idiomas** (inglés, español, alemán, francés, italiano, japonés, chino y portugués), tras normalizar acentos, puntuación y muletillas de cortesía. Cualquier otra cosa, o cualquier cosa ambigua, no se entiende.
* **Una confirmación que emite el servicio:** `arm` y `disarm` devuelven un token firmado en el primer turno y solo se aceptan cuando un turno posterior lo repite para la misma intención en 30 s, **del mismo usuario**. El que llama no puede falsificarla, una caducada se rechaza y los nonces de las no caducadas nunca se olvidan para hacer sitio.
* **Un servicio HTTP local:** `python -m armor_voice_ai.service` escucha solo en la dirección de loopback, pide un token y responde `POST /v1/command` con la decisión en el idioma pedido; el menú Servicios del servidor muestra qué versión corre.
* **Un punto de turno:** `POST /v1/turn` recibe una grabación, ejecuta el comando de voz a texto que configures, pasa la orden por el motor y responde con una grabación hecha por el comando de texto a voz; los comandos, la dirección del servidor y su token vienen del entorno.
* **Decisiones, no audio:** con `--audit-file` cada decisión registra la intención, el resultado y un SHA-256 de la transcripción, nunca audio ni las palabras sin procesar.
* **Solo recomendaciones:** un comando aceptado se pasa a ARMOR-SERVER, que sigue autenticándolo y autorizándolo; desde el panel de pared desarmar por voz nunca es posible (el PIN se teclea en la pantalla); desde la app sigue `ARMOR_DISARM_PIN` del servidor (ponlo en `required`).

## 🧩 Papel en A.R.M.O.R.

ARMOR-VOICE-AI convierte lo que se dice en uno de una lista cerrada de comandos y nunca hace nada por sí mismo: [ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) le pregunta y luego autentica y autoriza el comando exactamente como un clic en [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO). Está pensado para vivir tras el micrófono del panel de pared [ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI) y atiende al asistente escrito y hablado de la app Android.

## 📂 Estructura del repositorio

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
├── tools/                the shared CI checks (armor_ci_validate.py, armor_project_tool.py, _armor_readme_parity.py)
└── docs/                 SAFETY.md, SERVICE.md, SILENCE_POLICY.md
```

## 🛠️ Entorno de desarrollo

**Requisitos:** Python 3.11+ (solo la biblioteca estándar), opcional: un comando de voz a texto y otro de texto a voz para `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 114 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

Véanse la [seguridad de la voz](docs/SAFETY.md) y el [servicio](docs/SERVICE.md).

## 🔗 Proyectos relacionados

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) es un sistema de seguridad perimetral hecho de repositorios independientes. Cada uno tiene su propia versión, sus propias pruebas y su propio README; esta es la familia:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensajes, validadores, vectores de conformidad y tipos generados
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Firmware del nodo de campo para ESP32-S3 con tres radares y su propio panel web
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protocolos de inversores y baterías solares y los mensajes de un nodo pasarela
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Nodo eléctrico: contadores, el mensaje de las lecturas de la red y las reglas para maniobrar
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Nodo y central de alarma: zonas, armado, retardos, sirena y PIN, con el servidor o sin él
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Panel táctil: el estado del sistema en una pantalla de pared, armar y reconocer alarmas, y el hogar del asistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - La red local: sus dispositivos, internet y lo que cambia
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinador central: telemetría, alarmas, dispositivos, lecturas solares y cámaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: cámaras, radar, alarmas, energía solar y el diseñador de sitio 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android del operador con radar 2D/3D en vivo
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - Cliente de operador para iPhone
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferencia visual que explica sus decisiones y nunca actúa
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de cámara, máscaras y reglas de detección para la Jetson Orin NX
* **ARMOR-VOICE-AI** (este repositorio) - Intenciones de voz sin conexión con una confirmación imposible de falsificar
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Cajas, electrónica y la matriz de aceptación en banco
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Despliegue, el banco de pruebas de la CM5, copias de seguridad y TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetría sin conexión con fallos repetibles
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detecta, instala y actualiza los propios repositorios del ecosistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitectura, base de seguridad y la matriz de capacidades

## 📚 Documentación y comunidad

Dónde leer más:

* [Matriz de capacidades: qué está probado y qué no](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de proyectos: versiones y cómo dependen unos de otros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Historial de cambios de este repositorio](CHANGELOG.md)
* [Licencia (GPL-3.0-or-later)](LICENSE)
* Preguntas, ideas e informes: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
