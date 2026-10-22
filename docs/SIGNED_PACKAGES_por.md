# Pacotes assinados: como a máquina decide o que instala

O assistente de manutenção da máquina (`armor_maintenance_agent.py`) atualiza os programas do A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) a partir das releases dos respetivos repositórios no GitHub. Antes de extrair seja o que for, verifica três coisas, por esta ordem:

1. **O hash:** o pacote tem de dar o SHA-256 indicado em `armor-<componente>-<versão>.tgz.sha256`. Assim deteta-se uma transferência cortada.
2. **A assinatura:** `armor-<componente>-<versão>.tgz.sig` contém a assinatura Ed25519 (64 bytes como 128 dígitos hexadecimais) do texto

   `armor-pkg/1|<componente>|<versão>|<sha256>`

   feita com a chave privada das releases. O assistente verifica-a com a chave pública incluída no seu código (`PACKAGE_PUBLIC_KEY`), a mesma em que confia o firmware dos nós. Uma release sem `.sig`, ou com uma que não verifica, é recusada (`missing_signature`, `bad_signature`) e o sistema fica como estava: nada é extraído nem reiniciado.
3. **O ficheiro:** sem nomes absolutos, sem `..`, sem ligações nem dispositivos.

Quem apenas consiga alterar o conteúdo de uma release no GitHub (uma conta roubada, uma dependência maliciosa das ferramentas de publicação) pode publicar um pacote e o seu hash, mas não a assinatura: a chave privada nunca está no GitHub. O texto começa por `armor-pkg/1` e não pelo `armor-fw/1` do firmware, pelo que uma assinatura de firmware nunca pode passar por assinatura de pacote; e inclui o componente e a versão, pelo que um pacote assinado não se pode fazer passar por outro programa nem por uma versão mais recente.

A verificação é Python puro (RFC 8032): não precisa de OpenSSL nem de módulos adicionais na máquina.

## Publicar

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Escreve `.tgz`, `.sha256` e `.sig` e envia os três. O assinador é `~/.armor/sign.mjs` (ou `--signer` / `ARMOR_PACKAGE_SIGNER`); lê a chave de `ARMOR_FIRMWARE_KEY` ou de `~/.armor/firmware_ed25519.pem`. A chave nunca é copiada para um repositório. `--sign` falha se não houver assinador ou chave; sem ele, o pacote é assinado quando existem. Nunca se usa uma chave diferente da que o assistente aceita. `--publish` recusa enviar um pacote sem assinatura.

Para assinar um pacote já publicado, transfira-o junto com o seu `.sha256` e execute:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

O nome indica o componente e a versão; `--upload` acrescenta a `.sig` à release `v<versão>` do respetivo repositório (requer `gh`).

## Exceção de emergência

Se for preciso instalar um pacote sem assinatura (por exemplo, com a chave perdida), escreva esta linha no `armor.maint.env` da máquina (em `$PREFIX/etc/`) e retire-a depois:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

É lida desse ficheiro sempre que se instala algo, pelo que não pode ser ativada pela API HTTP nem pelo ambiente do processo. O assistente escreve um `WARNING` no registo da tarefa e no seu próprio sempre que é usada, e o resumo indica `unsigned_allowed`.

## Mudar a chave

Crie um par novo e coloque a nova chave pública em `PACKAGE_PUBLIC_KEY` e no firmware (`fw_trust.hpp`). Publique um pacote `devops` assinado com a chave **antiga** (as máquinas instalam-no e passam a confiar na nova) e assine os seguintes com a nova.

## Testes

`scripts/test_maintenance_agent.py` cobre uma assinatura válida, um pacote adulterado, um `.sig` em falta, uma assinatura de outra chave, lixo, a exceção (só a partir do ficheiro), o vetor de teste da RFC 8032 e que a chave do assistente é a de `fw_trust.hpp`. Usam chaves descartáveis, nunca a verdadeira.

O empacotador recusa-se a empacotar uma compilação desatualizada: para `server` e `studio`, a versão em `package.json` (e, no Studio, em `dist/version.json`) tem de ser a de `armor.project.json`, e `dist/` não pode ser mais antigo do que o código-fonte a partir do qual foi compilado. Compile de novo (`npm run build`) primeiro.
