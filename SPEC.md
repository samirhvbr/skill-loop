# SPEC.md — Pipeline e formato do LOOP

> **Normativo.** O que está fechado vem sem marca; lacuna restante é marcada com
> ⛔ e o que a bloqueia. Decisões em [docs/decisoes.md](docs/decisoes.md);
> ameaças e controles em [SECURITY.md](SECURITY.md).
>
> Nomes: repositório `skill-LOOP` · skill `loop-work` · comando `/loop-work` ·
> estado `.loop/`.

---

## 1. Gatilho

Hook **`Stop`** do Claude Code, instalado global em `~/.claude/settings.json` por
`install.sh`, em **grupo próprio** (ADR-007). Contrato:

```
stdin  ← {"session_id", "transcript_path", "cwd", "hook_event_name",
          "stop_hook_active"}
stdout → {"decision": "block", "reason": "<instrução>"}   continua
         (nada, exit 0)                                    deixa parar
```

O `reason` é entregue ao agente como instrução nova, e é isso que substitui o
"continua" digitado. Timeout de 15 s no registro.

### 1.1 `stop_hook_active` não é a trava

O campo vira `true` já na **segunda** parada e não volta a `false`. O padrão
documentado (`if stop_hook_active: allow stop`) renderia **uma** continuação e o
loop morreria ali. Aqui ele é registrado e ignorado; quem limita é §5 (ADR-002).

### 1.2 Convivência com outros hooks `Stop`

Todos os hooks `Stop` do ambiente rodam. Só o LOOP devolve `decision: block`. O
instalador **anexa** um grupo e nunca reescreve os existentes (ai-memory hoje; o
`Stop` do COMMITTER quando a F2 de lá existir).

---

## 2. Classificação ASK × DOC

Determinística, léxica, sem modelo e sem rede (`lib/classificador.py`).

### 2.1 Pré-processamento
1. Blocos de código (``` e `inline`) viram espaço — `?` em código não é pergunta.
2. Texto em parágrafos (separados por linha em branco).
3. **Zona de fecho** = os **2 últimos parágrafos**, por posição.

   > Corte por posição, não por contagem de caracteres. A primeira versão
   > acumulava até 300 chars e, em mensagem curta, o fecho engolia o texto
   > inteiro — desligando a leitura de zona justamente onde ela decide.

### 2.2 Supressão de retórica (independente de zona)
Uma frase terminada em `?` é **retórica** — não conta como pergunta — quando:

- **R1** — foi anunciada: `a pergunta`, `pergunta seguinte`, `me perguntei`,
  `a questão era`, `resta saber`, `merecia a pergunta`; ou
- **R2** — a frase imediatamente seguinte **relata ação concluída** (léxico de
  relato: `varri`, `rodei`, `commitei`, `435 testes`, `0 falhas`, …).

R2 exige o relato de propósito: *"Removo o endpoint antigo? Fico esperando para
não quebrar o app."* também tem frase depois, mas ela é justificativa, não
resposta — a pergunta continua de pé (ADR-004).

### 2.3 Decisão (na ordem)
1. Última tool do turno ∈ {`AskUserQuestion`} → **ASK** (`tool`, alta).
2. Pergunta direta **no fecho** → **ASK** (`pergunta-direta`, alta).
3. Marca de **handoff** ou imperativo de decisão **no fecho** → **ASK**
   (`handoff`, alta). Léxico PT-BR/EN: `do teu lado`, `cabe a você`, `aguardo`,
   `me diz`, `posso seguir`, `quer que eu`, `antes de prosseguir`, `up to you`,
   `let me know`, `your call`, `should I`…
4. Pergunta direta **fora do fecho** → **ASK** (`pergunta-narrativa`, média).
5. Senão → **DOC** (`relato`; alta se houver marcas de relato, média se não).

### 2.4 Colheita para a fila
Independe do veredito ASK/DOC — é o que mantém o fio:

- **Do fecho de handoff:** lista markdown, ou enumeração em prosa depois de `:`,
  com split **ciente de parênteses** e artigo obrigatório após a vírgula
  (`, a ` / `, o ` / ` e as `). Sem isso, `(coluna versao no Ciclo e no Período)`
  vira dois itens.
- **De qualquer zona:** **pendência declarada pelo próprio agente** — `declarado
  e não feito`, `fica para a próxima`, `candidato natural`, `ficou de fora`,
  `não coberto`, `follow-up`, `out of scope for today`… O rótulo em negrito é
  removido e o item é a primeira frase (ADR-005).
- Teto de 12 itens por parada; dedup por slug dos 60 primeiros caracteres,
  contra a fila inteira (pendentes **e** feitos).
- **A pergunta detectada nunca vira item** — nos dois vereditos (emenda ao
  ADR-005). Candidato que seja, ou contenha, uma pergunta já detectada (direta no
  fecho, direta na narrativa ou retórica) é descartado antes do dedup;
  a comparação é por conteúdo normalizado, sem marcação, nos dois sentidos de
  contenção, com piso de 12 caracteres. A pergunta já tem seus lugares: a entry,
  o `INDEX.md` e a premissa do `ASSUMPTIONS.md`. Na fila ela seria **marcável
  como feita** — e um `- [x]` numa pergunta zera a fila e encerra a rodada.
- Marcação solta (`*`, `_`, `` ` ``) é retirada das **pontas** do item: a
  colheita corta no último `:` e herdava o negrito partido (`**Pendente:** rodar
  o lint` deixava `** rodar o lint`). No meio do item, marcação é do item.

---

## 3. Leitura do transcript

Pela **cauda**: últimos 2 MB, descartando a primeira linha da janela (partida).
Varre de trás para frente até a primeira entrada `type == "assistant"`, com
`isSidechain` falso, que tenha bloco de texto.

O filtro de subagente é obrigatório: um `Explore` que termina em "devo procurar
mais?" seria classificado como ASK do agente principal. Desligá-lo derruba 8
testes.

### 3.1 A corrida contra o fecho do turno (ADR-012)

O hook dispara **antes** de o Claude Code gravar o último bloco de texto. Ler
direto devolve resto velho — medido no EOP em 16/08: leitura às 00:19:22
trouxe texto de 00:12:30, 154 entradas atrás.

A leitura classifica o que achou como **fecho** ou **resto velho**: é fecho
quando não há conteúdo do agente principal depois dele (`tool_use` do agente,
`tool_result`). Sendo resto velho, **espera** — releitura a cada 100 ms até
`LOOP_ESPERA_MAX_S` (default **3 s**; teto bem abaixo do timeout de 15 s).

Não geram espera: entrada de **subagente** (`isSidechain`), que é outro turno; e
**`AskUserQuestion`**, que fecha o turno por si — o agente perguntou e parou ali.

Espera estourada → o loop **segue** (fail-open), e a `entry` grava
`fecho_do_turno: PARCIAL`, confiança `baixa` e a evidência dizendo que aquilo
não é o relatório.

---

## 4. O `reason` de continuação

Template em [prompts/continuacao.md](prompts/continuacao.md) — **artefato do
produto**; mudar ali é mudar comportamento e exige bump. Substituição por
`str.replace`, nunca `str.format`: o arquivo é markdown editável à mão e uma
chave solta não pode derrubar o hook.

Placeholders: `iteracao`, `max_iteracoes`, `kind`, `sinal`, `entry`, `item`,
`pendentes`, `feitos`, `objetivo`, `bloco_ask`, `bloco_colhidos`.

O texto precisa carregar, sempre:

1. **que o chat não está sendo lido** — sem isso o agente volta a resumir;
2. **o item exato** — "continua" faz o agente re-planejar e derivar;
3. o que fazer com decisão em aberto (assumir default reversível + registrar em
   `ASSUMPTIONS.md`);
4. **a condição de parada explícita** — senão ele para na primeira dúvida.

Template ausente ou ilegível → fallback embutido no hook (nunca falha).

**Dois templates, um por trabalho** (ADR-015). Quando a fila está vazia e há
relógio, o trabalho do turno não é executar item — é encher a fila —, e o hook
devolve [prompts/reabastecimento.md](prompts/reabastecimento.md) (§5.2), com os
placeholders `escopo` e `restante_relogio` no lugar de `item` e `pendentes`.
Mandar o template de continuação com `(fila vazia)` no lugar do item era o caminho
barato e o pior: uma ordem para executar o que não existe. Cada template tem seu
próprio fallback embutido e seu próprio override por ambiente (`LOOP_TEMPLATE`,
`LOOP_TEMPLATE_REABASTECIMENTO`).

---

## 5. Condições de fim (ADR-010)

Verificadas a cada parada, **nesta ordem**; a primeira que bater encerra:

| # | Condição | Campo | Default |
|---|---|---|---|
| 1 | kill-switch | arquivo `.loop/STOP` | — |
| 2 | teto de iterações | `max_iteracoes` | 200 |
| 3 | sem progresso | `sem_progresso ≥ max_sem_progresso` | 3 |
| 4 | escopo esgotado | arquivo `.loop/SEM-ESCOPO` | — |
| 5 | fila zerada — **só sem relógio** | nenhum `- [ ]` | — |
| 6 | fora da janela | `janela` + `dias` | `null` |
| 7 | relógio | `duracao_max_min` | `null` |
| 8 | escopo por itens | `escopo_itens` | `null` |
| 9 | escopo por marcador | `escopo_ate` | `null` |
| 10 | política de ASK | `politica_ask` | `continuar` |

**Fila zerada só encerra rodada sem relógio** (ADR-015). Com `duracao_max_min` ou
`janela` na mesa, a missão declarada é o **tempo** e a fila é rascunho: a fila
vazia sai da cadeia e vira **turno de reabastecimento** (§5.2). Enquanto ela
mandava, o `--duracao` nunca chegava a valer — três rodadas do EOP encerraram na
iteração 1 com ~5h50 sobrando.

**Escopo esgotado** é o fim que a rodada por tempo passou a ter: o **agente**
escreve em `.loop/SEM-ESCOPO` o veredito com os números que mediu, e a parada
seguinte encerra citando a primeira linha dele no `STATUS.md`. Arquivo separado do
`STOP` de propósito — o kill-switch é ordem do dono, este é medição do agente, e
um arquivo só para os dois apagaria quem decidiu encerrar. Vem **depois** de `sem
progresso`: o teto de degeneração manda em tudo que o agente escreve, inclusive no
veredito dele. `armar` apaga o arquivo; `retomar` não, e `porque` avisa que ele
está lá.

**Progresso** = sha1 de `git status --porcelain` + `HEAD` + contagem da fila.
Duas paradas com a mesma impressão significam agente falando sem produzir. Fora
de repositório git, a fila responde sozinha.

**Escopo por itens** conta apenas a rodada: `feitos - feitos_ao_armar`. O
denominador é gravado em `armar`, junto de `pendentes_ao_armar` — quantos itens
havia a fazer na hora de armar. Zero ali identifica a rodada que **nasceu morta**
(§5.1 item 5); `None` é estado de versão anterior, e "não sei" nunca vale zero.

**Janela** aceita `HH:MM-HH:MM`, cruza a meia-noite (`22:00-06:00`), e `dias`
aceita `seg-sex` ou `seg,qua,sex`. **Formato inválido nunca encerra** — typo em
`--janela` não pode parar o trabalho em silêncio.

**Política de ASK:** `continuar` (default — assume e registra),
`continuar-exceto-irreversivel` (consulta o léxico de ação sem volta: `drop
table`, `rm -rf`, `push --force`, `produção`, `cobrança`, …) ou `parar`.

⛔ **Rearme automático** (retomar às 08:00 do dia seguinte) é F3: exige cron, e
segue a decisão do ADR-003 do COMMITTER — crontab do Linux, nunca rotina
agendada do Claude Code (que roda na nuvem e não enxerga `~/x`).

Esta tabela **não é implementada duas vezes**: `lib/diagnostico.py::condicoes_de_fim`
é a cadeia, o hook a consome no lugar da própria `if/elif`, e quem só exibe
(`loop-ctl porque`, `loop-watch`) pergunta a ela em vez de manter uma lista
paralela — inclusive para a **ordem** em que as condições aparecem (ADR-013).

### 5.1 Encerramento
1. Grava no `STATE.json` o `encerrado_por` (motivo), o `encerrado_detalhe` e o
   `encerrado_em`. O detalhe é o que separa duas condições que **dividem o mesmo
   motivo** — `escopo concluído` por N itens × por marcador alcançado — e o que
   responde "zerada com quantos?" sem abrir outro arquivo. Campo aditivo: estado
   escrito antes dele lê `None`.
2. Grava `.loop/STATUS.md` com motivo, detalhe, iterações e saldo da fila.
3. `notificar: true` (default) → `fase = "encerrando"` e um **último** `block`
   mandando o agente enviar a push notification e **não** retomar trabalho. A
   parada seguinte encerra de vez. (O hook é um script; a tool de notificação é
   do agente — ADR-009.)
4. `notificar: false` → `ativo = false` na hora, `systemMessage` e exit 0.
5. **Rodada que nasceu morta não relata.** `iteracao == 1`, zero pendente agora e
   `pendentes_ao_armar == 0` → encerra como no item 4, com `systemMessage` dizendo
   "nada a relatar", mesmo com `notificar: true`. Armar sem pendente produz uma
   rodada que morre na primeira parada, e o relatório cairia no turno de quem
   estava fazendo outra coisa (três vezes em 17/08). `pendentes_ao_armar` é `None`
   em estado de versão anterior, e "não sei" **relata**. O registro não muda:
   `STATUS.md`, entry e `INDEX.md` são escritos igual.

`armar` e `retomar` **recusam** fila sem nenhum pendente (`--mesmo-sem-fila`
força). O aviso existia desde a primeira versão e não impediu nenhuma das três
rodadas mortas: texto impresso depois de o estado estar gravado não é
guarda-corpo.

### 5.2 Reabastecimento da fila (ADR-014, revisto pelo ADR-015)

Duas cláusulas são normativas nos dois caminhos abaixo: **escopo declarado** (com
o que "para e pergunta") e **escape da reposição**. Sem a primeira o loop decide
onde a decisão é do dono; sem a segunda ele fabrica trabalho para cumprir a
cláusula — e prosa sem lastro, num repositório onde a documentação é fonte de
verdade, é pior que parar.

**Com relógio — o motor reabastece.** Fila vazia sai da cadeia de fim (§5) e o
hook devolve o **segundo template**,
[prompts/reabastecimento.md](prompts/reabastecimento.md), em vez do de
continuação: o turno escolhe o próximo bloco não coberto dentro do escopo, lê a
documentação dele **inteira**, destila `- [ ]` no fim do `QUEUE.md`, registra o que
mediu, e segue trabalhando. O escopo vem de `.loop/SCOPE.md` **verbatim** quando
existe; sem o arquivo, do `--objetivo`, e o prompt diz ao turno que a fronteira
**não foi declarada** — quem não sabe onde parar precisa saber que não sabe.
O escape é o `.loop/SEM-ESCOPO` da §5.

A parada de reabastecimento é uma parada como qualquer outra: classificada,
arquivada em `entries/`, indexada. E o guarda-corpo contra loop infinito não é
novo — é o `sem progresso`: turno que repõe muda a contagem da fila (que entra no
sha1 da impressão) e zera o contador; turno que não produz nada acumula e encerra.

**Sem relógio — item na cauda que se reproduz.**
[prompts/reabastecer.md](prompts/reabastecer.md) segue válido para a rodada por
itens: uma linha `- [ ]` colada no fim do `QUEUE.md`, que faz o mesmo trabalho e
**repõe-se** ao final. Ali a fila continua sendo o critério de pronto do ciclo, e
o motor não tem por que assumir que existe um próximo bloco.

---

## 6. `.loop/` — o estado

```
.loop/
├── STATE.json        estado do ciclo
├── QUEUE.md          a fila — `- [ ]` / `- [x]`
├── INDEX.md          uma linha por parada
├── ASSUMPTIONS.md    premissas adotadas para não parar
├── STATUS.md         por que encerrou (só no fim)
├── STOP              kill-switch do DONO (presença basta)
├── SCOPE.md          escopo do reabastecimento — opcional, lido verbatim
├── SEM-ESCOPO        veredito do AGENTE: não há bloco em escopo (presença basta)
└── entries/NNNN-{ASK,DOC}-slug.md
```

`SCOPE.md` é **entrada** escrita pelo dono; `SEM-ESCOPO` é **saída** escrita pelo
agente. Nenhum dos dois é criado por `armar` — mas `armar` **apaga** o `SEM-ESCOPO`
(junto do `STOP`) depois das guardas, para a rodada nova não morrer citando a
medição da anterior.

`STATE.json` é gravado por `os.replace` sobre temporário (nunca meio-escrito).
JSON inválido → o hook trata como ausente e sai (fail-open).

Item da fila que carregue `<!-- colhido em #NNNN -->` tem o comentário removido
antes de virar chave de dedup **e** antes de entrar no `reason`: o rastro é
auditoria, não conteúdo. Os dois vazamentos aconteceram e viraram teste.

**O número de uma parada é o do nome do arquivo** (`NNNN-`), nunca o campo `n:`
do front-matter nem a iteração: `armar` zera a iteração a cada rodada, então
numerar por ela faz a rodada de hoje passar por cima da de ontem. Quem escreve
(`proximo_numero_de_entry`) e quem lê (o painel) usam a mesma régua,
`estado.NUM_DE_ENTRY`. O campo `n:` continua sendo gravado, e entries anteriores
a `0.2.3` trazem nele o número antigo — o disco é que manda.

**`objetivo` é reportado, nunca executado** — vai para o `STATUS.md` e para o
`reason` de toda parada. Objetivo que exista e não tenha letra nem dígito
(pontuação, mojibake, placeholder) é recusado por `armar` **e** substituído na
exibição, pela mesma função (`estado.objetivo_legivel`). Guarda na entrada não
dispensa régua na saída: estado gravado antes de uma guarda não passa a
obedecê-la. Vazio segue válido — é a rodada sem objetivo declarado, que imprime
`—`.

---

## 7. Opt-in

`.loop/STATE.json` com `ativo: true` na raiz (ou até 6 níveis acima do `cwd`) é
a **única** condição para o hook agir. Sem ele, o hook global sai em
milissegundos em qualquer repositório da máquina. `.loop/` só nasce por
`loop_ctl.py armar`.

**Amarração à sessão:** `armar` não conhece o próprio `session_id` (a skill roda
de dentro da sessão). A **primeira parada** grava o seu — é necessariamente a da
sessão que armou. Depois disso, outra sessão no mesmo repositório é ignorada
(ADR-008). `--qualquer-sessao` desliga.

`retomar` **limpa** o `session_id` (a menos que `--sessao` venha explícito): quem
retoma quase sempre retoma no dia seguinte, em sessão nova, e manter o id da
rodada anterior fazia o hook sair em silêncio no portão da sessão. `retomar`
também **não** zera `armado_em` — rodada com relógio estourado precisa de `armar`,
e os dois comandos avisam quando é o caso.

**Diagnóstico:** os portões anteriores a qualquer mutação (hook instalado,
`.loop/`, `ativo`, `fase`, amarração) e a cadeia de condições de fim ficam em
`lib/diagnostico.py`, que `loop_ctl.py porque` imprime na ordem em que o hook os
testa. A cadeia tem **uma** cópia: o hook consome `condicoes_de_fim` em vez de
repetir a lista.

---

## 8. Fora de escopo da v1 (não relitigar sem ADR)

- Classificação semântica por modelo (custo por parada, e a léxica cobre os
  casos reais medidos). O desempate por modelo em caso ambíguo é v2.
- Rearme automático por cron (F3).
- O loop escolher **o quê** fazer: a fila vem da documentação, escrita antes.
- Editar `ASSUMPTIONS.md` retroativamente ou apagar `.loop/`.
