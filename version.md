# Versão — skill-LOOP

**Versão atual:** `0.3.0`

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
