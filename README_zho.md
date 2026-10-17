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
  <img src="https://img.shields.io/badge/Version-0.5.3-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**诚实性检查 - 今天真正能运行的部分:** CM5 测试台的安装程序已在一台托管其他软件的真实 CM5 上运行过，其他软件保持正常，测试台日常运行着服务器、Studio、网络节点、观察和语音服务、代理以及下面两个助手；其组件已通过 Studio 从 GitHub 更新过。Docker Compose 拓扑及其可选的 TLS 配置已在 WSL 的 Docker Engine 中真实构建并运行（`scripts/test_compose.sh`），但**没有在 Jetson 上**。备份和恢复脚本有通过的往返测试，两个助手有自己的测试。**尚未**证明的是：在从未见过该项目的机器上全新安装，以及整个 Docker 拓扑在目标设备上运行。

---

## 📋 速览

| | |
|---|---|
| 版本 | `0.5.3` |
| 成熟度 | 可用 |
| 技术栈 | Docker Compose / Bash / YAML |
| 真实硬件 | 日常运行 CM5 测试台，在托管其他软件的真实 CM5 上；尚未在 Jetson 上 |

## 🎯 概述

* **CM5 测试台：**`scripts/deploy_cm5.sh` 在干净副本中构建，发送一个归档并运行 `scripts/install_cm5.sh`，它为服务器和 Studio 创建自己的用户、自己的目录和使用独立端口的 systemd 单元，并可通过选项加入 MQTT 代理、网络节点、观察服务、语音网关、管理代理、维护助手和每日备份。它从不触碰机器上运行的其他东西。
* **维护助手**（`armor_maintenance_agent.py`）：从 GitHub 更新安装自身的组件（下载发布包，检查其 SHA-256，并带回滚地替换）、操作系统更新和可选的 root 控制台，全部从 Studio 的*更新*标签页驱动；控制台除非开启否则关闭。
* **管理代理**（`armor_admin_agent.py`）：唯一有特权的部分，只有一份封闭的服务、设置文件和代理账户列表，因此 Studio 从不需要 root。
* **每个版本的包：**`scripts/package_component.py` 构建某个组件（Studio、服务器、网络、观察服务、语音网关、DevOps）的包，在旁边写入其 SHA-256，并作为 GitHub 发布版发布。
* **Compose 拓扑：**每个节点一个身份并带 ACL 的非匿名 Mosquitto 代理（包括报警节点和服务器告诉它们的 Zigbee 防区）、服务器，以及位于代理 `/api/` 的 nginx 之后的 Studio；只有 Studio 对外发布，且在回环上。加固的容器、固定的镜像、内部核心网络和用于状态的命名卷。
* **TLS：**可选的 `tls` Compose 配置在 Studio 前放置带自有本地证书颁发机构的 Caddy，并提供基于 TLS 的 Mosquitto 配置（[详情](docs/BACKUP_AND_TLS.md)）。
* **核心机器的主机防火墙**（`scripts/firewall_core.sh`）：代理端口只对现场网络开放，服务器和 Studio 端口只对客户端网络开放（如果给出），放在不提及其他任何内容的独立表中。
* **密钥：**`scripts/generate_secrets.sh` 创建随机密钥且不打印任何一个；`scripts/check-required-env.sh` 拒绝缺失、占位、过短或重复的值。
* **备份与恢复：**`scripts/backup_data.sh` 生成服务器数据的 AES-256 加密、经验证并带校验和的归档（除非要求否则不含证据）；`scripts/restore_data.sh` 列出或恢复它，且从不覆盖已有数据。

## 🧩 在 A.R.M.O.R. 中的角色

ARMOR-DEVOPS 是其他一切到达机器并保持最新的途径。它在 CM5 测试台上安装服务器、Studio、网络节点、观察和语音服务以及代理，制作 [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) 的*更新*标签页从 GitHub 安装的每个版本的包，并保存两个小助手，让 Studio 可以在不以 root 运行的情况下更新安装并管理其服务。

## 📂 仓库结构

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, tests of the agents, the backup, the firewall and the Compose topology
│   └── dist-packages/   the packages of each release (Studio, server, network, observation, voice, DevOps) with their SHA-256
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ 开发环境

**环境要求:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys

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
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - 适用于 ESP32-S3 的现场节点固件，带三个雷达和自带网页面板
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - 太阳能逆变器与电池的协议，以及网关节点的消息
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - 电气节点：电表、电网读数消息和开关规则
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - 报警节点与报警主机：防区、布防、延时、警笛和 PIN，有无服务器均可
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - 触摸面板：墙面屏幕上的系统状态、布防与确认，以及语音助手的所在
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - 本地网络：其设备、互联网以及变化
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - 中央协调器：遥测、报警、设备、太阳能读数和摄像头
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - 网页控制台：摄像头、雷达、报警、太阳能和 2D/3D 场地设计器
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - 带实时 2D/3D 雷达的 Android 操作员客户端
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
