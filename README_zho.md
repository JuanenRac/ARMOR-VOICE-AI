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
  🇨🇳 <b>简体中文</b> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### 八种语言的离线语音意图，带有调用方无法伪造的确认

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Language-Python%203.11%2B-3776ab.svg" alt="Language">
  <img src="https://img.shields.io/badge/Mode-offline-2ea44f.svg" alt="Mode">
  <img src="https://img.shields.io/badge/Languages-8-00E5FF.svg" alt="Languages">
  <img src="https://img.shields.io/badge/Tests-83%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.3.1-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**诚实性检查 - 今天真正能运行的部分:** 意图规则、八种语言、绑定到说话人的签名确认、本地服务、轮次端点和审计都是真实的并经过测试（83 个测试），服务器在 CM5 测试台上向该服务发起请求。**本仓库不包含任何语音识别或合成引擎**：`/v1/turn` 运行你为它们配置的命令，目前都还没有用真实麦克风试过；打算承载助手的触摸面板还没有在板上运行过。

---

## 📋 速览

| | |
|---|---|
| 版本 | `0.3.1` |
| 成熟度 | 成熟 |
| 测试 | 83 (`python -m unittest discover -s tests`) |
| 技术栈 | Python 3.11+ |
| 真实硬件 | 在 CM5 测试台上作为服务运行，由服务器调用；尚未试过麦克风或语音引擎 |

## 🎯 概述

* **十五个命令组成的封闭白名单：**`status`、`silence`、`arm`、`disarm`，以及用于询问的 `alarms`、`nodes`、`cameras`、`radar`、`solar`、`electrical`、`network`、`time`、`help`，还有开关灯，支持**八种语言**（英语、西班牙语、德语、法语、意大利语、日语、中文和葡萄牙语），先规范化重音、标点和客套话。其他任何内容或有歧义的内容都不会被理解。
* **由服务签发的确认：**`arm` 和 `disarm` 在第一轮返回签名令牌，只有在 30 秒内的后续一轮为**同一用户**的同一意图回传它时才被接受。调用方无法伪造，过期的会被拒绝，未过期令牌的随机数也绝不会为腾出空间而被忘记。
* **本地 HTTP 服务：**`python -m armor_voice_ai.service` 只监听回环地址，需要令牌，对 `POST /v1/command` 以所要求的语言返回决定；服务器的“服务”菜单会显示运行的是哪个版本。
* **轮次端点：**`POST /v1/turn` 接收一段录音，运行你配置的语音转文字命令，把指令交给引擎，并用文字转语音命令生成的录音作答；命令、服务器地址及其令牌来自环境变量。
* **只记录决定，不记录音频：**使用 `--audit-file` 时，每个决定记录意图、结果和转写文本的 SHA-256，绝不记录音频或原话。
* **只是建议：**被接受的命令会交给 ARMOR-SERVER，由它继续认证和授权；在墙面面板上绝不可能用语音撤防（PIN 在屏幕上输入）；在应用中则遵循服务器的 `ARMOR_DISARM_PIN`（请设为 `required`）。

## 🧩 在 A.R.M.O.R. 中的角色

ARMOR-VOICE-AI 把所说的话变成封闭列表中的某个命令，自己从不做任何事：[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) 向它询问，然后像对待 [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) 中的一次点击那样认证并授权该命令。它打算放在壁挂面板 [ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI) 的麦克风之后，并为 Android 应用的文字和语音助手服务。

## 📂 仓库结构

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
└── docs/                 SAFETY.md, SERVICE.md
```

## 🛠️ 开发环境

**环境要求:** Python 3.11+（仅标准库）, 可选：用于 `/v1/turn` 的语音转文字和文字转语音命令

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 83 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

参见[语音安全](docs/SAFETY.md)和[服务](docs/SERVICE.md)。

## 🔗 相关项目

**A.R.M.O.R.**（Autonomous Radar & Multimodal Observation Range）是由若干独立仓库组成的周界安防系统。每个仓库都有自己的版本、测试和 README；家族成员如下：

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - 消息契约、验证器、一致性向量和生成的类型
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - 适用于 ESP32-S3 的现场节点固件，带三个雷达和自带网页面板
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - 太阳能逆变器与电池的协议，以及网关节点的消息
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - 电气节点：电表、电网读数消息和开关规则
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - 报警节点与报警主机：防区、布防、延时、警笛和 PIN，有无服务器均可
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - 触摸面板：墙面屏幕上的系统状态、布防与确认，以及语音助手的所在
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - 本地网络：其设备、互联网以及变化
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - 中央协调器：遥测、报警、设备、太阳能读数和摄像头
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - 网页控制台：摄像头、雷达、报警、太阳能和 2D/3D 场地设计器
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - 带实时 2D/3D 雷达的 Android 操作员客户端
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone 操作员客户端
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - 会解释决策且从不执行动作的视觉推理策略
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Jetson Orin NX 上的摄像头区域、遮罩与检测规则
* **ARMOR-VOICE-AI** (本仓库) - 带无法伪造确认的离线语音意图
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 外壳、电子器件和台架验收矩阵
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - 部署、CM5 测试台、备份与 TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - 带可重复故障的离线遥测模拟器
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - 发现、安装并更新生态系统自身的仓库
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - 架构、安全基线和能力矩阵

## 📚 文档与社区

更多阅读：

* [能力矩阵：哪些已被证实，哪些没有](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [项目目录：版本以及各仓库之间的依赖](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [本仓库的变更记录](CHANGELOG.md)
* [许可证（GPL-3.0-or-later）](LICENSE)
* 问题、想法与反馈：electrohobby3d@gmail.com

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 许可证

GPL-3.0-or-later - 见 [LICENSE](LICENSE)。
