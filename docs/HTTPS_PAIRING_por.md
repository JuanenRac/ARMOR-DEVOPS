# HTTPS para os telemóveis: a autoridade própria da casa e o emparelhamento

A aplicação Android mantém `http` sem cifra para a rede local enquanto não houver outra coisa. Este guia é o caminho para uma casa a que se chega por `https` em todo o lado, com uma autoridade própria que o telemóvel recorda, para que a aplicação possa um dia recusar `http`.

## O perfil por omissão

O perfil `tls` deste repositório coloca o Caddy à frente do Studio e do servidor. O seu valor por omissão é o seguro: a **autoridade local própria** do Caddy (`tls internal`), um certificado para `ARMOR_TLS_HOST`, HSTS de cinco minutos, apenas `https`. Nada disto precisa da internet. Para um nome da internet ponha um endereço de correio em `ARMOR_TLS_ISSUER` e o Caddy pede o certificado ao Let's Encrypt (ver `REMOTE_ACCESS_por.md`): então o telemóvel confia no certificado por si e não há nada a emparelhar.

## Os passos

1. **Nome.** Escolha o nome com que os telemóveis chegam à casa (o nome de DNS dinâmico a partir de fora, ou um nome da rede local) e ponha-o em `ARMOR_TLS_HOST` (`ARMOR_TLS_PORT=443` se o router reencaminhar o 443).
2. **Arranque-o.** `docker compose --profile tls up -d` (ou o Caddy do pacote com o mesmo `Caddyfile`). O servidor corre com `ARMOR_TRUST_PROXY=1` e `ARMOR_PUBLIC_ORIGIN=https://<nome>`.
3. **Verifique.** `scripts/armor_tls_check.sh <nome> 443 <root.crt>` diz se o servidor responde, se a cadeia é válida para o nome, se restam mais de 14 dias e que chave fixaria um telemóvel, e escreve a linha `armor-pin:<nome>:<pin>`. O certificado raiz é `pki/authorities/local/root.crt` nos dados do Caddy (o assistente de manutenção encontra-o; `ARMOR_TLS_CA_FILE` indica-o se estiver noutro sítio).
4. **Emparelhe cada telemóvel.** No Studio, Configuração > Segurança > acesso a partir de fora > *Emparelhar o telemóvel com o HTTPS da casa*: escreva o nome, prima o botão, copie o texto. Na aplicação, Mais > Segurança, cole-o. A aplicação passa a aceitar para a casa só essa autoridade; uma chave diferente é recusada e dito.
5. **Experimente tudo** em cada telemóvel, com o Wi-Fi de casa e com dados móveis: início de sessão, câmaras, armar, alarmes, push.
6. **Só então** o dono pode proibir `http` sem cifra na aplicação (`cleartext=false`) numa compilação nova. Enquanto não estiverem todos os telemóveis emparelhados e experimentados, deixe como está.

## O que convém saber

* O pin é o SHA-256 da chave **pública** da autoridade: não é um segredo, mas quem o dá a um telemóvel decide em quem ele confia; por isso só se mostra aos administradores e deve ser comparado com o que a aplicação mostra.
* O Caddy renova sozinho o certificado da casa. A autoridade dura cerca de dez anos; se for substituída (uma pasta de dados nova do Caddy) o pin muda e emparelha-se de novo.
* A chave da autoridade nunca sai da máquina e o A.R.M.O.R. nunca a lê.
* Um telemóvel emparelhado que encontre uma chave diferente recusa-se a ligar: é o que se pretende. Para o emparelhar outra vez, esqueça o pin na aplicação (Mais > Segurança) e cole o texto novo.

## O teste na máquina (para o dono)

`scripts/armor_tls_check.sh` passa na CM5; o texto de emparelhamento é o mesmo no Studio e na saída do script; um telemóvel emparelhado com o Wi-Fi de casa também liga com dados móveis; depois de `systemctl restart caddy` (ou do contentor) não é preciso emparelhar de novo.
