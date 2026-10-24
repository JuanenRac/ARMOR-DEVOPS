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
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.7-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**诚实性检查 - 今天真正能运行的部分:** CM5 测试台的安装程序已在一台托管其他软件的真实 CM5 上运行过，其他软件保持正常，测试台日常运行着服务器、Studio、网络节点、观察和语音服务、代理以及下面两个助手；其组件已通过 Studio 从 GitHub 更新过。Docker Compose 拓扑及其可选的 TLS 配置已在 WSL 的 Docker Engine 中真实构建并运行（`scripts/test_compose.sh`），但**没有在 Jetson 上**。备份和恢复脚本有通过的往返测试，两个助手有自己的测试。**尚未**证明的是：在从未见过该项目的机器上全新安装，以及整个 Docker 拓扑在目标设备上运行。

---

## 📋 速览

| | |
|---|---|
| 版本 | `0.6.7` |
| 成熟度 | 成熟 |
| 技术栈 | Docker Compose / Bash / YAML |
| 真实硬件 | 日常运行 CM5 测试台，在托管其他软件的真实 CM5 上；尚未在 Jetson 上 |

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
* **可在 Studio 中设置的 VPN 和家的域名：** `armor_wireguard.sh` 用几条命令建立 WireGuard VPN（密钥保存在本机，每部手机一份带二维码的配置，需要时可路由到节点），`armor_ddns.sh` 在运营商更换地址时让 DuckDNS、Cloudflare 或其他域名始终指向您家；维护代理把两者提供给 Studio 和手机，无需任何人输入命令，并有八种语言的分步指南说明路由器设置。**签名软件包：** 维护助手只有在软件包带有项目发布密钥的有效 Ed25519 签名时，才会安装服务器、Studio 或其他程序的软件包（用纯 Python 验证，无需额外软件）；签名缺失、错误或被篡改时机器保持不变。紧急例外仅作为机器自身文件中的设置存在。
* **可选的通往代理的加密入口(基于 TLS 的 MQTT):** `scripts/armor_mqtt_tls.sh` 为本安装创建证书颁发机构(密钥留在本机,权限 `0600`)、为本机名称和地址签发代理证书,并在普通监听器旁增加 8883 的第二个 Mosquitto 监听器(绝不改动普通监听器);它是幂等的,提供 `status`、`export-ca`、`server-tls` 和 `remove`(文件被放到一边,绝不删除)。已用 OpenSSL(含真实握手)和真实的 Mosquitto 2.0 测试([指南](docs/MQTT_TLS_zho.md))。
* **允许健康报告：** 代理规则允许每个节点写入自己的 `armor/health/<节点>`，并允许服务器读取 `armor/health/#`；`mqtt_identity.sh add` 为每种节点写入该行，`mqtt_identity.sh health-report <角色> <节点>` 把它加到此前安装的节点上（幂等，保留之前的规则）。
* **节点控制的代理规则：** 只有服务器的身份可以向 `armor/control/+/command`（包含 `armor/control/all/command`）发布；每个节点只读取自己的命令主题和广播主题，并只在 `armor/control/<节点>/result` 上写自己的应答，仅此而已，因此任何节点都不能指挥另一个节点，被盗的节点密码也无法重启其他节点。`mqtt_identity.sh node-control` 会给较早安装的节点补上这三行，ACL 测试会检查每一种节点。

## 🧩 在 A.R.M.O.R. 中的角色

ARMOR-DEVOPS 是其他一切到达机器并保持最新的途径。它在 CM5 测试台上安装服务器、Studio、网络节点、观察和语音服务以及代理，制作 [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) 的*更新*标签页从 GitHub 安装的每个版本的包，并保存两个小助手，让 Studio 可以在不以 root 运行的情况下更新安装并管理其服务。

## 📂 仓库结构

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example
├── mosquitto/ mosquitto.conf, mosquitto-tls.conf (the TLS profile), acl.example
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, armor_mqtt_tls (the optional encrypted door of the broker), armor_ddns, armor_wireguard, armor_tls_check (remote access), tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
├── tools/     the shared CI checks (armor_ci_validate.py, armor_project_tool.py, _armor_readme_parity.py)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (the last four also in eight languages)
```

## 🛠️ 开发环境

**环境要求:** 带 Compose 的 Docker Engine（用于容器拓扑）, CM5 或任何可通过 SSH 访问的基于 Debian 的机器（用于测试台）, 执行部署的机器上需要 Bash、`ssh` 和 `tar`

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

参见[部署边界](docs/DEPLOYMENT_BOUNDARY.md)。

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
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - 带无法伪造确认的离线语音意图
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - 外壳、电子器件和台架验收矩阵
* **ARMOR-DEVOPS** (本仓库) - 部署、CM5 测试台、备份与 TLS
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
