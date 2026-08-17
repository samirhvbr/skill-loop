# Escopo e fases — skill-LOOP

> Fases com critério de pronto. Decisões fechadas em
> [`docs/decisoes.md`](../docs/decisoes.md) (ADR-001 a ADR-011); pendências P-01
> a P-06 na tabela de lá. Alterar fase = atualizar aqui + bumpar `version.md`.

## F0 — Baseline de documentação ✅ (0.1.0)

Proposta fechada com o Samir (16/08), ADRs registrados, pipeline normativo,
modelo de ameaça, prompt do produto. As três perguntas de desenho foram
respondidas na conversa: ASK sempre continua com premissa (ADR-003), fila
destilada da documentação (ADR-006), notificação push ao encerrar (ADR-009).

## F1 — Motor determinístico ✅ (0.1.0)

Entregue em 16/08, no mesmo dia da proposta — o classificador só ficou de pé
depois de calibrado contra **duas mensagens reais** do agente do Samir, e por
isso código e documentação saíram juntos. Os fixtures publicados são a versão
anonimizada delas — verificado que as duas classificam idêntico.

- ✅ `classificador.py` — zona de fecho, supressão de retórica auto-respondida,
  léxico de handoff PT-BR/EN, colheita com split ciente de parênteses, colheita
  de pendências declaradas.
- ✅ `loop-stop.py` — hook completo, fail-open absoluto.
- ✅ `estado.py` — `.loop/` inteiro, impressão digital de progresso, condições
  de fim (janela, dias, relógio, escopo).
- ✅ `transcricao.py` — leitura pela cauda, filtro de subagente.
- ✅ `loop_ctl.py` + `install.sh` (idempotente, `--dry-run`, `--uninstall`).
- ✅ **83 testes**, verificados por mutação: desligar o léxico de handoff derruba
  6; a zona de fecho, 5; o filtro de subagente, 8; o kill-switch, 3.

**Dois defeitos achados pelos próprios testes**, antes de qualquer uso: o
comentário de proveniência entrava na chave de dedup e vazava para o prompt; e
encerrar com `notificar: false` deixava o loop ativo.

**Critério de pronto atingido:** o hook classifica as duas mensagens reais
corretamente, colhe os itens de ambas, e nenhuma condição de fim passa sem teste.

## F2 — Operação real ⛔

Nada aqui foi feito. É a fase que transforma o motor em produto.

- ⛔ Instalar no ambiente do Samir e armar em **um** repositório de trabalho real.
- ⛔ Primeira rodada com condições de fim conservadoras (escopo pequeno + janela).
- ⛔ **Medir** (P-05): iterações por sessão, distribuição das condições de fim,
  trabalho por iteração, e quantas paradas foram classificadas erradas.
- ⛔ Revisar o primeiro `ASSUMPTIONS.md` cheio — é o teste real do ADR-003.
- ⛔ Decidir P-01: versionar `.loop/` no repositório alvo ou ignorá-lo.

**Pronto quando:** uma jornada de trabalho inteira roda sem ninguém digitar
"continua", o loop encerra por uma condição declarada, e o `ASSUMPTIONS.md`
revisado não tem nenhuma decisão que o Samir queria ter tomado.

## F3 — Rearme automático ⛔

- ⛔ Cron que retoma o loop quando a janela reabre (08:00 do dia útil seguinte).
- ⛔ Decisão herdada: crontab do Linux, na crontab do usuário `samir` — rotina
  agendada do Claude Code roda na nuvem e não enxerga `~/x` (ADR-003 do
  COMMITTER).
- ⛔ Ordenação contra os ciclos do COMMITTER e do AUDITOR no mesmo repositório.

**Pronto quando:** "produz das 8h às 18h" é verdade sem intervenção nenhuma.

## v2 (fora de escopo até ADR próprio)

- Desempate por modelo quando a confiança do classificador é `media` (P-03).
- Scan de segredo antes de gravar a `entry` (P-02).
- Fila hierárquica com dependências, em vez de lista linear.
