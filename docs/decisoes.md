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
- ⚠️ **A premissa do "necessariamente" foi DESMENTIDA por medição (01–02/09) —
  ver [P-09](#pendências).** A primeira parada é a da primeira sessão que
  **terminar um turno** no repositório, e essa pode ser qualquer chat já aberto
  ali: no EOP o loop adotou uma sessão que o dono havia aberto para triar PRs do
  Dependabot, enquanto o `loop.sh` armava de outra. O `print` do próprio `armar`
  já dizia a verdade — `sessão: a primeira que parar` — e é o texto desta decisão
  que está errado, não o código. A decisão **continua de pé** (auto-bind é a
  saída certa para quem não conhece o próprio id); o que cai é a garantia de que
  a sessão adotada é a que armou. O conserto exige emenda, e as saídas estão
  listadas na P-09.
- **Alternativa descartada:** exigir que o usuário passe o id à mão (ninguém
  sabe de cor) ou ler o transcript para inferi-lo (frágil e indireto).
- **Emenda (2026-09-02) — a adoção continua, e passa a ser PEDIDA.** O `armar`
  recusa-se a armar com `bind_session: true` e sem `--sessao`, e nomeia as três
  saídas: `--sessao <id>` (amarra a esta), `--adotar-primeira-parada` (aceita a
  adoção de propósito) e `--qualquer-sessao` (não amarra a nenhuma).
  > 🔴 **Errata de 2026-09-11 (`0.3.15`, caixa `A66` do EOP) — as três viraram
  > DUAS: o `--adotar-primeira-parada` saiu.** A emenda acima o criou porque
  > *"quem não sabe o id segue tendo um caminho de uma palavra"* — e o caminho
  > existia porque o `.loop/loop.sh` semeado **não tinha por onde passar
  > `--sessao`**. A `0.3.14` consertou o molde: ele exige o id. Sem chamador
  > legítimo, o flag virou a porta por onde a adoção volta a ser herdada, e a
  > reincidência de 10/09 (três adoções numa rodada só, apagando vínculo
  > correto) é o que o derrubou. ⛔ **A ordem foi do dono:** molde primeiro,
  > flag depois — o contrário empurraria todo chamador para `--qualquer-sessao`. ⚠️ **Isto
  NÃO ressuscita a alternativa descartada acima** — não se exige o id, exige-se
  *dizer qual das três*; quem não sabe o id segue tendo um caminho de uma
  palavra. O que muda é que a adoção deixa de ser **herdada por omissão**, que é
  o único jeito em que ela custou caro (a P-09 mede: 18 entradas no item errado,
  4 itens espúrios, duas sessões numa árvore). A guarda mora na **porta** porque
  no hook já é tarde: quando ele roda, a sessão errada já é a sessão. E ela
  recusa **sem gravar estado** — `.loop/` meio-armado é o defeito que o `0.2.3`
  já pagou com o `¨¨`, porque estado gravado antes de uma guarda não passa a
  obedecê-la depois.
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

## ADR-016 — The timed re-arm is a file in the target repo, not a line the operator memorises

- **Date:** 2026-09-02 · **Status:** Accepted · **Extends:** ADR-010 (end
  conditions), ADR-008 amendment (session adoption)
- **Observed fact.** Starting a timed round takes two commands, in two
  terminals, with a path in each: `loop-ctl armar --raiz <repo> --duracao 6h`
  and `loop-watch --raiz <repo>`. Nobody memorises that, so in EOP it became a
  hand-written `loop.sh` at the root of the repository — and it is still there.
  That file carried two defects that stop it from shipping as it stands. Its
  root was a **literal** (`--raiz ~/x/EOP`), which ties the file to one tree and
  dies at the first clone. And it did not arrive on its own: every target
  repository needed someone to remember to write it.
- **Decision.** `armar` seeds `.loop/loop.sh` when the file is absent. The root
  is **derived** from the script's own path (`dirname "${BASH_SOURCE[0]}"/..`),
  the duration is an optional argument defaulting to `6h`, and the script
  prefers `loop-ctl`/`loop-watch` from `PATH`, falling back to the absolute path
  of the skill copy that seeded it — the same reason `install.sh` writes shims
  instead of symlinks: say which copy is serving.
- **Never overwritten.** The copy in the target repository is the **owner's** —
  it is where `--objetivo`, `--janela` and `--itens` live between rounds — so
  re-seeding it on every `armar` would erase his configuration. Same rule as the
  `QUEUE.md` skeleton. Deleting the file is the way to ask for a fresh one.
- **Seeded after the state, and it may fail.** The call sits after
  `loop.iniciar()`, never with the `QUEUE.md` skeleton before the guards: a
  command that refuses must leave nothing behind, which is what the empty-queue
  and session guards both already pay for. And an I/O failure is silent and
  returns `False` — trading a round for a convenience would invert the fail-open
  of ADR-009.
- **It asks for the session adoption out loud.** A shell cannot know its own
  `session_id`, so the shortcut passes `--adotar-primeira-parada` and prints the
  warning on stderr first. This is exactly the case P-09 measured, and the case
  the `0.2.6` guard was shaped around: refusing without an exit would break this
  very file. What the guard buys is that the adoption is **said**; what the
  warning buys is that the operator hears it at the only moment he can still
  close the other chats.
  > 🔴 **Errata de 11/09/2026 (`0.3.14`, caixa `A66` do EOP) — o atalho não pede
  > mais a adoção: ele RECUSA.** A linha acima descreve o que a `0.2.6` decidiu, e
  > o argumento dela (*"recusar sem saída quebraria este próprio arquivo"*) caiu
  > por medição: o atalho passou a **exigir o id** (`<session-id>` ou
  > `LOOP_SESSAO`), então há saída e ela não quebra nada. O que derrubou o aviso
  > foi a reincidência — em 10/09 a adoção disparou **três vezes numa rodada só**,
  > apagando vínculo correto. Aviso que o operador pode não ler não é guarda.
- **No `--ate-encerrar` on the watch,** deliberately: a turn that dies without
  emitting `Stop` pins the round at `ativo: true` (P-08), and a script blocked on
  that flag would hang forever. Ctrl+C leaves the panel; the round keeps running.
- **Alternative rejected:** a `loop-ctl atalho` subcommand. A new command is one
  more thing to memorise, which is the problem this decision removes.
- **Cost of undoing:** delete the template and the helper. Nothing reads the
  file; no state depends on it.
- **Controls, and the mutation that proves each.** Six mutations over 248 green
  tests: removing the seeding call drops **10**; moving it ahead of the guards
  drops **1** (the one that asserts a refused `armar` leaves no file); dropping
  the never-overwrite check drops **2**; taking the root from `pwd` instead of
  the script path drops **2**; removing the session warning drops **4**;
  disabling `set -e` drops **1**.

---

## ADR-017 — Time is measured, never enforced: the clock stops ending rounds

- **Date:** 2026-09-18 · **Status:** Accepted · **Revises:** ADR-010 (drops the
  clock from the end conditions), ADR-015 (keeps the decision, drops its gate)
- **Observed fact.** The EOP round armed on 17/09 at 14:32 with `--duracao 16h`
  ended at `duração máxima`: 27 iterations, `sem_progresso: 0`, **16 items still
  in the queue**. Nothing was wrong with it — it was producing, the guardrails
  were all green, and a number typed the night before is what stopped it. The
  16 remaining items were owner-decision items (`🔒 MESA DO DONO`), so the round
  had to hand back anyway; what the clock bought was cutting the work that was
  still running.
- **The number never meant what it enforced.** `--duracao 16h` is how the owner
  says *"keep going tonight"*, not *"stop at 06:30"*. The ceiling was a side
  effect of there being no other way to declare a long round — and the side
  effect is what fired.
- **Decision.** `duracao_max_min` leaves `condicoes_de_fim`. It stays in
  `STATE.json`, it is still accepted on the command line, and it becomes a
  **production target that is measured**: the panel reads `produzindo há 17h37 ·
  meta 16h00`, counting up. A round now ends by kill switch, iteration ceiling,
  no-progress, the agent's `SEM-ESCOPO` verdict, the work window, scope by items
  or marker, or ASK policy — every one of them a fact about the work, not about
  the hour.
- **The window stays.** It answers *when* work is allowed, not *how long* it may
  run. A round out of hours has nowhere to go; a round past a target does.
- **`fila zerada` leaves the chain entirely, and ADR-015 becomes
  unconditional.** ADR-015 had to gate refuelling on `tem_relogio` precisely
  because an empty queue ended a clockless round on the spot — three EOP rounds
  died on iteration 1. With the clock no longer ending anything, that gate had
  nothing left to read: keeping it would mean every round dies the moment the
  queue empties, which is the defect ADR-015 was written to fix. So refuelling is
  what an empty queue always triggers, and `tem_relogio` is deleted rather than
  left returning a constant.
- **Consequences.**
  - `restante_da_rodada` reports only what the window allows. A target that
    never fires has no "remaining", and putting one in the refuelling prompt
    would hand the turn a deadline nothing enforces.
  - The empty-queue refusal in `armar`/`retomar` is gone with the defect it
    guarded, and `--mesmo-sem-fila` is accepted as a no-op so existing
    `.loop/loop.sh` copies keep working.
  - A round can now run until someone stops it. That is the point, and the
    guardrails that remain are the ones that measure the work: `sem progresso`
    catches a loop spinning on items it cannot execute, and the iteration
    ceiling is still there.
- **Alternatives rejected.** *Keeping the clock as a warning* — a condition that
  prints and does not fire is the panel lying about what governs, which is the
  exact defect the 17/08 panel had. *Dropping the window too* — it is the only
  lever for "not overnight", and it was not what bit: that round had
  `janela: None`.
- **Mutation.** Putting the clock back in the chain drops **4** tests; putting
  `fila zerada` back drops **14**; re-gating refuelling on the clock drops
  **2**; removing the header stopwatch drops **1**; letting the clock back into
  `restante_da_rodada` drops **2**.

---

## ADR-018 — `- 🔒` é a terceira caixa: o item que o agente não pode executar

- **Date:** 2026-09-18 · **Status:** Accepted · **Extends:** ADR-006 (the queue
  is the source of the next step)
- **Observed fact.** On the EOP, 18/09: all 14 pending items were owner boxes —
  money, contract, ADR, authentication. `proximo_item()` returns the head of the
  queue, so the same box came back at every stop. The round spun **25
  iterations** on `L781`, wrote ~31 identical diary entries, and what ended each
  session was the harness ceiling of consecutive blocks, not the loop.
- **Neither existing box works.** `- [ ]` puts the item back at the head forever.
  `- [x]` would say it was delivered, which is a lie — and the queue is the
  measurement of what is done. There was no way to say *"this is work, it is not
  finished, and I cannot be the one to do it"*.
- **Decision.** A third state, `- 🔒`, meaning **waiting on a decision only the
  owner can make**. It is counted apart from both — `bloqueados()` — and enters
  no progress calculation. Four consequences, each implemented:
  1. **The selector skips it.** `- 🔒` does not match `_PEND`, so the head of the
     queue moves on to the next executable item.
  2. **A queue with only locked items counts as empty**, which makes the stop a
     refuelling turn: the agent goes looking for new work instead of receiving
     the same box for the 26th time.
  3. **The agent marks it himself**, in the turn he finds out — clause 5 of
     `prompts/continuacao.md`. Depending on an owner decision is explicitly *not*
     a reason to end the turn: it is a reason to mark and move on.
  4. **It is always visible.** `loop-ctl` and the panel print
     `14 🔒 na mesa do dono` next to the queue counts. An item that vanishes from
     both counts and is shown nowhere would be the same lie by omission the
     panel of 17/08 told.
- **Why this symbol.** It was not invented here. The EOP already wrote `🔒` and
  `CAIXA DO DONO` on those lines by hand, for months, before the skill could read
  anything. The notation was chosen so that the skill learns to read what the
  repository was already saying — a convention that exists on disk does not need
  to be adopted, only recognised.
- **Consequences.** The `QUEUE.md` format gains a state, which is why this is a
  `Y` bump. Older `.loop/` copies are unaffected: a queue with no `- 🔒` behaves
  exactly as before, and `bloqueados()` returns 0. What the loop still cannot do
  is decide *for* the owner — when every remaining item is locked and there is no
  scope left to refuel, the round ends by the agent's `SEM-ESCOPO` verdict, and
  the boxes wait on the desk.
- **Mutation.** Removing `_BLOQUEADO` drops 1 (the item stops being counted and
  the desk goes invisible); deleting clause 5 from the continuation prompt drops
  1 — and that second test had to be tightened first, because asserting on the
  symbol alone passed even with the instruction deleted.

---

## ADR-019 — A stop count per item: the lock for an agent that moves and never closes

- **Date:** 2026-11-10 · **Status:** Accepted · **Extends:** ADR-018 (the third
  box). Complements — does not replace — the no-progress brake of ADR-010/`0.4.3`.
- **Where it came from.** A review of `cobusgreyling/loop-engineering` (MIT, a
  pattern library for scheduled agent loops). Its `loop-context` circuit breaker
  caps attempts *per item* ("max 3 fix attempts per item; escalate after"), and
  its CI-sweeper story records what the lack of that cap costs: 14 consecutive
  attempts on one failure, 1.8M tokens, three hours, until the breaker tripped.
- **The gap, verified in our code.** `sem_progresso` compares a fingerprint —
  `git status --porcelain` outside `.loop/`, `HEAD`, and the queue counts — so it
  answers *did the agent move?* An agent that commits at every stop and never
  ticks the item at the head moves all day: the fingerprint changes each stop and
  the brake never fires. And `proximo_item()` is stateless; nothing counted how
  many times the same item came back. ADR-018 asks the **agent** to lock an item
  it cannot do (clause 5 of the prompt) — an agent that does not is not caught by
  anything.
- **Measured, before choosing a number.** The EOP `INDEX.md`: 516 stops, 126
  distinct items delivered. Consecutive stops with the same item at the head:

  | Stops on the item | 1 | 2 | 3 | 4–5 | 6–7 | 8–9 | 13–14 | ≥15 |
  |---|---|---|---|---|---|---|---|---|
  | Items | 88 | 16 | 5 | 7 | 4 | 2 | 2 | 2 |

  70% of the items closed in one stop and 94% within six. The tail is two kinds of
  thing: owner boxes (`L781`, 34 stops, the incident behind ADR-018; `L446`, 13;
  `L544`, 9; `L520`, 8) and large items (`L680`, 29, labelled *grande*; `L608`, 14
  — *blocos 2..9* of one item, which was progressing).
  **Limits, stated:** one project, rounds from several versions of the code, the
  `INDEX` truncates the item at 70 characters, only *consecutive* stops are
  counted — and the data cannot separate a large item that is progressing from
  one that is stuck. That last limit is why the guard has two steps.
- **Decision.** The hook counts, at every stop, the consecutive stops at which the
  same item was at the head (`paradas_no_item`, with `item_cabeca` as its
  identity). Two thresholds:
  1. **Warning at `limiar_aviso_item(max)` — 40%, default 6.** The `reason` gains
     a block (`{bloco_item}` in `prompts/continuacao.md`) asking the agent to pick:
     close it now, **split** it into smaller `- [ ]` items with a recognisable
     end, or lock it. Splitting rewrites the head and resets the count, which is
     the point: an item that takes six stops is not *executable alone* and
     *verifiable*, the two things `SKILL.md` asks of every item.
  2. **Lock at `max_paradas_item` — default 15.** The hook rewrites the head line
     from `- [ ]` to `- 🔒`, appends the reason on the same line (`travado pelo
     loop após N paradas sem concluir (ADR-019, #NNNN)`), and the round goes on
     with the next item. The prompt of that stop says what happened. The entry
     gets a section, the `INDEX.md` decision reads `continuou · item 🔒`.
  `armar --max-paradas-item N` sets it; **`0` switches both off**. `status`,
  `armar` and the panel show the count; the panel row is informative (motivo
  `None`) — the lock is not an end condition and ends nothing.
- **What the numbers would have done.** The warning, at 6, reaches 10 of the 126
  items (8%). The lock, at 15, reaches 2 (1.6%): `L781`, which was the owner box,
  and `L680`.
- **Details that are decisions.**
  - *Identity is a normalised prefix, not a hash.* The agent writes progress notes
    on the line it is working; a hash would call every note a new item and
    switch the guard off for exactly the agent it exists to catch. Two keys are
    the same item when equal or when one is a prefix of the other, with a 12-
    character floor. Rewriting the *start* of the item is a new item — on purpose.
  - *The lock is reversible.* One line, `- 🔒` back to `- [ ]`, and the owner's
    edit is the undo. A lock that could not be undone would make this an end
    condition in disguise.
  - *Locking is not progress.* It changes `pend`, which is part of the
    fingerprint; the hook retakes the imprint after locking, or the **next** stop
    would read the change as movement and reset `sem_progresso` — the loop
    crediting itself for its own bookkeeping, the shape of the `0.4.3` defect.
  - *The head is checked again before writing,* and a failure to read or write
    the queue degrades to doing nothing. The file is read and written with
    `surrogateescape`: the agent writes it, and a byte cut mid-character must
    survive the round trip (`acrescentar_itens` reads with `replace` and can
    afford it because it only appends; this rewrites a line in place).
  - *The new head starts counting at 1,* because it is the head at the stop that
    locked its predecessor.
- **Alternatives rejected.** *A single hard cut at a low number* — it would have
  cut `L608`-shaped items, the large ones that are making progress, and the data
  has no way to tell them apart before the cut. *Ending the round when an item
  hits the ceiling* — ADR-017's lesson: an end condition must be a fact about the
  work the round cannot go on without; one stuck item is a fact about one item.
  *Counting only stops whose fingerprint did not change* — that is
  `sem_progresso`, and it is exactly what this must not depend on. *Asking the
  agent to count* — that is ADR-018's clause 5, which this exists to back up.
- **Consequences.**
  - `STATE.json` gains four fields, all additive and merged from defaults on read.
    **A `.loop/` armed before `0.5.7` picks up the default ceiling of 15** the
    next time it runs; there is no round to protect from that today (the three
    `ativo` ones on this machine last stopped 7 to 54 days ago).
  - The hook now writes `QUEUE.md` in one more place. The precedent is the
    harvest, which appends; this rewrites one line, under the rules above.
  - Two panel tests that enumerated the informative rows were updated to list the
    new one; the assertion that matters — the order of the rows *with* a motive,
    the chain — is untouched.
- **Open (P-10).** 6 and 15 are read off a single project. They are a first
  calibration, not a measurement of how long an item should take.
- **Mutation.** 17 controls switched off, one at a time, each dropping at least
  one test: the lock (3), the warning (1), the imprint retaken after a lock (1),
  identity as strict equality (2), the 12-character floor (1), `0` not switching
  the guard off (1), `surrogateescape` replaced by `replace` (1), the re-check of
  the head (1), the count not resetting on a new item (2), the prompt placeholder
  (1), `retomar` keeping the count (1), `armar` dropping the flag (2), the
  `INDEX` marker (1), the entry section (1), the new head not starting at 1 (1),
  the default ceiling (3), the reason written on the locked line (2).

---

## ADR-020 — Token use is measured from the transcript, and never enforced

- **Date:** 2026-11-10 · **Status:** Accepted · **Applies:** ADR-017 (a quantity
  that matters but must not end the round is *measured*, not enforced)
- **Where it came from.** The same review of `cobusgreyling/loop-engineering`.
  Its `loop-budget` skill sums a `tokens_estimate` per run, and its own story
  `thirty-weekday-runs` records the result: **22 runs, the field a constant 52,000
  written by the workflow, "not a meter"** — "estimates are not observations".
  Our loop has the opposite advantage: the hook receives `transcript_path`, where
  every assistant message carries the `usage` the API reported.
- **Three ways a first meter lies — each measured before writing it.**
  1. *Lines are not messages.* Claude Code writes one JSONL line per content
     block. On a real session, 190 usage-bearing lines were **62** distinct
     `message.id`s, the `usage` identical on every repeat. Summed naively the
     session read 315,106 output tokens; deduplicated, 98,827 — **3.2× too many**,
     and cache reads 33.6M against 11.4M.
  2. *Subagents are somewhere else.* The main transcript had 0 sidechain lines
     (`isSidechain` false on all 190). A subagent's usage is in
     `<session>/subagents/agent-*.jsonl`, `isSidechain` true — in the one file
     opened, 97 usage lines. A meter that skips them undercounts exactly the
     loops that spend the most.
  3. *`cost-state` is not a stop-by-stop meter.* The harness writes cumulative
     `totalCostUSD`/`modelUsage` records, but **2 in 940 lines** on that session,
     in an internal format. Rejected as the source.
- **Decision.** `lib/uso.py` folds the usage into `STATE.json` at every stop:
  - deduplicated by `message.id` (falling back to `requestId`, then `uuid`), with
    the ids of the last chunk kept so a message split across two stops counts once;
  - read **incrementally** — a saved byte offset per file, and only up to the last
    *complete* line (a line the harness is still writing waits for the next stop);
  - the main transcript **and** `<session>/subagents/*.jsonl`; a subagent file
    nobody has read and untouched since the round was armed is not even opened;
  - only lines with a timestamp at or after `uso_desde` — arm time, moved by
    `retomar`, so what the session spends with the loop off is not the round's;
  - three components, never summed: `saida` (`output_tokens`), `entrada_nova`
    (`input_tokens` + `cache_creation_input_tokens`) and `cache_lido`
    (`cache_read_input_tokens`). On the session measured the cache reads were
    ~100× the output; one number would mean nothing.
  The round's total is `uso`; the item at the head of the queue has its own,
  `uso_item` — credited *before* the head is re-read, because the turn that just
  ended worked on the item delivered at the **previous** stop, and reset when the
  head changes (not when there was no previous head: the work since arming, or
  since a refuel turn, belongs to the item that is now first).
- **Where it shows.** `loop-ctl status` (`uso` and the item's output), the panel
  (`uso da rodada`, informative, motivo `None`), `STATUS.md` at the end
  (`Uso observado`), and `uso_turno:` in each entry's front matter — absent, not
  zero, when no usage record was read: "nothing measured" and "the turn used
  nothing" are different facts.
- **Not decided here, on purpose.** *No ceiling.* ADR-017 is the reason: a
  quantity that cuts a round off at a number typed the night before is the clock
  again. *No money.* Prices differ by model and change, and a dollar figure built
  from mixed units is an estimate wearing an observation's clothes — the trap
  upstream fell into. A ceiling, if wanted, is an explicit opt-in on the measured
  `saida` (P-11), not a default.
- **Limits, stated.** (1) Only what the transcript records: a tool that calls a
  model on its own is invisible. (2) The `subagents/` layout is what Claude Code
  `2.1.318` writes; it is not documented as stable, and if it moves the meter
  undercounts — it does not break, and does not say how many files it read.
  (3) The hook can fire before the harness has flushed the last message
  (ADR-012's race), so a turn's tokens may be credited one stop late; totals
  converge, per-stop and per-item attribution can lag. (4) A file that grew by
  more than 16 MB since the last read is sampled from its tail and the round is
  flagged `parcial`; a file that got shorter is skipped, never recounted.
  (5) Whether `output_tokens` includes thinking tokens was not established.
- **Verified against reality.** Run on the real transcript of this session, the
  meter and an independent deduplicated sum agree to the token (141,079 output,
  541,280 new input, 16,017,298 cache read, 76 messages), in 8 ms; a second read
  with no new line adds nothing.
- **Consequences.** `STATE.json` gains five fields, all additive (`uso`,
  `uso_item`, `uso_desde`, `uso_offsets`, `uso_ids`); a `.loop/` armed before
  `0.5.8` starts measuring at its next stop, from `armado_em`. The hook reads more
  files than before, all derived from `transcript_path` — the same trust it
  already extended to that path — and writes nothing new outside `.loop/`. The
  mutable defaults in `PADRAO` (`{}`, `[]`) are never mutated in place; a test
  fails if they are.
- **Mutation.** 22 controls switched off, each dropping at least one test; two
  *survived* the first round and were closed by new tests: the broad `except`
  (the first failure tests only hit the missing-file shortcut, never an exception
  raised during the read) and `uso_turno:` printed with nothing measured. Dedupe
  by id (3), `entrada_nova` without cache creation (2), cache reads folded into
  new input (2), the timestamp filter (1), the offset not advancing (1), a
  half-written line consumed (1), ids not kept between stops (1), subagents not
  read (1), a stale subagent file opened (1), a shrunk file recounted (1), the
  window cap not flagged (1), exceptions escaping (1), a shared mutable default
  (73), the meter call removed from the hook (6), the item meter never reset (1)
  and reset with no previous head (1), the `uso_turno` line unconditional (1),
  `STATUS.md` without the line (1), `retomar` keeping the cursor (1), the panel
  row unconditional (41), `status` without the item's output (1) and without the
  round's usage (1). One mutant is equivalent and was not chased: `iniciar`
  setting `uso_desde` equals the `armado_em` fallback — it stays because
  `retomar` moves it.

---

## ADR-021 — `loop-ctl drill`: fire the installed hook, in both directions

- **Date:** 2026-11-10 · **Status:** Accepted · **Extends:** ADR-013 (the silence
  of the fail-open needs a command that speaks)
- **Where it came from.** `loop-drill` in `cobusgreyling/loop-engineering`: *"loop-audit
  scores whether your guardrails are **present**. loop-drill tests whether they
  **work**"* — inject a known fault, assert the guardrail fires, and always drill
  both directions. The idea is theirs; the scenarios here are ours.
- **The gap.** The suite proves the code in this repository. It cannot prove the
  copy that runs on this machine: a line in a `settings.json`, an interpreter on a
  `PATH`, a symlink, a vendored tree. `hook_instalado()` checks that the string
  `loop-stop.py` appears in a command; `loop-ctl porque` walks the gates in order.
  Neither *fires* the hook, and the hook is fail-open (ADR-009): when anything is
  wrong it exits 0 and says nothing, so a loop that never continues looks exactly
  like a loop with nothing to do. We have already paid for a guard that was present
  and never fired (`0.4.3`, the brake) — and found it only in a real round, 16
  iterations later. Three config homes exist on this machine (`.claude`,
  `.claude-blue3`, `.claude-pessoal`), each with its own `settings.json`.
- **Decision.** `loop-ctl drill [--settings FILE]... [--hook PATH] [--json]` reads
  the Stop command registered in every `settings.json` it finds, groups identical
  commands, and fires each one with synthetic Stop payloads inside a throwaway git
  repository, armed through the **installed tree's own `loop_ctl.py`** — so `armar`
  and its flags are exercised too. Eleven drills, each credited for the rule under
  test, read from `STATE.json` rather than from prompt text:

  | Drill | Direction | The failure it exists to catch |
  |---|---|---|
  | `inerte-fora-do-loop` | specificity | the global hook acts where nobody armed the loop (T-01) |
  | `continua-a-rodada` | sensitivity | the loop does not continue, silently (ADR-013) |
  | `freio-dispara` | sensitivity | the brake that never fires (`0.4.3`) — must end by `sem progresso`, not just end |
  | `freio-calado` | specificity | the brake fires on a round that commits |
  | `kill-switch` | sensitivity | `.loop/STOP` ignored |
  | `trava-dispara` | sensitivity | the item that moves and never closes eats the round (ADR-019) |
  | `trava-calada` | specificity | the lock cuts an item that closes |
  | `medidor` | sensitivity | the meter reads nothing (ADR-020) |
  | `medidor-sem-duplicar` | specificity | one line per content block counts 3× |
  | `fail-open-entrada` | contract | a bad stdin hangs the session (ADR-009) |
  | `fail-open-estado` | contract | a corrupt `STATE.json` hangs the session |

  Exit `0` all passed · `1` something could not run (no hook registered, no git,
  a command shape it will not execute) · `2` a guard failed to do its job.
  `install.sh` now runs it on the settings it just wrote and **exits 2 if a guard
  does not act**, instead of announcing "Pronto." over a hook that does nothing;
  `LOOP_SEM_DRILL=1` skips it for scripted installs.
- **A specificity drill is meaningless alone — measured, then fixed.** The first
  version of this ran `freio-calado` and `trava-calada` as plain passes, and on a
  hook with a syntax error both showed a green tick: a hook that never runs never
  brakes and never locks, so it "passes" every drill that says *it must not fire*.
  A report of a dead hook with two ticks is the exact lie the drill exists to
  prevent. Each specificity drill now names its sensitivity partner and counts
  **only if the partner passed**; otherwise it is reported as skipped, with the
  reason. (`inerte-fora-do-loop` and `medidor-sem-duplicar` need no rescue: they
  assert a positive fact — exit 0 with no output, 777 tokens — that a dead hook
  cannot produce.)
- **Safety, because it executes a command read from a file.** It runs only the
  exact shape `install.sh` writes — `python3 "<abs path>/loop-stop.py"` — matched
  by a regex and executed **without a shell**. A line that merely mentions the hook
  (`touch …; echo loop-stop.py`, in the test) is reported as not executed and the
  marker file never appears. All work happens in a temporary directory with its own
  `HOME`, removed afterwards; no `settings.json` is ever written (a test compares
  bytes). T-08 in `SECURITY.md`.
- **What it does not see.** It runs in the environment of whoever typed the
  command, not the one Claude Code gives the hook: a `python3` that resolves in a
  terminal and not under the desktop app's `PATH` is invisible to it. It does not
  drill the classifier (the fixtures of ADR-011 do that), the session binding, or
  the window. And it proves a copy at one moment, not a round that is running.
- **On this machine,** against the real installed hook, in 1.5 s: 11 passed, the
  one command registered in all three config homes, the `settings.json` bytes
  unchanged.
- **Alternatives rejected.** *Running the test suite against the installed copy* —
  `tests/` is not vendored, and it proves the repository, not the installation.
  *Reading the settings only* — that is `hook_instalado()`, the thing that is
  present-but-unproven. *Arming a real repository for the drill* — side effects in
  somebody's work for the sake of a check.
- **Mutation — of the drill itself.** The test of a drill is that it fails when the
  thing it guards is broken, so `tests/test_drill.py` breaks a **copy** of the tree,
  one fault at a time (14), and requires the right drill to go red — and, for the
  specific ones, only that one: dead brake → `freio-dispara`; brake on everyone →
  `freio-calado`; brake ending by the wrong reason → `freio-dispara` (the round did
  end — the drill names the reason it did); dead lock → `trava-dispara`; lock on
  everyone → both `trava-*`; kill switch ignored; meter off; meter without dedupe;
  fail-open broken; hook creating `.loop/` by itself; hook that does not continue;
  a reason without the head item; a syntax error; a broken `loop_ctl`. Then 21
  controls of the drill and of `install.sh` were switched off, each dropping at
  least one test (counts include sub-tests): each drill's own check (1–3 each),
  the pairing (2), the command-shape regex (3), command grouping (1), the missing-hook
  check (1), temp-dir cleanup (1), the isolated `HOME` (1), the exit code (17), the
  symlink dedupe (1), `CLAUDE_SETTINGS` (1), the `armar` failure report (1), the
  not-executed exit code (1), the `install.sh` step (2) and its exit 2 (1).
- **Consequences.** A new `lib/drill.py` and one subcommand; no change to the hook,
  the state or the prompt. The suite grows by about 13 s (13.3 s → 26.7 s; the fault-injected copies already run in parallel).
  An install over a broken tree now fails where before it succeeded — which is the
  point, and a behaviour change for anyone scripting `install.sh` (`LOOP_SEM_DRILL`).
  Not done: running the drill from `vendor.sh` on the vendored copy — the global
  hook points at this tree, not at the copies, so it would prove something that is
  not what runs.

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
| P-09 | **O auto-bind do ADR-008 adota sessão que NÃO armou o loop — contraexemplo medido em 01–02/09.** A decisão diz, com estas palavras, que a primeira parada *"é **necessariamente** a da sessão que armou"*, e o comentário em `hooks/loop-stop.py:167` repete a afirmação. **Não é necessariamente.** É a primeira sessão que terminar um turno naquele repositório — e no EOP foi uma sessão que o dono havia aberto para outra coisa (triagem dos PRs do Dependabot), enquanto o `loop.sh` armava de outra. Custo medido nessa rodada: **18 entradas** de diário (`0153`–`0160`, `0166`–`0172`) que são mensagens sobre PRs e sobre um artifact, arquivadas sob os itens `L191`, `L201`, `L219` e `L220`, com que nada têm a ver; **4 itens espúrios** enfileirados a partir de fragmentos truncados da mensagem (`- [ ] a página como fonte`), que é a **terceira** reincidência da família da emenda do ADR-005; e — o mais caro — **duas sessões dirigidas contra a mesma árvore de trabalho**, que no EOP produziu duas colisões de `version.md` (`1.76.71` e `1.76.72`, a segunda no próprio commit que consertava a primeira), duas `master` vermelhas na guarda `G2` e dois commits que anunciaram trabalho que o diff não continha. ⚠️ **O conserto não foi feito, e a razão é a norma desta casa:** mexer em `hooks/` ou `lib/` com rodada viva faz o hook sair fail-open e trava a rodada no meio — foi o motivo escrito no `0.2.4` para o conserto do `INDEX.md` ter ficado para depois — e a rodada do EOP estava rodando enquanto isto era escrito, com **outra** sessão executando o `L219`. ✅ **A PRIMEIRA saída foi entregue em 02/09 (`0.2.6`), e ela era a única fora do caminho do hook:** o `armar` vive em `loop_ctl.py`, que o `hooks/loop-stop.py` **não importa** — ele importa só `classificador`, `diagnostico`, `estado` e `transcricao` de `lib/`. Logo a guarda de porta podia entrar **com a rodada viva**, e entrou; as outras duas seguem barradas pela mesma norma. E ela não é a *falha ruidosa* pura que esta linha propunha: recusar sem saída quebraria o `loop.sh` do EOP (`loop-ctl armar --raiz ~/x/EOP --duracao 10h`, sem `--sessao`) e viraria `--force` na semana seguinte — nasceu o `--adotar-primeira-parada`, que mantém o comportamento alcançável e o obriga a ser dito. Saídas restantes, as duas em `hooks/`/`lib/`: gravar no ato do `armar` um marcador barato do processo que armou (PID/tty) e o hook conferir antes de adotar, caindo no comportamento antigo quando o campo estiver ausente, para não quebrar rodada em curso; e um lock de árvore em `.loop/` que faça a segunda sessão **recusar** item em vez de competir. | **aberta** |
| P-10 | **Calibrar 6 e 15 (ADR-019) em rodadas reais.** Os dois números saíram de um único projeto (EOP, 126 itens). Falta medir em outros repositórios e separar item grande que avança de item travado — o que o `INDEX.md` não permite hoje. | aberta |
| P-11 | **Teto opcional sobre o `saida` medido (ADR-020)?** Decidir só depois de algumas rodadas com o medidor ligado, olhando o gasto real por item e por rodada. Nunca como default: um teto que corta a rodada é o relógio de novo (ADR-017). | aberta |
