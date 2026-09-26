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
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### 部署拓扑与隔离的 CM5 测试台

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**诚实性检查 - 今天真正能运行的部分:** CM5 测试台安装程序已在一块真实的 CM5 上运行，这块 CM5 还托管着其他软件，它们一直保持正常。Docker Compose 拓扑及其可选的 TLS 配置已在 WSL 的 Docker Engine 中真实构建并运行（`scripts/test_compose.sh`，12 项检查，发现并修复了三处故障），但**没有在 Jetson 上**。备份和恢复脚本有一个通过的往返测试。

---

## 🎯 概述

* **核心主机的防火墙**（`scripts/firewall_core.sh`）：代理（broker）端口只允许现场网络访问，服务器和 Studio 的端口只允许客户端网络访问（如已指定），放在只提及这些端口、其余一概放行的独立表中；`apply --rollback-after` 会在未确认时自动移除规则，因此配置错误不会把你锁在外面。规则和拒绝情形已有测试（36 项，不会加载任何内容）；尚未在任何机器上加载，VLAN 本身仍是面向路由器和交换机的设计。
* **CM5 测试台：** `scripts/deploy_cm5.sh` 在干净的副本中构建，发送一个压缩包并运行 `scripts/install_cm5.sh`，后者创建自己的用户、自己的目录和两个使用各自端口的 systemd 单元（加 `--with-mqtt` 为三个：A.R.M.O.R. 自己的 Mosquitto，端口 18883，已在真实 CM5 上验证），带资源限制，且绝不触碰其他项目（[详情](docs/CM5_TEST_BENCH.md)）。
* **Compose 拓扑：** 非匿名的 Mosquitto 代理，每个节点一个身份；服务器；以及位于转发 `/api/` 的 nginx 之后的 Studio；只有 Studio 被发布，且仅在回环上。加固的容器、内部核心网络和用于保存状态的命名卷。
* **测试台代理上的设备与读数：** 服务器可以监听并控制 `armor/device/#`，并读取 `armor/node/+/info`、`armor/solar/#` 和 `armor/electrical/#`；`scripts/mqtt_identity.sh add device NAME` 为一个设备提供专属主题，`add bridge NAME` 为 Zigbee2MQTT 或 Shelly 桥接提供全部主题。 `scripts/mqtt_identity.sh electrical-switching NODE_ID on` 是唯一允许服务器控制电气节点开关的方式（默认关闭；`off` 可撤销）。
* **机密：** `scripts/generate_secrets.sh` 创建随机机密且不打印任何一个；`scripts/check-required-env.sh` 拒绝缺失、示例、过短或重复的值。
* **备份与恢复：** `scripts/backup_data.sh` 生成服务器数据的 AES-256 加密、已验证且带校验和的压缩包（除非要求，否则不含证据）；`scripts/restore_data.sh` 列出或恢复它，且绝不覆盖现有数据。摄像头密钥有意**不**放入压缩包。
* **TLS：** 可选的 `tls` Compose 配置在 Studio 前放置带自己本地证书颁发机构的 Caddy（[详情](docs/BACKUP_AND_TLS.md)）。

## 📂 仓库结构

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ 开发环境

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

* **[ARMOR-COMMON](../ARMOR-COMMON)** - 消息契约、验证器、一致性向量和生成的类型
* **[ARMOR-RADAR](../ARMOR-RADAR)** - 适用于 ESP32-S3 的现场节点固件，带三个雷达和自带网页面板
* **[ARMOR-SOLAR](../ARMOR-SOLAR)** - 太阳能逆变器与电池的协议，以及网关节点的消息
* **[ARMOR-ELECTRICAL](../ARMOR-ELECTRICAL)** - 电气节点：电表、电网读数消息和开关规则
* **[ARMOR-SERVER](../ARMOR-SERVER)** - 中央协调器：遥测、报警、设备、太阳能读数和摄像头
* **[ARMOR-STUDIO](../ARMOR-STUDIO)** - 网页控制台：摄像头、雷达、报警、太阳能和 2D/3D 场地设计器
* **[ARMOR-ANDROID-CONTROL](../ARMOR-ANDROID-CONTROL)** - 带实时 2D/3D 雷达的 Android 操作员客户端
* **[ARMOR-SERVER-AI](../ARMOR-SERVER-AI)** - 会解释决策且从不执行动作的视觉推理策略
* **[ARMOR-VOICE-AI](../ARMOR-VOICE-AI)** - 带无法伪造确认的离线语音意图
* **[ARMOR-HARDWARE](../ARMOR-HARDWARE)** - 外壳、电子器件和台架验收矩阵
* **ARMOR-DEVOPS** (本仓库) - 部署、CM5 测试台、备份与 TLS
* **[ARMOR-SIMULATOR](../ARMOR-SIMULATOR)** - 带可重复故障的离线遥测模拟器
* **[ARMOR-DOCS](../ARMOR-DOCS)** - 架构、安全基线和能力矩阵

## 📚 文档与社区

更多阅读：

* [能力矩阵：哪些已被证实，哪些没有](../ARMOR-DOCS/docs/CAPABILITY_MATRIX.md)
* [项目目录：版本以及各仓库之间的依赖](../ARMOR-DOCS/docs/PROJECT_CATALOG.md)
* [本仓库的变更记录](CHANGELOG.md)
* [许可证（GPL-3.0-or-later）](LICENSE)
* 问题、想法与反馈：electrohobby3d@gmail.com

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 许可证

GPL-3.0-or-later - 见 [LICENSE](LICENSE)。
