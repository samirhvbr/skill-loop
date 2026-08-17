# skill-LOOP — Instruções para Claude Code

> **Leia também:** [README_br.md](README_br.md) (o produto, canônico) ·
> [SECURITY.md](SECURITY.md) (**leitura obrigatória** — modelo de ameaça) ·
> [SPEC.md](SPEC.md) (pipeline normativo e formato do `.loop/`) ·
> [docs/decisoes.md](docs/decisoes.md) (ADR-001 a ADR-013 + pendências) ·
> [prompts/continuacao.md](prompts/continuacao.md) (o prompt do produto) ·
> [version.md](version.md) (versão + formato de commit).
>
> `CLAUDE.md` e `AGENTS.md` são **espelhados** abaixo do H1 — editar os dois.

---

## 🔄 Antes de começar: `git pull`

**SEMPRE** verifique atualizações remotas antes de escrever ou alterar qualquer
coisa neste repositório:

```bash
git pull          # já está pré-autorizado (allow)
```

---

## O que é este repo

Skill **loop-work** (comando `/loop-work`): um hook `Stop` que, a cada fim de
turno do agente principal, lê a última mensagem no transcript, classifica em
**ASK** (esperava decisão do humano) ou **DOC** (só relatou), arquiva em
`.loop/entries/`, colhe itens pendentes para a fila e devolve
`{"decision": "block", "reason": ...}` — o agente volta a trabalhar sem ninguém
digitar "continua".

Irmão do **AUDITOR** (`~/x/SKILLS/skill-AUDITOR`) e do **COMMITTER**
(`~/x/SKILLS/skill-COMMITTER`): mesmo padrão de documentação, e a mesma leitura
de gatilho do ADR-003 de lá — fim de turno é o único instante em que o estado do
trabalho está em repouso.

---

## ⚠️ Estado do projeto: F1 entregue, primeira rodada real feita

O que **existe e roda** (`0.1.0`, 16/08/2026):

- `skill/loop/lib/classificador.py` — ASK × DOC por zona e direção.
- `skill/loop/hooks/loop-stop.py` — o hook, com fail-open absoluto.
- `skill/loop/lib/estado.py` — `.loop/` inteiro + condições de fim.
- `skill/loop/lib/transcricao.py` — leitura pela cauda, filtro de subagente.
- `skill/loop/loop_ctl.py` — armar/parar/retomar/status/fila/**porque**.
- `skill/loop/lib/diagnostico.py` — os portões do hook em ordem, e a cadeia de
  condições de fim em **uma** cópia (o hook consome ela) — ADR-013.
- `skill/loop/loop_watch.py` — acompanhamento de longe (delta + tempo restante).
- `install.sh` — hook global idempotente, `--dry-run`, `--uninstall`.
- **155 testes**, controles verificados por mutação.

```bash
python3 -m unittest discover -s tests -v      # 155 testes, sem modelo, sem rede
./install.sh --dry-run                        # mostra o que faria
loop-watch --uma-vez --raiz <repo>            # uma leitura do acompanhamento
```

**Primeira rodada real (16/08, EOP):** 21/21 itens em 68 minutos, duas paradas,
encerrada por fila zerada. A auditoria dela achou o defeito central — o hook
lia o transcript antes de o fecho do turno chegar lá, e arquivava fragmento no
lugar do relatório (ADR-012). **Uma rodada não é medição**: o que a F2 pede
(distribuição das condições de fim, trabalho por iteração, taxa de erro de
classificação) continua sem número.

O que **não existe**: rearme automático por cron (F3), desempate por modelo
(v2), scan de segredo na entry (P-02). `SPEC.md` marca com ⛔ o que falta.

**Os dois fixtures em `tests/fixtures/` são mensagens reais do agente do Samir
(16/08), anonimizadas** para o repositório público: nomes de classe, tabela,
constraint, módulo e item de roadmap trocados; estrutura linguística intacta.
Eles não são exemplo — são a **calibração** do classificador, e cada um quebra o
detector ingênuo em um sentido. Não os altere para fazer um teste passar; se a
regra mudou, o ADR-004 muda junto.

Os originais ficam em `fixtures-reais/` (no `.gitignore`), com o script que
confere se as duas versões classificam igual. Anonimização que muda o veredito
apagou sinal e precisa ser refeita.

---

## Padrão de Commits (obrigatório)

Formato: `X.Y.Z - Descrição curta em português`. A versão **sempre** vem de
[`version.md`](version.md), bumpada **no mesmo commit**. Critério resumido:
**Z** = entrega que muda regra/spec/prompt/léxico/guarda-corpo; **Y** = fase
concluída, quebra de contrato do `.loop/`, ADR que muda direção; **X** = loop
operando em trabalho real da casa. **Proibido** `feat:`/`fix:`/`chore:` e
mensagens vagas.

---

## Regras do produto (não relitigar sem ADR)

1. Gatilho é o hook `Stop` — não skill sozinha, não timer (ADR-001).
2. `stop_hook_active` **não** é a trava; o contador é próprio (ADR-002).
3. ASK **sempre continua** com premissa registrada; `parar` e
   `continuar-exceto-irreversivel` são configuração, não default (ADR-003).
4. Classificação por **zona e direção**, não por pontuação; supressão de retórica
   é propriedade da frase (ADR-004).
5. Colheita de itens é **independente do veredito** ASK/DOC (ADR-005).
6. `QUEUE.md` é a fonte do próximo passo — não a todo list nativa (ADR-006).
7. Hook global, opt-in por `.loop/`, em grupo próprio no `settings.json`
   (ADR-007).
8. Amarração à sessão por auto-bind na primeira parada — e `retomar` **limpa** o
   `session_id` para re-amarrar (ADR-008 + emenda de 17/08).
9. **Fail-open absoluto**; a notificação push é emitida pelo agente, não pelo
   hook (ADR-009).
10. Condições de fim combináveis: escopo por itens, por marcador, janela de
    horário, relógio (ADR-010).
11. A cadeia de condições de fim tem **uma** cópia (`lib/diagnostico.py`, o hook
    consome); os portões de inércia são espelho, provado por teste emparelhado
    contra o hook. `loop-ctl porque` é a resposta a "por que não continuou?"
    (ADR-013).

E o que o LOOP **nunca** faz: agir sem `.loop/` armado, criar `.loop/` sozinho,
apagar ou reescrever `ASSUMPTIONS.md`, escrever fora de `.loop/`, chamar rede ou
modelo, sobreviver a `.loop/STOP`.

---

## Regras de escrita

- **Idioma do repositório: PT-BR.** `README_br.md` é o canônico; `README.md` é a
  tradução para inglês, porta de entrada do repositório público — **editar os
  dois no mesmo commit** quando a regra muda.
- Documentação durável → `docs/`. Notas de trabalho → `.continue/`. Contrato
  normativo → `SPEC.md`. Prompt do produto → `prompts/` (nunca na raiz com nome
  que ferramenta carrega sozinha — lição do ADR-007 do AUDITOR).
- Sem link para arquivo inexistente; futuro se descreve em texto.
- Distinguir **fato observado**, **inferência** e **recomendação**.

---

## Como o Claude Code deve operar aqui

- **Planeje antes de editar** (`defaultMode: plan`).
- Mudanças pequenas e atômicas; ao concluir entrega, **atualize `version.md`** e
  `.continue/estado-atual.md`.
- **Controle só conta com teste que falha quando o controle é desligado** —
  regra herdada do AUDITOR. Ao adicionar guarda-corpo ou regra do classificador,
  rode a mutação e registre quantos testes ela derruba.
- Mudou `prompts/continuacao.md`? É o produto: bump obrigatório.
- Decisão pendente bloqueia? Faça o que não depende dela e pergunte — não escolha
  por conta própria. (Ironia registrada: este repo constrói a skill que decide
  sozinha; o desenvolvimento **dele** segue o fluxo normal da casa.)
- Nunca teste o hook alterando o `~/.claude/settings.json` real: use
  `CLAUDE_SETTINGS` e `CLAUDE_SKILLS_DIR` apontando para diretório temporário.

---

## Referências rápidas

- Versão e commits: [version.md](version.md)
- Modelo de ameaça: [SECURITY.md](SECURITY.md)
- Pipeline e formato: [SPEC.md](SPEC.md)
- Decisões: [docs/decisoes.md](docs/decisoes.md)
- Escopo e fases: [.continue/escopo-projeto.md](.continue/escopo-projeto.md)
- Estado atual: [.continue/estado-atual.md](.continue/estado-atual.md)
- Perfil do agente: [.claude/README.md](.claude/README.md)
- Irmãos: `~/x/SKILLS/skill-AUDITOR`, `~/x/SKILLS/skill-COMMITTER`
- Remoto: `github.com/samirhvbr/skill-LOOP` (público) · branch `master`

---

## PS — Commits: a skill COMMITTER cuida disso

**Existe `.committer.yml` na raiz deste repositório** — é o opt-in da skill
**COMMITTER**, que roda em ciclo (cron, via `~/x/GIT/run.sh`). Enquanto esse
arquivo existir com `enabled: true`, **commitar e pushar não é trabalho seu**.

**O que muda para você:**

- **Não commite nem pushe por padrão.** Conclua a entrega bumpando o `version.md`
  **com a entrada de changelog** e deixe a árvore pronta. É dali que a mensagem
  do commit sai — o changelog virou o artefato de handoff entre você e a skill.
- A skill monta `X.Y.Z - descrição`, commita e pusha a branch atual sozinha. Ela
  **nunca bumpa versão** (isso continua sendo julgamento seu) e nunca inventa
  mensagem: sem entrada de changelog ela cai num fallback Sonnet, e sem conseguir
  descrever com honestidade ela aborta e espera.

**Você ainda commita quando:**

- o Samir pedir explicitamente;
- a tarefa exigir o SHA na hora (deploy, abrir PR, referência cruzada);
- o `.committer.yml` sumir ou estiver `enabled: false` — aí vale o fluxo antigo,
  você bumpa, commita e pusha.

**Por que isso existe:** tirar de um modelo caro (Opus/Fable) o trabalho mecânico
de empacotar commit, que um Sonnet — ou, na maioria das vezes, nenhum modelo —
resolve. Economiza token e devolve tempo de desenvolvimento.
