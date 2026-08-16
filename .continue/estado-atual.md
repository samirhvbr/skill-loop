# Estado atual — skill-LOOP

> Atualizado em **2026-08-16**, versão `0.1.0`. Onde o projeto está e o que
> precisa do Samir. Escopo e fases em
> [`escopo-projeto.md`](escopo-projeto.md).

## Onde está

**F0 e F1 entregues no mesmo dia.** O motor existe, roda e tem 72 testes com os
controles verificados por mutação. **Nada rodou em trabalho real ainda** — não
há um único número de operação.

O projeto nasceu de uma queixa medida, não de uma ideia: o agente do Samir
produz 5–10 minutos, encerra o turno com um relato, e ele só vê 10 minutos
depois. Duas mensagens reais daquela tarde viraram os fixtures de regressão, e
foram elas que derrubaram o desenho ingênuo (detector de `?`) antes de ele ser
escrito.

## O que roda hoje

```bash
python3 -m unittest discover -s tests -v      # 72 testes, sem modelo, sem rede
./install.sh --dry-run                        # mostra o que faria
python3 skill/loop/loop_ctl.py --raiz <repo> armar --objetivo "..." --itens 10
```

| Componente | Estado |
|---|---|
| `classificador.py` | ✅ ASK × DOC por zona e direção; colheita de itens e pendências declaradas |
| `loop-stop.py` | ✅ hook completo, fail-open absoluto |
| `estado.py` | ✅ `.loop/`, progresso, condições de fim (janela/dias/relógio/escopo) |
| `transcricao.py` | ✅ leitura pela cauda, filtro de subagente |
| `loop_ctl.py` | ✅ armar/parar/retomar/status/fila |
| `install.sh` | ✅ idempotente, convive com os hooks `Stop` existentes, `--uninstall` |
| Operação real | ⛔ nada |

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
