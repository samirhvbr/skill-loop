# Versão — skill-LOOP

**Versão atual:** `0.2.0`

> Este arquivo é a **fonte da verdade** da versão do projeto. Qualquer lugar que
> precise exibir ou reportar a versão extrai o **primeiro número semver (`X.Y.Z`)**
> encontrado aqui. Mantenha a linha **"Versão atual"** sempre como a primeira
> ocorrência de um número de versão. Mesma mecânica dos projetos-irmãos
> (AUDITOR, COMMITTER).

---

## 1. Convenção de Versionamento (`X.Y.Z`)

| Componente | Significado | Como sobe |
|---|---|---|
| **X** | Release estável — loop operando em trabalho real da casa | Manual |
| **Y** | Mudança estrutural — fase concluída, mudança de contrato (`STATE.json`, formato do `.loop/`), ADR aceito que muda a direção | Manual |
| **Z** | Incremento a cada entrega | A cada entrega |

Enquanto `X` for `0`, contratos podem quebrar entre versões `0.Y`.

### Gatilhos de bump do `Z`

- Alterar o **léxico do classificador** ou qualquer regra de ASK × DOC.
- Alterar o **prompt de continuação** (`prompts/continuacao.md`) — é o produto.
- Alterar guarda-corpos: teto de iterações, sem-progresso, kill-switch, fila.
- Alterar o esquema do `STATE.json` ou o formato de `.loop/`.
- Alterar `install.sh` ou `.claude/settings.json`.
- Criar ou alterar documento em `docs/`, `SPEC.md` ou `prompts/` que **muda uma
  regra** (não vale corrigir redação).
- Adicionar ou alterar testes que definem comportamento esperado.

### Gatilhos de bump do `Y`

- Fase concluída (ver `.continue/escopo-projeto.md`).
- Quebra de compatibilidade no `.loop/` já existente em algum repo.
- ADR novo com status **Aceito** que muda a direção.

> Correções de texto, typo e formatação **não** exigem bump.

---

## 2. Formato de Commit Obrigatório

```
X.Y.Z - Descrição curta em português
```

**Regras inegociáveis:**

1. A versão **sempre** vem deste `version.md`, bumpada **no mesmo commit**.
2. Mensagem em **português**, descritiva o suficiente para `git log --grep`.
3. **Proibido** Conventional Commits (`feat:`, `fix:`, `chore:`…) e vago.
4. Um objetivo por commit; mudanças pequenas e atômicas.

O bump entra em **um único commit** por entrega (o primeiro). Commits adicionais
da mesma entrega repetem a versão.

---

## 3. Changelog

### `0.2.0` — 2026-08-16 — primeira rodada real, e o defeito que ela revelou

**O loop rodou em trabalho de verdade** (EOP, 20:11→21:19): armado com fila de
21 itens e janela até 22h, fechou **21/21**, encerrou pela condição declarada
(fila zerada), mandou o agente enviar a push notification e parou. **Duas
paradas em 68 minutos** — uma única continuação substituiu o "continua" que
custaria 10 minutos de tela apagada. Saldo do outro lado: 72 arquivos tocados,
`version.md` do EOP de 1.27.11 → 1.29.0, ADR-081 escrito lá, e um
`ASSUMPTIONS.md` registrando as três premissas com o custo de desfazer cada uma.

**E a auditoria da rodada achou o defeito central do produto (ADR-012).** As
duas `entries` arquivadas eram **fragmentos de meio de raciocínio**, não
relatórios: o hook `Stop` dispara antes de o Claude Code gravar o último bloco
de texto no JSONL. Na parada #2 ele leu às 00:19:22 um texto de **00:12:30** —
154 entradas atrás — enquanto o relato verdadeiro era escrito naquele segundo.
Ler o retorno e documentá-lo **é** o produto, e ele documentava a coisa errada,
em silêncio: a decisão de continuar não depende do texto, então nada denunciava.
O único sinal era o `confianca: media` que o classificador registrou nas duas.

**Conserto:** a leitura passa a responder se o texto é o **fecho do turno**
(nada do agente principal depois dele) e **espera** até 3 s pelo fecho, relendo
a cada 100 ms. Estourando, segue mesmo assim — mas grava `fecho_do_turno:
PARCIAL`, derruba a confiança para `baixa` e diz na evidência que aquilo não é
o relatório. Subagente não conta como conteúdo depois; `AskUserQuestion` fecha
o turno por si e não gera espera.

**11 testes novos** (`tests/test_transcricao.py`), com a corrida reproduzida de
verdade: o fecho é escrito por outra thread **durante** a espera. Total **83**.
Mutação: desligar a espera derruba as duas regressões e devolve exatamente o
comportamento de 16/08.

**Ainda não feito:** a espera resolve a corrida do fecho, não mede quanto dela
sobra em sessões maiores — o teto de 3 s é escolha, não medição (P-07).

### `0.1.0` — 2026-08-16 — F0 e F1: proposta fechada e motor determinístico

Nasce a skill que faz o agente trabalhar sem "continua" a cada cinco minutos.
Proposta fechada com o Samir na conversa de 16/08, e o núcleo entregue no mesmo
dia — a documentação e o código saíram juntos porque o classificador só ficou de
pé depois de calibrado contra **duas mensagens reais** do agente dele,
publicadas anonimizadas (originais em `fixtures-reais/`, fora do git).

**Decidido** (ADR-001 a ADR-009): gatilho é hook `Stop`, não skill nem timer;
`stop_hook_active` não serve de trava; ASK sempre continua com premissa
registrada; classificação por **zona e direção**, não por pontuação; itens do
fecho e pendências declaradas viram fila; `QUEUE.md` é a fonte do próximo passo;
fail-open; auto-amarração à sessão; notificação push pelo próprio agente.

**Entregue e testado** — 72 testes, controles verificados por mutação:

- `skill/loop/lib/classificador.py` — ASK × DOC por zona de fecho, supressão de
  retórica auto-respondida, léxico de handoff PT-BR/EN, colheita de itens com
  split ciente de parênteses, colheita de pendências declaradas.
- `skill/loop/hooks/loop-stop.py` — o hook: classifica, arquiva, decide e
  devolve `decision: block` com o próximo item. Fail-open em qualquer erro.
- `skill/loop/lib/estado.py` — `.loop/` inteiro: estado, fila, entries, índice,
  premissas, status, impressão digital de progresso.
- `skill/loop/lib/transcricao.py` — leitura pela cauda do JSONL, filtro de
  subagente.
- `skill/loop/loop_ctl.py` — armar/parar/retomar/status/fila.
- `install.sh` — hook global idempotente que convive com os hooks `Stop` já
  instalados; `--dry-run` e `--uninstall`.

**Dois defeitos achados pelos próprios testes** antes de qualquer uso: o
comentário de proveniência entrava na chave de dedup (item recolhido a cada
parada) e vazava para o prompt; e encerrar com `notificar: false` deixava o loop
ativo.

**Ainda não feito:** operação em trabalho real (F2) — nenhum número de campo
existe. Ver `.continue/escopo-projeto.md`.
