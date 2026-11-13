# Abrir el puerto 18080 a Internet: qué comprobar antes

El servidor puede atender peticiones de Internet si reenvías el puerto 18080 en el router. Este proyecto no abre nada: el router es tuyo. El servidor solo se endurece. El broker (MQTT) y los nodos no se publican nunca.

## Antes de reenviar el puerto

* El token de control tiene al menos 32 caracteres aleatorios y la contraseña de Studio al menos 12 (si no, `public_access_unsafe` lista `control_token_short` / `password_short`).
* TLS está activo: el certificado propio del servidor (`TLS_CERT_PATH`, `TLS_KEY_PATH`) o un proxy inverso nombrado en `ARMOR_TRUST_PROXY` que hable https; la cookie es Secure (`tls_missing`, `cookie_not_secure`).
* El inicio de sesión en dos pasos está activo en todos los administradores y `ARMOR_TOTP_REQUIRED` es `remote` o `always`.
* `ARMOR_REMOTE_POLICY` es `operate` o `view`, salvo que de verdad necesites administrar desde fuera.
* `GET /api/v1/remote/check` desde un móvil con datos móviles muestra la dirección, `remote` y el protocolo `https`.

## Activarlo

En Studio, Configuración > Seguridad, activa `network.public_access` (desactivado por defecto; pide una nueva prueba de identidad). Mientras esté desactivado, toda petición de fuera de casa recibe `403 public_access_off`. Los inicios de sesión fallidos se cuentan por dirección: `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) dentro de `ARMOR_PUBLIC_LOGIN_WINDOW_S` segundos (900) cierran la dirección con `429 public_login_locked`.

## Después

Revisa el registro de auditoría (`public_access` y `studio.login` denegados), mantén actualizado el router y vuelve a desactivar la opción cuando no la necesites. Este modo solo se ha probado con un servidor simulado, nunca con tu router ni con Internet.
