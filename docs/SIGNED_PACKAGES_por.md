# Pacotes assinados: como a máquina decide o que instala

O assistente de manutenção da máquina (`armor_maintenance_agent.py`) atualiza os programas do A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) a partir das releases dos respetivos repositórios no GitHub. Antes de extrair seja o que for, verifica três coisas, por esta ordem:

1. **O hash:** o pacote tem de dar o SHA-256 indicado em `armor-<componente>-<versão>.tgz.sha256`. Assim deteta-se uma transferência cortada.
2. **A assinatura:** `armor-<componente>-<versão>.tgz.sig2` contém a assinatura Ed25519 (64 bytes como 128 dígitos hexadecimais) do manifesto

   `armor-fw/1|<componente>|package|<versão>|<sha256>`

   feita com a chave privada das releases, a mesma que assina o firmware dos nós: é o mesmo manifesto das imagens de firmware, com `package` no lugar da placa. O assistente verifica-a com a chave pública que faz parte do seu código (`PACKAGE_PUBLIC_KEY`) e, enquanto a chave é mudada, com uma segunda (ver abaixo). Uma release sem `.sig2`, ou com uma que não verifica, é recusada (`missing_signature`, `bad_signature`) e o sistema fica como estava: nada é descompactado, nada é reiniciado.
3. **O ficheiro:** sem nomes absolutos, sem `..`, sem ligações nem dispositivos.

Quem apenas consiga alterar o conteúdo de uma release no GitHub (uma conta roubada, uma dependência maliciosa das ferramentas de publicação) pode publicar um pacote e o seu hash, mas não a assinatura: a chave privada nunca está no GitHub. O manifesto liga a assinatura ao componente e à versão, pelo que um pacote assinado do passado ou de outro componente não pode passar pelo mais recente, e a assinatura de uma imagem de firmware (outro projeto, uma placa real) nunca vale como assinatura de pacote. A antiga `.sig` (texto `armor-pkg/1|<componente>|<versão>|<sha256>`) já não basta: só é aceite se o `armor.maint.env` da máquina disser `ARMOR_MAINT_SIGNATURE=either`, durante o tempo que levar a assinar os pacotes publicados antes.

A verificação é Python puro (RFC 8032): não precisa de OpenSSL nem de módulos adicionais na máquina.

## Publicar

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Escreve `.tgz`, `.sha256`, `.sig2` (o manifesto) e `.sig` (o texto antigo, que um assistente ainda não atualizado continua a verificar) e envia-os. O assinador é `~/.armor/sign.mjs` (ou `--signer` / `ARMOR_PACKAGE_SIGNER`); lê a chave de `ARMOR_FIRMWARE_KEY` ou de `~/.armor/firmware_ed25519.pem`. A chave nunca é copiada para um repositório. `--sign` falha se não houver assinador ou chave; sem ele, o pacote é assinado quando existirem. Uma chave diferente da que o assistente aceita nunca é usada. `--publish` recusa enviar um pacote sem assinatura.

Para assinar um pacote já publicado, transfira-o junto com o seu `.sha256` e execute:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

O nome indica o componente e a versão; `--upload` acrescenta a `.sig2` e a `.sig` à release `v<versão>` do seu repositório (precisa de `gh`).

## Publicação a partir do GitHub Actions

O pacote deste repositório é construído pelo fluxo `package-build.yml` (iniciado à mão, `dry_run` ativo por predefinição): empacota duas vezes os scripts do pacote `devops` em dois executores, para se os dois pacotes não forem idênticos byte a byte e carrega `armor-devops-<versão>.tgz` com `SHA256SUMS` e uma atestação. Não guarda nenhuma chave. Para assinar e publicar a release na máquina do responsável, a partir do artefacto de uma execução verde:

```
gh attestation verify armor-devops-<version>.tgz --repo JuanenRac/ARMOR-DEVOPS
python scripts/package_component.py --sign-existing armor-devops-<version>.tgz --upload
```

A release passa então a levar `armor-devops-<versão>.tgz`, `.sha256`, `.sig` e `.sig2`, de que o assistente de manutenção precisa; uma release sem eles faz a máquina dizer que o repositório não tem release.

## Exceção de emergência

Se for preciso instalar um pacote sem assinatura (por exemplo, com a chave perdida), escreva esta linha no `armor.maint.env` da máquina (em `$PREFIX/etc/`) e retire-a depois:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

É lida desse ficheiro sempre que se instala algo, pelo que não pode ser ativada pela API HTTP nem pelo ambiente do processo. O assistente escreve um `WARNING` no registo da tarefa e no seu próprio sempre que é usada, e o resumo indica `unsigned_allowed`.

## Definições da máquina

Duas definições sobre a assinatura, lidas do `armor.maint.env` sempre que se instala algo (nunca da API HTTP nem do ambiente do processo):

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` é `manifest` (por predefinição: só conta a `.sig2`) ou `either` (conta também a antiga `.sig`). `ARMOR_MAINT_NEXT_KEY` está vazia ou é a segunda chave pública, 64 dígitos hexadecimais, em que se confia além da incorporada durante uma rotação; nunca se confia em mais de duas chaves. O resumo do assistente mostra `signature_mode` e `trusted_fingerprints` (os primeiros 16 dígitos do SHA-256 de cada chave, nunca as chaves), para que quem cuida da máquina veja em que chaves ela confia. Uma alteração aqui muda a forma como a máquina decide o que instala: faz-se na máquina, como root, tal como a exceção de emergência.

## Mudar a chave

Crie um par novo. Primeiro escreva a nova chave pública como `ARMOR_MAINT_NEXT_KEY` no `armor.maint.env` de cada máquina (ou publique um pacote `devops`, assinado com a chave **antiga**, cujo `PACKAGE_PUBLIC_KEY` seja o novo). A partir daí assine os pacotes com a chave nova: as máquinas confiam nas duas enquanto essa linha lá estiver. Quando todas tiverem a chave nova incorporada, retire a linha. O firmware dos nós confia numa só chave (`fw_trust.hpp`): mude-a como diz a página do firmware assinado.

## Testes

`scripts/test_maintenance_agent.py` cobre uma assinatura de manifesto válida, que liga o componente, a versão e o hash, que uma assinatura de firmware, o texto antigo e o hash solto não passam por manifesto, um pacote adulterado, uma `.sig2` em falta, uma assinatura de outra chave, lixo, a antiga `.sig` sozinha (recusada, aceite só com `either`), as duas chaves de uma rotação (e que uma terceira nunca é de confiança), a exceção (só a partir do ficheiro), o vetor de teste da RFC 8032 e que a chave do assistente é a de `fw_trust.hpp`. Usam chaves descartáveis, nunca a verdadeira.

O empacotador recusa-se a empacotar uma compilação desatualizada: para `server` e `studio`, a versão em `package.json` (e, no Studio, em `dist/version.json`) tem de ser a de `armor.project.json`, e `dist/` não pode ser mais antigo do que o código-fonte a partir do qual foi compilado. Compile de novo (`npm run build`) primeiro.
