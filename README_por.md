<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-VOICE-AI banner" width="100%">
</p>

# 🎙️ ARMOR-VOICE-AI

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  🇵🇹 <b>Português</b>
</p>

### Intenções de voz offline com uma confirmação que quem chama não pode falsificar

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Maturity-functional%20baseline-00E5FF.svg" alt="Maturity">
</p>

---

**Verificação de honestidade - o que funciona hoje:** As regras de intenção, a confirmação assinada e a auditoria são reais e testadas (20 testes). **Ainda não faz parte deste repositório nenhum motor de reconhecimento nem de síntese de voz.**

---

## 🎯 Visão geral

* **Uma lista fechada de permitidos:** `status`, `silence`, `arm` e `disarm`, em inglês e espanhol, depois de normalizar acentos, pontuação e palavras de cortesia. Tudo o resto, ou tudo o que seja ambíguo, não se entende.
* **Uma confirmação emitida pelo serviço:** `arm` e `disarm` devolvem um token assinado no primeiro turno e só se aceitam quando um turno posterior o repete para a mesma intenção em 30 s. Não se pode falsificar, redirecionar, reutilizar nem enviar como um simples `confirmed: true` (isso é recusado).
* **Decisões, não áudio:** com `--audit-file` cada decisão regista a intenção, o resultado e um SHA-256 da transcrição, nunca áudio nem as palavras em bruto.
* **Só recomendações:** um comando aceite é passado ao ARMOR-SERVER, que continua a autenticá-lo e autorizá-lo.

## 📂 Estrutura do repositório

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   intent, confirmation, session, gateway
├── tests/
└── docs/SAFETY.md
```

## 🛠️ Ambiente de desenvolvimento

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
```

Veja a [segurança da voz](docs/SAFETY.md).

## 🔗 Projetos relacionados

O **A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) é um sistema de segurança perimetral feito de repositórios independentes. Cada um tem a sua própria versão, os seus próprios testes e o seu próprio README; esta é a família:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensagens, validadores, vetores de conformidade e tipos gerados
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware de nó de campo para ESP32-S3 com três radares e o seu próprio painel web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocolos de inversores e baterias solares e as mensagens de um nó de ligação
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nó elétrico: contadores, a mensagem das leituras da rede e as regras de comutação
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Painel tátil: o estado do sistema num ecrã de parede, armar e reconhecer, e a casa do assistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - A rede local: os seus dispositivos, a internet e o que muda
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordenador central: telemetria, alarmes, dispositivos, leituras solares e câmaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: câmaras, radar, alarmes, energia solar e o desenhador de local 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android de operador com um radar 2D/3D em direto
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferência visual que explica as suas decisões e nunca atua
* **ARMOR-VOICE-AI** (este repositório) - Intenções de voz offline com uma confirmação que não se pode falsificar
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Caixas, eletrónica e a matriz de aceitação de bancada
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - Implementação, a bancada de testes CM5, cópias de segurança e TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetria offline com falhas repetíveis
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Deteta, instala e atualiza os próprios repositórios do ecossistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitetura, linha de base de segurança e a matriz de capacidades

## 📚 Documentação e comunidade

Onde ler mais:

* [Matriz de capacidades: o que está provado e o que não](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de projetos: versões e como os repositórios dependem uns dos outros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Registo de alterações deste repositório](CHANGELOG.md)
* [Licença (GPL-3.0-or-later)](LICENSE)
* Perguntas, ideias e relatórios: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENÇA

GPL-3.0-or-later - veja [LICENSE](LICENSE).
