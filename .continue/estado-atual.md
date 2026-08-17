# Estado atual — skill-LOOP

> Atualizado em **2026-08-17**, versão `0.2.3`. Onde o projeto está e o que
> precisa do Samir. Escopo e fases em
> [`escopo-projeto.md`](escopo-projeto.md).

## Onde está

**F0 e F1 entregues no mesmo dia; duas rodadas reais feitas.** O motor existe,
roda e tem 171 testes com os controles verificados por mutação. A rodada de 16/08
no EOP fechou 21/21 itens em 68 minutos com duas paradas, e a auditoria dela
achou o defeito central do produto (ADR-012). **Duas rodadas não são medição:** a
distribuição das condições de fim, o trabalho por iteração e a taxa de erro de
classificação continuam sem número (P-05) — mas as duas encerraram por `fila
zerada`, e nenhuma bateu em janela, relógio, teto ou sem-progresso.

O projeto nasceu de uma queixa medida, não de uma ideia: o agente do Samir
produz 5–10 minutos, encerra o turno com um relato, e ele só vê 10 minutos
depois. Duas mensagens reais daquela tarde viraram os fixtures de regressão, e
foram elas que derrubaram o desenho ingênuo (detector de `?`) antes de ele ser
escrito.

## O que roda hoje

```bash
python3 -m unittest discover -s tests -v      # 171 testes, sem modelo, sem rede
./install.sh --dry-run                        # mostra o que faria
loop-ctl armar --raiz <repo> --objetivo "..." --itens 10
loop-ctl porque --raiz <repo>                 # por que não continuou
loop-watch --raiz <repo> --ate-encerrar       # acompanhar de longe
```

| Componente | Estado |
|---|---|
| `classificador.py` | ✅ ASK × DOC por zona e direção; colheita de itens e pendências declaradas |
| `loop-stop.py` | ✅ hook completo, fail-open absoluto |
| `estado.py` | ✅ `.loop/`, progresso, condições de fim (janela/dias/relógio/escopo) |
| `transcricao.py` | ✅ leitura pela cauda, filtro de subagente |
| `loop_ctl.py` | ✅ armar/parar/retomar/status/fila/`porque` |
| `diagnostico.py` | ✅ portões em ordem + cadeia de fim em uma cópia (ADR-013) |
| `loop_watch.py` | ✅ delta, tempo restante, aviso de hook inerte; consome a cadeia do `diagnostico` (ADR-013 emendado) |
| `install.sh` | ✅ idempotente, convive com os hooks `Stop` existentes, `--uninstall` |
| Operação real | 🟡 duas rodadas (EOP, 16 e 17/08) — sem distribuição, sem taxa de erro |

## Experimento em curso — reabastecimento da fila (17/08, tarde)

**O modo de uso do Samir não está previsto no produto.** Ele arma por *tempo*
(`--duracao 4h`, sem objetivo) esperando que o loop puxe o próximo documento e
siga trabalhando — mas `fila zerada` é a condição **#4** da cadeia e o relógio é
a **#6**, então a fila vazia dispara sempre antes. Foi o que encerrou as duas
rodadas do EOP; o `--duracao` nunca chegou a valer. O desenho assume fila
destilada antes de armar, com fila vazia como critério de pronto (ADR-006).

**Decisão de 17/08:** testar o contorno antes de mexer no guarda-corpo. O
reabastecimento entra como **item na cauda da fila** — trabalho comum, sem código
novo:

```markdown
- [ ] REABASTECER: ler o próximo documento ainda não coberto em `docs/`,
      destilar o próximo bloco em linhas `- [ ]` no fim deste arquivo, e
      terminar acrescentando um novo item REABASTECER.
```

Funciona porque o hook lê o `QUEUE.md` do disco no instante do `Stop`, depois de
o agente já ter escrito nele. Falha em segurança: se o agente esquecer de repor,
a fila zera e o loop encerra — em vez de rodar solto.

**O que a rodada tem de medir** (alimenta P-05 e decide se a flag existe):
quantos reabastecimentos ocorreram; se o item foi mantido na cauda todas as
vezes; e se o trabalho puxado da documentação **derivou**. Derivar é o achado
mais importante dos três — significaria que fila escrita pelo próprio loop
precisa de trava, e o teto da flag nasceria medido em vez de inventado.

⛔ **Não** escrever esse padrão no `SKILL.md` nem abrir ADR antes da rodada: a
alternativa descartada hoje foi justamente desenhar `--reabastecer N` antes de
saber como o padrão se comporta.

### Resultado parcial (17/08, 13:02 — rodada ainda viva)

**O padrão se sustenta.** Armada 10:40, o item entrou 11:19 e o `retomar` 11:21.
Da parada `#6` à `#11`:

| Medida | Valor |
|---|---|
| Paradas desde o `retomar` | 6 (`#6`…`#11`), **todas DOC/relato, todas `continuou`** |
| Reabastecimentos | **6 concluídos**, 1 pendente — o item se reproduziu toda vez |
| Fila | 22 → **53 itens** (48 feitos, 5 pendentes) |
| Intervalo entre paradas | 25 · 14 · 10 · 10 · 7 min |
| Condição que bate primeiro | **relógio** — pela primeira vez em três rodadas |

Zero ASK e zero encerramentos em 6 paradas: nenhuma das duas mortes por
`fila zerada` das rodadas anteriores se repetiu. O que ainda não foi observado é
o comportamento **no fim** — se o relógio bate às 14:40 com a fila cheia, o
encerramento por tempo é o primeiro do projeto e vale medir.

⚠️ **A observar:** `sem progresso` marcou **1/3**. Se chegar a 3 o loop encerra
por loop degenerado. Turno de reabastecimento mexe na contagem da fila, que entra
na impressão digital, então não deveria acumular — mas acumulou uma vez, e o
motivo não foi apurado.

⚠️ **Ainda não medido:** se o trabalho puxado da documentação está **no alvo**.
Os 6 relatos foram classificados DOC e arquivados, mas ninguém leu o conteúdo
para dizer se a fila que o próprio loop escreveu é boa. É o risco que o
README nomeia ("fila ruim = loop ruim, e o hook não detecta isso"), e agora quem
escreve a fila é o loop.

## O que precisa do Samir

1. **Rodar a primeira vez** (F2). Sugestão: um repositório de trabalho real, com
   escopo pequeno e janela curta na primeira rodada —
   `--itens 5 --duracao 2h` — para ver o `INDEX.md` e o `ASSUMPTIONS.md`
   encherem antes de soltar o loop por um dia inteiro.
2. **Decidir P-01:** versionar `.loop/` no repositório alvo (auditoria durável,
   risco de segredo no histórico permanente — T-07) ou ignorá-lo (registro
   local). Não há default seguro para os dois casos.
3. **Revisar o primeiro `ASSUMPTIONS.md` cheio.** É o teste real do ADR-003: se
   houver ali uma decisão que ele queria ter tomado, a política default muda.

## Observações de campo registradas

- **A parada silenciosa de 17/08** (o que virou o ADR-013): "continua" digitado
  na sessão do EOP não continuou, e o agente parou em 2min30. Nada estava
  quebrado — o `.loop/` tinha encerrado às 21:19 do dia anterior por fila zerada,
  e o hook sai no primeiro portão sem escrever nada. O achado que interessa é que
  havia **três** portões fechados ao mesmo tempo, e só o primeiro era óbvio:
  `ativo: false`; `session_id` da sessão de ontem (`retomar` preservava, o que
  faria a reativação falhar em silêncio de novo); e relógio de 2 h estourado
  (`retomar` não zera `armado_em`, só `armar`). Fatos usados no diagnóstico:
  zero ocorrências de `LOOP-WORK` no transcript do dia contra 6 no do dia
  anterior, nenhuma entry nova em `.loop/entries/`, nenhum commit no EOP.
  **Consequência:** fail-open silencioso precisa de comando que fale — e a
  primeira coisa a rodar antes de sair de perto do monitor é `loop-ctl porque`.

- **A rodada de 17/08 de manhã e o item que não era item** (o que virou a emenda
  do ADR-005 e a do ADR-013): armada 08:38, encerrada 09:32 por `fila zerada` em
  2 iterações. O que a fila dizia — 22/22 — não era o que tinha acontecido: o 22º
  item era a **pergunta** da parada `#0003`, colhida como se fosse trabalho e
  marcada `- [x]`. Descontada, a rodada armou com `feitos_ao_armar: 21` e terminou
  com 21: **nenhum item novo da fila fechado**, embora a entry `0004` relate
  entrega real (trabalho que não estava enfileirado). O painel lido às 09:42 sobre
  essa rodada trazia quatro erros ao mesmo tempo — `← primeira` numa rodada morta,
  `#4 #1 #2 #1` na numeração das paradas, `¨¨` de objetivo, e nada dizendo que o
  fim fora dez minutos antes. Os quatro consertados no `0.2.3`; o rastro do EOP
  corrigido no próprio `.loop/` dele, com a correção declarada nos arquivos.

- **Hook `Stop` quebrado no ambiente** (16/08): a saída do agente mostrou
  `Ran 2 stop hooks` com um deles falhando —
  `/home/samir/.local/share/GitKrakenCLI/versions/gk_3_1_68/gk_3_1_68: not found`.
  Não afeta o LOOP (hooks são independentes e o erro é não-bloqueante), mas é
  ruído a cada parada e vale limpar de onde estiver registrado. Reforçou o
  fail-open do ADR-009.
- O ambiente já tem hooks `Stop` do **ai-memory**; o instalador foi verificado
  contra uma cópia do `settings.json` real e os preserva.

## Onde este projeto encosta nos irmãos

- **COMMITTER** — quando o `Stop` dele existir (F2 de lá), os dois hooks
  convivem: o LOOP devolve `block` e o COMMITTER commita a cada parada. Efeito
  colateral desejável: cada iteração do loop vira checkpoint commitado.
- **AUDITOR** — commits regulares do ciclo dão a ele unidades limpas para
  auditar.
