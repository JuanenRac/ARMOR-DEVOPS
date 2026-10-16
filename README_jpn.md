<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

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

### デプロイ、CM5 テストベンチ、GitHub からのアップデート、設備の保守

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.5.2-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**正直さのチェック - 今日動いているもの:** CM5 ベンチのインストーラーは、他のソフトウェアも載っている実際の CM5 で実行され（それらは正常なまま）、ベンチはサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカー、下記の 2 つのヘルパーとともに日常的に動いており、コンポーネントの GitHub からのアップデート（Studio 経由）も行われています。Docker Compose の構成とオプションの TLS プロファイルは WSL 上の Docker Engine で実際にビルド・実行されています（`scripts/test_compose.sh`）が、**Jetson 上ではありません**。バックアップと復元のスクリプトには合格する往復テストがあり、2 つのヘルパーにも独自のテストがあります。**証明されていないもの：**このプロジェクトを一度も見たことがないマシンでのクリーンインストールと、Docker 構成全体の対象機での動作。

---

## 📋 ひと目で

| | |
|---|---|
| バージョン | `0.5.2` |
| 成熟度 | 確立 |
| 技術 | Docker Compose / Bash / YAML |
| 実機での確認 | 他のソフトウェアも載る実際の CM5 で CM5 テストベンチを日常的に運用。Jetson ではまだ |

## 🎯 概要

* **CM5 テストベンチ：**`scripts/deploy_cm5.sh` はクリーンなコピーでビルドし、アーカイブを 1 つ送って `scripts/install_cm5.sh` を実行します。これはサーバーと Studio のために専用ユーザー、専用ディレクトリ、専用ポートの systemd ユニットを作り、オプションで MQTT ブローカー、ネットワークノード、観察サービス、音声ゲートウェイ、管理エージェント、保守ヘルパー、日次バックアップも作ります。マシンで動く他のものには一切触れません。
* **保守ヘルパー**（`armor_maintenance_agent.py`）：設備自身のコンポーネントの GitHub からのアップデート（リリースパッケージをダウンロードし、SHA-256 を確認し、ロールバック付きで入れ替え）、OS のアップデート、任意の root コンソール。すべて Studio の*アップデート*タブから操作し、コンソールは有効にしない限りオフです。
* **管理エージェント**（`armor_admin_agent.py`）：唯一の特権部分で、サービス、設定ファイル、ブローカーアカウントの閉じた一覧だけを扱うため、Studio が root を必要とすることはありません。
* **各リリースのパッケージ：**`scripts/package_component.py` はコンポーネント（Studio、サーバー、ネットワーク、観察サービス、音声ゲートウェイ、DevOps）のパッケージを作り、隣に SHA-256 を書き、GitHub リリースとして公開します。
* **Compose 構成：**ノードごとに 1 つの ID と ACL（アラームノードやサーバーが伝える Zigbee ゾーンを含む）を持つ匿名でない Mosquitto ブローカー、サーバー、`/api/` をプロキシする nginx の背後の Studio。公開されるのは Studio のみで、ループバック上です。堅牢化したコンテナー、固定したイメージ、内部のコアネットワーク、状態用の名前付きボリューム。
* **TLS：**オプションの `tls` Compose プロファイルが、独自のローカル認証局を持つ Caddy を Studio の前に置き、TLS 上の Mosquitto 設定も用意されています（[詳細](docs/BACKUP_AND_TLS.md)）。
* **中核マシン用のホストファイアウォール**（`scripts/firewall_core.sh`）：ブローカーのポートはフィールドネットワークからのみ、サーバーと Studio のポートはクライアントのネットワークからのみ（指定時）、他には何も触れない専用のテーブルで。
* **秘密：**`scripts/generate_secrets.sh` はランダムな秘密を作って何も表示しません。`scripts/check-required-env.sh` は未設定、プレースホルダー、短すぎる、重複した値を拒否します。
* **バックアップと復元：**`scripts/backup_data.sh` はサーバーデータの AES-256 暗号化・検証済み・チェックサム付きアーカイブを作り（求めない限り証拠は除外）、`scripts/restore_data.sh` はそれを一覧するか、既存データを上書きせずに復元します。

## 🧩 A.R.M.O.R. での役割

ARMOR-DEVOPS は、他のすべてがマシンに載り、最新に保たれる手段です。CM5 テストベンチにサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカーをインストールし、[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) の*アップデート*タブが GitHub からインストールする各リリースのパッケージを作り、Studio が root で動くことなく設備を更新しサービスを管理できるようにする 2 つの小さなヘルパーを保持します。

## 📂 リポジトリの構成

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, tests of the agents, the backup, the firewall and the Compose topology
│   └── dist-packages/   the packages of each release (Studio, server, network, observation, voice, DevOps) with their SHA-256
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ 開発環境

**必要なもの:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

[デプロイの境界](docs/DEPLOYMENT_BOUNDARY.md)を参照。

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
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - 偽造できない確認を備えたオフライン音声インテント
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 筐体、電子部品、ベンチ受け入れマトリクス
* **ARMOR-DEVOPS** (このリポジトリ) - デプロイ、CM5 テストベンチ、バックアップ、TLS
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
