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

### Intenções de voz offline em oito idiomas, com uma confirmação que quem chama não pode forjar

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

**Verificação de honestidade - o que funciona hoje:** As regras de intenção, os oito idiomas, a confirmação assinada ligada a quem fala, o serviço local, o ponto de turno e a auditoria são reais e estão testados (83 testes), e o servidor pergunta ao serviço na bancada de testes do CM5. **Nenhum motor de reconhecimento ou síntese de voz faz parte deste repositório**: `/v1/turn` executa os comandos que configurar para eles, e nenhum foi ainda experimentado com um microfone real; o painel tátil destinado a levar o assistente não correu numa placa.

---

## 📋 Num relance

| | |
|---|---|
| Versão | `0.3.0` |
| Maturidade | Estabelecido |
| Testes | 83 (`python -m unittest discover -s tests`) |
| Tecnologia | Python 3.11+ |
| Em hardware real | A correr como serviço na bancada de testes do CM5, consultado pelo servidor; nenhum microfone ou motor de voz foi experimentado |

## 🎯 Visão geral

* **Uma lista fechada de quinze comandos:** `status`, `silence`, `arm`, `disarm`, e os que perguntam - `alarms`, `nodes`, `cameras`, `radar`, `solar`, `electrical`, `network`, `time`, `help` - mais ligar e desligar as luzes, em **oito idiomas** (inglês, espanhol, alemão, francês, italiano, japonês, chinês e português), depois de normalizar acentos, pontuação e fórmulas de cortesia. Qualquer outra coisa, ou qualquer coisa ambígua, não é entendida.
* **Uma confirmação emitida pelo serviço:** `arm` e `disarm` devolvem um token assinado no primeiro turno e só são aceites quando um turno posterior o repete para a mesma intenção em 30 s, **do mesmo utilizador**. Quem chama não a pode forjar, uma caducada é recusada e os nonces das não caducadas nunca são esquecidos para arranjar espaço.
* **Um serviço HTTP local:** `python -m armor_voice_ai.service` escuta só no endereço de loopback, exige um token e responde a `POST /v1/command` com a decisão no idioma pedido; o menu Serviços do servidor mostra que versão corre.
* **Um ponto de turno:** `POST /v1/turn` recebe uma gravação, executa o comando de voz para texto que configurar, passa a ordem pelo motor e responde com uma gravação feita pelo comando de texto para voz; os comandos, o endereço do servidor e o seu token vêm do ambiente.
* **Decisões, não áudio:** com `--audit-file` cada decisão regista a intenção, o resultado e um SHA-256 da transcrição, nunca áudio nem as palavras em bruto.
* **Só recomendações:** um comando aceite é passado ao ARMOR-SERVER, que continua a autenticá-lo e autorizá-lo; a partir do painel de parede desarmar por voz nunca é possível (o PIN digita-se no ecrã); a partir da app segue o `ARMOR_DISARM_PIN` do servidor (ponha-o em `required`).

## 🧩 Papel no A.R.M.O.R.

O ARMOR-VOICE-AI transforma o que é dito num de uma lista fechada de comandos e nunca faz nada por si: o [ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) pergunta-lhe e depois autentica e autoriza o comando exatamente como um clique no [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO). Destina-se a viver atrás do microfone do painel de parede [ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI) e serve o assistente escrito e falado da aplicação Android.

## 📂 Estrutura do repositório

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
└── docs/                 SAFETY.md, SERVICE.md
```

## 🛠️ Ambiente de desenvolvimento

**Requisitos:** Python 3.11+ (standard library only), optional: a speech-to-text and a text-to-speech command for `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 83 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

Veja a [segurança da voz](docs/SAFETY.md) e o [serviço](docs/SERVICE.md).

## 🔗 Projetos relacionados

O **A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) é um sistema de segurança perimetral feito de repositórios independentes. Cada um tem a sua própria versão, os seus próprios testes e o seu próprio README; esta é a família:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensagens, validadores, vetores de conformidade e tipos gerados
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware de nó de campo para ESP32-S3 com três radares e o seu próprio painel web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocolos de inversores e baterias solares e as mensagens de um nó de ligação
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nó elétrico: contadores, a mensagem das leituras da rede e as regras de comutação
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Nó e central de alarme: zonas, armar, atrasos, sirene e PIN, com o servidor ou sem ele
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Painel tátil: o estado do sistema num ecrã de parede, armar e reconhecer, e a casa do assistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - A rede local: os seus dispositivos, a internet e o que muda
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordenador central: telemetria, alarmes, dispositivos, leituras solares e câmaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: câmaras, radar, alarmes, energia solar e o desenhador de local 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android de operador com um radar 2D/3D em direto
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferência visual que explica as suas decisões e nunca atua
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de câmara, máscaras e regras de deteção para o Jetson Orin NX
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
