# skill-LOOP — Instruções para Claude Code

> **Leia também:** [README_br.md](README_br.md) (o produto, canônico) ·
> [SECURITY.md](SECURITY.md) (**leitura obrigatória** — modelo de ameaça) ·
> [SPEC.md](SPEC.md) (pipeline normativo e formato do `.loop/`) ·
> [docs/decisoes.md](docs/decisoes.md) (ADR-001 a ADR-016 + pendências) ·
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
- `prompts/reabastecer.md` — o item que faz a fila durar mais que o bloco
  destilado (ADR-014).
- `skill/loop/lib/diagnostico.py` — os portões do hook em ordem, e a cadeia de
  condições de fim em **uma** cópia (o hook consome ela) — ADR-013.
- `skill/loop/loop_watch.py` — acompanhamento de longe (delta + tempo restante).
- `install.sh` — hook global idempotente, `--dry-run`, `--uninstall`.
- `skill/loop/templates/loop.sh` — o atalho que `armar` semeia em
  `.loop/loop.sh` do repositório alvo: `./.loop/loop.sh [6h]` rearma e abre
  o painel, com a raiz derivada e sem sobrescrever a cópia do dono (ADR-016).
- **248 testes**, controles verificados por mutação.

```bash
python3 -m unittest discover -s tests -v      # 248 testes, sem modelo, sem rede
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

Formato: `X.Y.Z - Short description in English`. **Desde 02/09/2026 a
mensagem de commit deste repositório é em inglês** (a regra normativa vive em
[`version.md`](version.md) §2, que também está em inglês). A versão **sempre** vem de
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
5. Colheita de itens é **independente do veredito** ASK/DOC — e a **pergunta
   detectada nunca vira item de fila**, nos dois vereditos (ADR-005 + emenda de
   17/08: um `- [x]` numa pergunta zera a fila e encerra a rodada).
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
    consome) — e quem só **exibe** (`porque`, `loop-watch`) pergunta a ela, ordem
    inclusive: painel não opina sobre qual condição manda. Os portões de inércia
    são espelho, provado por teste emparelhado contra o hook. `loop-ctl porque` é
    a resposta a "por que não continuou?" (ADR-013 + emenda de 17/08).
12. Reabastecimento da fila é **item na cauda que se repõe**
    ([prompts/reabastecer.md](prompts/reabastecer.md)), não flag — com escopo
    declarado e escape da reposição, porque cumprir a cláusula sem insumo obriga a
    fabricar trabalho (ADR-014). Armar sem pendente é **erro**: rodada que nasce
    morta não roda, e ainda relatava no turno alheio.
13. `objetivo` é **reportado, nunca executado**: recusado por `armar` e
    substituído na exibição pela mesma régua (`estado.objetivo_legivel`). O
    número de uma parada vem do **nome do arquivo**, nunca da iteração.
14. A adoção de sessão é **pedida, nunca herdada**: sem `--sessao`, `armar`
    recusa e nomeia as três saídas (`--adotar-primeira-parada`,
    `--qualquer-sessao`) — emenda do ADR-008, custo medido na P-09.
15. O rearme por tempo é **arquivo no alvo**: `armar` semeia `.loop/loop.sh`
    quando ausente, com a raiz **derivada** do caminho do script, e **nunca**
    sobrescreve — a cópia é do dono, é onde as flags dele sobrevivem entre
    rodadas. Semeadura depois do estado gravado, e falhar nela nunca derruba
    o `armar` (ADR-016).

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

<!-- COMMIT-RULE:repodocs -->

## Commits — you commit, and nothing is delivered until you have

> Marked echo. The single source is **[samirhvbr/repodocs](https://github.com/samirhvbr/repodocs/blob/master/docs/versioning.md#who-commits-and-when)**
> — change it there, not here. This block is regenerated.

**Committing is your job.** Not "leave the tree ready and something downstream
packages it" — you run `git commit`, and `git push`, as the last step of the work
you were asked to do. The COMMITTER skill that used to commit on an agent's
behalf is `enabled: false` in every repository of this fleet since 03/09/2026;
what is left of it is a kill-switch, not a scheduler. **If you do not commit,
nobody does.**

**Do not report a task as finished before the commit exists.** "Done",
"delivered", "concluded" mean the work is in `git log` — never that it is sitting
uncommitted where only this session can see it. The commit is the last step *of
the task*, not a follow-up for someone else. If you are about to write
"finished", commit first, then write it.

**Every commit obeys the versioning rules**, with no exception:

- Subject `X.Y.Z - short description in English (US)`, the version taken from
  `version.md` and **bumped in the same commit**.
- The `CHANGELOG.md` entry is written first — its `## X.Y.Z - description`
  heading *is* the subject.
- No Conventional Commits prefix (`feat:`, `fix:`, `chore:`) and no vague
  subject ("update", "ajuste", "wip", "changes", "several improvements").

**The bump is the one clause a repository may override — in writing.** If this
repository's own documentation says the version is stamped some other way, and says
why, follow that. Otherwise the line above applies to you. An override nobody wrote
down is not an exception. Nothing else in this block bends: the changelog entry, the
subject, the language, one subject per commit, and committing before you report done
all hold regardless.

**One subject per commit.** The subject has to describe the whole commit
honestly. The moment your description needs an "and" to be true, it is two
commits.

**Split a large delivery into blocks.** A complex task is committed as a series
of commits grouped by subject, each small enough to be described in one line and
read on its own. They may share a version — bump `version.md` in the first and
repeat the number in the rest; two commits carrying one version is expected, not
a mistake. **Splitting is the default** for anything non-trivial, because the
history is the documentation of *how* the work was done, and one commit touching
six unrelated subjects documents none of them.

**The standard you are keeping:** someone reading `git log` alone — a year from
now, without the conversation that produced the work — can say what happened,
when, why, and at which version. If your commit would fail that test, it is too
big or its subject is too vague, and both are fixed the same way.

<!-- /COMMIT-RULE -->

---

<!-- RELEASES-RULE:repodocs -->

## Releases — the `version.md` on GitHub is what the Releases show

> Marked echo. The single source is **[samirhvbr/repodocs](https://github.com/samirhvbr/repodocs/blob/master/docs/versioning.md)**
> — change it there, not here. This block is regenerated.

**The `version.md` of the default branch, on GitHub, is what the GitHub Releases
must show.** The local checkout does not enter the calculation: it can be behind,
ahead or mid-work, and none of that is published — GitHub cannot tag a commit it
does not have.

**The bump and the Release are one act.** A commit that bumps `version.md` is not
finished until that version has a tag, a published Release, and the **`Latest`
badge on it** — the same push, not "later". A badge sitting on an older release
tells whoever looks that the project is at a version it is not.

- `.github/workflows/release.yml` does it on any push that touches `version.md`.
- `./tools/release.sh` does it by hand. It is **idempotent and self-healing**:
  it publishes whatever is missing and moves a drifted badge back. Running it is
  always safe, so it is both the check and the fix.

A PR publishes nothing while it is a PR. The moment it merges, the push moves
`version.md` on the default branch and the Release becomes that version.

Tag and Release title are the **bare version — no `v` prefix**.

## Language — English (US), everywhere in the repository

**Everything that lives in this repository, or in GitHub's interface around it,
is written in English (US)**: documents, **commit messages**, pull request titles
and bodies, issues, code comments, changelog entries, release notes.

Commit format: `X.Y.Z - short description in English`. The version comes from
`version.md` and is bumped in the same commit. Conventional Commits prefixes
(`feat:`, `fix:`, `chore:`) and vague one-word messages are forbidden.

**Exactly one carve-out:** end-user-facing strings — UI text, transactional
email, product copy. That is product i18n for a Brazilian audience, not
repository content.

History is not rewritten: Portuguese messages already in the log stay as they
are.

<!-- /RELEASES-RULE -->
