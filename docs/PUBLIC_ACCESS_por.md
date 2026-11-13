# Abrir a porta 18080 à Internet - o que verificar primeiro

O servidor pode aceitar pedidos da Internet se reencaminhar a porta 18080 no router. Este projeto não abre nada: o router é seu. O servidor limita-se a reforçar-se. O broker (MQTT) e os nós nunca são publicados.

## Antes de reencaminhar a porta

* O token de controlo tem pelo menos 32 carateres aleatórios e a palavra-passe do Studio pelo menos 12 (caso contrário, `public_access_unsafe` lista `control_token_short` / `password_short`).
* O TLS está ativo: o certificado próprio do servidor (`TLS_CERT_PATH`, `TLS_KEY_PATH`) ou um proxy inverso indicado em `ARMOR_TRUST_PROXY` que fale https; o cookie é Secure (`tls_missing`, `cookie_not_secure`).
* O início de sessão em dois passos está ativo em todos os administradores e `ARMOR_TOTP_REQUIRED` é `remote` ou `always`.
* `ARMOR_REMOTE_POLICY` é `operate` ou `view`, a menos que precise mesmo de administrar a partir do exterior.
* `GET /api/v1/remote/check` num telemóvel com dados móveis mostra o endereço, `remote` e o protocolo `https`.

## Ativá-lo

No Studio, Configuração > Segurança, ative `network.public_access` (desativado por predefinição; pede uma nova prova de identidade). Enquanto estiver desativado, todo o pedido de fora de casa recebe `403 public_access_off`. As tentativas de início de sessão falhadas contam-se por endereço: `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) em `ARMOR_PUBLIC_LOGIN_WINDOW_S` segundos (900) fecham o endereço com `429 public_login_locked`.

## Depois

Consulte o registo de auditoria (recusas `public_access` e `studio.login` negados), mantenha o firmware do router atualizado e desative a opção quando já não for necessária. Este modo só foi testado com um servidor simulado, nunca com o seu router nem com a Internet.
