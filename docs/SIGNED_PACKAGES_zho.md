# 签名软件包:机器如何决定安装什么

机器上的维护助手(`armor_maintenance_agent.py`)从 GitHub 上各仓库的发布版本更新 A.R.M.O.R. 的程序(`server`、`studio`、`network`、`ai`、`voice`、`devops`)。在解压任何内容之前,它会按以下顺序检查三件事:

1. **哈希:** 软件包的 SHA-256 必须与 `armor-<组件>-<版本>.tgz.sha256` 中的值一致。这样可以发现被截断的下载。
2. **签名：** `armor-<组件>-<版本>.tgz.sig2` 中是清单的 Ed25519 签名（64 字节，即 128 位十六进制数字）：

   `armor-fw/1|<组件>|package|<版本>|<sha256>`

   签名使用发布的私钥（与为节点固件签名的是同一把）。它与固件镜像使用同一种清单，只是在电路板的位置写 `package`。助手用写在其代码中的公钥（`PACKAGE_PUBLIC_KEY`）验证，在更换密钥期间还会用第二把公钥（见下文）。没有 `.sig2` 或验证不通过的发布会被拒绝（`missing_signature`、`bad_signature`），系统保持不变：不解压任何东西，不重启任何东西。
3. **压缩包:** 不允许绝对路径、`..`、链接或设备文件。

只能修改 GitHub 上发布内容的人（被盗的账号、发布工具中的恶意依赖）可以发布软件包及其哈希，但无法生成签名：私钥从不放在 GitHub 上。清单把签名与组件和版本绑定在一起，因此过去的已签名软件包或其他组件的软件包不能冒充最新版本，固件镜像的签名（另一个项目、真实的电路板）也永远不能当作软件包签名。旧的 `.sig`（文本 `armor-pkg/1|<组件>|<版本>|<sha256>`）不再足够：只有当机器的 `armor.maint.env` 写有 `ARMOR_MAINT_SIGNATURE=either` 时才会接受，用于给之前已发布的软件包补签的这段时间。

验证使用纯 Python(RFC 8032)实现:机器上不需要 OpenSSL 或额外的模块。

## 发布

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

它会写出 `.tgz`、`.sha256`、`.sig2`（清单）和 `.sig`（旧文本，尚未更新的助手仍会检查），并上传它们。签名工具是 `~/.armor/sign.mjs`（或 `--signer` / `ARMOR_PACKAGE_SIGNER`）；它从 `ARMOR_FIRMWARE_KEY` 或 `~/.armor/firmware_ed25519.pem` 读取密钥。密钥绝不会复制到任何仓库。没有签名工具或密钥时 `--sign` 会失败；不加该选项时，二者齐备才会签名。助手不信任的密钥绝不会被使用。`--publish` 拒绝上传未签名的软件包。

要为已经发布的软件包签名,请将它连同 `.sha256` 一起下载,然后运行:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

文件名给出组件和版本；`--upload` 会把 `.sig2` 和 `.sig` 添加到其仓库的发布 `v<版本>`（需要 `gh`）。

## 通过 GitHub Actions 发布

本仓库的软件包由工作流 `package-build.yml` 构建(手动启动,`dry_run` 默认开启):在两台运行器上各打包一次 `devops` 包的脚本,若两个包不是逐字节相同则停止,并上传 `armor-devops-<版本>.tgz`、`SHA256SUMS` 和构建证明。它不持有任何密钥。要在维护者的机器上用一次成功运行的产物签名并发布版本:

```
gh attestation verify armor-devops-<version>.tgz --repo JuanenRac/ARMOR-DEVOPS
python scripts/package_component.py --sign-existing armor-devops-<version>.tgz --upload
```

发布版本随后包含维护助手所需的 `armor-devops-<版本>.tgz`、`.sha256`、`.sig` 和 `.sig2`;缺少它们的发布会让机器报告该仓库没有发布。

## 紧急例外

如果必须安装没有签名的软件包(例如密钥丢失),请在机器的 `armor.maint.env`(位于 `$PREFIX/etc/`)中写入下面这一行,事后再删除:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

每次安装时都会从该文件读取,因此无法通过 HTTP API 或进程环境变量来设置。每次使用时,助手都会在任务日志和自己的日志中写入 `WARNING`,概览中会报告 `unsigned_allowed`。

## 机器的设置

关于签名的两项设置，每次安装时都从 `armor.maint.env` 读取（绝不来自 HTTP API 或进程环境）：

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` 为 `manifest`（默认：只有 `.sig2` 有效）或 `either`（旧的 `.sig` 也有效）。`ARMOR_MAINT_NEXT_KEY` 为空，或是更换期间除内置公钥外同时信任的第二把公钥（64 位十六进制数字）；信任的密钥最多两把。助手的概览显示 `signature_mode` 和 `trusted_fingerprints`（每把密钥 SHA-256 的前 16 位，绝不是密钥本身），让管理机器的人看到它信任哪些密钥。在这里修改会改变机器决定安装什么的方式：与紧急例外一样，必须在机器上以 root 身份进行。

## 更换密钥

生成一对新密钥。先把新公钥作为 `ARMOR_MAINT_NEXT_KEY` 写入每台机器的 `armor.maint.env`（或发布一个用**旧**密钥签名、其 `PACKAGE_PUBLIC_KEY` 为新密钥的 `devops` 软件包）。此后用新密钥为软件包签名：只要那一行还在，机器就同时信任两把密钥。所有机器都内置了新密钥后，删除那一行。节点固件只信任一把密钥（`fw_trust.hpp`）：按已签名固件页面所述更换。

## 测试

`scripts/test_maintenance_agent.py` 涵盖：有效的清单签名、它绑定组件、版本和哈希、固件签名、旧文本和单独的哈希不能当作清单、被篡改的软件包、缺少 `.sig2`、其他密钥的签名、乱码、仅有旧 `.sig`（被拒绝，只有设置 `either` 才接受）、更换期间的两把密钥（第三把永远不被信任）、例外（仅来自文件）、RFC 8032 的测试向量，以及助手中的密钥就是 `fw_trust.hpp` 中的密钥。测试使用一次性密钥，绝不使用真实密钥。

打包工具会拒绝打包过期的构建:对于 `server` 和 `studio`,`package.json` 中的版本(Studio 还包括 `dist/version.json`)必须与 `armor.project.json` 一致,且 `dist/` 不能比其构建所用的源代码更旧。请先重新构建(`npm run build`)。
