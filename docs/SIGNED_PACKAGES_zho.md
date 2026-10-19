# 签名软件包:机器如何决定安装什么

机器上的维护助手(`armor_maintenance_agent.py`)从 GitHub 上各仓库的发布版本更新 A.R.M.O.R. 的程序(`server`、`studio`、`network`、`ai`、`voice`、`devops`)。在解压任何内容之前,它会按以下顺序检查三件事:

1. **哈希:** 软件包的 SHA-256 必须与 `armor-<组件>-<版本>.tgz.sha256` 中的值一致。这样可以发现被截断的下载。
2. **签名:** `armor-<组件>-<版本>.tgz.sig` 中保存着下列文本的 Ed25519 签名(64 字节,即 128 个十六进制数字):

   `armor-pkg/1|<组件>|<版本>|<sha256>`

   签名由发布用的私钥生成。助手使用其代码中内置的公钥(`PACKAGE_PUBLIC_KEY`,与节点固件所信任的是同一把)进行验证。没有 `.sig`,或签名验证不通过的发布版本会被拒绝(`missing_signature`、`bad_signature`),系统保持不变:不会解压,也不会重启任何东西。
3. **压缩包:** 不允许绝对路径、`..`、链接或设备文件。

只能修改 GitHub 上发布内容的人(被盗的账号、发布工具中的恶意依赖)可以发布软件包及其哈希,但无法生成签名:私钥从不放在 GitHub 上。文本以 `armor-pkg/1` 开头,而不是固件使用的 `armor-fw/1`,因此固件签名永远不能冒充软件包签名;文本还包含组件和版本,所以已签名的软件包无法冒充其他程序或更新的版本。

验证使用纯 Python(RFC 8032)实现:机器上不需要 OpenSSL 或额外的模块。

## 发布

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

它会生成 `.tgz`、`.sha256` 和 `.sig` 并上传这三个文件。签名工具是 `~/.armor/sign.mjs`(或 `--signer` / `ARMOR_PACKAGE_SIGNER`),密钥从 `ARMOR_FIRMWARE_KEY` 或 `~/.armor/firmware_ed25519.pem` 读取。密钥绝不会复制到任何仓库。若缺少签名工具或密钥,`--sign` 会失败;不加该选项时,只要两者都在就会签名。不会使用助手不信任的其他密钥。`--publish` 拒绝上传未签名的软件包。

要为已经发布的软件包签名,请将它连同 `.sha256` 一起下载,然后运行:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

文件名决定组件和版本;`--upload` 会把 `.sig` 添加到其仓库的 `v<版本>` 发布中(需要 `gh`)。

## 紧急例外

如果必须安装没有签名的软件包(例如密钥丢失),请在机器的 `armor.maint.env`(位于 `$PREFIX/etc/`)中写入下面这一行,事后再删除:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

每次安装时都会从该文件读取,因此无法通过 HTTP API 或进程环境变量来设置。每次使用时,助手都会在任务日志和自己的日志中写入 `WARNING`,概览中会报告 `unsigned_allowed`。

## 更换密钥

生成新的密钥对,把新的公钥写入 `PACKAGE_PUBLIC_KEY` 和固件(`fw_trust.hpp`)。发布一个用**旧**密钥签名的 `devops` 软件包(机器安装它之后就会信任新密钥),之后的软件包再用新密钥签名。

## 测试

`scripts/test_maintenance_agent.py` 覆盖:有效签名、被篡改的软件包、缺失的 `.sig`、其他密钥的签名、乱码、例外(仅限来自该文件)、RFC 8032 测试向量,以及助手中的密钥与 `fw_trust.hpp` 中的一致。测试使用一次性密钥,绝不使用真实密钥。

打包工具会拒绝打包过期的构建:对于 `server` 和 `studio`,`package.json` 中的版本(Studio 还包括 `dist/version.json`)必须与 `armor.project.json` 一致,且 `dist/` 不能比其构建所用的源代码更旧。请先重新构建(`npm run build`)。
