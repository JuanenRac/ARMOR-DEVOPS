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
  🇯🇵 <b>日本語</b>
</p>

### デプロイのトポロジーと、隔離された CM5 テストベンチ

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**正直さのチェック - 今日動いているもの:** CM5 ベンチのインストーラーは、他のソフトウェアも動いている実際の CM5 で実行され、それらは正常なままでした。Docker Compose のトポロジーとオプションの TLS プロファイルは、WSL の Docker Engine で実際にビルドして実行しました（`scripts/test_compose.sh`、12 件のチェックで 3 つの不具合を発見し修正）が、**Jetson では行っていません**。バックアップと復元のスクリプトには往復テストがあり、通っています。

---

## 🎯 概要

* **中核マシン用のホストファイアウォール**（`scripts/firewall_core.sh`）：ブローカーのポートはフィールドネットワークからのみ、サーバーと Studio のポートはクライアントのネットワークからのみ（指定した場合）許可し、他には一切触れずそれ以外を許可する専用テーブルに入れます。`apply --rollback-after` は確認しないとルールを自動的に取り除くため、設定ミスで締め出されません。ルールと拒否のテストがあります（36 件、何も読み込みません）。どのマシンにも読み込んだことはなく、VLAN 自体はルーターとスイッチ向けの設計のままです。
* **CM5 テストベンチ：** `scripts/deploy_cm5.sh` はきれいなコピーでビルドし、アーカイブを送って `scripts/install_cm5.sh` を実行します。これは専用のユーザー、専用のディレクトリ、専用ポートの 2 つの systemd ユニット（`--with-mqtt` で 3 つ：A.R.M.O.R. 専用の Mosquitto をポート 18883 で、実際の CM5 で確認済み）を作り、リソース制限を設け、他のプロジェクトには決して触れません（[詳細](docs/CM5_TEST_BENCH.md)）。
* **Compose のトポロジー：** ノードごとに ID を持つ非匿名の Mosquitto ブローカー、サーバー、`/api/` を中継する nginx の背後にある Studio。公開されるのは Studio だけで、ループバック上です。堅牢化されたコンテナー、内部コアネットワーク、状態用の名前付きボリューム。
* **ベンチのブローカー上のデバイスと測定値：** サーバーは `armor/device/#` を購読して操作でき、`armor/node/+/info`、`armor/solar/#`、`armor/electrical/#` を読めます。`scripts/mqtt_identity.sh add device NAME` は 1 つのデバイスに専用トピックを、`add bridge NAME` は Zigbee2MQTT や Shelly のブリッジにすべてを与えます。 `scripts/mqtt_identity.sh electrical-switching NODE_ID on` だけが、サーバーが電気ノードの開閉器へコマンドを送れるようにします（既定ではオフ。`off` で取り消せます）。
* **シークレット：** `scripts/generate_secrets.sh` はランダムなシークレットを作り、何も表示しません。`scripts/check-required-env.sh` は、欠落、見本、短すぎる、重複した値を拒否します。
* **バックアップと復元：** `scripts/backup_data.sh` はサーバーデータの AES-256 暗号化、検証済み、チェックサム付きアーカイブを作ります（要求しない限り証拠は含めません）。`scripts/restore_data.sh` はそれを一覧または復元し、既存のデータを決して上書きしません。カメラの鍵は意図的にアーカイブに**入れません**。
* **TLS：** オプションの `tls` Compose プロファイルは、独自のローカル認証局を持つ Caddy を Studio の前に置きます（[詳細](docs/BACKUP_AND_TLS.md)）。
* **ベンチのすべてのサービス：** `install_cm5.sh` は、要求に応じて観測サービス（`--with-ai`）、音声サービス（`--with-voice`）、Studio がサービスの起動・停止・再起動と設定ファイルの編集を閉じた操作リストの範囲で行うための管理エージェント（`--with-admin`）、毎日の暗号化バックアップ（`--with-backup`）もインストールします。後で再実行すると、以前にインストールしたものを覚えています。

## 📂 リポジトリの構成

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ 開発環境

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
