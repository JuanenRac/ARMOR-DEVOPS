# ポート 18080 をインターネットに公開する前の確認事項

ルーターでポート 18080 を転送すると、サーバーはインターネットからのリクエストを受け付けられます。このプロジェクトは何も開放しません。ルーターはあなたのものです。サーバーは自分自身を堅牢にするだけです。ブローカー (MQTT) とノードは決して公開されません。

## ポートを転送する前に

* コントロールトークンは 32 文字以上のランダムな文字列で、Studio のパスワードは 12 文字以上であること (そうでない場合 `public_access_unsafe` が `control_token_short` / `password_short` を返します)。
* TLS が有効であること: サーバー自身の証明書 (`TLS_CERT_PATH`、`TLS_KEY_PATH`)、または `ARMOR_TRUST_PROXY` に指定され https を話すリバースプロキシ。クッキーは Secure であること (`tls_missing`、`cookie_not_secure`)。
* すべての管理者で 2 段階サインインが有効で、`ARMOR_TOTP_REQUIRED` が `remote` または `always` であること。
* 外部から本当に管理する必要がない限り、`ARMOR_REMOTE_POLICY` は `operate` または `view` にします。
* モバイル回線のスマートフォンから `GET /api/v1/remote/check` を開き、アドレス、`remote`、プロトコル `https` を確認します。

## 有効にする

Studio の「設定 > セキュリティ」で `network.public_access` をオンにします (既定はオフ。新たな本人確認が必要です)。オフの間は、家の外からのすべてのリクエストに `403 public_access_off` が返ります。サインインの失敗はアドレスごとに数えられ、`ARMOR_PUBLIC_LOGIN_WINDOW_S` 秒 (900) 以内に `ARMOR_PUBLIC_LOGIN_ATTEMPTS` 回 (5) 失敗すると、そのアドレスは `429 public_login_locked` で閉じられます。

## その後

監査ログ (`public_access` の拒否と拒否された `studio.login`) を確認し、ルーターのファームウェアを最新に保ち、不要になったらオプションをオフに戻してください。このモードはシミュレートしたサーバーでのみ試験されており、お使いのルーターやインターネットでは試していません。
