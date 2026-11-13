# 向互联网开放 18080 端口前需要检查什么

在路由器上转发 18080 端口后，服务器即可接受来自互联网的请求。本项目不会开放任何东西：路由器归您所有，服务器只负责加固自身。代理 (MQTT) 和节点永远不会公开。

## 转发端口之前

* 控制令牌至少 32 个随机字符，Studio 密码至少 12 个字符 (否则 `public_access_unsafe` 会列出 `control_token_short` / `password_short`)。
* 已启用 TLS：服务器自己的证书 (`TLS_CERT_PATH`、`TLS_KEY_PATH`)，或在 `ARMOR_TRUST_PROXY` 中指定且使用 https 的反向代理；Cookie 为 Secure (`tls_missing`、`cookie_not_secure`)。
* 所有管理员都已启用两步登录，且 `ARMOR_TOTP_REQUIRED` 为 `remote` 或 `always`。
* 除非确实需要从外部管理，否则 `ARMOR_REMOTE_POLICY` 应为 `operate` 或 `view`。
* 用使用移动数据的手机打开 `GET /api/v1/remote/check`，应显示地址、`remote` 和协议 `https`。

## 启用

在 Studio 的“配置 > 安全”中打开 `network.public_access` (默认关闭；需要重新验证身份)。关闭时，来自家庭网络之外的所有请求都返回 `403 public_access_off`。失败的登录按地址计数：在 `ARMOR_PUBLIC_LOGIN_WINDOW_S` 秒 (900) 内失败 `ARMOR_PUBLIC_LOGIN_ATTEMPTS` 次 (5)，该地址将被 `429 public_login_locked` 封闭。

## 之后

查看审计日志 (`public_access` 拒绝和被拒绝的 `studio.login`)，保持路由器固件更新，不再需要时请关闭该选项。此模式只在模拟服务器上测试过，从未在您的路由器或互联网上测试。
