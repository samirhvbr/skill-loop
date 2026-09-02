# Versão — skill-LOOP

**Versão atual:** `0.2.5`

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

Pedido do Samir durante a rodada, e o defeito é o mesmo que o enganou de manhã: o
painel mostrou `09:32 · 09:03 · 21:19 · 20:24` nas últimas paradas, e as duas de
baixo eram do **dia anterior** — nada na tela dizia isso. Num registro que
atravessa a meia-noite, `hh:mm` sozinho engana com cara de dado.

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
