# skill-LOOP — Decisões (ADRs)

Formato ADR. **Não relitigar direção já decidida dentro de um how-to** — linkar o
ADR. Decisão nova entra aqui, com data e status, no mesmo commit da mudança.

> Todas as decisões abaixo foram fechadas com o Samir na conversa de 2026-08-16,
> a partir de duas mensagens reais do agente dele (hoje `tests/fixtures/`).

---

## ADR-001 — Nasce o LOOP: o gatilho é o hook `Stop`, não uma skill nem um timer

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** o agente produz 5–10 min, encerra o turno e escreve um relato.
  Quem está longe do monitor vê 10 min depois e digita "continua". Em trabalho de
  meses, a maior parte do calendário é tela apagada. Medido nos dois casos reais:
  9m16s de produção seguidos de 10 min de espera; ~5 min seguidos de espera.
- **Alternativas descartadas:**
  1. **Só uma skill.** Skill é instrução que o modelo *lê*; ele continua
     encerrando o turno quando julga ter entregue um bloco. Não intercepta nada.
  2. **Loop por timer** (`/loop 5m continua`). Acorda no relógio: pode acordar no
     meio do trabalho, ou 4 min depois da parada. Tempo morto por construção.
- **Decisão:** hook `Stop`, que dispara **no instante** em que o turno encerra e
  pode devolver `{"decision": "block", "reason": ...}` para retomar o agente com
  instrução nova. O produto é o `reason`.
- **Nota:** é a mesma leitura do ADR-003 do COMMITTER — fim de turno é o único
  instante em que o estado do trabalho está em repouso.

---

## ADR-002 — `stop_hook_active` não é a trava; o contador é próprio

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** o campo `stop_hook_active` chega no payload e a documentação
  sugere usá-lo para evitar laço infinito (`if stop_hook_active: allow stop`).
- **Observação de campo:** ele vira `true` já na **segunda** parada e **não volta
  a `false`**. Com o padrão sugerido, o loop daria **uma** continuação e morreria
  — exatamente o comportamento que o projeto existe para eliminar.
- **Decisão:** registrar e ignorar. O limite é próprio, em `STATE.json`, com
  quatro dimensões independentes (iterações, progresso, fila, e as condições do
  ADR-010).
- **Consequência:** o risco de laço infinito passa a ser nosso, e o detector de
  **loop degenerado** (impressão digital de árvore + fila) vira controle de
  segurança, não conveniência (T-02).

---

## ADR-003 — ASK sempre continua, com premissa registrada

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** três opções foram postas ao Samir: (a) continuar sempre com
  premissa documentada, (b) continuar exceto em decisões irreversíveis, (c) parar
  em toda pergunta.
- **Decisão do Samir:** **(a)**. Pergunta vira `entry` marcada `ASK`, o agente
  adota o default mais razoável **e reversível**, registra em
  `.loop/ASSUMPTIONS.md` (pergunta · decisão · alternativa descartada · como
  reverter) e segue.
- **Consequência aceita:** nada mecânico impede o agente de decidir algo caro no
  default. O controle é o registro revisado depois, e está declarado como limite
  em T-03. As opções (b) e (c) ficam disponíveis por configuração
  (`politica_ask`), não por default.
- **Contrapartida:** revisar `ASSUMPTIONS.md` deixa de ser opcional — é o preço
  de não ter sido interrompido, e a skill diz isso ao usuário.

---

## ADR-004 — Classificar por zona e direção, não por pontuação

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** a intuição inicial era "se tem `?`, é pergunta". As duas
  mensagens reais quebram isso em sentidos opostos, na mesma tarde:
  - **falso ASK** — *"…merecia a pergunta seguinte: quantas outras estão assim?
    Varri as migrações dos dez schemas — sobrava uma."* Tem `?`, e o próprio
    texto responde na frase seguinte.
  - **falso DOC** — *"o que sobra de maior valor está do teu lado da mesa: a
    convenção do default no OpenAPI, a ✦A, a ✦B corrigida e as respostas
    X1–Y2."* **Zero `?`**, e é exatamente onde o agente parou de trabalhar.
- **Decisão:**
  1. **Zona de fecho** = os 2 últimos parágrafos, **por posição**. Handoff e
     pergunta ali valem; no meio da narrativa, valem menos.
  2. **Direção** — léxico de entrega de bastão (PT-BR/EN) pesa mais que
     pontuação, e sozinho classifica ASK.
  3. **Supressão de retórica é propriedade da frase, não da posição**: um `?`
     anunciado (`a pergunta seguinte:`) ou cuja frase seguinte **relata ação
     concluída** é retórica em qualquer zona.
- **Revisão dentro do mesmo dia:** a primeira versão definia o fecho por
  acumulação de caracteres (≥300) e amarrava a supressão à zona. Em mensagem
  curta o fecho engolia o texto inteiro e a supressão desligava — dois testes
  falharam e a regra foi trocada pela atual. Registrado porque o erro é
  atraente: parece mais robusto medir por tamanho.
- **Limite declarado:** o classificador é léxico. Handoff escrito fora do léxico
  passa como DOC (T-04). Desempate por modelo é v2.

---

## ADR-005 — Colher itens do fecho e pendências declaradas para a fila

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** a segunda mensagem real é DOC puro — nenhuma pergunta, nada a
  decidir. Mas o item mais valioso dela é a seção **"Declarado e não feito:"**,
  onde o próprio agente nomeia o próximo trabalho ("os dois irmãos seguem sem
  teste… candidato natural para a próxima rodada"). Um classificador só de
  perguntas perde isso inteiro.
- **Decisão:** a colheita é **independente do veredito ASK/DOC**:
  1. do **fecho de handoff**, a enumeração em prosa ou lista markdown;
  2. de **qualquer zona**, a pendência que o agente declarou (`declarado e não
     feito`, `fica para a próxima`, `candidato natural`, `ficou de fora`,
     `follow-up`…).
  Itens vão para `## Colhidos automaticamente` no `QUEUE.md`, com proveniência,
  dedup contra a fila inteira e teto de 12 por parada.
- **Detalhe que virou teste:** o split da prosa é **ciente de parênteses** e exige
  artigo depois da vírgula. Sem isso, `(coluna versao no Ciclo e no Período)`
  vira dois itens e a fila enche de fragmento.
- **Consequência:** o loop raramente fica sem fila — e quando fica, é sinal
  honesto de fim, não de perda de fio.

### Emenda de 2026-08-17 — a pergunta não é item

- **O que aconteceu:** no EOP, a parada `#0003` fechou com *"**Pergunta:** sigo
  com esse discriminador, ou você quer a guarda de fato-sem-listener mesmo
  assim?"*. `\bsigo (?:com|por|para|pra)\b` é HANDOFF; o parágrafo tem `:`; a
  colheita pegou o que vinha depois do último `:` e **a própria pergunta virou
  item de fila** — com o `**` do negrito partido na frente. Ela foi marcada
  `- [x]`, os pendentes foram a zero, a condição *"fila zerada"* disparou e a
  rodada encerrou às 09:32. Uma condição de fim correta, disparando sobre uma
  contagem que não devia existir.
- **Decisão:** candidato de colheita que **seja**, ou **contenha**, uma pergunta
  já detectada é descartado — nas três zonas (direta no fecho, direta na
  narrativa, retórica) e **nos dois vereditos**.
- **O que a emenda não muda:** a colheita continua **independente do veredito**,
  que é o coração do ADR-005. O filtro roda igual em ASK e em DOC. O que se
  corrige não é *quando* se colhe — é *o quê*.
- **Justificativa:** a colheita procura trabalho **declarado pendente**; a
  pergunta é o oposto — é trabalho que o agente declarou que *não* faz sem
  resposta. E ela já tem três lugares seus: a entry, o `INDEX.md` e a premissa do
  `ASSUMPTIONS.md` (ADR-003). Um quarto lugar, na fila, não a preserva melhor:
  torna-a **marcável como feita**, e um `- [x]` numa pergunta é o loop dizendo
  que respondeu a si mesmo.
- **Onde erra de propósito:** contenção com alvo curto acha qualquer coisa dentro
  de pergunta longa, então há piso de 12 caracteres. Abaixo dele o item passa —
  colher a mais deixa uma linha extra na fila, colher a menos apaga trabalho
  declarado, e só o segundo é silencioso.
- **Consequência:** condição de fim por fila zerada volta a medir trabalho. Uma
  rodada que termina é uma rodada que acabou o que tinha a fazer, não uma que
  perguntou alguma coisa.

---

## ADR-006 — `QUEUE.md` é a fonte do "próximo passo"

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** três opções para o que o `reason` deve mandar fazer: fila
  destilada da documentação, continuação genérica apontando para a doc, ou a
  todo list nativa do agente.
- **Decisão do Samir:** **fila destilada**. A skill lê a documentação inteira
  antes de armar e escreve `- [ ]` por unidade executável.
- **Justificativa:** "continua" sozinho faz o agente re-planejar a cada turno e
  derivar. Todo list nativa é volátil entre sessões e compactações — sumiria no
  meio de meses de trabalho. A fila em arquivo dá progresso mensurável
  (denominador), sobrevive à sessão, e é o critério de pronto do ciclo.
- **Consequência:** **fila ruim = loop ruim**, e o hook não detecta isso. Por
  isso a skill mostra a fila ao usuário antes de armar — última chance barata de
  corrigir rumo.

---

## ADR-007 — Hook global, opt-in por repositório, em grupo próprio

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** o hook precisa existir antes de alguém decidir usar o loop; e o
  ambiente do Samir já tem hooks `Stop` (ai-memory) — e terá o do COMMITTER.
- **Decisão:**
  1. Instalação **global** em `~/.claude/settings.json`, anexando um **grupo
     próprio**; os hooks existentes nunca são reescritos. Todos rodam; só o LOOP
     devolve `decision: block`.
  2. A guarda não é a instalação: é o **opt-in por `.loop/STATE.json` com
     `ativo: true`** no repositório. Sem ele, `exit 0` em milissegundos.
  3. Backup datado do `settings.json` antes de qualquer escrita; `--dry-run` e
     `--uninstall` obrigatórios; desinstalar **não** toca em nenhum `.loop/`.
- **Nota de campo (16/08):** o ambiente do Samir já mostrava
  `Ran 2 stop hooks` com um deles falhando (`GitKrakenCLI … not found`). Hook
  `Stop` quebrado é ruído recorrente — motivo extra para o fail-open do ADR-009.

---

## ADR-008 — Amarração à sessão por auto-bind na primeira parada

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** `armar` roda de dentro da sessão, pela skill, e **não conhece o
  próprio `session_id`**. Sem amarração, qualquer chat aberto no mesmo
  repositório passaria a ser dirigido pelo loop.
- **Decisão:** armar grava `session_id: null`; a **primeira parada** grava o seu
  — é necessariamente a da sessão que armou. Depois disso, outra sessão é
  ignorada. `--qualquer-sessao` desliga para quem quiser o contrário.
- **Alternativa descartada:** exigir que o usuário passe o id à mão (ninguém
  sabe de cor) ou ler o transcript para inferi-lo (frágil e indireto).
- **Emenda (2026-08-17):** `retomar` também limpa o `session_id`. A decisão é a
  mesma — auto-bind na primeira parada — aplicada ao segundo comando que reativa
  o loop. O que faltava: `retomar` preservava o id da rodada anterior, e como
  quem retoma retoma no dia seguinte, em sessão nova, o hook saía **em silêncio**
  no portão da sessão. Custo medido: uma manhã de 17/08 achando que o loop estava
  rodando. `--sessao` continua atalhando para quem sabe o id.

---

## ADR-009 — Fail-open, e a notificação é do agente

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** um hook `Stop` que estoura ou trava pode inutilizar o Claude Code
  da máquina inteira, em **todos** os repositórios. E o Samir pediu notificação
  push ao fim do loop — mas o hook é um script, sem acesso às tools do agente.
- **Decisão:**
  1. **Fail-open absoluto:** qualquer exceção → `exit 0`. O pior caso vira o
     comportamento de hoje (digitar "continua"), nunca uma sessão travada.
     Vale também para dado ausente: transcript ilegível classifica como DOC
     vazio e o loop **segue** — perder a mensagem não pode significar perder o
     trabalho.
  2. **A notificação é emitida pelo agente**, não pelo hook: ao encerrar, o hook
     dá um **último** `block` mandando enviar a push e não retomar trabalho; a
     parada seguinte encerra de vez (`fase: encerrando`). Usa a tool que o agente
     já tem, sem credencial nem rede no script.
- **Consequência:** com `notificar: false` não há turno seguinte para consumir a
  fase, então o encerramento precisa desativar na hora — bug encontrado por
  teste antes de qualquer uso.

---

## ADR-010 — Condições de fim: escopo e horário, além dos tetos

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** o Samir levantou, antes de qualquer uso real: *"pode ser caro se
  este skill começar e não tiver um fim"*. Os tetos originais (iterações, sem
  progresso, fila zerada) respondem "não rode para sempre", mas não respondem
  "rode **até onde** eu quero" nem "rode **quando** eu quero".
- **Decisão:** quatro condições opcionais, combináveis, verificadas a cada
  parada, somadas às três já existentes:
  1. **escopo por itens** — `--itens 10`: fecha N itens **desta rodada** e para.
     Denominador gravado em `armar` (`feitos_ao_armar`), senão trabalho de
     rodadas anteriores contaria.
  2. **escopo por marcador** — `--ate "3.10"`: para quando o item que contém o
     texto for marcado `[x]`.
  3. **janela de horário** — `--janela 08:00-18:00 --dias seg-sex`. Cruza a
     meia-noite; **formato inválido nunca encerra** (typo não pode parar o
     trabalho em silêncio).
  4. **relógio** — `--duracao 6h` desde que armou.
- **Recomendação registrada:** ao armar, preferir **duas** condições — uma de
  escopo e uma de tempo. Elas se cobrem quando a fila é maior ou menor do que
  parecia.
- **Fora de escopo (F3):** **rearme automático**. Fechada a janela das 18h, o
  loop encerra; às 8h do dia seguinte retomar é comando. Automatizar exige cron,
  e segue a decisão do ADR-003 do COMMITTER — crontab do Linux, nunca rotina
  agendada do Claude Code (roda na nuvem, não enxerga `~/x`).

---

## ADR-011 — Fixtures reais, publicados anonimizados

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto:** o Samir pediu o repositório **público**. Os dois fixtures são
  mensagens reais do agente dele e carregam nome de classe, tabela, constraint,
  módulo, item de roadmap, versão de SPEC interna — e a descrição de **como uma
  corrida em produção funcionava antes do conserto**. Histórico de git público é
  permanente e indexado; apagar depois não resolve.
- **Alternativas descartadas:**
  1. **Publicar como estão** — a calibração fica verificável por quem lê, mas
     expõe arquitetura interna e um defeito de concorrência de um produto
     comercial.
  2. **Repositório privado** — some a decisão, e some o benefício de publicar.
  3. **Fixtures sintéticos** — descartada antes: mensagem inventada não teria
     produzido o classificador. Foi a estrutura real que derrubou o detector de
     `?`, nos dois sentidos, no mesmo dia.
- **Decisão do Samir:** **anonimizar preservando a estrutura**. Trocam-se nomes
  próprios; preservam-se contagem e ordem de parágrafos, a retórica
  auto-respondida, o fecho sem `?`, o parêntese com `" e no "` dentro, a linha
  de estatística e a seção "Declarado e não feito". Originais em
  `fixtures-reais/`, no `.gitignore`.
- **Critério de aceite mecânico:** as duas versões precisam **classificar
  idêntico** (`kind`, `sinal`, `confiança`, nº de itens, nº de retóricas, nº de
  parágrafos de fecho). Verificado em 16/08 e roteirizado em
  `fixtures-reais/README.md`. Anonimização que muda o veredito apagou sinal e
  precisa ser refeita.
- **Evidência de que preservou:** depois da troca, a suíte segue em 72 verdes e
  a mutação derruba **exatamente os mesmos** testes de antes (handoff 6, zona 5,
  retórica 2, parênteses 2, código 1).

---

## ADR-012 — O hook espera o fecho do turno antes de ler

- **Data:** 2026-08-16 · **Status:** Aceito
- **Contexto — defeito medido em produção, na primeira rodada real.** O loop
  rodou no EOP das 20:11 às 21:19 e fechou 21/21 itens. Ao auditar o
  `.loop/entries/`, as duas mensagens arquivadas eram **fragmentos de meio de
  raciocínio**, não relatórios: *"O controle em que apoiei a correção também
  não tem testemunha. Vou fechar:"* e *"**D1** — releitura: conferindo cada
  afirmação nova contra a fonte."*
- **Causa, medida no transcript:** o hook `Stop` dispara **antes** de o Claude
  Code terminar de gravar o último bloco de texto no JSONL. Na parada #2, o
  hook leu às 00:19:22 e o texto mais recente no arquivo era de **00:12:30** —
  154 entradas atrás, com 21 `assistant[tool_use]` e seus `tool_result` entre
  os dois. O relato verdadeiro (*"Fila zerada — 21/21…"*) tinha timestamp
  **00:19:22**: estava sendo escrito naquele instante.
- **Gravidade:** é a promessa central do produto falhando **em silêncio**. Ler o
  retorno e documentá-lo era o produto; ele documentava a coisa errada. E o
  loop seguiu funcionando, porque a decisão de continuar não depende do texto —
  então nada denunciava o defeito, exceto o `confianca: media` que o próprio
  classificador registrou nas duas entries (não achou marca de relato nenhuma
  porque não estava lendo relato nenhum).
- **Decisão:**
  1. A leitura passa a responder **se o texto encontrado é o fecho do turno**:
     é fecho quando não há conteúdo do agente principal depois dele. `tool_use`
     e `tool_result` depois = resto velho.
  2. Sendo resto velho, o hook **espera** (releitura a cada 100 ms) até
     `LOOP_ESPERA_MAX_S` (**3 s**, teto bem abaixo do timeout de 15 s do hook).
  3. Estourando a espera, o loop **segue mesmo assim** (fail-open — ADR-009),
     mas a `entry` grava `fecho_do_turno: PARCIAL`, a confiança cai para
     `baixa` e a evidência diz que aquilo não é o relatório. **Dado duvidoso
     rotulado vale mais que dado duvidoso silencioso.**
  4. Duas exceções ao "esperar": **subagente** (`isSidechain`) não conta como
     conteúdo depois — senão todo turno com `Explore` gastaria o teto à toa; e
     **`AskUserQuestion` fecha o turno por si** — o turno para na tool, à espera
     do humano, e não há texto de fecho a aguardar.
- **Alternativa descartada:** ler o `stop_hook_active` ou algum campo do payload
  para saber se o turno fechou. Não existe tal campo — o único sinal disponível
  é a forma do próprio transcript.
- **Consequência declarada:** o hook passa a poder gastar até 3 s numa parada.
  É o preço de arquivar o texto certo, e o loop já é assíncrono por natureza.

---

## ADR-013 — O silêncio do fail-open precisa de um comando que fale

- **Data:** 2026-08-17 · **Status:** Aceito
- **Contexto:** em 17/08 o "continua" digitado no EOP não continuou, e a
  investigação à mão levou uma manhã para achar **três** portões fechados no
  mesmo `.loop/`: `ativo: false`, `session_id` da rodada de ontem, e relógio de
  2 h estourado. O hook estava certo em cada um — ele é fail-open e sai `exit 0`
  sem escrever nada (ADR-009), e é isso que impede um hook global de travar o
  Claude Code da máquina. O defeito não é o portão; é **não haver como
  perguntar**.
- **Decisão:**
  1. `loop-ctl porque` percorre os portões na ordem em que o hook os testa e
     nomeia o primeiro que barra, com o conserto — inclusive as condições de fim
     e os dois fatos que reativar não conserta (fila vazia, relógio estourado).
     Sai `1` quando algo barra, `0` quando o loop continuaria.
  2. A cadeia de condições de fim passa a ter **uma** cópia
     (`lib/diagnostico.py::condicoes_de_fim`), consumida pelo hook. Diagnóstico
     que mente sobre a ordem é pior que nenhum, e a lista já existia em três
     lugares.
  3. Os portões anteriores a qualquer mutação continuam **espelho**, não fonte:
     o hook muta estado em dois deles (consome `fase: encerrando`, auto-amarra) e
     mutação não cabe num diagnóstico. O preço do espelho é teste emparelhado —
     o mesmo estado vai ao hook (subprocesso) e ao espelho, e o silêncio de um
     tem de corresponder ao portão nomeado pelo outro.
  4. O painel do `loop-watch` diz "hook inerte" quando o loop está parado:
     "PARADO" era lido como "entre duas iterações".
- **Alternativa descartada:** o hook passar a logar por que saiu. Log em portão
  de inércia contraria o motivo de o portão existir (sair em milissegundos, em
  qualquer repositório da máquina, sem escrever em disco fora de `.loop/`), e
  ainda assim não responderia a pergunta em repositório onde o `.loop/` nunca
  existiu.
- **Consequência:** "não continuou" deixa de ser investigação e passa a ser um
  comando. `loop-ctl porque` antes de sair de perto do monitor é o rito novo.

### Emenda de 2026-08-17 (tarde) — o painel também consome a cadeia

- **O que aconteceu:** o item 2 acima tirou a cadeia do hook, mas o
  `loop-watch` seguiu com a **sua** lista — e ela tinha as condições erradas (sem
  kill-switch, sem sem-progresso), na ordem errada (por tempo restante), com o
  veredito errado. No EOP, num painel de rodada **já encerrada por fila zerada**,
  a marca `← primeira` apontava a janela, faltando 2h18, enquanto *"fila zerada,
  0 pendente(s)"* estava impressa duas linhas abaixo. Era a quarta cópia que o
  `diagnostico.py` foi escrito para impedir, escrita pela mesma mão, no mesmo dia.
- **Decisão:** o painel **pergunta**, não opina. `loop_watch.condicoes` devolve
  a cadeia na ordem do hook e cada linha carrega o `motivo` com que
  `condicoes_de_fim` a nomeia; `quem_encerra` separa três perguntas que o painel
  respondia como uma:
  1. a rodada morreu? o motivo é fato gravado (`encerrado_por`) → `← encerrou aqui`;
  2. está viva e alguma condição **já** é verdadeira? → `← já bateu: a próxima
     parada encerra` (aviso, não previsão);
  3. nenhuma bateu? só então vale a que chega primeiro no relógio → `← primeira`.
- **Regra que fica:** *ordenar por tempo restante só decide entre as condições
  que ainda não bateram.* Qual delas manda é a cadeia que decide.
- **Consequência:** um painel de rodada morta para de projetar futuro, e um
  painel de rodada viva ganha um aviso que não existia — "a próxima parada
  encerra" é acionável enquanto ainda dá tempo.

---

## ADR-014 — Reabastecimento é item na cauda da fila, não flag

- **Data:** 2026-08-17 · **Status:** Aceito
- **Contexto:** o modo de uso do dono não estava previsto no produto. Ele arma por
  **tempo** (`--duracao 6h`, sem objetivo) esperando que o loop puxe o próximo
  documento e siga; mas `fila zerada` é a condição **#4** e o relógio é a **#6**,
  então a fila vazia dispara sempre antes. Em três rodadas do EOP o `--duracao`
  **nunca chegou a valer**. O desenho assumia fila destilada antes de armar, com
  fila vazia como critério de pronto (ADR-006) — e assume ainda: o que faltava era
  o que reabastece a fila.
- **Decisão:** o reabastecimento é **trabalho comum**, não mecanismo: um item
  `- [ ]` na cauda do `QUEUE.md` que manda destilar o próximo bloco e **repor-se**.
  Canônico em [prompts/reabastecer.md](../prompts/reabastecer.md). Funciona porque
  o hook lê o `QUEUE.md` do disco no instante do `Stop`, depois de o agente já ter
  escrito nele. Duas cláusulas não são opcionais:
  1. **Escopo declarado**, com o que "para e pergunta". Sem ele o reabastecimento
     puxa trabalho que era decisão do dono, e o loop decide no lugar dele.
  2. **Escape da reposição.** Quando a medição diz que não há bloco em escopo, o
     item **não** se repõe: registra o veredito com os números e deixa a fila
     zerar. Cumprir a cláusula sem insumo obriga a **fabricar** trabalho — e prosa
     sem lastro, num repositório onde a documentação é fonte de verdade, é pior
     que parar.
- **Alternativa descartada:** desenhar `--reabastecer N` antes de saber como o
  padrão se comporta. A decisão de 17/08 foi testar o contorno sem código novo
  justamente para o teto da flag nascer **medido**. Se a flag existir um dia, o
  número já está: 13 reposições numa rodada.
- **Medição que fechou a decisão** (EOP, 17/08): 14 paradas seguidas **sem
  encerrar** (`#6`…`#19`), 13 delas com o REABASTECER como item da fila, fila de
  22 → 66 itens, intervalos de 25 · 14 · 10 · 10 · 7 min. O fim veio **por
  veredito escrito**, não por esquecimento: das sete hipóteses tabeladas, três
  viraram bloco, uma era dívida real e três mediram zero — e o agente quebrou a
  cláusula de reposição de propósito, documentando o porquê no próprio `QUEUE.md`.
- **Consequência:** a promessa de "horas sem digitar continua" passa a depender de
  um artefato que **alguém precisa colar na fila**. Está no `SKILL.md` como passo
  1.1 e o `armar` aponta para ele ao recusar fila vazia — mas não é automático, e
  isso é a decisão, não um esquecimento.
  → **Revisto pelo [ADR-015](#adr-015--fila-vazia-com-relógio-não-encerra-o-motor-reabastece)
  em 17/08:** esta consequência caiu para a rodada **com relógio**, onde o motor
  passou a reabastecer sozinho. As duas cláusulas normativas continuam valendo
  integralmente, e o item na cauda segue sendo o mecanismo da rodada **sem**
  relógio.
- ⛔ **Não medido:** se o trabalho puxado pelo próprio loop **deriva** ao longo de
  muitas voltas. Era a terceira pergunta do experimento e exige ler o que as 44
  linhas novas produziram, não contá-las. Segue na P-05.

---

## ADR-015 — Fila vazia com relógio não encerra: o motor reabastece

- **Data:** 2026-08-17 · **Status:** Aceito · **Revisa:** ADR-014 (a consequência,
  não as cláusulas)
- **Contexto:** a fila fazia **duas** coisas, e só uma era legítima. Como
  **conteúdo** ela é insubstituível — o hook injeta o primeiro `- [ ]` no `reason`
  porque "continua" sozinho faz o agente re-planejar e derivar (§4). Como
  **condição de fim** ela mandava na cadeia inteira: `pendentes == 0` era a #4 e o
  relógio a #6, então quem armava por tempo tinha o `--duracao` nunca chegando a
  valer. O ADR-014 contornou sem código e pediu medição antes de qualquer flag —
  *"se a flag existir um dia, o número já está: 13 reposições numa rodada"*. A
  medição existe. E o guarda-corpo que nasceu daquela rodada
  (`_recusar_fila_vazia`) passou a barrar exatamente o comando certo: o dono
  digitou `armar --raiz ~/x/EOP --duracao 6h` sobre fila 66/66 e tomou `erro:
  nenhum item - [ ] na fila`. Guarda-corpo que barra o caminho certo é defeito,
  não rigor. A pergunta do dono foi a mais curta possível: *"por que o loop está
  avaliando a fila? o trabalho do loop é meio que só dizer continua"*.
- **Decisão:** `fila zerada` **só encerra rodada sem relógio**. Com
  `duracao_max_min` ou `janela` declarados, a fila vazia sai da cadeia de fim e
  vira **turno de reabastecimento**, conduzido pelo hook por um **segundo
  template** (`prompts/reabastecimento.md`). Três peças:
  1. **Gatilho derivado, não flag nova** (`diagnostico.tem_relogio`): quem escreveu
     `--duracao 6h` já declarou que a missão é o relógio e a fila é rascunho.
     `STATE.json` não muda de contrato, e estado de versão anterior cai no
     comportamento antigo — que é o certo para rodada sem relógio.
  2. **Escopo por `--objetivo` + `.loop/SCOPE.md`** (opcional, lido **verbatim**).
     É a cláusula 1 do ADR-014 com endereço. Sem o arquivo o prompt **diz ao turno
     que a fronteira não foi declarada** e manda recusar o duvidoso: quem não sabe
     onde parar precisa saber que não sabe, senão infere uma fronteira e chama de
     escopo.
  3. **Fim por veredito, em `.loop/SEM-ESCOPO`** — a cláusula 2 do ADR-014 com um
     fim próprio. O agente mede que não há bloco em escopo, escreve os números, e
     a rodada encerra como `escopo esgotado`, com o veredito citado no `STATUS.md`.
- **Alternativas descartadas:**
  - **`--reabastecer N` como flag.** Redundante: quem arma por tempo quer isso
    sempre, e uma flag a mais para lembrar é uma flag a mais para esquecer — o
    esquecimento sendo justamente a rodada que morre na primeira parada.
  - **Fila vazia nunca encerrar.** Mais simples de explicar e pior: rodada sem
    relógio nem escopo ficaria sem fim natural. A fila **é** o critério de pronto
    da rodada por itens (ADR-006), e tirar isso dela era resolver um caso quebrando
    o outro.
  - **Só reordenar a cadeia** (relógio antes da fila). Não basta: com fila vazia e
    relógio de pé, o `reason` iria com `(fila vazia)` no lugar do item — uma ordem
    para executar o que não existe.
  - **Reusar `.loop/STOP` como veredito do agente.** Um arquivo só para ordem do
    dono e medição do agente apagaria **quem decidiu encerrar**, que é a primeira
    pergunta que se faz ao `STATUS.md` depois.
- **Consequências:**
  - `armar --duracao`/`--janela` deixa de recusar fila vazia (e avisa que a
    primeira parada é reabastecimento, e de onde sai o escopo). Sem relógio a
    recusa continua intacta.
  - `loop-watch` não pode mais marcar `fila zerada` como fim sob relógio — era o
    painel de 17/08 apontando o fim para o lugar errado, com `resta 5h22` duas
    linhas abaixo.
  - O anti-loop-infinito **não é novo**: `sem progresso` já cobre. Turno que repõe
    muda a contagem da fila (entra no sha1 da impressão) e zera o contador; turno
    que não produz nada acumula e encerra em 3. Verificado por mutação.
  - Quatro controles, quatro mutações, 228 testes verdes: desligar o gatilho
    derruba 10 testes; o veredito, 5; a guarda do `armar`, 4; a linha do painel, 2.
- ⛔ **Não medido:** se o reabastecimento **conduzido pelo motor** deriva menos ou
  mais que o conduzido pelo item na cauda. São dois prompts com as mesmas
  cláusulas e um contexto diferente (o do motor não vê a fila que o antecedeu).
  Junta-se à P-05.

---

## Pendências

| # | Pendência | Estado |
|---|---|---|
| P-01 | Versionar `.loop/` no repositório alvo ou ignorá-lo? Não há default seguro: versionar dá auditoria durável e arrisca segredo no histórico permanente (T-07). A skill precisa perguntar ao armar. | **aberta** |
| P-02 | Scan de segredo no texto antes de gravar a `entry` — vendorizar os padrões do `redact.py` do AUDITOR, como o COMMITTER fez. | aberta |
| P-03 | Desempate por modelo quando a confiança é `media` (v2). Hoje o veredito léxico vale. | aberta |
| P-04 | Rearme automático por cron ao reabrir a janela (F3). | aberta |
| P-05 | Medir em operação: iterações por sessão, distribuição das condições de fim, trabalho por iteração. Só o uso real dá esses números. **Duas rodadas no EOP, as duas encerradas por `fila zerada`** (16/08 21:19 e 17/08 09:32) — nenhuma bateu em janela, relógio, teto ou sem-progresso. E a de 17/08 zerou por item espúrio (a emenda do ADR-005): das 2 iterações, **zero** itens reais da fila foram fechados. Duas rodadas não são distribuição; a leitura preliminar é que a fila acaba antes de todo o resto. | aberta |
| P-06 | Teste de item hostil plantado numa mensagem (T-06). | aberta |
| P-07 | O teto de 3 s da espera pelo fecho (ADR-012) é **escolha, não medição**. Falta medir quanto o fecho realmente demora a chegar, e em que tamanho de sessão a espera estoura. | aberta |
| P-08 | **Rodada órfã: turno que morre sem emitir `Stop`.** O único gatilho é o hook, e `condicoes_de_fim` só é avaliada dentro dele — então erro de API a meio da resposta, crash ou queda de rede deixam a rodada pendurada em `ativo: true` e **nenhuma condição de fim pode encerrá-la**, nem o relógio, porque ele só é consultado numa parada que não vai acontecer. O painel mostra `relógio esgotado` e o loop segue "ativo"; `--ate-encerrar` nunca sai. Observado em 17/08 (`API Error: Server error mid-response` no EOP, às ~13:33). Não é o fail-open falhando — é o gatilho nunca disparando. Saídas a avaliar: `loop-watch` declarar a rodada órfã quando o relógio estoura sem parada nova; ou o rearme por cron da F3 varrer estado vencido. | aberta |
