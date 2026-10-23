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
  <img src="https://img.shields.io/badge/Version-0.6.6-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**正直さのチェック - 今日動いているもの:** CM5 ベンチのインストーラーは、他のソフトウェアも載っている実際の CM5 で実行され（それらは正常なまま）、ベンチはサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカー、下記の 2 つのヘルパーとともに日常的に動いており、コンポーネントの GitHub からのアップデート（Studio 経由）も行われています。Docker Compose の構成とオプションの TLS プロファイルは WSL 上の Docker Engine で実際にビルド・実行されています（`scripts/test_compose.sh`）が、**Jetson 上ではありません**。バックアップと復元のスクリプトには合格する往復テストがあり、2 つのヘルパーにも独自のテストがあります。**証明されていないもの：**このプロジェクトを一度も見たことがないマシンでのクリーンインストールと、Docker 構成全体の対象機での動作。

---

## 📋 ひと目で

| | |
|---|---|
| バージョン | `0.6.6` |
| 成熟度 | 確立 |
| 技術 | Docker Compose / Bash / YAML |
| 実機での確認 | 他のソフトウェアも載る実際の CM5 で CM5 テストベンチを日常的に運用。Jetson ではまだ |

## 🎯 概要

* **CM5 テストベンチ：**`scripts/deploy_cm5.sh` はクリーンなコピーでビルドし、アーカイブを 1 つ送って `scripts/install_cm5.sh` を実行します。これはサーバーと Studio のために専用ユーザー、専用ディレクトリ、専用ポートの systemd ユニットを作り、オプションで MQTT ブローカー、ネットワークノード、観察サービス、音声ゲートウェイ、管理エージェント、保守ヘルパー、日次バックアップも作ります。マシンで動く他のものには一切触れません。
* **保守ヘルパー**（`armor_maintenance_agent.py`）：設備自身のコンポーネントの GitHub からのアップデート（リリースパッケージをダウンロードし、SHA-256 を確認し、ロールバック付きで入れ替え）、OS のアップデート、任意の root コンソール。すべて Studio の*アップデート*タブから操作し、コンソールは有効にしない限りオフです。退避したコピーは新しい順に 6 つ保持し、ディスクがほぼ満杯のときはそれより少なくします（設定ファイルの `ARMOR_MAINT_MIN_FREE_MB`：既定は 500、0 で無効）。
* **管理エージェント**（`armor_admin_agent.py`）：唯一の特権部分で、サービス、設定ファイル、ブローカーアカウントの閉じた一覧だけを扱うため、Studio が root を必要とすることはありません。
* **各リリースのパッケージ：**`scripts/package_component.py` はコンポーネント（Studio、サーバー、ネットワーク、観察サービス、音声ゲートウェイ、DevOps）のパッケージを作り、隣に SHA-256 を書き、GitHub リリースとして公開します。
* **Compose 構成：**ノードごとに 1 つの ID と ACL（アラームノードやサーバーが伝える Zigbee ゾーンを含む）を持つ匿名でない Mosquitto ブローカー、サーバー、`/api/` をプロキシする nginx の背後の Studio。公開されるのは Studio のみで、ループバック上です。堅牢化したコンテナー、固定したイメージ、内部のコアネットワーク、状態用の名前付きボリューム。
* **TLS：**オプションの `tls` Compose プロファイルが、独自のローカル認証局を持つ Caddy を Studio の前に置き、TLS 上の Mosquitto 設定も用意されています（[詳細](docs/BACKUP_AND_TLS.md)）。
* **中核マシン用のホストファイアウォール**（`scripts/firewall_core.sh`）：ブローカーのポートはフィールドネットワークからのみ、サーバーと Studio のポートはクライアントのネットワークからのみ（指定時）、他には何も触れない専用のテーブルで。
* **秘密：**`scripts/generate_secrets.sh` はランダムな秘密を作って何も表示しません。`scripts/check-required-env.sh` は未設定、プレースホルダー、短すぎる、重複した値を拒否します。
* **バックアップと復元：**`scripts/backup_data.sh` はサーバーデータの AES-256 暗号化・検証済み・チェックサム付きアーカイブを作り（求めない限り証拠は除外）、`scripts/restore_data.sh` はそれを一覧するか、既存データを上書きせずに復元します。
* **Studio から設定できる VPN と家の名前：** `armor_wireguard.sh` は数コマンドで WireGuard VPN を作り（鍵はマシン上、スマホごとに QR コード付きの設定、必要ならノードへのルーティング）、`armor_ddns.sh` はプロバイダーがアドレスを変えても DuckDNS・Cloudflare などの名前が家を指し続けるようにします。メンテナンスエージェントが両方を Studio とスマホに提供するので、コマンドを打つ必要はなく、ルーターの設定も 8 言語の手順書で説明しています。**署名付きパッケージ：** メンテナンスヘルパーは、サーバー、Studio などのパッケージを、プロジェクトのリリース鍵による有効な Ed25519 署名がある場合にのみインストールします（追加ソフトなしの純粋な Python で検証）。署名がない、誤っている、改ざんされている場合、マシンは変更されません。緊急用の例外は、マシン自身のファイルの設定としてのみ存在します。
* **ブローカーへの任意の暗号化された入口(TLS 上の MQTT):** `scripts/armor_mqtt_tls.sh` は設備用の認証局(鍵はマシン上に留まり、モード `0600`)、マシンの名前とアドレス向けのブローカー証明書、通常のリスナーの隣の 8883 番の 2 つ目の Mosquitto リスナーを作ります(通常のリスナーには触れません)。冪等で、`status`、`export-ca`、`server-tls`、`remove` があります(ファイルは退避され、削除されません)。実際のハンドシェイクを含む OpenSSL での検証と、実際の Mosquitto 2.0 での検証済みです([ガイド](docs/MQTT_TLS_jpn.md))。
* **状態報告の許可:** ブローカーの規則は、各ノードが自分の `armor/health/<ノード>` に書き込み、サーバーが `armor/health/#` を読むことを許可します。`mqtt_identity.sh add` はすべての種類のノードにこの行を書き、`mqtt_identity.sh health-report <ロール> <ノード>` は以前に設置したノードに追加します（冪等で、以前の規則は保存されます）。
* **ノード制御のためのブローカー規則：** `armor/control/+/command`（`armor/control/all/command` を含む）に発行できるのはサーバーの ID だけです。各ノードは自分の命令トピックと一斉配信トピックを読み、自分の応答を `armor/control/<ノード>/result` に書くだけで、それ以外はできません。そのため、あるノードが別のノードに命令することはできず、盗まれたノードのパスワードで他のノードを再起動することもできません。`mqtt_identity.sh node-control` は以前にインストールしたノードに 3 行を追加し、ACL テストはすべての種類のノードを確認します。

## 🧩 A.R.M.O.R. での役割

ARMOR-DEVOPS は、他のすべてがマシンに載り、最新に保たれる手段です。CM5 テストベンチにサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカーをインストールし、[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) の*アップデート*タブが GitHub からインストールする各リリースのパッケージを作り、Studio が root で動くことなく設備を更新しサービスを管理できるようにする 2 つの小さなヘルパーを保持します。

## 📂 リポジトリの構成

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, armor_mqtt_tls (the optional encrypted door of the broker), tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS, MQTT_TLS
```

## 🛠️ 開発環境

**必要なもの:** Compose 付きの Docker Engine（コンテナ構成用）, CM5 または SSH で到達できる Debian 系のマシン（テストベンチ用）, デプロイを行うマシンの Bash、`ssh`、`tar`

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
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - ESP32-S3 用フィールドノードのファームウェア。レーダー 3 基と独自の Web パネル付き
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - 太陽光インバーターとバッテリーのプロトコル、およびゲートウェイノードのメッセージ
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - 電気ノード：電力量計、電力網の計測メッセージ、開閉のルール
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - 警報ノードと警報盤：警戒区域、警戒セット、遅延、サイレン、PIN。サーバーがあってもなくても
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - タッチパネル：壁面ディスプレイでのシステム状態表示、警戒・確認操作、音声アシスタントの拠点
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
