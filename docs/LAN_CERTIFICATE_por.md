# Um certificado para o endereço da máquina na rede local

Este é o caminho para um `https://192.168.0.180` em que um telemóvel ou um navegador confiam, com uma autoridade própria da instalação e sem qualquer nome no DNS público. É **opcional e está desligado**: o perfil `tls` (um nome, a autoridade própria do Caddy, ver HTTPS_PAIRING.md) e o perfil `lan-ca` continuam a funcionar como estão. A porta 18080 do servidor **nunca é aberta à Internet**: chega-se a ela a partir da rede local ou através da VPN, e nada neste guia o altera.

## O que cria

`scripts/armor_lan_cert.py` cria, uma só vez, uma **autoridade local** e, para o endereço indicado, um **segundo certificado** assinado por essa autoridade:

* `~/.armor/lan-ca/ca.crt`: o certificado da autoridade (público: é o que se instala nos telemóveis e computadores).
* `~/.armor/lan-ca/ca.key`: a chave privada da autoridade. Fica nessa pasta (modo 0700, a chave 0600), nunca é impressa, o programa nunca a copia e nunca faz parte de um repositório nem de um pacote.
* `leaf.crt`, `leaf.key`, `fullchain.pem`: o certificado do endereço (um endereço IPv4 privado, mais os nomes `.lan` / `.local` que acrescentar, mais 127.0.0.1) e a sua chave.

A autoridade é limitada por uma restrição de nomes dentro do seu próprio certificado: só pode garantir endereços privados e nomes `.lan` / `.local`, pelo que uma cópia roubada da sua chave não pode fazer-se passar por um sítio da Internet perante um dispositivo que confie nela. O programa recusa um endereço público.

## Os passos

1. **Veja primeiro.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` diz o que seria criado e não altera nada.
2. **Ligue-o e crie-o.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Sem `--enable` (ou `"enabled": true` em `~/.armor/lan-ca/lan-ca.json`) recusa: o predefinido é desligado. Se for executado outra vez, mantém a autoridade e o certificado enquanto o endereço for o mesmo e restarem mais de `renew_days` dias; se o endereço mudar, cria um certificado novo com a mesma autoridade, pelo que os dispositivos não são tocados.
3. **Dê o certificado ao proxy.** Use a variante `caddy/Caddyfile.lan-issued`, que serve `/lan-certs/leaf.crt` e `/lan-certs/leaf.key`: `ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`. A pasta é montada só de leitura; sem essas duas variáveis o proxy continua a usar a autoridade própria do Caddy.
4. **Instale a autoridade uma vez em cada dispositivo.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` escreve o certificado público. Android: Definições > Segurança > Encriptação e credenciais > Instalar um certificado > Certificado de CA. iPhone: abra o ficheiro, instale o perfil e depois Definições > Geral > Informações > Definições de confiança de certificados e ative-o. Windows: duplo clique e instalação em «Autoridades de certificação de raiz fidedignas». Linux: copie-o para `/usr/local/share/ca-certificates/` e execute `update-ca-certificates`.
5. **Verifique.** `python3 scripts/armor_lan_cert.py fingerprint` imprime o SHA-256 da autoridade (o que o painel de parede fixa); com `--spki`, a impressão da sua chave pública (o que a aplicação do telemóvel fixa). Compare-a com o que o dispositivo mostra antes de confiar.

## O ficheiro de definições

`~/.armor/lan-ca/lan-ca.json` (tudo opcional; um valor fora do intervalo ou desconhecido é um erro, nunca um palpite): `enabled` (false), `ca_days` (3650), `leaf_days` (397; os navegadores e telemóveis recusam mais de 398 dias para alguns certificados), `renew_days` (30), `curve` (`prime256v1` ou `secp384r1`) e `name_constraints` (true). `ARMOR_LAN_CA_DIR` muda a pasta de sítio.

## O que convém saber

* Quem tiver `ca.key` pode emitir certificados, para endereços privados, que os dispositivos que confiam na autoridade aceitam: guarde a pasta para si, faça cópia de segurança como de qualquer outro segredo e nunca a ponha num repositório.
* `remove` põe a pasta de lado (`lan-ca.removed-<hora>`); nada é apagado. Os dispositivos que instalaram a autoridade antiga devem removê-la.
* Nada disto correu no CM5: os testes criam uma autoridade e um certificado numa pasta descartável com o openssl e verificam que a cadeia é válida para o endereço e não para outro.
