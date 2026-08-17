# Estado atual — skill-LOOP

> Atualizado em **2026-08-17**, versão `0.2.2`. Onde o projeto está e o que
> precisa do Samir. Escopo e fases em
> [`escopo-projeto.md`](escopo-projeto.md).

## Onde está

**F0 e F1 entregues no mesmo dia; uma rodada real feita.** O motor existe, roda
e tem 155 testes com os controles verificados por mutação. A rodada de 16/08 no
EOP fechou 21/21 itens em 68 minutos com duas paradas, e a auditoria dela achou o
defeito central do produto (ADR-012). **Uma rodada não é medição:** a
distribuição das condições de fim, o trabalho por iteração e a taxa de erro de
classificação continuam sem número (P-05).

O projeto nasceu de uma queixa medida, não de uma ideia: o agente do Samir
produz 5–10 minutos, encerra o turno com um relato, e ele só vê 10 minutos
depois. Duas mensagens reais daquela tarde viraram os fixtures de regressão, e
foram elas que derrubaram o desenho ingênuo (detector de `?`) antes de ele ser
escrito.

## O que roda hoje

```bash
python3 -m unittest discover -s tests -v      # 155 testes, sem modelo, sem rede
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
| `loop_watch.py` | ✅ delta, tempo restante, aviso de hook inerte |
| `install.sh` | ✅ idempotente, convive com os hooks `Stop` existentes, `--uninstall` |
| Operação real | 🟡 uma rodada (EOP, 16/08) — sem distribuição, sem taxa de erro |

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
