# 加密与代理(broker)的连接(基于 TLS 的 MQTT) - 可选,分步说明

语言: [English](MQTT_TLS.md) · [Español](MQTT_TLS_spa.md) · [Deutsch](MQTT_TLS_deu.md) · [Français](MQTT_TLS_fra.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [Português](MQTT_TLS_por.md)

**默认是关闭的。** 目前节点在家庭网络中通过未加密的 MQTT(端口 `18883`)与代理通信,不按本指南操作就不会有任何变化。开启后会在普通端口旁边增加**第二个入口**(`8883`,TLS);普通端口会一直保留,直到您决定移除它。

证书不来自互联网:安装会在运行代理的机器上创建**自己的证书颁发机构**。被设置为使用 `mqtts://` 的节点(或服务器)**只信任这一个机构**,并检查代理的证书是否是为其所连接的名称或地址签发的。其他一切——另一个机构、为另一个地址签发的证书——都会被拒绝。

## 1. 在运行代理的机器上

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # 显示将要做的事;不改变任何内容
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* 证书为这台机器的名称和地址(主机名、`localhost`、`127.0.0.1`、它的 IPv4 地址)以及您给出的每个 `--name` 和 `--ip` 担保。**节点连接其中之一**(`mqtts://192.168.0.180:8883`):请给出节点将要使用的地址。
* **证书颁发机构的私钥**在机器上生成,保存在 `etc/mqtt-ca`(文件夹 `0700`,密钥 `0600`,仅 root)。它从不进入代码仓库,从不放在代理旁边,也从不离开这台机器。代理只会得到它自己的密钥。
* `setup` 会重启代理(新的监听器需要重启):节点会在几秒内重新连接。未加密的端口不受影响。
* 再次运行 `setup` 不会改变仍然有效的内容。当地址变化或有效期不足 30 天时(代理证书有效期两年),它会用**同一个机构签发新的代理证书**。因为机构不变,**无需改动节点**。机构的有效期为十年。
* 如果使用了本仓库的主机防火墙,它只认识未加密的端口:请自行允许来自现场网络的 `8883/tcp`。

## 2. 在每个节点上

打开节点的面板,**代理**页面:

1. 将地址写成 `mqtts://192.168.0.180:8883`(必须是证书所担保的地址之一)。
2. 勾选**加密与代理的连接 (TLS)**。
3. 把证书颁发机构的证书粘贴到框中。用 `sudo scripts/armor_mqtt_tls.sh export-ca` 获取(它是公开的:从 `-----BEGIN CERTIFICATE-----` 到 `-----END CERTIFICATE-----` 的一个块,约 600 字节;最大 2 KB)。不是单个 PEM 证书的内容会被拒绝。
4. 保存并重启。

节点在代理上的账户(用户名和密码)不变。开启加密后,由于证书有有效期,节点会等到时间正确后再连接(最长两分钟)。开关开启期间,已保存的备用代理也必须使用 `mqtts://`,并用同一个机构验证。**关闭**(默认)时,节点的行为与以前完全相同。

## 3. 本机的服务器

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # 环境文件中的 ARMOR_MQTT_URL=mqtts://localhost:8883 和 ARMOR_MQTT_CA_FILE
sudo systemctl restart armor-server
```

手动设置:`ARMOR_MQTT_URL=mqtts://localhost:8883` 和 `ARMOR_MQTT_CA_FILE=/path/to/ca.pem`。如果文件不是有效证书,或者设置了 `ARMOR_MQTT_CA_FILE` 却使用 `mqtt://` 地址(连接仍未加密,而您却以为已加密),服务器会拒绝启动。Studio 在**配置 > 代理**中显示状态:连接是否已加密,以及机构的指纹,可与 `sudo scripts/armor_mqtt_tls.sh status` 对照。`server-tls off` 会回到未加密的端口。

## 4. 关闭

在每个节点取消勾选开关(并改回 `mqtt://` 地址),运行 `server-tls off`,然后运行 `sudo scripts/armor_mqtt_tls.sh remove`。不会删除任何东西:代理的文件和配置会被放到旧文件旁边,机构会被保留(`--forget-ca` 会把它也放到一边),这样以后再运行 `setup`,已经信任它的节点仍可继续使用。

## 它做什么,不做什么

* 它向节点和服务器加密并认证代理。它**不**要求节点提供自己的证书:节点仍然用自己的账户表明身份。
* 它保护家庭网络,防止有人监听或冒充代理。这并不是公开代理的理由:`8883` 绝不转发到互联网(见 `REMOTE_ACCESS.md`)。
* 已在计算机上用 OpenSSL 和 Mosquitto 2.0 验证(证书、第二个监听器、握手、只固定一个机构、拒绝其他机构和其他地址,以及服务器的连接)。**尚未在节点的电路板上验证**:握手会在微控制器上占用一些时间和内存。
