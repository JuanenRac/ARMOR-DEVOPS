# Usar o A.R.M.O.R. de fora de casa - passo a passo

A regra: **uma só porta** e **um nome, nunca um endereço**. O broker MQTT e os nós nunca se publicam na Internet.

## 1. Escolha a porta

* **A. Uma VPN (recomendado)**: WireGuard ou Tailscale na máquina que executa o servidor. De fora o telemóvel entra na VPN e tudo funciona como em casa (também o painel de cada nó). Se o seu operador não lhe dá um endereço público próprio (CGNAT), o Tailscale funciona sem abrir nada.
* **B. HTTPS**: um proxy inverso com certificado verdadeiro (o perfil `tls` deste repositório) numa porta do router. Cómodo a partir de qualquer navegador; ponha a política «operate» para que administrar fique para a casa ou a VPN.

## 2. Um nome que acompanhe o seu endereço

O seu endereço público é fixo ou muda de vez em quando. Nos dois casos use um **nome** (DuckDNS, No-IP, o DNS dinâmico do router ou um domínio próprio) e algo que o atualize quando o endereço mudar (o cliente do router, ou o `ddclient`/o script do DuckDNS na máquina). Ponha um TTL curto (60 a 300 s). O telemóvel, o Studio e a VPN usam sempre o nome.

## 3. No router

Redirecione **uma** porta para a máquina do servidor: `443/TCP` para B (e `80/TCP` se o certificado for verdadeiro, para a sua verificação), ou `51820/UDP` para WireGuard em A. Nunca `1883`, `8883` nem a porta de um nó.

## 4. No servidor (Docker)

No `.env`:

```
ARMOR_TLS_HOST=casa.duckdns.org          # o seu nome
ARMOR_TLS_ISSUER=voce@example.com        # pede o certificado ao Let's Encrypt e renova-o
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # assim o servidor vê o endereço real de cada visitante
ARMOR_TOTP_REQUIRED=remote               # segundo fator de fora (configure-o antes de dentro)
ARMOR_REMOTE_POLICY=operate              # de fora: ver e manobrar o alarme; administrar só de casa ou da VPN
```

e depois `docker compose --profile tls up -d`. Na bancada CM5 as mesmas definições estão em `armor.network.env` (o Studio > Configuração > Segurança escreve-as por si).

## 5. No Studio

Configuração > Segurança: ative o segundo fator (aplicação de autenticação) em cada conta, guarde os códigos de recuperação e veja as sessões abertas. Como administrador, indique o proxy de confiança, as redes que contam como a casa, a política e a duração das sessões de fora.

## 6. No telemóvel

A.R.M.O.R. Control: escreva o nome como servidor (`https://casa.duckdns.org`), entre (o código da aplicação é pedido como segundo passo) e confira Mais > Segurança.

## 7. Verifique

No telemóvel **com dados móveis**, no Studio ou na aplicação, carregue em «Verificar como o servidor me vê»: deve dizer **de fora** e mostrar o seu endereço real. Se disser «de casa», o proxy não passa o endereço: corrija o `ARMOR_TRUST_PROXY` antes de confiar em seja o que for.

## Nunca

Redirecionar a porta do broker ou de um nó, nem «só por um momento»; usar o endereço em vez do nome; deixar as palavras-passe por defeito; saltar o segundo fator num administrador que entra de fora.
