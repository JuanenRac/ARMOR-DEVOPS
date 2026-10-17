# 在家外使用 A.R.M.O.R. - 分步指南

原则：**只开一个入口**，并且使用**名称而不是地址**。MQTT 代理和节点绝不向互联网公开。

## 1. 选择入口

* **A. VPN（推荐）**：在运行服务器的机器上安装 WireGuard 或 Tailscale。在外面时手机先加入 VPN，之后一切如同在家（包括每个节点的面板）。如果运营商不提供独立的公网地址（CGNAT），Tailscale 无需开放任何端口也能工作。
* **B. HTTPS**：在路由器的一个端口上放置带真实证书的反向代理（本仓库的 `tls` 配置）。任何浏览器都方便；请把策略设为“operate”，让管理操作只能在家里或通过 VPN 进行。

## 2. 跟随地址变化的名称

您的公网地址要么固定，要么偶尔变化。无论哪种，都请使用**名称**（DuckDNS、No-IP、路由器的动态 DNS 或自己的域名），并配合地址变化时更新它的工具（路由器的客户端，或机器上的 `ddclient`/DuckDNS 脚本）。TTL 设短一些（60 到 300 秒）。手机、Studio 和 VPN 始终使用名称。

## 3. 在路由器中

只向运行服务器的机器转发**一个**端口：B 用 `443/TCP`（若证书是真实的，还需 `80/TCP` 用于验证），A 的 WireGuard 用 `51820/UDP`。绝不要转发 `1883`、`8883` 或节点的端口。

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

## 6. 在手机上

A.R.M.O.R. Control：把名称作为服务器填入（`https://casa.duckdns.org`），登录（第二步会要求应用中的代码），并检查 更多 > 安全。

## 7. 检查

用**移动数据**的手机，在 Studio 或应用中点击“检查服务器如何看待我”：应显示**来自外部**以及您的真实地址。如果显示“来自家中”，说明代理没有传递地址：在信任任何东西之前，先修正 `ARMOR_TRUST_PROXY`。

## 绝不要

转发代理或节点的端口（哪怕“只一会儿”）；用地址代替名称；保留默认密码；让从外部登录的管理员跳过第二重验证。
