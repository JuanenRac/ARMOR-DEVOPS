# 为本地网络中机器地址签发的证书

这是通往手机或浏览器信任的 `https://192.168.0.180` 的方法：使用安装自己的证书颁发机构，不需要公共 DNS 中的任何名称。它是**可选的，默认关闭**：`tls` 配置（使用域名，Caddy 自带的颁发机构，见 HTTPS_PAIRING.md）和 `lan-ca` 配置保持原样工作。服务器的 18080 端口**绝不会向互联网开放**：只能从本地网络或通过 VPN 访问，本指南中的任何内容都不会改变这一点。

## 它会生成什么

`scripts/armor_lan_cert.py` 只做一次：生成一个**本地证书颁发机构**，并为你给定的地址生成由该机构签名的**第二张证书**：

* `~/.armor/lan-ca/ca.crt`：颁发机构的证书（公开：安装到手机和电脑上的就是它）。
* `~/.armor/lan-ca/ca.key`：颁发机构的私钥。它留在该文件夹中（目录权限 0700，密钥 0600），从不打印，程序从不复制，也从不进入任何仓库或软件包。
* `leaf.crt`、`leaf.key`、`fullchain.pem`：该地址的证书（一个私有 IPv4 地址，加上你添加的 `.lan` / `.local` 名称，以及 127.0.0.1）及其密钥。

颁发机构受其自身证书中的名称约束限制：它只能为私有地址和 `.lan` / `.local` 名称作保，因此即使私钥副本被盗，也无法在信任它的设备面前冒充互联网上的网站。程序会拒绝公共地址。

## 步骤

1. **先看一看。** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` 会说明将生成什么，不会改动任何东西。
2. **开启并生成。** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`。没有 `--enable`（或 `~/.armor/lan-ca/lan-ca.json` 中的 `"enabled": true`）它会拒绝：默认是关闭。再次运行时，只要地址不变且剩余有效期超过 `renew_days` 天，就会保留颁发机构和证书；如果地址改变，则用同一个颁发机构生成新证书，因此无需改动设备。
3. **把证书交给代理。** 使用变体 `caddy/Caddyfile.lan-issued`，它提供 `/lan-certs/leaf.crt` 和 `/lan-certs/leaf.key`：`ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`。该文件夹以只读方式挂载；没有这两个变量时，代理继续使用 Caddy 自带的颁发机构。
4. **在每台设备上安装一次颁发机构。** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` 会写出公开证书。Android：设置 > 安全 > 加密与凭据 > 安装证书 > CA 证书。iPhone：打开文件，安装描述文件，然后到 设置 > 通用 > 关于本机 > 证书信任设置 中开启。Windows：双击并安装到“受信任的根证书颁发机构”。Linux：复制到 `/usr/local/share/ca-certificates/` 并运行 `update-ca-certificates`。
5. **检查。** `python3 scripts/armor_lan_cert.py fingerprint` 会打印颁发机构的 SHA-256（壁挂面板所固定的值）；加上 `--spki` 则打印其公钥的指纹（手机应用所固定的值）。信任之前，请与设备显示的内容比对。

## 设置文件

`~/.armor/lan-ca/lan-ca.json`（全部可选；超出范围或未知的值是错误，绝不猜测）：`enabled`（false）、`ca_days`（3650）、`leaf_days`（397；对某些证书，浏览器和手机会拒绝超过 398 天的有效期）、`renew_days`（30）、`curve`（`prime256v1` 或 `secp384r1`）和 `name_constraints`（true）。`ARMOR_LAN_CA_DIR` 可移动该文件夹。

## 需要了解

* 持有 `ca.key` 的人可以为私有地址签发被信任该颁发机构的设备接受的证书：请独自保管该文件夹，像对待其他机密一样备份，切勿放入仓库。
* `remove` 会把文件夹搁置一旁（`lan-ca.removed-<时间>`）；不会删除任何东西。安装过旧颁发机构的设备应将其移除。
* 以上内容尚未在 CM5 上运行过：测试用 openssl 在一次性文件夹中生成颁发机构和证书，并检查证书链对该地址有效、对其他地址无效。
