<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  🇵🇹 <b>Português</b>
</p>

### Implementação, a bancada de testes do CM5, as suas atualizações a partir do GitHub e a manutenção da instalação

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.7-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Verificação de honestidade - o que funciona hoje:** O instalador da bancada do CM5 foi executado num CM5 real que aloja outro software, que se manteve saudável, e a bancada corre em uso diário com o servidor, o Studio, o nó de rede, os serviços de observação e de voz, o broker e os dois assistentes abaixo; nela foram feitas atualizações dos seus componentes a partir do GitHub (através do Studio). A topologia Docker Compose e o seu perfil TLS opcional foram construídos e executados a sério com o Docker Engine no WSL (`scripts/test_compose.sh`), mas **não no Jetson**. Os scripts de cópia de segurança e restauro têm um teste de ida e volta que passa, e os dois assistentes têm os seus próprios testes. O que **não** está provado: uma instalação limpa numa máquina que nunca viu o projeto e toda a topologia Docker no seu destino.

---

## 📋 Num relance

| | |
|---|---|
| Versão | `0.6.7` |
| Maturidade | Estabelecido |
| Função | Kit de implantação: instalador da bancada do CM5, pacotes de versão, dois ajudantes, topologia Compose |
| Tecnologia | Bash, Python 3 (biblioteca padrão), Docker Compose, Mosquitto, Caddy, nginx, systemd |
| Testes | Um script de teste para cada parte (`scripts/test_*.sh` e `test_*.py`); a topologia Compose é construída e executada com Docker no WSL |
| Contrato | Portas da bancada: servidor 18080, Studio 18081, MQTT 18883 (nunca 1883), voz 18090 |
| Funciona em | Um CM5 ou qualquer máquina baseada em Debian acessível por SSH; Docker Engine com Compose para a topologia de contentores |
| Em hardware real | Faz correr a bancada de testes do CM5 em uso diário, num CM5 real que aloja outro software; ainda não no Jetson |
| Licença | GPL-3.0-or-later |

**Ir para:** [Visão geral](#-visão-geral) · [Arquitetura](#-arquitetura) · [Segurança](#-segurança-e-proteção) · [Interfaces](#-interfaces) · [Configuração](#-configuração) · [Início rápido](#-início-rápido) · [Testes](#-testes) · [Problemas](#-resolução-de-problemas) · [Estrutura](#-estrutura-do-repositório) · [Relacionados](#-projetos-relacionados)

## 🚦 Estado do projeto

Cada linha é uma parte deste repositório e a luz diz até onde chega hoje. É escrita com o que o repositório consegue demonstrar (testes, compilações, execuções), não com o que está previsto.

🟢 Feito e verificado · 🟡 Funciona, com limites conhecidos · 🟠 Feito a meio ou ainda por verificar · 🔴 Por fazer ou a não funcionar

| Área | Estado | O que significa aqui |
|---|---|---|
| Software | 🟡 | O instalador da bancada CM5 correu num CM5 real que aloja outro software, que se manteve saudável; uma instalação limpa numa máquina que nunca viu o projeto não está provada. |
| Testes | 🟡 | Os scripts de cópia de segurança e restauro têm um teste de ida e volta que passa, os dois auxiliares têm testes próprios, e a topologia Docker com o seu perfil TLS opcional foi construída e executada com o Docker Engine no WSL; a topologia completa não correu no seu destino. |
| Hardware | 🟡 | Faz funcionar a bancada de testes CM5 em uso diário; nada funcionou no Jetson. |
| Atualizações | 🟢 | As atualizações dos componentes a partir do GitHub, através do Studio, foram feitas na bancada de testes CM5. |
| Documentação | 🟢 | Oito idiomas e o registo de alterações estão atualizados. |

## 🎯 Visão geral

* **Bancada de testes do CM5:** `scripts/deploy_cm5.sh` compila numa cópia limpa, envia um ficheiro e executa `scripts/install_cm5.sh`, que cria o seu próprio utilizador, o seu próprio diretório e unidades systemd em portas próprias para o servidor e o Studio e, com opções, o broker MQTT, o nó de rede, o serviço de observação, a porta de ligação de voz, o agente de administração, o assistente de manutenção e a cópia de segurança diária. Nunca toca no que mais a máquina executa.
* **O assistente de manutenção** (`armor_maintenance_agent.py`): as atualizações dos componentes da própria instalação a partir do GitHub (descarrega o pacote da versão, verifica o seu SHA-256 e troca-o com reversão), as do sistema operativo e uma consola root opcional, tudo comandado a partir do separador *Atualizações* do Studio; a consola está desligada salvo se for ativada. Guarda as seis cópias mais recentes que põe de lado e menos quando o disco está quase cheio (`ARMOR_MAINT_MIN_FREE_MB` no seu ficheiro de definições: 500 por omissão, 0 desliga-o).
* **O agente de administração** (`armor_admin_agent.py`): a única parte com privilégios, com uma lista fechada de serviços, ficheiros de definições e contas do broker, de modo que o Studio nunca precisa de root.
* **Pacotes de cada versão:** `scripts/package_component.py` constrói o pacote de um componente (Studio, servidor, rede, serviço de observação, porta de ligação de voz, DevOps), escreve o seu SHA-256 ao lado e publica-o como versão do GitHub.
* **Topologia Compose:** um broker Mosquitto não anónimo com uma identidade por nó e uma ACL (incluindo os nós de alarme e as zonas Zigbee que o servidor lhes diz), o servidor e o Studio atrás de um nginx que faz proxy de `/api/`; só o Studio é publicado, em loopback. Contentores reforçados, imagens fixadas, uma rede interna do núcleo e volumes com nome para o estado.
* **TLS:** um perfil `tls` opcional do Compose põe o Caddy, com a sua própria autoridade certificadora local, à frente do Studio, e é fornecida uma configuração do Mosquitto sobre TLS ([detalhes](docs/BACKUP_AND_TLS.md)).
* **Uma firewall de anfitrião para a máquina central** (`scripts/firewall_core.sh`): a porta do broker só a partir da rede de campo, as do servidor e do Studio só a partir da rede dos clientes (quando indicada), numa tabela própria que não menciona mais nada.
* **Segredos:** `scripts/generate_secrets.sh` cria segredos aleatórios e não imprime nenhum; `scripts/check-required-env.sh` recusa valores em falta, de exemplo, curtos ou repetidos.
* **Cópia de segurança e restauro:** `scripts/backup_data.sh` faz um ficheiro cifrado com AES-256, verificado e com soma de verificação dos dados do servidor (sem provas salvo se pedidas); `scripts/restore_data.sh` lista-o ou restaura-o sem nunca sobrescrever dados existentes.
* **Uma VPN e um nome para a casa, configurados a partir do Studio:** `armor_wireguard.sh` monta uma VPN WireGuard com poucos comandos (chaves na máquina, uma configuração por telemóvel com código QR, encaminhamento para os nós se quiser) e `armor_ddns.sh` mantém um nome DuckDNS, Cloudflare ou outro a apontar para a casa quando o operador muda o endereço; o agente de manutenção oferece ambos ao Studio e ao telemóvel, por isso ninguém tem de escrever um comando, e um guia passo a passo em oito idiomas cobre o router.
* **Pacotes assinados:** o assistente de manutenção só instala um pacote do servidor, do Studio ou de qualquer outro programa se levar uma assinatura Ed25519 válida da chave de releases do projeto (verificada em Python puro, sem software adicional); uma assinatura em falta, errada ou adulterada deixa a máquina como estava. Existe uma exceção de emergência apenas como definição no ficheiro da própria máquina.
* **Uma porta cifrada opcional para o broker (MQTT sobre TLS):** `scripts/armor_mqtt_tls.sh` cria uma autoridade de certificação para a instalação (a chave fica na máquina, modo `0600`), um certificado do broker para os nomes e endereços da máquina e um segundo listener do Mosquitto na 8883 ao lado do normal, que nunca toca; é idempotente e tem `status`, `export-ca`, `server-tls` e `remove` (os ficheiros são postos de parte, nunca apagados). Testado com OpenSSL, com handshakes reais, e num Mosquitto 2.0 real ([guia](docs/MQTT_TLS_por.md)).
* **Relatórios de saúde permitidos:** as regras do broker deixam cada nó escrever o seu `armor/health/<nó>` e o servidor ler `armor/health/#`; `mqtt_identity.sh add` escreve a linha para cada tipo de nó e `mqtt_identity.sh health-report <papel> <nó>` acrescenta-a a um nó instalado antes (idempotente, as regras anteriores ficam guardadas).
* **Regras do broker para o controlo dos nós:** só a identidade do servidor pode publicar em `armor/control/+/command` (que cobre `armor/control/all/command`); cada nó lê o seu próprio tópico de ordens e o de difusão e escreve a sua própria resposta em `armor/control/<nó>/result`, e mais nada, de modo que nenhum nó pode mandar noutro e a palavra-passe roubada de um nó não consegue reiniciar os outros. `mqtt_identity.sh node-control` acrescenta as três linhas a um nó instalado antes, e o teste das ACL verifica cada tipo de nó.

## 🧩 Papel no A.R.M.O.R.

O ARMOR-DEVOPS é como tudo o resto chega a uma máquina e se mantém atualizado. Instala o servidor, o Studio, o nó de rede, os serviços de observação e de voz e o broker na bancada de testes do CM5, faz os pacotes de cada versão que o separador *Atualizações* do [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) instala a partir do GitHub, e guarda os dois pequenos assistentes que deixam o Studio atualizar a instalação e gerir os seus serviços sem nunca correr como root.

| Fala com | Como | Para quê |
|---|---|---|
| ARMOR-STUDIO | o separador *Atualizações* pede ao ajudante de manutenção por um socket local | nunca precisa de root |
| GitHub Releases | `package_component.py` publica o pacote com o seu SHA-256 e assinatura | os componentes a instalar |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | instalados como unidades systemd próprias | os serviços da bancada |
| ARMOR-UPDATER | à parte | a ferramenta de quem guarda uma cópia da família num PC; este repositório é para o CM5 e a topologia Compose |

## 🏛️ Arquitetura

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 Segurança e proteção

| Ameaça | Defesa |
|---|---|
| Interferir com outro software do CM5 | Utilizador, diretoria e portas próprios (servidor 18080, Studio 18081, MQTT 18883 e voz 18090, todas entre 1024 e 65535 e diferentes, nunca a padrão 1883); não toca na firewall do sistema |
| Um broker aberto ou sem autenticação | `allow_anonymous false`, um ficheiro de palavras-passe e uma ACL (segredos montados em `/run/secrets`), uma identidade por nó; só o servidor pode publicar `armor/control/+/command`; cada nó lê a sua ordem e a de difusão e escreve só o seu `armor/control/<nó>/result` e `armor/health/<nó>`; o servidor lê `armor/health/#` |
| Escuta acidental na rede | O Compose só publica o broker e o Studio em `127.0.0.1`, salvo se `ARMOR_MQTT_BIND`, `ARMOR_STUDIO_BIND` (e `ARMOR_TLS_BIND` para o Caddy) disserem outra coisa |
| MQTT e Studio em claro | Opcional: um segundo recetor do Mosquitto em 8883 ao lado do simples (`armor_mqtt_tls.sh`: autoridade própria, chave em modo `0600`, certificado para os nomes da máquina, idempotente, nunca toca no simples) e um perfil `tls` do Compose com Caddy e a sua autoridade local |
| A máquina central aberta a todos | `firewall_core.sh` escreve uma tabela própria (`/etc/armor/firewall.nft`, com uma unidade de reversão): a porta do broker só a partir da rede de campo, as do servidor e do Studio só a partir da rede de clientes; `check` verifica-a com `nft -c` |
| Segredos fracos ou impressos | `generate_secrets.sh` cria segredos aleatórios e não imprime nenhum; `check-required-env.sh` recusa valores em falta, de modelo, curtos ou repetidos |
| Uma cópia de segurança roubada | `backup_data.sh` faz um arquivo cifrado AES-256, verificado e com soma de verificação (provas excluídas salvo pedido); `restore_data.sh` lista-o ou restaura-o sem nunca sobrescrever dados existentes |
| Uma atualização falsa de um componente | O ajudante de manutenção descarrega o pacote de versão, verifica o seu SHA-256 e a assinatura Ed25519 da chave de publicação do projeto (em Python puro) e troca-o com reversão; uma assinatura em falta, errada ou adulterada deixa a máquina inalterada |
| Root ao alcance do Studio | Nunca é preciso: o agente de administração (`armor_admin_agent.py`) tem uma lista fechada de serviços, ficheiros de definições e contas do broker; a consola de root do ajudante de manutenção está desligada salvo se for ligada |

Os contentores estão reforçados, as imagens fixadas, a rede `core` é interna e o estado fica em volumes com nome. Os dois ajudantes usam sockets Unix locais, por isso os seus testes precisam de Linux. Uma instalação limpa numa máquina que nunca viu o projeto e a topologia Docker completa no seu destino não estão provadas; não houve revisão independente.

## 🔌 Interfaces

| Rota | Autenticação | O que faz |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | constrói numa cópia limpa, envia um arquivo por SSH e executa `install_cm5.sh` |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | cria o utilizador, a diretoria e as unidades systemd; `--server-port`, `--studio-port`, `--mqtt-port` e `--also-reach` ajustam-no; sem `--apply` só mostra o plano |
| `scripts/package_component.py` | - | empacota o Studio, o servidor, o nó de rede, o serviço de observação, a gateway de voz ou o DevOps como o ajudante de manutenção os instala, escreve o seu SHA-256 e publica-o como versão do GitHub |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` e `secrets/` (ignorados pelo Git); a verificação recusa valores em falta, de modelo, curtos ou repetidos |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | o arquivo cifrado e verificado dos dados do servidor |
| `scripts/restore_data.sh` | - | lista um arquivo ou restaura-o sem sobrescrever dados existentes |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | a tabela da firewall da máquina central; `check` verifica-a (`FIREWALL_CHECK=SKIP` se `nft` não estiver instalado) |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | escreve a linha do broker de cada tipo de nó; acrescenta relatórios de saúde e controlo a um nó instalado antes (idempotente) |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | a porta cifrada do broker (`status`, `export-ca`, `server-tls`...), a VPN WireGuard com um QR por telemóvel, um nome DuckDNS, Cloudflare ou outro para a casa e a verificação do acesso remoto; o Studio oferece-os sem escrever um comando |

Os dois ajudantes (`armor_admin_agent.py`, `armor_maintenance_agent.py`) escutam em sockets Unix locais e por isso não correm no Windows. O ficheiro Compose arranca o broker (Mosquitto), o servidor e o Studio (nginx, que reencaminha `/api/`), e um perfil `tls` acrescenta o Caddy; só o Studio é publicado, por predefinição em loopback (`127.0.0.1:8088`, TLS em 8443). Os pacotes de cada versão são ficheiros das versões do GitHub, não ficheiros deste repositório.

## ⚙️ Configuração

| Definição | Predefinição | O que faz |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`, `--studio-port`, `--mqtt-port` (mantém-se o instalado se não for repetido) e a porta de voz; todas entre 1024 e 65535 e diferentes; o endereço do broker vai para `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | onde o Compose publica o broker e o Studio |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | a origem pela qual se chega ao Studio |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | Caddy do perfil `tls` |
| `.env`  `.env.example` | - | criado por `generate_secrets.sh`, ignorado pelo Git; o exemplo lista cada variável |

A consola de root do ajudante de manutenção é uma definição do próprio ficheiro da máquina e está desligada por predefinição; a firewall e o TLS são opções do instalador, não predefinições. Detalhes em [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md).

## 🚀 Início rápido

**Requisitos:** Docker Engine com Compose (para a topologia de contentores), um CM5 ou qualquer máquina baseada em Debian acessível por SSH (para a bancada de testes), Bash, `ssh` e `tar` na máquina que implanta.

```bash
scripts/generate_secrets.sh                                                            # `.env` e `secrets/` (ignorados pelo Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # a topologia de contentores
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # a bancada de testes
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # uma cópia cifrada
```

Consulte o [limite da implantação](docs/DEPLOYMENT_BOUNDARY.md) e a [bancada de testes](docs/CM5_TEST_BENCH.md).

## 🧪 Testes

| Área | O que cobre |
|---|---|
| `test_admin_agent.py`  `.sh` | a lista fechada do agente de administração (precisa de Linux: sockets Unix) |
| `test_maintenance_agent.py`  `.sh` | o ajudante de manutenção: descarga, SHA-256, assinatura, troca e reversão (precisa de Linux) |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | os pacotes, a lista de componentes e os ajudantes de acesso remoto |
| `test_backup.sh`  `test_env_and_restore.sh` | a ida e volta de cópia e restauro, os segredos e a verificação do ambiente |
| `test_compose.sh`  `validate-compose.sh` | a topologia Compose e o seu perfil TLS, construídos e executados com Docker Engine no WSL |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | a firewall, o plano do instalador, as identidades do broker, MQTT sobre TLS, a verificação TLS, a VPN e o nome dinâmico |

Os testes de Python correm com `python -m unittest discover -s scripts -p "test_*.py"`; no Windows os três que precisam de sockets Unix não podem correr. Os scripts precisam de Bash, WSL, Docker ou root e têm de ser executados em Linux. Ainda não há um número único de testes: o Project status diz o que foi executado. O GitHub Actions executa a base do A.R.M.O.R. em cada push e pull request: a validação do manifesto, da versão, do registo de alterações e da paridade dos README, e depois a compilação e os testes do próprio projeto.

## 🏗️ Compilação e publicação

Não se compila nada: são scripts, um ficheiro Compose e ajudantes em Python. `scripts/package_component.py` constrói o pacote de um componente e escreve o seu SHA-256 ao lado; os pacotes são ficheiros das versões do GitHub, não ficheiros deste repositório. A versão está em `armor.project.json` e no emblema do README (lido do manifesto); cada versão tem a sua entrada em [CHANGELOG.md](CHANGELOG.md).

## 🩺 Resolução de problemas

| Vê | Porque | Faça |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | uma porta de `install_cm5.sh` está fora do intervalo ou repetida | use portas diferentes entre 1024 e 65535 (nunca a padrão 1883) |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | o endereço adicional não está escrito como endereço do Studio = endereço do servidor | escreva `--also-reach http://<anfitrião>:<porta-studio>=http://<anfitrião>:<porta-servidor>` |
| `FIREWALL_CHECK=SKIP nft is not installed here` | falta `nft`, por isso `firewall_core.sh check` não pode verificar a tabela | instale o nftables na máquina e verifique outra vez |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | os testes dos dois ajudantes estão a correr no Windows | execute-os em Linux (ou WSL) |

## 📂 Estrutura do repositório

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>Versão em texto da árvore</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      implanta na bancada, instala-o
│   ├── package_component.py                              o pacote de cada versão
│   ├── armor_admin_agent.py armor_maintenance_agent.py   os dois ajudantes do Studio
│   ├── generate_secrets.sh check-required-env.sh         segredos aleatórios; recusa os fracos
│   ├── backup_data.sh restore_data.sh                    cópia cifrada e restauro
│   ├── firewall_core.sh mqtt_identity.sh                 firewall e identidades do broker
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              MQTT sobre TLS e a sua verificação
│   ├── armor_ddns.sh armor_wireguard.sh                  um nome para a casa e uma VPN
│   └── test_*.py test_*.sh validate-compose.sh           os testes dos ajudantes e scripts
├── docker-compose.yml docker-compose.tls.yml             broker, servidor, Studio; perfil TLS
├── mosquitto/                                            mosquitto.conf, config TLS, acl.example
├── caddy/                                                Caddyfile: HTTPS à frente do Studio
├── docs/                                                 DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (as últimas quatro também em oito idiomas)
├── tools/                                                as verificações de CI e as ferramentas partilhadas
├── images/                                               faixa, ícone e as imagens do README
├── .github/                                              fluxo de CI, aviso ao painel, modelos de issues e pull requests
├── armor.project.json                                    manifesto: versão, função, maturidade
├── CHANGELOG.md                                          o que mudou em cada versão
├── run.sh run.bat                                        arrancar, fluxo partilhado
├── build.sh build.bat                                    compilar e testar, fluxo partilhado
├── build-test.sh build-test.bat                          compilar, testar e empacotar
├── test.sh test.bat                                      só os testes, nunca a versão
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ Roteiro e limites conhecidos

**Limites conhecidos hoje**

* Uma instalação limpa numa máquina que nunca viu o projeto não está provada.
* A topologia Docker completa foi construída e executada com Docker Engine no WSL, mas não no seu destino, o Jetson.
* Não há um número único de testes, e os testes dos dois ajudantes precisam de Linux.
* Sem revisão de segurança independente.

**A seguir**

* Uma instalação limpa numa máquina nova e a topologia Docker no Jetson.

## 🌍 Idiomas

O README e os textos existem em inglês, espanhol, francês, italiano, alemão, chinês, japonês e português europeu.

## 🔗 Projetos relacionados

O **A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) é um sistema de segurança perimetral feito de repositórios independentes. Cada um tem a sua própria versão, os seus próprios testes e o seu próprio README; esta é a família:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensagens, validadores, vetores de conformidade e tipos gerados
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Firmware de nó de campo para ESP32-S3 com três radares e o seu próprio painel web
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protocolos de inversores e baterias solares e as mensagens de um nó porta de ligação
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Nó elétrico: contadores, a mensagem das leituras da rede e as regras de comutação
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Nó e painel de alarme: zonas, armar, atrasos, sirene e PIN, com o servidor ou sem ele
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Painel tátil: o estado do sistema num ecrã de parede, armar e reconhecer, e a casa do assistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - A rede local: os seus dispositivos, a internet e o que muda
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordenador central: telemetria, alarmes, dispositivos, leituras solares e câmaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: câmaras, radar, alarmes, energia solar e o desenhador 2D/3D do local
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente de operador Android com radar 2D/3D em direto
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - Cliente de operador para iPhone
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferência visual que explica as suas decisões e nunca atua
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de câmara, máscaras e regras de deteção para o Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intenções de voz offline com uma confirmação que não pode ser falsificada
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Caixas, eletrónica e a matriz de aceitação em bancada
* **ARMOR-DEVOPS** (este repositório) - Implantação, a bancada de testes do CM5, cópias de segurança e TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetria offline com falhas repetíveis
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Deteta, instala e atualiza os repositórios do próprio ecossistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitetura, base de segurança e a matriz de capacidades

## 📚 Documentação

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md): o que este repositório implanta e o que não
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md): o instalador, as unidades, as portas e os ajudantes da bancada
* [BENCH_TESTS](docs/BENCH_TESTS.md): como a bancada é testada
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md): cópia e restauro, e o perfil TLS do Compose
* [MQTT_TLS](docs/MQTT_TLS.md): a porta cifrada do broker (também em oito idiomas)
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md): confiar no certificado de um nó (também em oito idiomas)
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md): VPN, um nome para a casa e o router, passo a passo (também em oito idiomas)
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md): a assinatura dos pacotes (também em oito idiomas)
* [Matriz de capacidades: o que está demonstrado e o que não está](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de projetos: versões e como os repositórios dependem uns dos outros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Registo de alterações deste repositório](CHANGELOG.md)

## 🤝 Contribuir e comunidade

* Antes de um pull request execute `python -I tools/armor_ci_validate.py` e os testes: ambos têm de passar. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) e o [código de conduta](CODE_OF_CONDUCT.md).
* O README existe em oito idiomas e é gerado a partir das fontes do ARMOR-DOCS: uma alteração ao texto faz-se lá.
* Uma alteração a uma mensagem entre componentes começa no ARMOR-COMMON.
* Não descreva como a funcionar numa placa aquilo que só foi compilado.
* Comunique uma vulnerabilidade em privado: [SECURITY.md](SECURITY.md). Perguntas, ideias e relatórios: electrohobby3d@gmail.com ([SUPPORT.md](SUPPORT.md)).

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENÇA

GPL-3.0-or-later - consulte [LICENSE](LICENSE).
