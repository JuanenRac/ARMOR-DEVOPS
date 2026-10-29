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
  🇨🇳 <b>简体中文</b> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### 部署、CM5 测试台、来自 GitHub 的更新以及安装的维护

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**诚实性检查 - 今天真正能运行的部分：** CM5 测试台的安装程序已在一台托管其他软件的真实 CM5 上运行过，其他软件保持正常，测试台日常运行着服务器、Studio、网络节点、观察和语音服务、代理以及下面两个助手；其组件已通过 Studio 从 GitHub 更新过。Docker Compose 拓扑及其可选的 TLS 配置已在 WSL 的 Docker Engine 中真实构建并运行（`scripts/test_compose.sh`），但**没有在 Jetson 上**。备份和恢复脚本有通过的往返测试，两个助手有自己的测试。**尚未**证明的是：在从未见过该项目的机器上全新安装，以及整个 Docker 拓扑在目标设备上运行。

---

## 📋 速览

| | |
|---|---|
| 版本 | `0.6.8` |
| 成熟度 | 成熟 |
| 角色 | 部署工具包：CM5 测试台安装器、发布包、两个助手、Compose 拓扑 |
| 技术栈 | Bash、Python 3（标准库）、Docker Compose、Mosquitto、Caddy、nginx、systemd |
| 测试 | 每个部分都有测试脚本（`scripts/test_*.sh` 和 `test_*.py`）；Compose 拓扑在 WSL 的 Docker 中构建并运行 |
| 契约 | 测试台端口：服务器 18080、Studio 18081、MQTT 18883（绝不用 1883）、语音 18090 |
| 运行位置 | CM5 或可通过 SSH 访问的任何基于 Debian 的机器；容器拓扑需要带 Compose 的 Docker Engine |
| 真实硬件 | 日常运行 CM5 测试台，在托管其他软件的真实 CM5 上；尚未在 Jetson 上 |
| 许可证 | GPL-3.0-or-later |

**跳转到：** [概述](#-概述) · [架构](#-架构) · [安全](#-安全与防护) · [接口](#-接口) · [配置](#-配置) · [快速开始](#-快速开始) · [测试](#-测试) · [故障排除](#-故障排除) · [结构](#-仓库结构) · [相关项目](#-相关项目)

## 🚦 项目状态

每一行是本仓库的一个部分，灯号表示它今天做到了哪一步。内容依据仓库能够展示的证据（测试、构建、运行），而不是计划。

🟢 已完成并验证 · 🟡 可用，有已知限制 · 🟠 部分完成或尚未验证 · 🔴 未完成或不可用

| 领域 | 状态 | 在这里的含义 |
|---|---|---|
| 软件 | 🟡 | CM5 测试台安装程序已在一台承载其他软件的真实 CM5 上运行，其他软件保持正常；在从未接触过本项目的干净机器上安装尚未证明。 |
| 测试 | 🟡 | 备份与恢复脚本有通过的往返测试，两个辅助程序有各自的测试，带可选 TLS 配置的 Docker 拓扑已在 WSL 的 Docker Engine 中构建并运行；完整拓扑尚未在目标设备上运行。 |
| 硬件 | 🟡 | 它在日常使用中运行 CM5 测试台；还没有在 Jetson 上运行过。 |
| 更新 | 🟢 | 已在 CM5 测试台上通过 Studio 完成了从 GitHub 更新各组件。 |
| 文档 | 🟢 | 八种语言和更新日志均为最新。 |

## 🎯 概述

* **CM5 测试台：**`scripts/deploy_cm5.sh` 在干净副本中构建，发送一个归档并运行 `scripts/install_cm5.sh`，它为服务器和 Studio 创建自己的用户、自己的目录和使用独立端口的 systemd 单元，并可通过选项加入 MQTT 代理、网络节点、观察服务、语音网关、管理代理、维护助手和每日备份。它从不触碰机器上运行的其他东西。
* **维护助手**（`armor_maintenance_agent.py`）：从 GitHub 更新安装自身的组件（下载发布包，检查其 SHA-256，并带回滚地替换）、操作系统更新和可选的 root 控制台，全部从 Studio 的*更新*标签页驱动；控制台除非开启否则关闭。它保留最新的六份备份，磁盘接近写满时则更少（设置文件中的 `ARMOR_MAINT_MIN_FREE_MB`：默认 500，0 表示关闭）。
* **管理代理**（`armor_admin_agent.py`）：唯一有特权的部分，只有一份封闭的服务、设置文件和代理账户列表，因此 Studio 从不需要 root。
* **每个版本的包：**`scripts/package_component.py` 构建某个组件（Studio、服务器、网络、观察服务、语音网关、DevOps）的包，在旁边写入其 SHA-256，并作为 GitHub 发布版发布。
* **Compose 拓扑：**每个节点一个身份并带 ACL 的非匿名 Mosquitto 代理（包括报警节点和服务器告诉它们的 Zigbee 防区）、服务器，以及位于代理 `/api/` 的 nginx 之后的 Studio；只有 Studio 对外发布，且在回环上。加固的容器、固定的镜像、内部核心网络和用于状态的命名卷。
* **TLS：**可选的 `tls` Compose 配置在 Studio 前放置带自有本地证书颁发机构的 Caddy，并提供基于 TLS 的 Mosquitto 配置（[详情](docs/BACKUP_AND_TLS.md)）。
* **核心机器的主机防火墙**（`scripts/firewall_core.sh`）：代理端口只对现场网络开放，服务器和 Studio 端口只对客户端网络开放（如果给出），放在不提及其他任何内容的独立表中。
* **密钥：**`scripts/generate_secrets.sh` 创建随机密钥且不打印任何一个；`scripts/check-required-env.sh` 拒绝缺失、占位、过短或重复的值。
* **备份与恢复：**`scripts/backup_data.sh` 生成服务器数据的 AES-256 加密、经验证并带校验和的归档（除非要求否则不含证据）；`scripts/restore_data.sh` 列出或恢复它，且从不覆盖已有数据。
* **可在 Studio 中设置的 VPN 和家的域名：** `armor_wireguard.sh` 用几条命令建立 WireGuard VPN（密钥保存在本机，每部手机一份带二维码的配置，需要时可路由到节点），`armor_ddns.sh` 在运营商更换地址时让 DuckDNS、Cloudflare 或其他域名始终指向您家；维护代理把两者提供给 Studio 和手机，无需任何人输入命令，并有八种语言的分步指南说明路由器设置。
* **签名软件包：** 维护助手只有在软件包带有项目发布密钥的有效 Ed25519 签名时，才会安装服务器、Studio 或其他程序的软件包（用纯 Python 验证，无需额外软件）；签名缺失、错误或被篡改时机器保持不变。紧急例外仅作为机器自身文件中的设置存在。
* **可选的通往代理的加密入口(基于 TLS 的 MQTT):** `scripts/armor_mqtt_tls.sh` 为本安装创建证书颁发机构(密钥留在本机,权限 `0600`)、为本机名称和地址签发代理证书,并在普通监听器旁增加 8883 的第二个 Mosquitto 监听器(绝不改动普通监听器);它是幂等的,提供 `status`、`export-ca`、`server-tls` 和 `remove`(文件被放到一边,绝不删除)。已用 OpenSSL(含真实握手)和真实的 Mosquitto 2.0 测试([指南](docs/MQTT_TLS_zho.md))。
* **允许健康报告：** 代理规则允许每个节点写入自己的 `armor/health/<节点>`，并允许服务器读取 `armor/health/#`；`mqtt_identity.sh add` 为每种节点写入该行，`mqtt_identity.sh health-report <角色> <节点>` 把它加到此前安装的节点上（幂等，保留之前的规则）。
* **节点控制的代理规则：** 只有服务器的身份可以向 `armor/control/+/command`（包含 `armor/control/all/command`）发布；每个节点只读取自己的命令主题和广播主题，并只在 `armor/control/<节点>/result` 上写自己的应答，仅此而已，因此任何节点都不能指挥另一个节点，被盗的节点密码也无法重启其他节点。`mqtt_identity.sh node-control` 会给较早安装的节点补上这三行，ACL 测试会检查每一种节点。

## 🧩 在 A.R.M.O.R. 中的角色

ARMOR-DEVOPS 是其他一切到达机器并保持最新的途径。它在 CM5 测试台上安装服务器、Studio、网络节点、观察和语音服务以及代理，制作 [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) 的*更新*标签页从 GitHub 安装的每个版本的包，并保存两个小助手，让 Studio 可以在不以 root 运行的情况下更新安装并管理其服务。

| 对话对象 | 方式 | 用途 |
|---|---|---|
| ARMOR-STUDIO | 其“更新”标签页通过本地套接字请求维护助手 | 从不需要 root |
| GitHub Releases | `package_component.py` 发布带 SHA-256 和签名的包 | 要安装的组件 |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | 安装为各自的 systemd 单元 | 测试台的服务 |
| ARMOR-UPDATER | 另一套 | 在 PC 上保存家族副本的人使用的工具；本仓库面向 CM5 和 Compose 拓扑 |

## 🏛️ 架构

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 安全与防护

| 威胁 | 防御 |
|---|---|
| 干扰 CM5 上的其他软件 | 专用的用户、目录和端口（服务器 18080、Studio 18081、MQTT 18883、语音 18090，均在 1024 到 65535 之间且互不相同，绝不用标准的 1883）；不触碰系统防火墙 |
| 开放或未认证的代理 | `allow_anonymous false`、密码文件和 ACL（密钥挂载在 `/run/secrets`），每个节点一个身份；只有服务器能发布 `armor/control/+/command`；每个节点读取自己的命令和广播命令，只写自己的 `armor/control/<节点>/result` 和 `armor/health/<节点>`；服务器读取 `armor/health/#` |
| 意外在网络上监听 | 除非 `ARMOR_MQTT_BIND`、`ARMOR_STUDIO_BIND`（Caddy 为 `ARMOR_TLS_BIND`）另有设置，Compose 只在 `127.0.0.1` 上发布代理和 Studio |
| 明文的 MQTT 与 Studio | 可选：在明文监听旁再加一个 8883 的 Mosquitto 监听（`armor_mqtt_tls.sh`：专用机构、`0600` 权限的密钥、面向本机名称的证书、幂等、从不触碰明文监听）以及带 Caddy 和本地机构的 Compose `tls` 配置 |
| 核心机器向所有人开放 | `firewall_core.sh` 写入专用表（`/etc/armor/firewall.nft`，附带回滚单元）：代理端口只对现场网络开放，服务器和 Studio 端口只对客户端网络开放；`check` 用 `nft -c` 校验 |
| 弱密钥或被打印的密钥 | `generate_secrets.sh` 生成随机密钥且不打印任何一个；`check-required-env.sh` 拒绝缺失、占位、过短或重复的值 |
| 被盗的备份 | `backup_data.sh` 生成 AES-256 加密、已校验并带校验和的归档（除非要求，否则不含证据）；`restore_data.sh` 列出或恢复，且从不覆盖已有数据 |
| 组件的伪造更新 | 维护助手下载发布包，检查其 SHA-256 和项目发布密钥的 Ed25519 签名（用纯 Python 验证），并带回滚地替换；签名缺失、错误或被篡改时，机器保持不变 |
| Studio 可触及 root | 从不需要：管理代理（`armor_admin_agent.py`）只处理封闭列表中的服务、设置文件和代理账户；维护助手的 root 控制台除非开启否则关闭 |

容器经过加固，镜像已固定，`core` 网络为内部网络，状态保存在命名卷中。两个助手使用本地 Unix 套接字，因此其测试需要 Linux。在从未见过该项目的机器上的全新安装，以及整个 Docker 拓扑在目标上的运行都未验证；也没有独立审查。

## 🔌 接口

| 路由 | 认证 | 作用 |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | 在干净副本中构建，通过 SSH 发送一个归档并运行 `install_cm5.sh` |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | 创建用户、目录和 systemd 单元；可用 `--server-port`、`--studio-port`、`--mqtt-port`、`--also-reach` 调整；没有 `--apply` 只显示计划 |
| `scripts/package_component.py` | - | 按维护助手的安装方式打包 Studio、服务器、网络节点、观察服务、语音网关或 DevOps，写出其 SHA-256 并作为 GitHub 发布版本发布 |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` 与 `secrets/`（Git 忽略）；检查会拒绝缺失、占位、过短或重复的值 |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | 服务器数据的加密并已校验的归档 |
| `scripts/restore_data.sh` | - | 列出归档或在不覆盖已有数据的情况下恢复 |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | 核心机器的防火墙表；`check` 校验它（未安装 `nft` 时为 `FIREWALL_CHECK=SKIP`） |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | 写入每种节点的代理条目；给早先安装的节点补上健康报告和控制（幂等） |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | 代理的加密入口（`status`、`export-ca`、`server-tls` 等）、每部手机一个二维码的 WireGuard VPN、家的 DuckDNS、Cloudflare 或其他域名，以及远程访问检查；Studio 无需输入命令即可提供 |

两个助手（`armor_admin_agent.py`、`armor_maintenance_agent.py`）监听本地 Unix 套接字，因此不能在 Windows 上运行。Compose 文件启动代理（Mosquitto）、服务器和 Studio（转发 `/api/` 的 nginx），`tls` 配置再加入 Caddy；只发布 Studio，默认在回环地址上（`127.0.0.1:8088`，TLS 在 8443）。每个版本的包是 GitHub 发布版本的附件，不是本仓库的文件。

## ⚙️ 配置

| 设置 | 默认值 | 作用 |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`、`--studio-port`、`--mqtt-port`（不重复指定则保留已安装的）和语音端口；均在 1024 到 65535 之间且互不相同；代理地址写入 `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | Compose 发布代理和 Studio 的位置 |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | 访问 Studio 所用的来源 |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | `tls` 配置的 Caddy |
| `.env`  `.env.example` | - | 由 `generate_secrets.sh` 创建，Git 忽略；示例列出每个变量 |

维护助手的 root 控制台是机器自身文件中的设置，默认关闭；防火墙和 TLS 是安装器的选项而非默认值。详见 [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md)。

## 🚀 快速开始

**要求：** 带 Compose 的 Docker Engine（容器拓扑用）、CM5 或可通过 SSH 访问的基于 Debian 的机器（测试台用）、执行部署的机器上的 Bash、`ssh` 和 `tar`。

```bash
scripts/generate_secrets.sh                                                            # `.env` 与 `secrets/`（Git 忽略）
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # 容器拓扑
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # 测试台
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # 加密备份
```

请参阅[部署边界](docs/DEPLOYMENT_BOUNDARY.md)和[测试台](docs/CM5_TEST_BENCH.md)。

## 🧪 测试

| 领域 | 覆盖内容 |
|---|---|
| `test_admin_agent.py`  `.sh` | 管理代理的封闭列表（需要 Linux：Unix 套接字） |
| `test_maintenance_agent.py`  `.sh` | 维护助手：下载、SHA-256、签名、替换和回滚（需要 Linux） |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | 包、组件列表和远程访问助手 |
| `test_backup.sh`  `test_env_and_restore.sh` | 备份与恢复的往返、密钥和环境检查 |
| `test_compose.sh`  `validate-compose.sh` | Compose 拓扑及其 TLS 配置，在 WSL 的 Docker Engine 中构建并运行 |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | 防火墙、安装器的计划、代理身份、TLS 上的 MQTT、TLS 检查、VPN 和动态域名 |

Python 测试用 `python -m unittest discover -s scripts -p "test_*.py"` 运行；在 Windows 上需要 Unix 套接字的三项无法运行。脚本需要 Bash、WSL、Docker 或 root，须在 Linux 上运行。目前还没有统一的测试数量：Project status 说明已运行的内容。GitHub Actions 在每次推送和拉取请求时运行 A.R.M.O.R. 基线：清单、版本、更新日志和 README 一致性的校验，然后是项目自身的构建和测试。

## 🏗️ 构建与发布

不需要编译：这里只有脚本、一个 Compose 文件和 Python 助手。`scripts/package_component.py` 构建组件的包并在旁边写出其 SHA-256；这些包是 GitHub 发布版本的附件，不是本仓库的文件。版本记录在 `armor.project.json` 和 README 徽章中（读取自清单）；每个版本在 [CHANGELOG.md](CHANGELOG.md) 中都有对应条目。

## 🩺 故障排除

| 你看到 | 原因 | 处理 |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | `install_cm5.sh` 的某个端口超出范围或重复 | 使用 1024 到 65535 之间互不相同的端口（绝不用标准的 1883） |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | 额外地址没有写成“Studio 地址 = 服务器地址” | 写成 `--also-reach http://<主机>:<Studio 端口>=http://<主机>:<服务器端口>` |
| `FIREWALL_CHECK=SKIP nft is not installed here` | 缺少 `nft`，`firewall_core.sh check` 无法校验该表 | 在机器上安装 nftables 后重新检查 |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | 在 Windows 上运行了两个助手的测试 | 在 Linux（或 WSL）上运行 |

## 📂 仓库结构

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>目录树的文本版本</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      部署到测试台并安装
│   ├── package_component.py                              每个版本的包
│   ├── armor_admin_agent.py armor_maintenance_agent.py   Studio 的两个助手
│   ├── generate_secrets.sh check-required-env.sh         随机密钥；拒绝弱密钥
│   ├── backup_data.sh restore_data.sh                    加密备份与恢复
│   ├── firewall_core.sh mqtt_identity.sh                 防火墙与代理身份
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              TLS 上的 MQTT 及其检查
│   ├── armor_ddns.sh armor_wireguard.sh                  房子的域名和 VPN
│   └── test_*.py test_*.sh validate-compose.sh           助手与脚本的测试
├── docker-compose.yml docker-compose.tls.yml             代理、服务器、Studio；TLS 配置
├── mosquitto/                                            mosquitto.conf、TLS 配置、acl.example
├── caddy/                                                Caddyfile：Studio 前的 HTTPS
├── docs/                                                 DEPLOYMENT_BOUNDARY、CM5_TEST_BENCH、BENCH_TESTS、BACKUP_AND_TLS、MQTT_TLS、HTTPS_PAIRING、REMOTE_ACCESS、SIGNED_PACKAGES（后四篇另有八种语言版）
├── tools/                                                共用的 CI 检查和工具
├── images/                                               横幅图、图标和 README 的图片
├── .github/                                              CI 工作流、仪表板通知、议题和 pull request 模板
├── armor.project.json                                    清单：版本、角色、成熟度
├── CHANGELOG.md                                          每个版本的变化
├── run.sh run.bat                                        启动（共用流程）
├── build.sh build.bat                                    构建并测试（共用流程）
├── build-test.sh build-test.bat                          构建、测试并打包
├── test.sh test.bat                                      只运行测试，不改版本
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ 路线图与已知限制

**当前已知限制**

* 在从未见过该项目的机器上的全新安装尚未验证。
* 整个 Docker 拓扑已在 WSL 的 Docker Engine 中构建并运行，但没有在目标 Jetson 上运行。
* 没有统一的测试数量，两个助手的测试需要 Linux。
* 没有独立的安全审查。

**下一步**

* 在新机器上全新安装，并在 Jetson 上运行 Docker 拓扑。

## 🌍 语言

README 和文本提供英语、西班牙语、法语、意大利语、德语、汉语、日语和欧洲葡萄牙语版本。

## 🔗 相关项目

**A.R.M.O.R.**（Autonomous Radar & Multimodal Observation Range）是一个由相互独立的仓库组成的周界安全系统。每个仓库都有自己的版本、自己的测试和自己的 README；这是整个系列：

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - 消息契约、验证器、一致性向量和生成的类型
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - 面向 ESP32-S3 的现场节点固件，配三个雷达和自带的网页面板
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - 太阳能逆变器和电池的协议，以及网关节点的消息
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - 电气节点：电表、电网读数的消息和切换规则
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - 报警节点与面板：防区、布防、延时、警笛和 PIN，可配合服务器也可独立使用
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - 触摸面板：壁挂屏幕上的系统状态、布防与确认，以及语音助手的所在
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - 本地网络：其设备、互联网以及变化
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - 中央协调器：遥测、报警、设备、太阳能读数和摄像头
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - 网页控制台：摄像头、雷达、报警、太阳能以及 2D/3D 场地设计器
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - 带实时 2D/3D 雷达的 Android 操作员客户端
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone 操作员客户端
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - 视觉推理策略，会解释其决策且从不驱动设备
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - 面向 Jetson Orin NX 的摄像头区域、遮罩和检测规则
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - 离线语音意图，附带无法伪造的确认
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 外壳、电子器件和台架验收矩阵
* **ARMOR-DEVOPS**（本仓库） - 部署、CM5 测试台、备份和 TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - 带可重复故障的离线遥测模拟器
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - 检测、安装和更新生态系统自身的仓库
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - 架构、安全基线和能力矩阵

## 📚 文档

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md)：本仓库部署什么、不部署什么
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md)：测试台上的安装器、单元、端口和助手
* [BENCH_TESTS](docs/BENCH_TESTS.md)：测试台如何测试
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md)：备份与恢复以及 Compose 的 TLS 配置
* [MQTT_TLS](docs/MQTT_TLS.md)：代理的加密入口（另有八种语言版）
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md)：信任节点的证书（另有八种语言版）
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md)：VPN、房子的域名和路由器，一步一步（另有八种语言版）
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md)：包的签名（另有八种语言版）
* [能力矩阵：哪些已被证明，哪些没有](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [项目目录：版本以及各仓库之间如何相互依赖](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [本仓库的更新日志](CHANGELOG.md)

## 🤝 参与贡献与社区

* 提交 pull request 之前，请运行 `python -I tools/armor_ci_validate.py` 和测试：两者都必须通过。请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 和[行为准则](CODE_OF_CONDUCT.md)。
* README 提供八种语言，由 ARMOR-DOCS 中的源文件生成：文本的修改在那里进行。
* 组件之间消息的变更从 ARMOR-COMMON 开始。
* 不要把仅仅构建过的东西描述为已在板子上运行。
* 请私下报告漏洞：[SECURITY.md](SECURITY.md)。问题、想法和报告：electrohobby3d@gmail.com（[SUPPORT.md](SUPPORT.md)）。

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 许可证

GPL-3.0-or-later - 见 [LICENSE](LICENSE)。
