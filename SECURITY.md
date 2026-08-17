# SECURITY.md — Segurança do LOOP

Leitura **obrigatória** antes de mexer em qualquer coisa que toque o hook, o
classificador, o prompt de continuação ou as condições de fim.

O LOOP é, por definição, um mecanismo que **reinicia um agente autônomo sem
supervisão humana**, possivelmente por horas. Ele não escreve código, não
commita e não chama rede — mas devolve ao trabalho um agente que faz tudo isso.
Cada ameaça abaixo existe por causa dessa mecânica.

> Status: `[x]` = decidido e escrito (ADR + spec) · `[x] ✅` = implementado e
> testado nos dois sentidos · `[ ]` = exige código e teste. Regra de aceite
> herdada do AUDITOR: **cada teste precisa falhar com o controle desligado.**
> As mutações verificadas em 16/08 estão anotadas em cada controle.

---

## T-01 — Agir sem supervisão em repositório que ninguém armou

O hook é **global**: instalado uma vez, dispara no fim de todo turno de toda
sessão da máquina. Se ele agisse por default, passaria a dirigir trabalho em
repositórios onde ninguém pediu.

- [x] ✅ Opt-in **por arquivo no repositório**: `.loop/STATE.json` com
      `ativo: true`. Sem ele, `exit 0` imediato — testado em diretório limpo e
      com loop inativo.
- [x] ✅ `.loop/` só nasce por `loop_ctl.py armar`; nada no hook o cria.
- [x] ✅ **Amarração à sessão** (ADR-008): a primeira parada fixa o
      `session_id`; outra sessão no mesmo repositório é ignorada. Mutação:
      remover a amarração derruba 1 teste.
- [x] ✅ `install.sh --uninstall` remove hook e skill e **não toca em nenhum
      `.loop/`** — desinstalar não apaga registro de trabalho.

## T-02 — Custo sem teto

Um motor que reinicia o agente e não tem fim é uma fatura silenciosa. É a
ameaça de maior probabilidade — e a que o Samir levantou antes de qualquer
linha rodar em trabalho real.

- [x] ✅ **Seis condições de fim independentes** (SPEC §5), a primeira que bater
      encerra: kill-switch, teto de iterações (200), sem progresso (3), fila
      zerada, janela de horário, relógio, escopo por itens, escopo por marcador.
      Mutação: desligar qualquer uma derruba pelo menos 1 teste (kill-switch
      derruba 3).
- [x] ✅ **Detector de loop degenerado**: impressão digital de árvore
      (`git status --porcelain` + `HEAD`) + contagem da fila. Duas paradas
      idênticas = agente falando sem produzir; 3 encerram. É o que impede o pior
      caso — um agente que responde ao `reason` com outro relato, para sempre.
- [x] ✅ **Escopo conta só a rodada** (`feitos_ao_armar` como denominador):
      sem isso `--itens 10` num backlog com 10 `[x]` encerraria de imediato —
      falha benigna, mas mascararia a intenção.
- [x] Nenhuma chamada de modelo, rede ou dependência no caminho do hook: o custo
      do LOOP em si é zero; o que ele gasta é o turno do agente que ele retoma.
- [ ] **Medir em operação**: iterações por sessão, quantas encerram por qual
      condição, quanto trabalho por iteração. Nenhum número de campo existe (F2).

## T-03 — Ação destrutiva decidida por premissa

O default decidido pelo Samir em 16/08 é **continuar sempre** e registrar a
premissa (ADR-003). Isso significa, por construção, que uma pergunta sobre ação
irreversível pode ser respondida pelo próprio agente.

- [x] O `reason` **sempre** manda adotar o default "mais razoável **e
      reversível**" e registrar pergunta · decisão · alternativa descartada ·
      **como reverter** em `.loop/ASSUMPTIONS.md`.
- [x] O `reason` **sempre** lista, como condição de parada real, "a próxima ação
      é destrutiva ou irreversível e não está coberta por uma premissa" — a
      última linha de defesa é o julgamento do agente, e isso está declarado.
- [x] ✅ Política opcional `continuar-exceto-irreversivel`: léxico de ação sem
      volta (`drop table`, `delete from`, `rm -rf`, `push --force`,
      `filter-branch`, `produção`, `revogar`, `cobrança`, `enviar e-mail para`…)
      encerra o loop em vez de continuar. Testada nos dois sentidos: pergunta
      comum passa, `DROP TABLE` encerra.
- [x] ✅ Política `parar` disponível para quem não aceita o default.
- [x] **`ASSUMPTIONS.md` é append-only por convenção** e a skill proíbe editá-lo
      retroativamente — premissa apagada é auditoria destruída.

> **Limite declarado da garantia:** no default, **nada mecânico** impede o agente
> de decidir algo caro. O controle é o registro, revisado depois. Quem quiser a
> cerca liga a política explicitamente — e ela é léxica, não semântica.

## T-04 — Classificação errada silencia uma decisão que era do humano

Um handoff lido como DOC faz o loop seguir sem registrar que havia decisão sua.
É a falha silenciosa do produto.

- [x] ✅ Classificação por **zona e direção**, não por pontuação: os dois casos
      reais de 16/08 quebram o detector ingênuo em sentidos opostos e são
      fixtures de regressão. Mutação: desligar o léxico de handoff derruba 6
      testes; desligar a zona de fecho derruba 5.
- [x] ✅ Toda parada vira `entry` com a **mensagem original inteira**, o veredito,
      o sinal e as evidências — inclusive a retórica suprimida. Erro de
      classificação é auditável depois, mesmo quando não muda a decisão.
- [x] ✅ `AskUserQuestion` curto-circuita para ASK: pergunta declarada pelo
      protocolo não depende de heurística.
- [x] ✅ Filtro de subagente (`isSidechain`): sem ele, o relatório de um `Explore`
      terminando em "?" seria lido como pergunta do agente principal. Mutação:
      derruba 8 testes.
- [x] Falso DOC é mitigado pela **colheita**: mesmo classificando errado, o item
      pendente entra na fila e não se perde.
- [x] ✅ **Rótulo de fecho parcial** (ADR-012): quando o fecho do turno não
      chegou ao transcript a tempo, a `entry` grava `fecho_do_turno: PARCIAL` e
      a confiança cai para `baixa`. Nasceu de um defeito real, e silencioso: na
      primeira rodada em produção as duas entries arquivaram fragmento de meio
      de raciocínio como se fosse relatório. Mutação: desligar a espera derruba
      as 2 regressões.
- [ ] Desempate por modelo em caso de confiança `media` (v2). Hoje `media` segue
      o veredito léxico.

## T-05 — Hook quebrado trava a sessão

Um hook `Stop` que estoura, trava ou devolve lixo pode inutilizar o Claude Code
da máquina inteira — em **todos** os repositórios, não só nos que usam o LOOP.

- [x] ✅ **Fail-open absoluto**: `try/except Exception → exit 0` no topo. Testado
      com stdin inválido, stdin vazio, transcript inexistente e `STATE.json`
      corrompido.
- [x] ✅ Perder o transcript **não** encerra o loop: classifica como DOC vazio e
      segue. Perder a mensagem não pode significar perder o trabalho.
- [x] Timeout de 15 s no registro; leitura do transcript limitada a 2 MB pela
      cauda (sessão de meses não vira leitura de arquivo inteiro).
- [x] Sem rede, sem dependência externa, sem escrita fora de `.loop/`.
- [x] ✅ Instalador **anexa** grupo e preserva os hooks `Stop` existentes —
      verificado contra uma cópia do `settings.json` real, com backup datado
      antes de escrever.

## T-06 — Injeção pelo conteúdo da mensagem

Os itens colhidos saem do **texto da mensagem** e vão para o `QUEUE.md`, que
volta ao agente dentro do `reason`. É um caminho de dado → prompt.

- [x] A origem é a saída do próprio agente principal, não conteúdo de terceiro
      — a superfície é bem menor que a de um diff arbitrário (T-04 do COMMITTER).
      Mas a saída dele pode repetir texto que ele leu.
- [x] ✅ Colheita **limitada**: 12 itens por parada, cada um truncado, dedup
      contra a fila inteira. Não há caminho pelo qual a colheita apague ou
      reordene item existente — ela só **anexa** sob `## Colhidos automaticamente`.
- [x] ✅ Proveniência (`<!-- colhido em #NNNN -->`) fica no arquivo para auditoria
      e é **removida** antes de entrar no `reason`.
- [x] O `QUEUE.md` é arquivo do repositório, visível e editável: item plantado
      aparece no `git diff` da fila.
- [ ] Teste com item hostil plantado numa mensagem de fixture (ex.: item que
      instrui a ignorar as condições de fim) — o alvo do teste é que ele apareça
      no `QUEUE.md` como texto e não altere estado.

## T-07 — Vazamento pelo arquivo de registro

`.loop/entries/NNNN-*.md` guarda a **mensagem inteira** do agente. Se ele ecoou
uma credencial no relato, ela vai para o disco — e, se o repositório versiona
`.loop/`, para o histórico do git, que é permanente.

- [x] Registrar a mensagem inteira é **deliberado**: sem ela o `INDEX.md` não é
      auditável e o classificador não é revisável.
- [x] O `.gitignore` deste repositório ignora `.loop/` — aqui ele é fixture de
      desenvolvimento, não registro de trabalho real.
- [ ] **Decisão por repositório alvo**: versionar `.loop/` (auditoria durável,
      risco de segredo no histórico) ou ignorá-lo (registro local). Não há
      default seguro para os dois casos; a skill precisa perguntar ao armar. ⛔
- [ ] Scan de segredo no texto antes de gravar a `entry` — os padrões do
      `redact.py` do AUDITOR estão vendorizados no COMMITTER e podem ser
      vendorizados de novo aqui.

---

## Política do repositório

- Nunca commitar `.env`, chave ou credencial; fixtures usam texto real de
  mensagens do agente, revisado — **nunca** cole transcript sem ler.
- Os dois fixtures em `tests/fixtures/` são mensagens reais de trabalho do
  Samir, **anonimizadas** antes da publicação (nomes de classe, tabela,
  constraint, módulo, item de roadmap e versão de SPEC trocados; estrutura
  preservada). Os originais ficam em `fixtures-reais/`, no `.gitignore`.
  Anonimizar é obrigatório e verificável: as duas versões precisam classificar
  idêntico, senão a troca apagou sinal. Qualquer fixture novo passa pelo mesmo
  processo.
- Dependência nova exige justificativa em ADR — meta: **zero** além de Python 3.
- Reescrita de histórico proibida no working copy de `~/x`.

## Reportar vulnerabilidade

Repositório público (`github.com/samirhvbr/skill-LOOP`). Falha que permita
execução indevida, travamento de sessão ou vazamento: reporte direto ao
mantenedor — Samir Hanna Verza ([@samirhvbr](https://github.com/samirhvbr)); não
abra issue pública descrevendo a falha.
