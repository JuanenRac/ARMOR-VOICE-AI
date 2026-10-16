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
  🇯🇵 <b>日本語</b> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### 8 言語のオフライン音声インテント。呼び出し側が偽造できない確認付き

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

**正直さのチェック - 今日動いているもの:** インテントのルール、8 言語、話者に結び付いた署名付き確認、ローカルサービス、ターンエンドポイント、監査は実在し、テストされています（49 件）。サーバーは CM5 テストベンチでこのサービスに問い合わせています。**音声認識・合成エンジンはこのリポジトリに含まれません**：`/v1/turn` は設定されたコマンドを実行するだけで、実際のマイクではまだ試されていません。アシスタントを載せる予定のタッチパネルは基板上で動いたことがありません。

---

## 📋 ひと目で

| | |
|---|---|
| バージョン | `0.2.8` |
| 成熟度 | 確立 |
| テスト | 49 (`python -m unittest discover -s tests`) |
| 技術 | Python 3.11+ |
| 実機での確認 | CM5 テストベンチでサービスとして動作し、サーバーが問い合わせます。マイクや音声エンジンは未検証 |

## 🎯 概要

* **15 個のコマンドからなる閉じた許可リスト：**`status`、`silence`、`arm`、`disarm`、尋ねる系の `alarms`、`nodes`、`cameras`、`radar`、`solar`、`electrical`、`network`、`time`、`help`、さらに照明のオン・オフを、アクセント・句読点・丁寧語の除去後に **8 言語**（英語、スペイン語、ドイツ語、フランス語、イタリア語、日本語、中国語、ポルトガル語）で。それ以外や曖昧なものは理解されません。
* **サービスが発行する確認：**`arm` と `disarm` は最初のターンで署名付きトークンを返し、30 秒以内の後続ターンで**同じユーザー**が同じインテントについてそれを返したときだけ受け付けます。呼び出し側は偽造できず、期限切れは拒否され、期限内のトークンのノンスは場所を空けるために忘れられることはありません。
* **ローカル HTTP サービス：**`python -m armor_voice_ai.service` はループバックアドレスのみで待ち受け、トークンを要求し、`POST /v1/command` に求められた言語で判断を返します。サーバーのサービスメニューで動作中のバージョンが分かります。
* **ターンエンドポイント：**`POST /v1/turn` は録音を受け取り、設定した音声認識コマンドを実行し、指示をエンジンに通し、音声合成コマンドで作った録音で答えます。コマンド、サーバーアドレス、そのトークンは環境変数から読みます。
* **音声ではなく判断を記録：**`--audit-file` を使うと、各判断はインテント、結果、文字起こしの SHA-256 を記録し、音声や生の言葉は決して記録しません。
* **推奨のみ：**受け付けたコマンドは ARMOR-SERVER に渡され、サーバーが引き続き認証と認可を行います。本人が画面で PIN を入力せずに、音声で解除することは決してできません。

## 🧩 A.R.M.O.R. での役割

ARMOR-VOICE-AI は、話された内容を閉じたリストのコマンドのひとつに変えるだけで、自分では何もしません。[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER) が問い合わせ、[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) でのクリックと同じようにコマンドを認証・認可します。壁掛けパネル [ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI) のマイクの背後で動く想定で、Android アプリの文字・音声アシスタントにも応えます。

## 📂 リポジトリの構成

```text
ARMOR-VOICE-AI/
├── src/armor_voice_ai/   phrases, intent, confirmation, session, gateway (stdin), service (HTTP), turn (speech to text, order, text to speech)
├── tests/                gateway, languages, service and turn tests
└── docs/                 SAFETY.md, SERVICE.md
```

## 🛠️ 開発環境

**必要なもの:** Python 3.11+ (standard library only), optional: a speech-to-text and a text-to-speech command for `/v1/turn`

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests   # 49 tests
echo '{"text":"arm the system"}' | python -m armor_voice_ai.gateway
python -m armor_voice_ai.service        # the local HTTP service the server asks (loopback only)
```

[音声の安全性](docs/SAFETY.md)と[サービス](docs/SERVICE.md)を参照してください。

## 🔗 関連プロジェクト

**A.R.M.O.R.**（Autonomous Radar & Multimodal Observation Range）は、独立したリポジトリで構成される周辺警備システムです。それぞれに独自のバージョン、テスト、README があります。ファミリーは次のとおりです：

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - メッセージ契約、検証器、適合性ベクトル、生成された型
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - ESP32-S3 用フィールドノードのファームウェア。レーダー 3 基と独自の Web パネル付き
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - 太陽光インバーターとバッテリーのプロトコル、およびゲートウェイノードのメッセージ
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - 電気ノード：電力量計、電力網の計測メッセージ、開閉のルール
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - 警報ノードと警報盤：警戒区域、警戒セット、遅延、サイレン、PIN。サーバーがあってもなくても
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - タッチパネル：壁面ディスプレイでのシステム状態表示、警戒・確認操作、音声アシスタントの拠点
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - ローカルネットワーク：機器、インターネット、そして変化
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - 中央コーディネーター：テレメトリ、アラーム、デバイス、太陽光の測定値、カメラ
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web コンソール：カメラ、レーダー、アラーム、太陽光発電、2D/3D サイト設計
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - リアルタイム 2D/3D レーダー付きの Android オペレータークライアント
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - 判断を説明し、決して動作しない視覚推論ポリシー
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Jetson Orin NX 向けのカメラのゾーン、マスク、検知ルール
* **ARMOR-VOICE-AI** (このリポジトリ) - 偽造できない確認を備えたオフライン音声インテント
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 筐体、電子部品、ベンチ受け入れマトリクス
* **[ARMOR-DEVOPS](https://github.com/JuanenRac/ARMOR-DEVOPS)** - デプロイ、CM5 テストベンチ、バックアップ、TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - 再現可能な故障を備えたオフラインのテレメトリシミュレーター
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - エコシステム自身のリポジトリを検出し、インストールし、更新する
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - アーキテクチャ、セキュリティ基準、機能マトリクス

## 📚 ドキュメントとコミュニティ

詳しくは：

* [機能マトリクス：実証済みのものとそうでないもの](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [プロジェクト一覧：バージョンとリポジトリ間の依存関係](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [このリポジトリの変更履歴](CHANGELOG.md)
* [ライセンス（GPL-3.0-or-later）](LICENSE)
* 質問・提案・報告：electrohobby3d@gmail.com

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 ライセンス

GPL-3.0-or-later - [LICENSE](LICENSE) を参照。
