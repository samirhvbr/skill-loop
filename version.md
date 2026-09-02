# Versão — skill-LOOP

**Versão atual:** `0.3.5`

> Este arquivo é a **fonte da verdade** da versão do projeto. Qualquer lugar que
> precise exibir ou reportar a versão extrai o **primeiro número semver (`X.Y.Z`)**
> encontrado aqui. Mantenha a linha **"Versão atual"** sempre como a primeira
> ocorrência de um número de versão. Mesma mecânica dos projetos-irmãos
> (AUDITOR, COMMITTER).

---

## 1. Convenção de Versionamento (`X.Y.Z`)

| Componente | Significado | Como sobe |
|---|---|---|
| **X** | Release estável — loop operando em trabalho real da casa | Manual |
| **Y** | Mudança estrutural — fase concluída, mudança de contrato (`STATE.json`, formato do `.loop/`), ADR aceito que muda a direção | Manual |
| **Z** | Incremento a cada entrega | A cada entrega |

Enquanto `X` for `0`, contratos podem quebrar entre versões `0.Y`.

### Gatilhos de bump do `Z`

- Alterar o **léxico do classificador** ou qualquer regra de ASK × DOC.
- Alterar o **prompt de continuação** (`prompts/continuacao.md`) — é o produto.
- Alterar guarda-corpos: teto de iterações, sem-progresso, kill-switch, fila.
- Alterar o esquema do `STATE.json` ou o formato de `.loop/`.
- Alterar `install.sh` ou `.claude/settings.json`.
- Criar ou alterar documento em `docs/`, `SPEC.md` ou `prompts/` que **muda uma
  regra** (não vale corrigir redação).
- Adicionar ou alterar testes que definem comportamento esperado.

### Gatilhos de bump do `Y`

- Fase concluída (ver `.continue/escopo-projeto.md`).
- Quebra de compatibilidade no `.loop/` já existente em algum repo.
- ADR novo com status **Aceito** que muda a direção.

> Correções de texto, typo e formatação **não** exigem bump.

---

## 2. Formato de Commit Obrigatório

```
X.Y.Z - Descrição curta em português
```

**Regras inegociáveis:**

1. A versão **sempre** vem deste `version.md`, bumpada **no mesmo commit**.
2. Mensagem em **português**, descritiva o suficiente para `git log --grep`.
3. **Proibido** Conventional Commits (`feat:`, `fix:`, `chore:`…) e vago.
4. Um objetivo por commit; mudanças pequenas e atômicas.

O bump entra em **um único commit** por entrega (o primeiro). Commits adicionais
da mesma entrega repetem a versão.

---

## 3. Changelog

### `0.3.5` — 2026-09-02 — a cópia versionada ganha ferramenta, e ela é quem sabe da armadilha

O `install.sh` liga um symlink por config dir do Claude Code: sempre atual, zero
manutenção. Mas quem quer a skill **dentro** do repositório alvo — commitada,
para o clone já vir com ela e não depender de instalação global — estava copiando
`skill/loop/` à mão. Foi o que aconteceu hoje em **27 repositórios** (SHVIA,
BLUE3, SSHVTERM), e a cópia à mão erra em dois lugares que não avisam.

#### `vendor.sh`

- `./vendor.sh <repo>...` instala ou atualiza a cópia em
  `<repo>/.claude/skills/loop-work/`; `--dry-run` mostra antes.
- Re-rodar **é** o update: o diretório é substituído inteiro, nunca mesclado. Um
  arquivo de versão antiga sobrevivendo à cópia a que pertencia não teria como
  ser notado.
- Imprime `versão-antes -> versão-depois` por repositório, lendo o `VERSION.md`
  que ele mesmo escreveu. Sem isso não há como saber quais das 27 cópias estão
  velhas — foi exatamente o que faltou no `auditor`, que se instala do mesmo
  jeito e não carimba versão nenhuma.
- A versão sai deste `version.md` e a origem inclui o commit: a cópia diz de onde
  veio, não só o que é.

#### As duas armadilhas que ele fecha

- **`prompts/` fica fora do que se copia.** `hooks/loop-stop.py` resolve os
  templates três níveis acima de `skill/loop/`; a partir de
  `.claude/skills/loop-work/` isso cai em `<repo>/.claude/prompts/`. Copiar só o
  diretório do skill deixa o hook sem `continuacao.md` — e a falha é silenciosa
  até a primeira parada. O script leva os dois arquivos junto.
- **A cópia tem precedência sobre o symlink global** para o que o agente *lê*
  (`SKILL.md`, `loop_ctl.py`), enquanto o hook que dirige a continuação é sempre
  o do repositório. Depois de um bump, a cópia é a metade velha. O `VERSION.md`
  gerado diz isso por escrito, no lugar onde alguém vai procurar.

Nenhum hook é registrado por repositório, de propósito: o global já cobre todo
repo e é inerte sem `.loop/STATE.json` ativo — registrar de novo dispararia duas
vezes.

Sem teste novo: o script não é do caminho de execução do loop (não roda no hook
nem no `loop_ctl`), e o que ele produz é verificado pelos testes que já existem,
rodando na cópia. **248 testes**, verdes.

### `0.3.4` — 2026-09-02 — o rearme por tempo vira arquivo no alvo

Subir uma rodada por tempo custava dois comandos, em dois terminais, com um
caminho em cada. Ninguém decora isso, então no EOP virou um `loop.sh` escrito à
mão na raiz do repositório — e **ele está lá até hoje**, com os dois defeitos que
o impediam de virar produto: a raiz é um literal (`--raiz ~/x/EOP`), o que prende
o arquivo a uma árvore e morre no primeiro clone; e ele não chega sozinho, cada
repositório alvo dependia de alguém lembrar de escrevê-lo.

#### O atalho é semeado pelo próprio `armar`

- Novo molde versionado em `skill/loop/templates/loop.sh`; `armar` grava
  `.loop/loop.sh` (modo 755) **quando ele não existe**, substituindo dois
  placeholders pelos caminhos absolutos desta cópia do skill.
- `./.loop/loop.sh` arma por **6h** e abre o painel; `./.loop/loop.sh 10h` toma
  qualquer duração que o `parse_duracao` aceite.
- A raiz é **derivada** (`dirname "${BASH_SOURCE[0]}"/..`), não escrita: mover,
  clonar ou renomear o repositório continua funcionando. É a diferença entre o
  molde e o original que ele substitui.
- Prefere `loop-ctl`/`loop-watch` do `PATH` e cai no caminho absoluto da cópia
  que semeou — mesma razão do shim do `install.sh`: dizer qual cópia serve.
- **Nunca sobrescreve.** A cópia no alvo é do dono: é no bloco `EXTRA=(...)` dela
  que `--objetivo`, `--janela` e `--itens` sobrevivem entre rodadas. Apagar o
  arquivo é o jeito de pedir um novo.
- A semeadura roda **depois** de `loop.iniciar()`, nunca junto do esqueleto do
  `QUEUE.md`: comando que recusa não pode deixar arquivo atrás. E erro de I/O
  sai calado — derrubar um `armar` que já armou por causa de um atalho inverteria
  o fail-open do ADR-009.

#### A adoção de sessão é pedida em voz alta, e é a mesma P-09

O atalho passa `--adotar-primeira-parada` e imprime o aviso na saída de erro
**antes** de armar. Um shell não conhece o próprio `session_id`, e este é
exatamente o caso que a P-09 mediu — a rodada do EOP que adotou a sessão aberta
para triar PRs do Dependabot. A guarda do `0.2.6` foi desenhada em torno dele:
recusar sem saída quebraria este arquivo. O que a guarda compra é a adoção ser
**dita**; o que o aviso compra é o operador ouvir no único momento em que ainda
dá para fechar os outros chats.

Sem `--ate-encerrar` no watch, de propósito: turno que morre sem emitir `Stop`
prende a rodada em `ativo: true` (P-08), e script bloqueado nessa flag penduraria
para sempre. Ctrl+C sai do painel; a rodada segue.

#### Também neste commit

O merge da `origin/master` (`0.2.5` e `0.2.6`) entrou logo antes, em commit
próprio. As duas linhas haviam divergido no `0.2.4` e alocaram o número `0.2.5`
em paralelo, para entregas diferentes — o changelog ganhou a nota da colisão, e
nada foi renumerado, porque cada número está preso à mensagem de um commit
publicado.

**Testes: 248** (13 novos, `tests/test_atalho.py`), verdes. Metade olha a
semeadura; a outra metade **executa o script gerado**, com `loop-ctl` e
`loop-watch` trocados por stubs à frente do `PATH` — testar só o texto do arquivo
passaria por cima de tudo que quebra num shell.

**Seis controles, seis mutações:** desligar a chamada da semeadura derruba **10**
testes; movê-la para antes das guardas, **1** (o que exige que um `armar` recusado
não deixe arquivo); tirar a guarda de "nunca sobrescreve", **2**; tomar a raiz do
`pwd` em vez do caminho do script, **2**; remover o aviso de sessão, **4**;
desligar o `set -e`, **1**.

⛔ **Não medido:** se o atalho muda alguma coisa na taxa de rodada armada com a
sessão errada. Ele torna a adoção visível no instante certo, mas quem fecha os
outros chats é o operador — e isso é comportamento, não código.

### `0.3.3` — 2026-08-18 — o changelog volta a bater com o log

O bump da 0.3.1 foi feito com `sed` sem âncora e renomeou a entrada histórica
da 0.3.0 além do cabeçalho. Os dois consertos seguintes tropeçaram: o
`1d36e61` prometeu na mensagem uma entrada que não escreveu, e o `52898f8`
truncou o arquivo. Esta entrada fecha os três.

### `0.3.1` — 2026-08-18 — o aviso de encerramento vira ato único

O hook reemitia o aviso de fecho em todo stop, sobre um loop já encerrado —
quatro vezes numa rodada, e uma delas dentro de uma sessão que não era do
loop. Agora o `STATE.json` marca `notificado` e o aviso sai uma vez só.

### `0.3.0` — 2026-08-17 — a fila mandava na rodada por tempo, e não era dela a missão

O dono digitou `loop-ctl armar --raiz ~/x/EOP --duracao 6h` sobre uma fila 66/66 e
tomou `erro: nenhum item - [ ] na fila`. A pergunta que veio junto é a mais curta
que este projeto recebeu: *"por que o loop está avaliando a fila? o trabalho do loop
é meio que só dizer continua"*. Ela está certa, e o defeito era de desenho: a fila
fazia **duas** coisas — o **conteúdo** da continuação (legítimo, insubstituível) e a
**condição de fim #4** (errada quando há relógio). O guarda-corpo do `0.2.5` foi a
consequência final: nascido para barrar rodada morta, passou a barrar o caminho
certo.

#### Fila vazia com relógio não encerra: o motor reabastece (ADR-015)

- `fila zerada` **só encerra rodada sem relógio**. Com `duracao_max_min` ou `janela`
  declarados, a fila vazia sai da cadeia e vira **turno de reabastecimento**.
  Gatilho **derivado** (`diagnostico.tem_relogio`), não flag nova: quem escreveu
  `--duracao 6h` já declarou que a missão é o relógio. `STATE.json` **não muda de
  contrato**, e estado de versão anterior cai no comportamento antigo.
- Segundo template, `prompts/reabastecimento.md` — o `reabastecer.md` que o dono
  colava na cauda da fila, virado prompt do motor, com as mesmas cláusulas do
  ADR-014. O hook escolhe por trabalho: `item is None` + relógio → reabastecer.
  Mandar o prompt de continuação com `(fila vazia)` no lugar do item seria uma ordem
  para executar o que não existe.
- **Escopo** do reabastecimento: `.loop/SCOPE.md` **verbatim** quando existe; senão
  o `--objetivo`, e o prompt diz ao turno que a fronteira **não foi declarada** e
  manda recusar o duvidoso. Quem não sabe onde parar precisa saber que não sabe.
- **Fim novo — `escopo esgotado`**, condição #4, lida de `.loop/SEM-ESCOPO`: o agente
  mede que não há bloco em escopo, escreve os números, e o `STATUS.md` cita o
  veredito. Arquivo separado do `STOP` porque um só apagaria **quem** decidiu
  encerrar: o kill-switch é ordem do dono, este é medição do agente. `armar` apaga o
  arquivo (depois das guardas); `retomar` não, e `porque` avisa que ele está lá.
- `armar --duracao`/`--janela` **deixa de recusar** fila vazia, e avisa que a
  primeira parada é reabastecimento — mais um aviso se falta `SCOPE.md`. Sem
  relógio, a recusa do `0.2.5` fica intacta, mensagem inclusive.
- `loop-watch` não pode mais marcar `fila zerada` como fim sob relógio: a linha da
  fila vira informativa (`fila (não encerra) · N pendente(s) → reabastece`, motivo
  `None` de propósito) e entra a de `escopo esgotado`. Era este painel que, em
  17/08, apontava `← encerrou aqui` na fila com `resta 5h22` duas linhas abaixo.
- `dur()` e o novo `restante_da_rodada()` saíram do `loop_watch` para a lib: o prompt
  precisa do mesmo formatador, e duas cópias divergem na primeira borda (`0` não é
  "0min", é "esgotado").

#### O que **não** mudou, de propósito

- **Rodada por itens** — sem relógio a fila continua sendo o critério de pronto
  (ADR-006), a recusa do `armar` continua, e o `reabastecer.md` continua sendo o
  mecanismo dela.
- **O anti-loop-infinito é o mesmo**: `sem progresso`. Turno que repõe muda a
  contagem da fila (entra no sha1 da impressão) e zera o contador; turno que não
  produz nada acumula e encerra em 3 — com teste que prova.
- **Ordem da cadeia**: kill-switch e tetos continuam na frente do veredito. Ordem do
  dono acima de medição do agente, e o teto de degeneração acima de tudo que o
  agente escreve.

**228 testes verdes**, +21. Quatro controles, quatro mutações: desligar o gatilho
derivado derruba 10 testes; o veredito, 5; a guarda do `armar`, 4; a linha do
painel, 2.

⛔ **Não medido:** se o reabastecimento conduzido pelo motor deriva menos ou mais que
o conduzido pelo item na cauda — dois prompts com as mesmas cláusulas e contextos
diferentes. Junta-se à P-05.

> ⚠️ **Colisão de numeração — as duas `0.2.5` abaixo são entregas
> diferentes.** Em 18/08 esta árvore seguiu para `0.3.x` sem ter recebido o
> que a `origin/master` publicou em 02/09, e as duas linhas alocaram `0.2.5`
> sem saber uma da outra. Nada foi renumerado de propósito: cada número está
> preso à mensagem de um commit publicado, e mudá-lo aqui quebraria o
> casamento entre o changelog e o log — que é o defeito que a `0.3.3` acabou
> de consertar. A reconciliação foi por **merge** em 02/09; a linha segue em
> `0.3.4`. Ordem abaixo: por versão, com as duas `0.2.5` lado a lado.

### `0.2.6` — 2026-09-02 — a adoção de sessão deixa de ser herdada por omissão

**A primeira das três saídas da P-09, e a única que cabia com a rodada viva.** O
`0.2.5` registrou o defeito e não o consertou, pela norma que o `0.2.4` já havia
escrito: mexer em `hooks/` ou `lib/` com rodada em curso faz o hook sair
fail-open e travar a rodada no meio. **Medido agora, e é o que destravou:** o
`hooks/loop-stop.py` importa `classificador`, `diagnostico`, `estado` e
`transcricao` — todos de `lib/` — e **não importa `loop_ctl.py`**. O `armar`,
portanto, está fora do caminho do hook, exatamente como o `loop_watch.py` estava
no `0.2.4`. As outras duas saídas (marcador do processo, lock de árvore) moram no
hook e em `lib/`, e continuam esperando rodada morta.

**O que muda:** `armar` recusa-se a armar com `bind_session: true` e sem
`--sessao`, e nomeia as três saídas — `--sessao <id>`,
`--adotar-primeira-parada` (novo) e `--qualquer-sessao`.

⛔ **Não é a "falha ruidosa" pura que a P-09 propunha, e a diferença foi
medida:** o `loop.sh` do EOP arma com `loop-ctl armar --raiz ~/x/EOP --duracao
10h`, **sem `--sessao`** — uma recusa seca quebraria o script do dono, e guarda
que atrapalha vira `--force` na semana seguinte. Também não se pode exigir o id:
o ADR-008 já descartou isso porque **ninguém sabe o próprio de cor**. Então o
comportamento histórico continua alcançável em uma palavra; o que ele deixa de
ser é **herdado por omissão** — o único jeito em que custou caro.

**A guarda recusa SEM GRAVAR ESTADO**, e isso é o segundo controle, não detalhe:
`.loop/` meio-armado é o defeito que o `0.2.3` pagou com o `¨¨` — estado gravado
antes de uma guarda não passa a obedecê-la depois, e um `retomar` o reativaria
sem passar pela escolha. O teste afirma `ler() is None`, que é o desfecho mais
forte disponível.

O resumo do `armar` passa a dizer **como** a sessão foi escolhida
(`a primeira que parar — ADOÇÃO PEDIDA` · `qualquer (não amarra)`): a linha
antiga era verdadeira e ambígua, e foi lida como default por uma rodada inteira.

**Testes: 188 → 193.** ADR-008 ganha emenda; a P-09 registra a saída entregue e
as duas que restam.

| Controle desligado | Testes que caem |
|---|---|
| a guarda de porta sai (adoção volta a ser o default silencioso) | 2 |
| o resumo volta a não dizer COMO a sessão foi escolhida | 2 |

### `0.2.5` — 2026-09-02 — o auto-bind adotou a sessão errada, e o ADR dizia "necessariamente"

**O produto se auditou rodando pela segunda vez, e o achado é no texto de uma
decisão, não no código.** Só `docs/` mudou: nenhuma linha de `hooks/` ou `lib/`,
de propósito — a rodada do EOP estava viva, com **outra** sessão executando o
`L219`, e é a mesma razão que no `0.2.4` adiou o conserto do `INDEX.md`.

O **ADR-008** afirma que a primeira parada *"é **necessariamente** a da sessão
que armou"*, e o comentário em `hooks/loop-stop.py:167` repete. **Não é.** É a
primeira sessão que **termina um turno** no repositório — qualquer chat já aberto
ali serve. No EOP o loop adotou uma sessão que o dono havia aberto para triar os
PRs do Dependabot, enquanto o `loop.sh` armava de outra. O `print` do próprio
`armar` já dizia a verdade (`sessão: a primeira que parar`): o defeito é de
documentação, e documentação que promete garantia inexistente é pior que silêncio.

**Custo medido na rodada** (é o que torna isto pendência e não curiosidade):

- **18 entradas** de diário (`0153`–`0160`, `0166`–`0172`) que são mensagens sobre
  PRs e sobre um artifact, arquivadas sob `L191`, `L201`, `L219` e `L220`;
- **4 itens espúrios** na fila, colhidos de fragmentos truncados da mensagem
  (`- [ ] a página como fonte`) — **terceira** reincidência da família que a
  emenda do ADR-005 e o marcador nu do `0.2.4` já visitaram;
- **duas sessões dirigidas contra a mesma árvore**, o mais caro: duas colisões de
  `version.md` no EOP (`1.76.71` e `1.76.72`, a segunda no commit que consertava a
  primeira), duas `master` vermelhas na guarda `G2` do repo alvo, e dois commits
  que anunciaram trabalho que o diff não continha.

**Entregue:** a **P-09** com o contraexemplo, o custo e três saídas a avaliar
(recusar `armar` sem `--sessao` quando `bind_session: true`; marcador do processo
que armou, conferido pelo hook e retrocompatível quando ausente; lock de árvore
que faça a segunda sessão RECUSAR item em vez de competir). E o ADR-008 ganha a
ressalva onde a afirmação vive — a decisão continua de pé, o que cai é a garantia.

**Testes: 188, sem mudança** — nada de comportamento mudou, e isso é o ponto.

### `0.2.5` — 2026-08-17 — a rodada que nasce morta, e o reabastecimento promovido

A rodada de 22 paradas do EOP encerrou por `fila zerada` às 16:30 — **corretamente,
e com veredito escrito**. O que veio depois é que estava errado: três `armar` sobre
a fila já 66/66 produziram as paradas `#20`, `#21` e `#22`, cada uma durando **uma**
parada com horas de relógio sobrando, e cada uma injetando o relatório de
encerramento no turno de quem estava fazendo outra coisa. Foi o que o agente do EOP
nomeou como *"instrução de parada injetada em contexto errado"*.

#### Armar sem pendente vira erro, não aviso

- `armar` e `retomar` **recusam** fila sem nenhum `- [ ]` (`--mesmo-sem-fila`
  força). O aviso já existia hoje de manhã e não impediu **nenhuma** das três:
  texto impresso depois de o estado estar gravado não é guarda-corpo.
- A recusa não deixa efeito atrás: o `armar` apagava o `.loop/STOP` **antes** das
  guardas, então um comando que abortava já tinha desarmado o kill-switch — a única
  trava que o dono aciona sem terminal na sessão.

#### Rodada que nasceu morta encerra calada

- `pendentes_ao_armar` (campo novo, aditivo) grava quantos itens havia a fazer na
  hora de armar. Zero + primeira parada + zero pendente agora = **nada aconteceu**:
  o hook encerra com `systemMessage` e **não** emite o relatório. `None` (estado de
  versão anterior) relata como antes — "não sei" nunca vale zero.
- O predicado começou como `iteracao == 1 and feitos == feitos_ao_armar` e a suíte
  cobrou: silenciava encerramento **legítimo** na primeira parada (política
  ASK=parar, `--itens 1`), onde houve rodada e o relatório é o certo. Medir o fato
  no `armar` substituiu a inferência por dois contadores que podiam coincidir.
- Registro inalterado: `STATUS.md`, entry e `INDEX.md` continuam escritos.

#### Leitura de registro não pode matar quem lê

O painel morreu com traceback às **16:39:57**, no refresh seguinte a uma tela que
renderizou certo 30 s antes: leu uma entry no meio da gravação e
`UnicodeDecodeError` — que é `ValueError` — passou por baixo do
`except (IOError, OSError)`.

- `errors="replace"` nas leituras de registro: entries e `STATUS.md` no painel,
  `QUEUE.md` no motor. A entry estragada **continua na tela**, com o byte ruim como
  U+FFFD; sobreviver escondendo a parada seria o mesmo painel mentiroso por outro
  caminho — e foi assim que a primeira versão do teste passou com o controle
  desligado (a mutação derrubou 0 testes, e o teste foi refeito).
- Na fila isso é mais que cosmético: quem escreve o `QUEUE.md` é o **agente**, e o
  hook a lê no instante do `Stop` — a janela é o turno de reabastecimento. A
  exceção seria engolida pelo fail-open e a parada se perderia **em silêncio**,
  justamente na volta em que a fila cresceu.
- E a colheita deixou de gravar esqueleto por cima de fila ilegível: ela lê o
  `QUEUE.md` para **reescrevê-lo**, e o fallback `"# Fila do loop\n"` valia para
  qualquer falha de leitura — com o arquivo existindo, isso apagava o contrato do
  ciclo. Agora esqueleto só quando não há arquivo; qualquer outra falha desiste da
  colheita, que é acessória.

#### O reabastecimento vira artefato do produto (ADR-014)

O ⛔ de hoje de manhã dizia para **não** documentar o padrão antes de a rodada
medir. A rodada mediu: **14 paradas seguidas sem encerrar** (`#6`…`#19`), **13
reabastecimentos**, fila de **22 → 66 itens**, intervalos de 25 · 14 · 10 · 10 · 7
min. E o achado que mudou o desenho: na 10ª volta o agente **quebrou a cláusula de
reposição de propósito**, com as sete hipóteses tabeladas (três viraram bloco, três
mediram zero), porque *"cumpri-la sem insumo obriga a fabricar bloco"*.

- [prompts/reabastecer.md](prompts/reabastecer.md) — o item canônico, com as duas
  cláusulas normativas: **escopo declarado** (com o que "para e pergunta") e
  **escape da reposição**.
- `SKILL.md` §1.1, `SPEC.md` §5.2, ADR-014, e o `armar` apontando para o arquivo
  quando recusa fila vazia.
- Fica dito o que isso **não** é: automático. A promessa de horas depende de alguém
  colar o item na fila — é decisão, não esquecimento.
- ⛔ Segue sem medição se a fila escrita pelo próprio loop **deriva** ao longo de
  muitas voltas (P-05). Contar as 44 linhas novas não responde; ler o que elas
  produziram, sim.

**Testes: 184 → 200.** Mutação de cada controle:

| Controle desligado | Testes que caem |
|---|---|
| `armar`/`retomar` voltam a avisar em vez de recusar | 3 |
| recusa volta a apagar o kill-switch antes de abortar | 1 |
| rodada que nasceu morta volta a emitir o rito | 1 |
| predicado largo (qualquer 1ª parada fica calada) | 8 |
| `pendentes_ao_armar` deixa de ser gravado | 1 |
| painel volta a morrer com byte inválido na entry | 1 |
| contagem da fila volta a estourar com byte inválido | 1 |
| colheita volta a gravar esqueleto por cima da fila ilegível | 1 |

**A mutação pendente do `0.2.4` foi medida** — a rodada do EOP encerrou e o
`classificador.py` parou de ser editado, então mutar-e-restaurar deixou de arriscar
o trabalho de outro. Cada marcador voltando a ser nu (`\s*:` → `\b`):

| Marcador que volta a ser nu | Testes que caem |
|---|---|
| `próxima rodada` | 2 |
| `próximo ciclo` | 1 |
| `não coberto` | 2 |
| os três juntos | 3 |

Os três juntos derrubam **menos** que a soma: os testes de regressão do `0.2.4`
usam prosa real e uma frase pode casar com mais de um marcador, então a mesma
asserção cai por qualquer um deles. O que importa é que **nenhum** dos três está
sem teste — era exatamente o que o ⛔ deixava em aberto.

### `0.2.4` — 2026-08-17 — o marcador nu, e quando cada parada foi

> Duas entregas na mesma árvore, e o registro diz de quem é cada uma: o conserto
> do classificador foi feito **pelo agente do EOP**, dentro da rodada de loop, e
> o painel por esta sessão. Estão num commit só porque assim aconteceram.

#### O classificador colhia prosa — achado em operação, pelo próprio loop

Primeira vez que o produto se auditou **rodando**. A colheita errou três vezes na
rodada de 17/08; na terceira reproduziu de primeira, e a causa não era falta de
teste — a suíte já tinha nove asserções negativas dedicadas a não colher prosa. A
causa era a **forma do padrão**.

- **Marcador nu** — sintagma sem verbo de adiamento — casa narrativa. *"a tabela
  ficou no QUEUE.md para a próxima rodada não repetir a varredura"* fala sobre
  para que serve um registro, e virou item de fila. Agravante: como o
  `colher_declarados` pega a primeira frase do parágrafo quando não há lista, **o
  item que nascia nem era a frase que casou**.
- A varredura das cinco listas achou **três** nus na que alimenta a fila:
  `próxima rodada`, `próximo ciclo` e `não coberto` — o terceiro descoberto ao
  consertar os dois primeiros, e confirmado com prosa real antes da mudança
  (*"esse caminho ficou não coberto pela imutabilidade do banco"*). Os outros
  doze padrões carregam verbo e nunca morderam.
- Os três passam a exigir `\s*:`. Com dois-pontos a expressão **anuncia** itens,
  que é o único uso que o colhedor sabe ler.
- **Catraca meta:** um teste varre `DECLARADO_PENDENTE` inteira e reprova
  marcador que não tenha verbo de adiamento nem exija `:` — com prova de execução
  nos dois sentidos, para a catraca não absolver por engano.

#### O painel: quando cada parada foi, e quanto tempo levou

Pedido do Samir durante a terceira rodada, e o defeito é o mesmo que o enganou de
manhã: o painel mostrou `09:32 · 09:03 · 21:19 · 20:24` nas últimas paradas, e as
duas de baixo eram do **dia anterior** — nada na tela dizia isso. Num registro
que atravessa a meia-noite, `hh:mm` sozinho engana com cara de dado.

- **`Últimas paradas` carrega `DD/MM/YYYY-hh:mm`** (`carimbo()`). Carimbo que não
  casa com o formato ISO devolve o texto cru truncado em vez de data inventada —
  o painel pode não saber ler um carimbo, não pode fabricar um.
- **O cabeçalho ganha a data** pelo `--uma-vez >> registro.log`: num arquivo que
  acumula por dias, `12:57:11` sozinho não diz de quando é.
- **Cada parada mostra o intervalo desde a anterior** (`+12min`). A data responde
  *quando*; o intervalo responde *quanto tempo levou* — e era a informação que o
  painel nunca teve, não a que a data substituiu. É também o "trabalho por
  iteração" que a P-05 pede e que nenhuma rodada tinha medido.
  `ultimas_paradas` passa a ler **uma parada a mais** do que exibe: o intervalo
  da linha mais antiga da tela depende da anterior a ela, que já saiu da janela.
- O intervalo é rotulado como **fato medido, não tempo de trabalho**: entre a
  `#5` e a `#6` de 17/08 há meia hora em que o loop estava encerrado esperando um
  `retomar`. O painel mede o relógio; inferir produtividade dali é de quem lê.

Mudança só em `loop_watch.py` — leitura pura, fora do caminho do hook — porque a
rodada do EOP estava **rodando** na hora, e o hook roda do symlink: erro em
`lib/` ou no hook faria ele sair fail-open e travaria a rodada no meio.

**Testes: 172 → 184.** Seis do painel, seis do classificador (quatro de
regressão, dois por marcador nos dois sentidos, mais a catraca meta e a prova de
execução dela).

| Controle desligado | Testes que caem |
|---|---|
| painel deixa de calcular o intervalo entre paradas | 2 |
| carimbo volta a ser só `hh:mm` (`ts[11:16]`) | 1 |
| não lê a parada extra — linha mais antiga fica sem intervalo | 1 |
| marcador volta a ser nu (sem `\s*:`) | ⛔ **não medido** |

⛔ A mutação dos três marcadores **não foi rodada**: o agente do EOP estava
editando `classificador.py` no mesmo minuto, e mutar-e-restaurar teria apagado o
que ele gravasse no meio. A catraca meta cobre a **forma** do padrão; falta o
número de testes que cada marcador derruba. Rodar quando a rodada encerrar.

⛔ **Falta o mesmo conserto no `INDEX.md`**, que é o registro durável e hoje não
tem timestamp **nenhum** — nem hora. Adiado de propósito: mexe em
`estado.py::indexar`, que o hook consome, e a rodada estava viva.

### `0.2.3` — 2026-08-17 — a pergunta não era item, e o painel não era testemunha

Um painel do EOP lido às 09:42 sobre uma rodada morta às 09:32. Quatro coisas
erradas nele, e a pior não era de exibição.

- **A pergunta virava item de fila — e foi ela que encerrou a rodada.** O fecho
  da parada `#0003` era *"**Pergunta:** sigo com esse discriminador…"*: `\bsigo
  (?:com|por|para|pra)\b` é HANDOFF, o parágrafo tem `:`, e a colheita levou o que
  vinha depois do último `:` para o `QUEUE.md` — com o `**` do negrito partido na
  frente. Marcada `- [x]`, ela zerou os pendentes e disparou *"fila zerada"*: uma
  condição de fim correta disparando sobre uma contagem que não devia existir.
  Agora candidato que **seja** ou **contenha** pergunta detectada é descartado,
  nas três zonas e **nos dois vereditos** — o ADR-005 continua de pé, porque o que
  muda não é *quando* se colhe, é *o quê* (emenda ao ADR-005).
- **O painel voltou a consumir a cadeia, em vez de manter a sua.** O `0.2.2`
  tirou a lista de condições do hook e deixou a do `loop-watch` de lado: sem
  kill-switch, sem sem-progresso, ordenada por tempo restante. Numa rodada
  **já encerrada por fila zerada**, ele marcava `← primeira` na janela — faltando
  2h18 — com *"fila zerada, 0 pendente(s)"* impressa duas linhas abaixo. Era a
  quarta cópia que o `diagnostico.py` foi escrito para impedir. A marca agora
  responde qual das três perguntas cabe: `← encerrou aqui` (fato gravado),
  `← já bateu: a próxima parada encerra` (aviso, numa rodada viva), `← primeira`
  (relógio — só quando nenhuma bateu). Emenda ao ADR-013.
- **O número da parada vem do nome do arquivo.** O painel lia o `n:` do
  front-matter, que até hoje de manhã era a iteração — e `armar` zera a iteração a
  cada rodada. Quatro paradas gravadas como `0001`..`0004` apareciam como
  `#4 #1 #2 #1`. Régua única em `estado.NUM_DE_ENTRY`, para quem escreve e para
  quem lê.
- **Objetivo ilegível é recusado também na saída.** A guarda de `armar` nasceu no
  `0.2.2`, depois de o `.loop/` do EOP já estar armado com `"¨¨"` — e estado
  gravado antes de uma guarda não passa a obedecê-la. O painel anunciou o mojibake
  por rodada inteira. Porta e vitrine agora medem com a mesma função
  (`estado.objetivo_legivel`), e a exibição diz **o que** há de errado e **com
  quê** consertar, em vez de trocar o lixo por um `—` que se confundiria com
  "não declarou objetivo".
- **`encerrado_detalhe` no `STATE.json`** (campo aditivo): o detalhe morava só no
  `STATUS.md`, em prosa. É ele que separa duas condições que dividem o mesmo
  motivo — `escopo concluído` por N itens × por marcador — e o que responde
  "zerada com quantos?" sem abrir outro arquivo.
- O cabeçalho do painel diz **há quanto tempo** encerrou: ele carimba a hora da
  *leitura*, e 09:42 sobre uma rodada morta às 09:32 parecia rodada de agora.

**16 testes novos** (10 em `test_watch.py`, 6 em `test_classificador.py`, 1 em
`test_ciclo.py`), total **171**.

| Controle desligado | Testes que caem |
|---|---|
| painel volta a ranquear por relógio (ignora `encerrado_por`) | 3 |
| pergunta volta a virar item de fila | 2 |
| `quem_encerra` não consulta `condicoes_de_fim` | 2 |
| painel volta a ler o `n:` do front-matter | 1 |
| objetivo ilegível passa na régua (porta e vitrine) | 1 |
| `_linha_do_motivo` ignora o detalhe (escopo ambíguo) | 1 |
| hook para de gravar `encerrado_detalhe` | 1 |
| `_dedup` sem tirar marcação solta das pontas | 1 |

**Medição que a rodada rendeu (P-05):** duas rodadas reais no EOP, **as duas**
encerradas por `fila zerada` — nenhuma bateu em janela, relógio, teto ou
sem-progresso. E a de 17/08 zerou por item espúrio: das suas 2 iterações,
**zero** itens reais da fila foram fechados. Duas rodadas não são distribuição,
mas a leitura preliminar é que a fila acaba antes de tudo o mais.

### `0.2.2` — 2026-08-17 — o fail-open era mudo: `loop-ctl porque`

Hoje o "continua" digitado no EOP não continuou, e a investigação à mão levou uma
manhã. O hook estava certo: `ativo: false` desde 16/08 às 21:19, e ele sai no
primeiro portão com `exit 0` sem escrever nada (ADR-009). **Havia três portões
fechados no mesmo `.loop/`** e nenhuma linha de log sobre nenhum: o `ativo`, o
`session_id` da sessão de ontem, e o relógio de 2 h estourado. O defeito não é o
portão — é não haver como perguntar (ADR-013).

- **`loop-ctl porque`** percorre os portões na ordem em que o hook os testa —
  hook instalado, `.loop/`, `ativo`, `fase`, amarração à sessão — para no
  primeiro que barra, e segue para as condições de fim quando nenhum barra. Sai
  `1` quando algo barra, `0` quando o loop continuaria. Alias: `diagnostico`.
- **A cadeia de condições de fim passa a ter uma cópia só**
  (`lib/diagnostico.py::condicoes_de_fim`), consumida pelo hook em vez da própria
  cadeia `if/elif`. A lista já vivia em três lugares; uma quarta apodreceria, e
  diagnóstico que mente sobre a ordem é pior que nenhum.
- **`retomar` re-amarra a sessão** (emenda do ADR-008): limpa o `session_id`, a
  menos que `--sessao` venha explícito. Quem retoma retoma no dia seguinte, em
  sessão nova — e o id preservado fazia o hook sair em silêncio no portão da
  sessão. `retomar` também avisa quando a fila está vazia ou o relógio estourou,
  os dois fatos que reativar **não** conserta (relógio pede `armar`).
- **O painel do `loop-watch` diz "hook inerte"** quando o loop está parado, com
  a linha da sessão amarrada. "PARADO" era lido como "entre duas iterações".
- `--raiz` passa a valer **antes ou depois** do subcomando: a ordem natural era
  erro de uso, justamente no comando que socorre quem está no escuro.

**54 testes novos** (49 em `tests/test_diagnostico.py`, 5 em `test_watch.py`),
total **155**. Entre eles o que impede o espelho de desalinhar: cada estado que faz o
hook calar vai ao hook (subprocesso) **e** ao diagnóstico, e o silêncio de um tem
de corresponder ao portão nomeado pelo outro.

Mutação de cada controle novo, com o número de testes que cada uma derruba:

| Controle desligado | Testes que caem |
|---|---|
| `retomar` volta a preservar o `session_id` | 1 |
| painel sem o aviso de hook inerte | 2 |
| painel sem a linha da sessão amarrada | 1 |
| portão `ativo` informa em vez de barrar | 4 |
| portão da sessão não barra | 3 |
| settings ilegível vira veredito de hook ausente | 3 |
| kill-switch deixa de vir primeiro na cadeia | 5 |
| `condicoes_de_fim` reconta a fila em vez de usar a contagem recebida | 1 |
| avisos de rearme (fila vazia, relógio) desligados | 3 |
| `--raiz` volta a valer só antes do subcomando | 1 |

### `0.2.1` — 2026-08-16 — `loop-watch`: acompanhar de longe

`watch -n 30 loop_ctl.py status` re-renderiza a mesma tela e **não responde as
duas perguntas de quem está longe do monitor**: *andou?* e *quanto falta?*.

`skill/loop/loop_watch.py` responde as duas:

- **delta entre leituras** — `+3 parada(s), +2 item(ns) fechado(s)`, ou
  "sem mudança"; é a única coisa que uma tela repintada não dá;
- **tempo restante de cada condição de fim**, com a que vai bater primeiro
  marcada (`← primeira`). Para isso nasceu `minutos_ate_fechar` no motor, que
  cruza a meia-noite e devolve `None` para janela inválida — nunca inventa
  número;
- barra de progresso da fila, próximo item, e as últimas paradas com
  **ASK sinalizada** (premissa foi registrada) e **fecho parcial sinalizado**
  (o defeito do ADR-012, visível de longe se voltar);
- `--uma-vez` (cron/log), `--ate-encerrar` (sai com sino quando o loop para),
  `--raiz`, `--sem-cor`. Sem cor automaticamente quando a saída não é terminal.

O `install.sh` passa a criar os atalhos **`loop-watch`** e **`loop-ctl`** em
`~/.local/bin` (shim, não symlink — deixa explícito qual repositório serve), e
avisa se o diretório não está no PATH. `--uninstall` remove os dois.

**18 testes novos** (`tests/test_watch.py`), total **101**.

### `0.2.0` — 2026-08-16 — primeira rodada real, e o defeito que ela revelou

**O loop rodou em trabalho de verdade** (EOP, 20:11→21:19): armado com fila de
21 itens e janela até 22h, fechou **21/21**, encerrou pela condição declarada
(fila zerada), mandou o agente enviar a push notification e parou. **Duas
paradas em 68 minutos** — uma única continuação substituiu o "continua" que
custaria 10 minutos de tela apagada. Saldo do outro lado: 72 arquivos tocados,
`version.md` do EOP de 1.27.11 → 1.29.0, ADR-081 escrito lá, e um
`ASSUMPTIONS.md` registrando as três premissas com o custo de desfazer cada uma.

**E a auditoria da rodada achou o defeito central do produto (ADR-012).** As
duas `entries` arquivadas eram **fragmentos de meio de raciocínio**, não
relatórios: o hook `Stop` dispara antes de o Claude Code gravar o último bloco
de texto no JSONL. Na parada #2 ele leu às 00:19:22 um texto de **00:12:30** —
154 entradas atrás — enquanto o relato verdadeiro era escrito naquele segundo.
Ler o retorno e documentá-lo **é** o produto, e ele documentava a coisa errada,
em silêncio: a decisão de continuar não depende do texto, então nada denunciava.
O único sinal era o `confianca: media` que o classificador registrou nas duas.

**Conserto:** a leitura passa a responder se o texto é o **fecho do turno**
(nada do agente principal depois dele) e **espera** até 3 s pelo fecho, relendo
a cada 100 ms. Estourando, segue mesmo assim — mas grava `fecho_do_turno:
PARCIAL`, derruba a confiança para `baixa` e diz na evidência que aquilo não é
o relatório. Subagente não conta como conteúdo depois; `AskUserQuestion` fecha
o turno por si e não gera espera.

**11 testes novos** (`tests/test_transcricao.py`), com a corrida reproduzida de
verdade: o fecho é escrito por outra thread **durante** a espera. Total **83**.
Mutação: desligar a espera derruba as duas regressões e devolve exatamente o
comportamento de 16/08.

**Ainda não feito:** a espera resolve a corrida do fecho, não mede quanto dela
sobra em sessões maiores — o teto de 3 s é escolha, não medição (P-07).

### `0.1.0` — 2026-08-16 — F0 e F1: proposta fechada e motor determinístico

Nasce a skill que faz o agente trabalhar sem "continua" a cada cinco minutos.
Proposta fechada com o Samir na conversa de 16/08, e o núcleo entregue no mesmo
dia — a documentação e o código saíram juntos porque o classificador só ficou de
pé depois de calibrado contra **duas mensagens reais** do agente dele,
publicadas anonimizadas (originais em `fixtures-reais/`, fora do git).

**Decidido** (ADR-001 a ADR-009): gatilho é hook `Stop`, não skill nem timer;
`stop_hook_active` não serve de trava; ASK sempre continua com premissa
registrada; classificação por **zona e direção**, não por pontuação; itens do
fecho e pendências declaradas viram fila; `QUEUE.md` é a fonte do próximo passo;
fail-open; auto-amarração à sessão; notificação push pelo próprio agente.

**Entregue e testado** — 72 testes, controles verificados por mutação:

- `skill/loop/lib/classificador.py` — ASK × DOC por zona de fecho, supressão de
  retórica auto-respondida, léxico de handoff PT-BR/EN, colheita de itens com
  split ciente de parênteses, colheita de pendências declaradas.
- `skill/loop/hooks/loop-stop.py` — o hook: classifica, arquiva, decide e
  devolve `decision: block` com o próximo item. Fail-open em qualquer erro.
- `skill/loop/lib/estado.py` — `.loop/` inteiro: estado, fila, entries, índice,
  premissas, status, impressão digital de progresso.
- `skill/loop/lib/transcricao.py` — leitura pela cauda do JSONL, filtro de
  subagente.
- `skill/loop/loop_ctl.py` — armar/parar/retomar/status/fila.
- `install.sh` — hook global idempotente que convive com os hooks `Stop` já
  instalados; `--dry-run` e `--uninstall`.

**Dois defeitos achados pelos próprios testes** antes de qualquer uso: o
comentário de proveniência entrava na chave de dedup (item recolhido a cada
parada) e vazava para o prompt; e encerrar com `notificar: false` deixava o loop
ativo.

**Ainda não feito:** operação em trabalho real (F2) — nenhum número de campo
existe. Ver `.continue/escopo-projeto.md`.
