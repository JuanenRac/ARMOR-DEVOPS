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
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**正直さのチェック - 今日動いているもの:** CM5 ベンチのインストーラーは、他のソフトウェアも載っている実際の CM5 で実行され（それらは正常なまま）、ベンチはサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカー、下記の 2 つのヘルパーとともに日常的に動いており、コンポーネントの GitHub からのアップデート（Studio 経由）も行われています。Docker Compose の構成とオプションの TLS プロファイルは WSL 上の Docker Engine で実際にビルド・実行されています（`scripts/test_compose.sh`）が、**Jetson 上ではありません**。バックアップと復元のスクリプトには合格する往復テストがあり、2 つのヘルパーにも独自のテストがあります。**証明されていないもの：**このプロジェクトを一度も見たことがないマシンでのクリーンインストールと、Docker 構成全体の対象機での動作。

---

## 📋 ひと目で

| | |
|---|---|
| バージョン | `0.6.8` |
| 成熟度 | 確立 |
| 役割 | デプロイキット：CM5 テストベンチのインストーラー、リリースパッケージ、2 つのヘルパー、Compose 構成 |
| 技術 | Bash、Python 3（標準ライブラリ）、Docker Compose、Mosquitto、Caddy、nginx、systemd |
| テスト | 各部分にテストスクリプト（`scripts/test_*.sh` と `test_*.py`）。Compose 構成は WSL の Docker でビルドして実行 |
| 契約 | ベンチのポート：サーバー 18080、Studio 18081、MQTT 18883（1883 は使わない）、音声 18090 |
| 動作環境 | CM5 または SSH で届く Debian 系マシン。コンテナ構成には Docker Engine と Compose |
| 実機での確認 | 他のソフトウェアも載る実際の CM5 で CM5 テストベンチを日常的に運用。Jetson ではまだ |
| ライセンス | GPL-3.0-or-later |

**移動先：** [概要](#-概要) · [アーキテクチャ](#-アーキテクチャ) · [セキュリティ](#-セキュリティと安全) · [インターフェース](#-インターフェース) · [設定](#-設定) · [クイックスタート](#-クイックスタート) · [テスト](#-テスト) · [トラブルシューティング](#-トラブルシューティング) · [構成](#-リポジトリの構成) · [関連](#-関連プロジェクト)

## 🚦 プロジェクトの状況

各行はこのリポジトリの一部分で、信号は今日どこまで進んでいるかを示します。計画ではなく、リポジトリが示せるもの（テスト、ビルド、実行）に基づいて書かれています。

🟢 完了・検証済み · 🟡 動作する（既知の制限あり） · 🟠 一部のみ、または未検証 · 🔴 未実装または動作しない

| 領域 | 状態 | ここでの意味 |
|---|---|---|
| ソフトウェア | 🟡 | CM5 ベンチのインストーラーは、他のソフトも動いている実機の CM5 で実行し、そちらは正常なままでした。このプロジェクトをまだ一度も入れていない新品の機器への導入は未確認です。 |
| テスト | 🟡 | バックアップと復元のスクリプトには通過する往復テストがあり、2 つの補助プログラムにも専用のテストがあります。オプションの TLS 構成を含む Docker 構成は WSL の Docker Engine でビルドして実行しましたが、構成全体を対象機器では動かしていません。 |
| ハードウェア | 🟡 | CM5 テストベンチを日常的に動かしています。Jetson ではまだ何も動かしていません。 |
| アップデート | 🟢 | GitHub からのコンポーネントの更新は、Studio 経由で CM5 テストベンチ上で実施済みです。 |
| ドキュメント | 🟢 | 8 言語と変更履歴は最新です。 |

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
* **Studio から設定できる VPN と家の名前：** `armor_wireguard.sh` は数コマンドで WireGuard VPN を作り（鍵はマシン上、スマホごとに QR コード付きの設定、必要ならノードへのルーティング）、`armor_ddns.sh` はプロバイダーがアドレスを変えても DuckDNS・Cloudflare などの名前が家を指し続けるようにします。メンテナンスエージェントが両方を Studio とスマホに提供するので、コマンドを打つ必要はなく、ルーターの設定も 8 言語の手順書で説明しています。
* **署名付きパッケージ：** メンテナンスヘルパーは、サーバー、Studio などのパッケージを、プロジェクトのリリース鍵による有効な Ed25519 署名がある場合にのみインストールします（追加ソフトなしの純粋な Python で検証）。署名がない、誤っている、改ざんされている場合、マシンは変更されません。緊急用の例外は、マシン自身のファイルの設定としてのみ存在します。
* **ブローカーへの任意の暗号化された入口(TLS 上の MQTT):** `scripts/armor_mqtt_tls.sh` は設備用の認証局(鍵はマシン上に留まり、モード `0600`)、マシンの名前とアドレス向けのブローカー証明書、通常のリスナーの隣の 8883 番の 2 つ目の Mosquitto リスナーを作ります(通常のリスナーには触れません)。冪等で、`status`、`export-ca`、`server-tls`、`remove` があります(ファイルは退避され、削除されません)。実際のハンドシェイクを含む OpenSSL での検証と、実際の Mosquitto 2.0 での検証済みです([ガイド](docs/MQTT_TLS_jpn.md))。
* **状態報告の許可:** ブローカーの規則は、各ノードが自分の `armor/health/<ノード>` に書き込み、サーバーが `armor/health/#` を読むことを許可します。`mqtt_identity.sh add` はすべての種類のノードにこの行を書き、`mqtt_identity.sh health-report <ロール> <ノード>` は以前に設置したノードに追加します（冪等で、以前の規則は保存されます）。
* **ノード制御のためのブローカー規則：** `armor/control/+/command`（`armor/control/all/command` を含む）に発行できるのはサーバーの ID だけです。各ノードは自分の命令トピックと一斉配信トピックを読み、自分の応答を `armor/control/<ノード>/result` に書くだけで、それ以外はできません。そのため、あるノードが別のノードに命令することはできず、盗まれたノードのパスワードで他のノードを再起動することもできません。`mqtt_identity.sh node-control` は以前にインストールしたノードに 3 行を追加し、ACL テストはすべての種類のノードを確認します。

## 🧩 A.R.M.O.R. での役割

ARMOR-DEVOPS は、他のすべてがマシンに載り、最新に保たれる手段です。CM5 テストベンチにサーバー、Studio、ネットワークノード、観察・音声サービス、ブローカーをインストールし、[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) の*アップデート*タブが GitHub からインストールする各リリースのパッケージを作り、Studio が root で動くことなく設備を更新しサービスを管理できるようにする 2 つの小さなヘルパーを保持します。

| 連携先 | 方法 | 目的 |
|---|---|---|
| ARMOR-STUDIO | その *更新* タブがローカルソケット経由でメンテナンスヘルパーに依頼 | root は不要 |
| GitHub Releases | `package_component.py` が SHA-256 と署名付きでパッケージを公開 | インストールするコンポーネント |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | 専用の systemd ユニットとしてインストール | ベンチのサービス |
| ARMOR-UPDATER | 別物 | PC にファミリーのコピーを置く人のツール。このリポジトリは CM5 と Compose 構成向け |

## 🏛️ アーキテクチャ

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 セキュリティと安全

| 脅威 | 防御 |
|---|---|
| CM5 上の他のソフトへの干渉 | 専用のユーザー、ディレクトリ、ポート（サーバー 18080、Studio 18081、MQTT 18883、音声 18090。すべて 1024〜65535 で互いに異なり、標準の 1883 は使わない）。システムのファイアウォールには触れません |
| 開放された、または認証のないブローカー | `allow_anonymous false`、パスワードファイル、ACL（秘密は `/run/secrets` にマウント）、ノードごとに 1 つの ID。`armor/control/+/command` を発行できるのはサーバーだけ。各ノードは自分のコマンドと一斉コマンドを読み、自分の `armor/control/<ノード>/result` と `armor/health/<ノード>` だけに書き込みます。サーバーは `armor/health/#` を読みます |
| 意図しないネットワーク公開 | `ARMOR_MQTT_BIND`、`ARMOR_STUDIO_BIND`（Caddy は `ARMOR_TLS_BIND`）で指定しない限り、Compose はブローカーと Studio を `127.0.0.1` だけに公開 |
| 平文の MQTT と Studio | 任意：平文リスナーの隣に 8883 の 2 つ目の Mosquitto リスナー（`armor_mqtt_tls.sh`：専用の認証局、鍵はモード `0600`、マシンの名前向け証明書、冪等で平文側には触れない）と、Caddy と専用ローカル認証局を使う Compose の `tls` プロファイル |
| 中核マシンが誰にでも開いている | `firewall_core.sh` は専用テーブル（`/etc/armor/firewall.nft`、ロールバックユニット付き）を書きます：ブローカーのポートはフィールドネットワークからのみ、サーバーと Studio のポートはクライアントネットワークからのみ。`check` は `nft -c` で検証 |
| 弱い、または表示された秘密 | `generate_secrets.sh` はランダムな秘密を作り、何も表示しません。`check-required-env.sh` は未設定、プレースホルダー、短い値、重複を拒否します |
| 盗まれたバックアップ | `backup_data.sh` は AES-256 で暗号化し、検証とチェックサム付きのアーカイブを作ります（証拠は要求しない限り除外）。`restore_data.sh` は一覧表示または復元し、既存のデータは決して上書きしません |
| コンポーネントの偽の更新 | メンテナンスヘルパーはリリースパッケージを取得し、SHA-256 とプロジェクトのリリース鍵による Ed25519 署名（純 Python で検証）を確認し、ロールバック付きで入れ替えます。署名がない、誤り、改ざんのときはマシンを変更しません |
| Studio から root に届く | 不要です：管理エージェント（`armor_admin_agent.py`）はサービス、設定ファイル、ブローカーアカウントの固定リストだけを扱い、メンテナンスヘルパーの root コンソールは有効にしない限りオフです |

コンテナは強化済みで、イメージは固定、`core` ネットワークは内部のみ、状態は名前付きボリュームに置きます。2 つのヘルパーはローカルの Unix ソケットを使うため、テストには Linux が必要です。プロジェクトを一度も見たことのないマシンへのクリーンインストールと、Docker 構成全体の実環境での動作は未確認で、第三者によるレビューもありません。

## 🔌 インターフェース

| ルート | 認証 | 内容 |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | クリーンなコピーでビルドし、SSH で 1 つのアーカイブを送り `install_cm5.sh` を実行 |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | ユーザー、ディレクトリ、systemd ユニットを作成。`--server-port`、`--studio-port`、`--mqtt-port`、`--also-reach` で調整。`--apply` がなければ計画を表示するだけ |
| `scripts/package_component.py` | - | Studio、サーバー、ネットワークノード、観察サービス、音声ゲートウェイ、DevOps をメンテナンスヘルパーが入れる形にまとめ、SHA-256 を書き、GitHub リリースとして公開 |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` と `secrets/`（Git は無視）。検査は未設定・プレースホルダー・短い値・重複を拒否 |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | サーバーデータの暗号化・検証済みアーカイブ |
| `scripts/restore_data.sh` | - | アーカイブの一覧表示、または既存データを上書きしない復元 |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | 中核マシンのファイアウォールテーブル。`check` で検証（`nft` がなければ `FIREWALL_CHECK=SKIP`） |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | 各種ノードのブローカー行を書き込み、以前入れたノードに健康レポートと制御を追加（冪等） |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | ブローカーの暗号化された入口（`status`、`export-ca`、`server-tls` など）、スマホごとの QR 付き WireGuard VPN、家の DuckDNS・Cloudflare などの名前、リモートアクセスの確認。Studio からコマンドなしで使えます |

2 つのヘルパー（`armor_admin_agent.py`、`armor_maintenance_agent.py`）はローカルの Unix ソケットで待ち受けるため、Windows では動きません。Compose ファイルはブローカー（Mosquitto）、サーバー、Studio（`/api/` を中継する nginx）を起動し、`tls` プロファイルで Caddy を追加します。公開されるのは Studio だけで、既定ではループバック（`127.0.0.1:8088`、TLS は 8443）です。各リリースのパッケージは GitHub リリースのアセットで、このリポジトリのファイルではありません。 システム更新のログは 10% ごとに `downloading: N%` と表示するため、遅い回線でも更新が止まったように見えません。依存関係の再インストール（`npm ci`）は、プロジェクトの新バージョンだけでは行わず、ロックファイルが依存関係について述べる内容が変わったときだけ行います。

## ⚙️ 設定

| 設定 | 既定値 | 内容 |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`、`--studio-port`、`--mqtt-port`（再指定しなければ現在のものを保持）と音声ポート。すべて 1024〜65535 で互いに異なる。ブローカーのアドレスは `PREFIX/etc/armor.mqtt.env` に入ります |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | Compose がブローカーと Studio を公開する場所 |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | Studio にアクセスするオリジン |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | `tls` プロファイルの Caddy |
| `.env`  `.env.example` | - | `generate_secrets.sh` が作成し、Git は無視。例に全変数を記載 |

メンテナンスヘルパーの root コンソールはマシン自身のファイルの設定で、既定ではオフです。ファイアウォールと TLS はインストーラーのオプションで、既定ではありません。詳細は [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md)。

## 🚀 クイックスタート

**要件：** Docker Engine と Compose（コンテナ構成用）、CM5 または SSH で届く Debian 系マシン（テストベンチ用）、デプロイ側マシンの Bash、`ssh`、`tar`。

```bash
scripts/generate_secrets.sh                                                            # `.env` と `secrets/`（Git は無視）
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # コンテナ構成
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # テストベンチ
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # 暗号化バックアップ
```

[デプロイの境界](docs/DEPLOYMENT_BOUNDARY.md)と[テストベンチ](docs/CM5_TEST_BENCH.md)を参照してください。

## 🧪 テスト

| 分野 | 対象 |
|---|---|
| `test_admin_agent.py`  `.sh` | 管理エージェントの固定リスト（Linux が必要：Unix ソケット） |
| `test_maintenance_agent.py`  `.sh` | メンテナンスヘルパー：取得、SHA-256、署名、入れ替え、ロールバック（Linux が必要） |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | パッケージ、コンポーネント一覧、リモートアクセスヘルパー |
| `test_backup.sh`  `test_env_and_restore.sh` | バックアップと復元の往復、秘密、環境の検査 |
| `test_compose.sh`  `validate-compose.sh` | Compose 構成と TLS プロファイル（WSL の Docker Engine でビルドして実行） |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | ファイアウォール、インストーラーの計画、ブローカー ID、TLS 上の MQTT、TLS 検査、VPN、動的な名前 |

Python のテストは `python -m unittest discover -s scripts -p "test_*.py"` で実行します。Windows では Unix ソケットが必要な 3 件は動きません。スクリプトには Bash、WSL、Docker または root が必要で、Linux で実行します。テスト件数の単一の数字はまだなく、Project status が実行済みの内容を示します。GitHub Actions は push と pull request のたびに A.R.M.O.R. の基本検査（マニフェスト、バージョン、変更履歴、README の一致）と、プロジェクト自身のビルドとテストを実行します。

## 🏗️ ビルドとリリース

コンパイルするものはなく、スクリプト、Compose ファイル、Python ヘルパーだけです。`scripts/package_component.py` がコンポーネントのパッケージを作り、隣に SHA-256 を書きます。パッケージは GitHub リリースのアセットで、このリポジトリのファイルではありません。バージョンは `armor.project.json` と README のバッジ（マニフェストから読み取り）にあり、各バージョンには [CHANGELOG.md](CHANGELOG.md) にエントリーがあります。

## 🩺 トラブルシューティング

| 表示 | 原因 | 対処 |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | `install_cm5.sh` のポートが範囲外または重複 | 1024〜65535 の異なるポートを使う（標準の 1883 は不可） |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | 追加アドレスが「Studio のアドレス = サーバーのアドレス」の形でない | `--also-reach http://<ホスト>:<Studio ポート>=http://<ホスト>:<サーバーポート>` と書く |
| `FIREWALL_CHECK=SKIP nft is not installed here` | `nft` がなく、`firewall_core.sh check` が表を検証できない | nftables を入れて再度確認 |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | 2 つのヘルパーのテストを Windows で実行している | Linux（または WSL）で実行 |

## 📂 リポジトリの構成

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>ツリーのテキスト版</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      ベンチへデプロイしてインストール
│   ├── package_component.py                              各リリースのパッケージ
│   ├── armor_admin_agent.py armor_maintenance_agent.py   Studio の 2 つのヘルパー
│   ├── generate_secrets.sh check-required-env.sh         ランダムな秘密、弱いものは拒否
│   ├── backup_data.sh restore_data.sh                    暗号化バックアップと復元
│   ├── firewall_core.sh mqtt_identity.sh                 ファイアウォールとブローカー ID
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              TLS 上の MQTT とその確認
│   ├── armor_ddns.sh armor_wireguard.sh                  家の名前と VPN
│   └── test_*.py test_*.sh validate-compose.sh           ヘルパーとスクリプトのテスト
├── docker-compose.yml docker-compose.tls.yml             ブローカー、サーバー、Studio、TLS プロファイル
├── mosquitto/                                            mosquitto.conf、TLS 設定、acl.example
├── caddy/                                                Caddyfile：Studio の前段の HTTPS
├── docs/                                                 DEPLOYMENT_BOUNDARY、CM5_TEST_BENCH、BENCH_TESTS、BACKUP_AND_TLS、MQTT_TLS、HTTPS_PAIRING、REMOTE_ACCESS、SIGNED_PACKAGES（後ろ 4 つは 8 言語版あり）
├── tools/                                                共通の CI 検査とツール
├── images/                                               バナー、アイコン、README の画像
├── .github/                                              CI ワークフロー、ダッシュボード通知、Issue と Pull Request のテンプレート
├── armor.project.json                                    マニフェスト：版・役割・成熟度
├── CHANGELOG.md                                          各バージョンの変更点
├── run.sh run.bat                                        起動（共通フロー）
├── build.sh build.bat                                    ビルドとテスト（共通フロー）
├── build-test.sh build-test.bat                          ビルド、テスト、パッケージ化
├── test.sh test.bat                                      テストのみ（版は変えません）
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ ロードマップと既知の制限

**現時点の既知の制限**

* プロジェクトを一度も見たことのないマシンへのクリーンインストールは未確認です。
* Docker 構成全体は WSL の Docker Engine でビルドして実行しましたが、対象の Jetson では動かしていません。
* テスト件数の単一の数字はなく、2 つのヘルパーのテストには Linux が必要です。
* 第三者によるセキュリティレビューはありません。

**今後**

* 新しいマシンでのクリーンインストールと、Jetson 上の Docker 構成。

## 🌍 言語

README とテキストは、英語、スペイン語、フランス語、イタリア語、ドイツ語、中国語、日本語、ヨーロッパポルトガル語で提供されています。

## 🔗 関連プロジェクト

**A.R.M.O.R.**（Autonomous Radar & Multimodal Observation Range）は、独立したリポジトリで構成される境界セキュリティシステムです。各リポジトリは独自のバージョン、テスト、README を持ちます。ファミリーは次のとおりです：

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - メッセージのコントラクト、バリデーター、適合ベクトル、生成された型
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - 3 つのレーダーと独自の Web パネルを備えた ESP32-S3 向けフィールドノードのファームウェア
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - ソーラーインバーターとバッテリーのプロトコル、ゲートウェイノードのメッセージ
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - 電気ノード：メーター、系統の読み取り値のメッセージ、切り替えのルール
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - 警報ノードとパネル：ゾーン、警戒、遅延、サイレン、PIN。サーバーありでもなしでも動作
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - タッチパネル：壁面画面でのシステムの状態、警戒と確認応答、そして音声アシスタントの置き場
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - ローカルネットワーク：そのデバイス、インターネット、そして変化
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - 中央コーディネーター：テレメトリ、警報、デバイス、ソーラーの読み取り値、カメラ
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web コンソール：カメラ、レーダー、警報、太陽光エネルギー、2D/3D のサイトデザイナー
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - ライブの 2D/3D レーダーを備えた Android オペレータークライアント
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone オペレータークライアント
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - 判断を説明し、決して作動させない視覚推論ポリシー
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Jetson Orin NX 向けのカメラゾーン、マスク、検出ルール
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - 偽造できない確認つきのオフライン音声インテント
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 筐体、電子回路、ベンチ受け入れマトリクス
* **ARMOR-DEVOPS**（このリポジトリ） - デプロイ、CM5 テストベンチ、バックアップ、TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - 再現可能な障害を持つオフラインのテレメトリシミュレーター
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - エコシステム自身のリポジトリを検出、インストール、更新
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - アーキテクチャ、セキュリティのベースライン、機能マトリクス

## 📚 ドキュメント

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md)：このリポジトリがデプロイするものとしないもの
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md)：ベンチのインストーラー、ユニット、ポート、ヘルパー
* [BENCH_TESTS](docs/BENCH_TESTS.md)：ベンチのテスト方法
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md)：バックアップと復元、Compose の TLS プロファイル
* [MQTT_TLS](docs/MQTT_TLS.md)：ブローカーの暗号化された入口（8 言語版あり）
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md)：ノードの証明書を信頼する（8 言語版あり）
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md)：VPN、家の名前とルーターを手順ごとに（8 言語版あり）
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md)：パッケージの署名（8 言語版あり）
* [機能マトリクス：何が証明され、何が証明されていないか](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [プロジェクトカタログ：バージョンと、リポジトリ同士の依存関係](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [このリポジトリの変更履歴](CHANGELOG.md)

## 🤝 コントリビュートとコミュニティ

* Pull Request の前に `python -I tools/armor_ci_validate.py` とテストを実行してください。どちらも通る必要があります。[CONTRIBUTING.md](CONTRIBUTING.md) と[行動規範](CODE_OF_CONDUCT.md)を参照してください。
* README は 8 言語で提供され、ARMOR-DOCS のソースから生成されます。文面の変更はそちらで行います。
* コンポーネント間のメッセージの変更は ARMOR-COMMON から始めます。
* ビルドしただけのものを、ボード上で動いているかのように書かないでください。
* 脆弱性は非公開で報告してください：[SECURITY.md](SECURITY.md)。質問、アイデア、報告：electrohobby3d@gmail.com（[SUPPORT.md](SUPPORT.md)）。

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 ライセンス

GPL-3.0-or-later - [LICENSE](LICENSE) を参照してください。
