# 在家外使用 A.R.M.O.R. - 分步指南

原则：**只开一个入口**，并且使用**名称而不是地址**。MQTT 代理和节点绝不向互联网公开。

也可以直接转发服务器的 18080 端口，但只能配合加固的公开模式 (`network.public_access`，默认关闭)：见 PUBLIC_ACCESS_zho.md。

## 1. 选择入口

* **A. VPN（推荐）**：在运行服务器的机器上安装 WireGuard 或 Tailscale。在外面时手机先加入 VPN，之后一切如同在家（包括每个节点的面板）。如果运营商不提供独立的公网地址（CGNAT），Tailscale 无需开放任何端口也能工作。
* **B. HTTPS**：在路由器的一个端口上放置带真实证书的反向代理（本仓库的 `tls` 配置）。任何浏览器都方便；请把策略设为“operate”，让管理操作只能在家里或通过 VPN 进行。

## 2. 跟随地址变化的名称

您的公网地址要么固定，要么偶尔变化。无论哪种，都请使用**名称**（DuckDNS、No-IP、路由器的动态 DNS 或自己的域名），并配合地址变化时更新它的工具（路由器的客户端，或机器上的 `ddclient`/DuckDNS 脚本）。TTL 设短一些（60 到 300 秒）。手机、Studio 和 VPN 始终使用名称。

## 3. 在路由器中

只向运行服务器的机器转发**一个**端口：B 用 `443/TCP`（若证书是真实的，还需 `80/TCP` 用于验证），A 的 WireGuard 用 `51820/UDP`。绝不要转发 `18883`、`8883` 或节点的端口。

## 4. 在服务器上（Docker）

在 `.env` 中：

```
ARMOR_TLS_HOST=casa.duckdns.org          # 您的名称
ARMOR_TLS_ISSUER=you@example.com         # 向 Let's Encrypt 申请证书并自动续期
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # 这样服务器才能看到每位访问者的真实地址
ARMOR_TOTP_REQUIRED=remote               # 从外部登录需要第二重验证（先在家中设置）
ARMOR_REMOTE_POLICY=operate              # 来自外部：查看并操作报警；管理只能在家中或通过 VPN
```

然后运行 `docker compose --profile tls up -d`。在 CM5 台架上，同样的设置位于 `armor.network.env`（Studio > 配置 > 安全会替您写入）。

## 5. 在 Studio 中

配置 > 安全：为每个账户启用第二重验证（验证器应用），保存恢复代码，并查看已打开的会话。管理员可设置受信任的代理、视为家庭的网络、策略以及来自外部的会话时长。

## 6. 在 Studio 中设置 VPN、域名和节点面板（无需命令）

安装好维护代理（`install_cm5.sh --with-maintenance`）并在本机装有 WireGuard（`sudo apt install wireguard-tools qrencode`）后，管理员可在 Studio > 配置 > 安全 > 从家外访问 中完成全部设置：

1. **VPN：** 填写手机要用的名称或地址（例如 `casa.duckdns.org`），保持端口和家庭网络不变，点击“设置 VPN”。它会告诉您要在路由器上把哪个 UDP 端口转发到本机。
2. **手机或笔记本：** 在“添加设备”中起个名字（`phone-ana`），点击“创建”，用 WireGuard 应用扫描二维码。二维码含私钥：用完请关闭，不要交给他人。以后可以再次显示，或移除该设备。
3. **跟随您家的域名：** 选择 DuckDNS、Cloudflare 或可调用的地址，填写数据，点击“保存并立即检查”。本机每五分钟检查一次，仅在地址变化时才调用服务商。
4. **从外部打开节点面板：** 登记节点（其 ID 和在家中的地址）。对使用 HTTPS 的节点，点击“查看其证书”，把指纹与节点自身面板（关于）中的比对，然后点击“信任此证书”。之后“打开面板”即可在家外通过服务器使用，节点不会被公开。

同样的事也可以在终端用 `armor_wireguard.sh` 和 `armor_ddns.sh` 完成（每个脚本开头列出了命令；`plan` 会在写入任何内容前显示将要写入的内容）。


**封禁反复失败的地址:** 安装 `fail2ban`(`sudo apt install fail2ban`)后,`sudo scripts/armor_fail2ban.sh setup` 会写入一个读取服务器审计日志中被拒绝的登录和被拒绝的第二因素验证码的过滤器,以及一个监狱规则(10 分钟内失败 5 次则封禁该地址一小时;数值在 `jail.d/armor-studio.local` 中)。用 `--ignoreip` 给出家中的网络,使其永不被封禁,并让服务器信任你的反向代理,这样日志中的地址才是访客的地址。`plan` 显示将要写入的内容;`status` 和 `remove` 如其名所示。

**复制到 USB 磁盘:** 仅当 `/mnt/usb` 是空间足够的已挂载磁盘时,`backup_data.sh --copy-to /mnt/usb --require-mount` 才会复制加密归档,因此拔掉的磁盘不会填满系统卡(见 `docs/BACKUP_AND_TLS.md`)。


## 7. 在手机上

A.R.M.O.R. Control：把名称作为服务器填入（`https://casa.duckdns.org`），登录（第二步会要求应用中的代码），并检查 更多 > 安全。

## 8. 检查

用**移动数据**的手机，在 Studio 或应用中点击“检查服务器如何看待我”：应显示**来自外部**以及您的真实地址。如果显示“来自家中”，说明代理没有传递地址：在信任任何东西之前，先修正 `ARMOR_TRUST_PROXY`。

## 绝不要

转发代理或节点的端口（哪怕“只一会儿”）；用地址代替名称；保留默认密码；让从外部登录的管理员跳过第二重验证。

关于使用住宅自有证书颁发机构的 HTTPS 以及如何将手机与之配对，见 `HTTPS_PAIRING_zho.md`。
