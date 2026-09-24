<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center"><a href="README.md">🇺🇸 English</a> | 🇪🇸 <b>Español</b></p>

### Intenciones de voz sin conexión con una confirmación que el llamante no puede falsificar

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Maturity-functional%20baseline-00E5FF.svg" alt="Maturity">
</p>

---

**Comprobación de honestidad - qué funciona hoy:** Las reglas de intención, la confirmación firmada y la auditoría son reales y están probadas (20 tests). **Ningún motor de reconocimiento o síntesis de voz forma parte todavía de este repositorio.**

---

## 1. 🛠️ DESCRIPCIÓN

* **Una lista cerrada:** `status`, `silence`, `arm` y `disarm`, en inglés y español, tras normalizar acentos, puntuación y muletillas de cortesía. Cualquier otra cosa, o algo ambiguo, no se entiende.
* **Una confirmación que emite el servicio:** `arm` y `disarm` devuelven un token firmado en el primer turno y solo se aceptan cuando un turno posterior lo repite para la misma intención en 30 s. No se puede falsificar, reorientar, reutilizar ni enviar como un simple `confirmed: true` (se rechaza).
* **Decisiones, no audio:** con `--audit-file` cada decisión guarda la intención, el resultado y el SHA-256 de la transcripción, nunca audio ni las palabras.
* **Solo recomendaciones:** un comando aceptado pasa a ARMOR-SERVER, que sigue autenticándolo y autorizándolo.

---

## 2. 🔧 COMPILAR Y EJECUTAR

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
```

Véase [seguridad de voz](docs/SAFETY.md).

---

## 📂 ESTRUCTURA DE DIRECTORIOS

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   intent, confirmation, session, gateway
├── tests/
└── docs/SAFETY.md
```

---

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
