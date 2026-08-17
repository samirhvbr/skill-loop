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

---

## 5. Condições de fim (ADR-010)

Verificadas a cada parada, **nesta ordem**; a primeira que bater encerra:

| # | Condição | Campo | Default |
|---|---|---|---|
| 1 | kill-switch | arquivo `.loop/STOP` | — |
| 2 | teto de iterações | `max_iteracoes` | 200 |
| 3 | sem progresso | `sem_progresso ≥ max_sem_progresso` | 3 |
| 4 | fila zerada | nenhum `- [ ]` | — |
| 5 | fora da janela | `janela` + `dias` | `null` |
| 6 | relógio | `duracao_max_min` | `null` |
| 7 | escopo por itens | `escopo_itens` | `null` |
| 8 | escopo por marcador | `escopo_ate` | `null` |
| 9 | política de ASK | `politica_ask` | `continuar` |

**Progresso** = sha1 de `git status --porcelain` + `HEAD` + contagem da fila.
Duas paradas com a mesma impressão significam agente falando sem produzir. Fora
de repositório git, a fila responde sozinha.

**Escopo por itens** conta apenas a rodada: `feitos - feitos_ao_armar`. O
denominador é gravado em `armar`.

**Janela** aceita `HH:MM-HH:MM`, cruza a meia-noite (`22:00-06:00`), e `dias`
aceita `seg-sex` ou `seg,qua,sex`. **Formato inválido nunca encerra** — typo em
`--janela` não pode parar o trabalho em silêncio.

**Política de ASK:** `continuar` (default — assume e registra),
`continuar-exceto-irreversivel` (consulta o léxico de ação sem volta: `drop
table`, `rm -rf`, `push --force`, `produção`, `cobrança`, …) ou `parar`.

⛔ **Rearme automático** (retomar às 08:00 do dia seguinte) é F3: exige cron, e
segue a decisão do ADR-003 do COMMITTER — crontab do Linux, nunca rotina
agendada do Claude Code (que roda na nuvem e não enxerga `~/x`).

### 5.1 Encerramento
1. Grava `.loop/STATUS.md` com motivo, detalhe, iterações e saldo da fila.
2. `notificar: true` (default) → `fase = "encerrando"` e um **último** `block`
   mandando o agente enviar a push notification e **não** retomar trabalho. A
   parada seguinte encerra de vez. (O hook é um script; a tool de notificação é
   do agente — ADR-009.)
3. `notificar: false` → `ativo = false` na hora, `systemMessage` e exit 0.

---

## 6. `.loop/` — o estado

```
.loop/
├── STATE.json        estado do ciclo
├── QUEUE.md          a fila — `- [ ]` / `- [x]`
├── INDEX.md          uma linha por parada
├── ASSUMPTIONS.md    premissas adotadas para não parar
├── STATUS.md         por que encerrou (só no fim)
├── STOP              kill-switch (presença basta)
└── entries/NNNN-{ASK,DOC}-slug.md
```

`STATE.json` é gravado por `os.replace` sobre temporário (nunca meio-escrito).
JSON inválido → o hook trata como ausente e sai (fail-open).

Item da fila que carregue `<!-- colhido em #NNNN -->` tem o comentário removido
antes de virar chave de dedup **e** antes de entrar no `reason`: o rastro é
auditoria, não conteúdo. Os dois vazamentos aconteceram e viraram teste.

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
