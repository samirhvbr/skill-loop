# skill-LOOP

Skill que faz o agente principal trabalhar por horas sem que ninguém digite
"continua". Um hook `Stop` dispara no instante em que o turno encerra, **lê o
relato**, classifica em **ASK** (esperava decisão sua) ou **DOC** (só relatou o
que fez), arquiva em `.loop/` e devolve o agente ao próximo item da fila.

> **Documentação:** [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) (regras de
> quem desenvolve este repo) · [SECURITY.md](SECURITY.md) (modelo de ameaça —
> leitura obrigatória) · [SPEC.md](SPEC.md) (pipeline e formato do `.loop/`) ·
> [skill/loop/SKILL.md](skill/loop/SKILL.md) (a skill) ·
> [prompts/continuacao.md](prompts/continuacao.md) (o prompt do produto) ·
> [docs/README.md](docs/README.md) (índice técnico) ·
> [docs/decisoes.md](docs/decisoes.md) (ADRs) ·
> [version.md](version.md) (versão e formato de commit) ·
> [.continue/estado-atual.md](.continue/estado-atual.md) (onde o projeto está).
>
> Irmão do [AUDITOR](https://github.com/samirhvbr/AUDITOR) e do
> [COMMITTER](https://github.com/samirhvbr/skill-COMMITTER) — mesmo padrão de
> documentação e a mesma leitura de gatilho: fim de turno é o único instante em
> que o estado do trabalho está em repouso. Status: **F1 entregue** (motor
> testado), **sem operação em trabalho real**. Versão em inglês: [README.md](README.md).

## O problema, medido

O agente produz por 5 a 10 minutos, encerra o turno e escreve um relato do que
fez. Quem está longe do monitor só vê isso 10 minutos depois, digita "continua",
e o ciclo recomeça.

Dois casos reais de 16/08/2026, que viraram os fixtures de regressão da suíte
(**anonimizados** para o repositório público — nomes internos trocados, estrutura
linguística preservada; as duas versões classificam idêntico):

| Mensagem | Produção | Tinha pergunta? | Parou |
|---|---|---|---|
| `tests/fixtures/relato-corrida-instancia.txt` | 9m16s | **nenhuma** | sim |
| `tests/fixtures/relato-fitness-schema.txt` | ~5min | nenhuma explícita — entregou o bastão no fecho | sim |

Em trabalho de meses, a maior parte do calendário é tela apagada. **Não é
lentidão do agente; é vão entre turnos.**

## A tese

Uma skill sozinha não resolve: skill é instrução que o modelo *lê*, e ele
continua encerrando o turno quando julga ter entregue um bloco. Quem intercepta
isso é o **hook `Stop`** — ele recebe o `transcript_path` e, devolvendo
`{"decision": "block", "reason": ...}`, põe o agente de volta a trabalhar com o
`reason` como instrução nova.

Melhor que um loop por timer (`/loop 5m`): timer acorda no relógio e pode acordar
no meio do trabalho ou 4 minutos depois da parada. Hook acorda **quando** ele
para. É a mesma leitura do ADR-003 do COMMITTER.

## O classificador — o sinal não está na pontuação

Detector de `?` erra nos **dois** sentidos, e as duas mensagens reais provam:

**Falso ASK.** "…merecia a pergunta seguinte: quantas outras estão assim?
*Varri as migrações dos dez schemas — sobrava uma.*" Tem `?`, mas o próprio texto
responde na frase seguinte.

**Falso DOC.** "Daqui pra frente, o que sobra de maior valor está do teu lado da
mesa: a convenção do default no OpenAPI, a ✦A, a ✦B corrigida e as respostas
X1–Y2 do canal de voz." **Zero pontos de interrogação** — e é exatamente onde o
agente parou de trabalhar e passou a esperar.

Então o peso é por **zona** e por **direção**:

| Sinal | Onde conta | Efeito |
|---|---|---|
| Entrega de bastão (`do teu lado`, `aguardo`, `cabe a você`, `posso seguir`) | só no **fecho** (2 últimos parágrafos) | ASK |
| `?` no fecho | fecho | ASK |
| `?` auto-respondido (frase seguinte relata ação concluída) ou anunciado (`a pergunta seguinte:`) | qualquer zona | **suprimido** |
| `?` em bloco de código | — | ignorado |
| `AskUserQuestion` como última tool | — | ASK, curto-circuito |
| Marcas de relato (`435 testes · 434 ok`, `varri`, `commitei`) | texto todo | DOC |

E o mais valioso: **o que vira fila**. Do fecho de handoff sai a enumeração em
prosa (com split ciente de parênteses, para `(coluna versao no Ciclo e no
Período)` não virar dois itens); e de qualquer zona sai a **pendência declarada
pelo próprio agente** — a seção "Declarado e não feito" da segunda mensagem real
nomeava o próximo trabalho, e um classificador só de perguntas a perderia inteira.

## Pipeline de cada parada

1. Hook recebe `{session_id, transcript_path, cwd, stop_hook_active}`.
2. Sem `.loop/STATE.json` com `ativo: true` → **exit 0 em milissegundos**. O hook
   é global, o opt-in é por repositório.
3. Lê a última mensagem do agente **principal** no transcript (`isSidechain` é
   subagente e é descartado — sem isso, todo turno com `Explore` viraria ASK).
4. Classifica ASK × DOC.
5. Arquiva `.loop/entries/NNNN-{ASK,DOC}-slug.md` + linha no `INDEX.md`.
6. Colhe itens do fecho e pendências declaradas para o `QUEUE.md`, sem duplicar.
7. Guarda-corpos (abaixo). Nenhum disparou → `decision: block` com o próximo
   item nomeado.
8. Disparou → escreve `STATUS.md` e manda o agente enviar **uma push
   notification** antes de encerrar. (O hook é um script; a tool de notificação
   é do agente — ADR-009.)

## Condições de fim — o loop precisa custar um valor previsível

Um motor que reinicia o agente sozinho e não tem fim é uma fatura sem teto. São
**seis** condições independentes; a primeira que bater encerra, escreve o
`STATUS.md` e dispara a notificação. As quatro primeiras são opcionais e se
combinam livremente (ADR-010).

| Condição | Flag | Exemplo | Para o quê |
|---|---|---|---|
| **Escopo por itens** | `--itens N` | `--itens 10` | "fecha os 10 primeiros e para" |
| **Escopo por marcador** | `--ate TEXTO` | `--ate "3.10 VoIP"` | "vai até este item e para" |
| **Janela de horário** | `--janela` `--dias` | `--janela 08:00-18:00 --dias seg-sex` | "produz das 8h às 18h, dia útil" |
| **Relógio** | `--duracao` | `--duracao 6h` | teto de parede desde que armou |
| Fila zerada | — | — | critério de pronto do ciclo |
| Teto de iterações | `--max` (200) | — | rede final |

O escopo por itens conta **só a rodada atual**: `feitos_ao_armar` é o
denominador, senão `--itens 10` num backlog que já tinha 10 `[x]` encerraria na
primeira parada. A janela cruza a meia-noite (`22:00-06:00`) e **falha aberta**:
`--janela "oito às seis"` não para o trabalho em silêncio.

> **O loop não se rearma sozinho.** Fechada a janela das 18h, ele encerra; às 8h
> do dia seguinte alguém precisa dar `/loop-work retomar`. Rearme automático por
> cron é F3 — e segue a decisão da casa no ADR-003 do COMMITTER (crontab do
> Linux; rotina agendada do Claude Code roda na nuvem e não enxerga `~/x`).

## Outros guarda-corpos

| Guarda | Default | Por quê |
|---|---|---|
| `.loop/STOP` (kill-switch) | — | `touch` de qualquer lugar, sem terminal na sessão |
| Sem progresso | 3 paradas | árvore e fila idênticas = agente falando sem produzir |
| Amarração à sessão | auto | outro chat no mesmo repo não é dirigido por este loop |
| Política de ASK | `continuar` | decisão do Samir; `continuar-exceto-irreversivel` e `parar` disponíveis |

**Fail-open por desenho:** qualquer erro no hook → `exit 0`. O pior caso vira o
comportamento de hoje (você digita "continua"), nunca uma sessão travada.

## Instalação

```bash
./install.sh                 # hook Stop global + skill /loop-work
./install.sh --dry-run       # mostra o que faria
./install.sh --uninstall     # remove os dois; não toca em nenhum .loop/
```

O hook entra em **grupo próprio** no `~/.claude/settings.json`: os hooks `Stop`
já instalados (ai-memory, e o do COMMITTER quando existir) continuam intactos e
todos rodam — só o LOOP devolve `decision: block`.

## Uso

```
/loop-work <objetivo>     destila a fila da documentação e arma
/loop-work status         onde está
/loop-work parar          desarma
/loop-work retomar        rearma de onde parou
```

Com condições de fim explícitas (recomendado para deixar rodando sozinho):

```bash
# fecha 10 itens e para
python3 <skill>/loop_ctl.py armar --objetivo "fase 3" --itens 10

# produz das 8h às 18h em dia útil, com teto de 6 horas de relógio
python3 <skill>/loop_ctl.py armar --objetivo "fase 3" \
        --janela 08:00-18:00 --dias seg-sex --duracao 6h
```

Armar sem fila não funciona: `.loop/QUEUE.md` é o que o hook injeta no `reason`,
e sem ele a continuação vira "continue de onde parou" — o agente re-planeja a
cada turno e o trabalho deriva. A skill lê a documentação e destila a fila antes
de armar; é o passo que decide se o loop funciona.

## O que fica registrado

```
.loop/
├── STATE.json        estado do ciclo
├── QUEUE.md          a fila — e o progresso medido
├── INDEX.md          uma linha por parada
├── ASSUMPTIONS.md    o que foi decidido sem você      ← leia primeiro
├── STATUS.md         por que encerrou
├── STOP              kill-switch (se existir)
└── entries/NNNN-{ASK,DOC}-slug.md
```

Revisar `ASSUMPTIONS.md` não é opcional — é o preço de não ter sido interrompido.

## Limitações declaradas da v1

- **O classificador é léxico, não semântico.** Handoff escrito fora do léxico
  (PT-BR/EN) passa como DOC e o loop continua sem registrar que era decisão sua.
  A cerca é o `ASSUMPTIONS.md` e o `INDEX.md`, revisados depois — não a
  precisão do detector.
- **Nenhum número de campo.** O motor tem 59 testes; operação real é a F2.
- **A fila é escrita por um modelo** a partir da documentação. Fila ruim = loop
  ruim, e isso não é detectável pelo hook.
- **`.loop/entries/` guarda a mensagem inteira do agente.** Se ele ecoar segredo
  no relato, o segredo vai para o disco (T-07 do `SECURITY.md`).
