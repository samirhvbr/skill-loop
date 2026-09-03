# Version — skill-LOOP

**Current version:** `0.3.10`

> This file is the **source of truth** for the project's version. Anywhere that
> needs to display or report the version extracts the **first semver number
> (`X.Y.Z`)** found here. Always keep the **"Current version"** line as the first
> occurrence of a version number. Same mechanics as the sibling projects
> (AUDITOR, COMMITTER).

---

## 1. Versioning convention (`X.Y.Z`)

| Component | Meaning | How it moves |
|---|---|---|
| **X** | Stable release — the loop operating on the house's real work | Manual |
| **Y** | Structural change — phase completed, contract change (`STATE.json`, `.loop/` format), accepted ADR that changes direction | Manual |
| **Z** | One increment per delivery | Every delivery |

While `X` is `0`, contracts may break between `0.Y` versions.

### `Z` bump triggers

- Changing the **classifier lexicon** or any ASK × DOC rule.
- Changing the **continuation prompt** (`prompts/continuacao.md`) — it is the product.
- Changing guardrails: iteration ceiling, no-progress, kill switch, queue.
- Changing the `STATE.json` schema or the `.loop/` format.
- Changing `install.sh`, `vendor.sh` or `.claude/settings.json`.
- Creating or changing a document under `docs/`, `SPEC.md` or `prompts/` that
  **changes a rule** (fixing wording does not count).
- Adding or changing tests that define expected behaviour.

### `Y` bump triggers

- A phase completed (see `.continue/escopo-projeto.md`).
- A compatibility break in a `.loop/` that already exists in some repository.
- A new ADR with status **Accepted** that changes direction.

> Text fixes, typos and formatting do **not** require a bump.

---

## 2. Mandatory commit format

```
X.Y.Z - Short description in English
```

**Non-negotiable rules:**

1. The version **always** comes from this `version.md`, bumped **in the same commit**.
2. Message in **English**, descriptive enough for `git log --grep`.
3. Conventional Commits (`feat:`, `fix:`, `chore:`…) and vagueness are **forbidden**.
4. One objective per commit; small, atomic changes.

The bump goes into **a single commit** per delivery (the first one). Additional
commits of the same delivery repeat the version.

> ⚠️ **English since 2026-09-02.** Every document in this repository, commit
> messages included, is written in English. Entries below `0.3.5` were translated
> in one pass and their wording is the translation, not the original; the numbers,
> dates, ADR references and measurements are unchanged.

---

## 3. Changelog

### `0.3.8` — 2026-09-02 — Agent doc: Releases rule and the English-only language rule

Marked echo of the single source at samirhvbr/repodocs. Two rules land here:

1. The `version.md` of the default branch ON GITHUB is what the GitHub Releases
   show, and a commit that bumps it is not finished until that version has a
   tag, a Release and the `Latest` badge — same push, not "later".
2. Everything in this repository is English (US): documents, commit messages,
   pull requests, issues, code comments. The only carve-out is end-user-facing
   product strings. History is not rewritten.

Delimited by a marker, so re-running replaces instead of duplicating.

### `0.3.7` — 2026-09-02 — Regra de Releases no doc de agente: bump e Release sao um ato so

Eco marcado da norma unica em samirhvbr/repodocs (docs/versioning.md). O
`version.md` da branch padrao NO GITHUB e o que as Releases no GitHub mostram, e
um commit que bumpa o `version.md` nao esta terminado ate aquela versao ter tag,
Release e o badge `Latest`.

Bloco delimitado por marcador: rodar de novo substitui, nao duplica.

### `0.3.6` — 2026-09-02 — Releases automaticas: o version.md da master vira tag e Release

O GitHub nao deduz versao de mensagem de commit: sem tag, o numero e string no
`git log` e `git diff` entre versoes nao existe. Entram o
`.github/workflows/release.yml` e o `tools/release.sh`.

**A regra:** o `version.md` da branch padrao **no GitHub** e o que as Releases
**no GitHub** refletem. Checkout local nao entra na conta. Um PR nao publica
nada; no merge, o push do `version.md` dispara o workflow e a Release vira
aquela versao.

Tag e titulo = a versao pura, sem prefixo `v`. Norma:
[samirhvbr/repodocs](https://github.com/samirhvbr/repodocs/blob/master/docs/versioning.md).

### `0.3.5` — 2026-09-02 — the vendored copy gets a tool, and the tool is what knows the trap

`install.sh` links one symlink per Claude Code config dir: always current, zero
maintenance. But anyone who wants the skill **inside** the target repository —
committed, so a clone carries it and no global install is needed — was copying
`skill/loop/` by hand. That is what happened today across **27 repositories**
(SHVIA, BLUE3, SSHVTERM), and copying by hand gets two things wrong in places
that never announce themselves.

#### `vendor.sh`

- `./vendor.sh <repo>...` installs or updates the copy at
  `<repo>/.claude/skills/loop-work/`; `--dry-run` shows it first.
- Re-running **is** the update: the directory is replaced wholesale, never
  merged. A file from an older version outliving the copy it belonged to would
  have no way of being noticed.
- It prints `version-before -> version-after` per repository, reading the
  `VERSION.md` it wrote itself. Without that there is no way to tell which of the
  27 copies are stale — which is exactly what is missing from `auditor`, which
  installs the same way and stamps no version at all.
- The version comes from this `version.md` and the origin includes the commit:
  the copy says where it came from, not just what it is.

#### The two traps it closes

- **`prompts/` falls outside what gets copied.** `hooks/loop-stop.py` resolves
  its templates three levels above `skill/loop/`; from
  `.claude/skills/loop-work/` that lands in `<repo>/.claude/prompts/`. Copying
  only the skill directory leaves the hook without `continuacao.md` — and the
  failure is silent until the first stop. The script carries both files along.
- **The copy takes precedence over the global symlink** for what the agent
  *reads* (`SKILL.md`, `loop_ctl.py`), while the hook that drives the
  continuation is always the repository's. After a bump, the copy is the stale
  half. The generated `VERSION.md` says so in writing, in the place someone will
  look.

No hook is registered per repository, deliberately: the global one already covers
every repo and is inert without an active `.loop/STATE.json` — registering it
again would fire it twice.

No new tests: the script is not on the loop's execution path (it runs neither in
the hook nor in `loop_ctl`), and what it produces is verified by the tests that
already exist, running against the copy. **248 tests**, green.

#### English, from this delivery on

Also in `0.3.5`, in its own commit: this `version.md` was translated whole, and §2
now requires commit messages in English. `CLAUDE.md`, `AGENTS.md` and the
`README.md` note were corrected in the same pass so the repository stops
contradicting itself about its own rule. Only wording changed — every number,
date, ADR reference and measurement below is the original. `README_br.md`,
`SPEC.md`, `SECURITY.md`, `docs/` and `prompts/` are still in Portuguese and
follow as they are touched; `prompts/` is product text the hook injects into the
agent, so translating it changes behaviour and is a delivery of its own.

### `0.3.4` — 2026-09-02 — re-arming by time becomes a file in the target

Starting a timed round cost two commands, in two terminals, with a path in each.
Nobody memorises that, so at EOP it became a `loop.sh` written by hand at the
root of the repository — and **it is still there today**, with the two defects
that kept it from becoming product: the root is a literal (`--raiz ~/x/EOP`),
which pins the file to one tree and dies on the first clone; and it does not
arrive on its own, so every target repository depended on someone remembering to
write it.

#### The shortcut is seeded by `armar` itself

- New versioned template at `skill/loop/templates/loop.sh`; `armar` writes
  `.loop/loop.sh` (mode 755) **when it does not exist**, replacing two
  placeholders with the absolute paths of this copy of the skill.
- `./.loop/loop.sh` arms for **6h** and opens the dashboard; `./.loop/loop.sh 10h`
  takes any duration `parse_duracao` accepts.
- The root is **derived** (`dirname "${BASH_SOURCE[0]}"/..`), not written: moving,
  cloning or renaming the repository keeps working. That is the difference
  between the template and the original it replaces.
- It prefers `loop-ctl`/`loop-watch` from `PATH` and falls back to the absolute
  path of the copy that seeded it — same reasoning as the `install.sh` shim: say
  which copy is serving.
- **It never overwrites.** The copy in the target belongs to its owner: it is in
  that copy's `EXTRA=(...)` block that `--objetivo`, `--janela` and `--itens`
  survive between rounds. Deleting the file is how you ask for a new one.
- Seeding runs **after** `loop.iniciar()`, never alongside the `QUEUE.md`
  skeleton: a command that refuses must not leave a file behind. And I/O errors
  stay silent — bringing down an `armar` that already armed because of a
  shortcut would invert the fail-open of ADR-009.

#### Session adoption is asked for out loud, and it is the same P-09

The shortcut passes `--adotar-primeira-parada` and prints the warning on standard
error **before** arming. A shell does not know its own `session_id`, and this is
exactly the case P-09 measured — the EOP round that adopted the session opened to
triage Dependabot PRs. The `0.2.6` guard was designed around it: refusing with no
way out would break this file. What the guard buys is that adoption is **said**;
what the warning buys is the operator hearing it at the only moment when closing
the other chats is still possible.

No `--ate-encerrar` in the watch, deliberately: a turn that dies without emitting
`Stop` pins the round at `ativo: true` (P-08), and a script blocked on that flag
would hang forever. Ctrl+C leaves the dashboard; the round goes on.

#### Also in this commit

The merge of `origin/master` (`0.2.5` and `0.2.6`) went in just before, in its own
commit. The two lines had diverged at `0.2.4` and allocated the number `0.2.5` in
parallel, for different deliveries — the changelog got the note about the
collision, and nothing was renumbered, because each number is bound to the message
of a published commit.

**Tests: 248** (13 new, `tests/test_atalho.py`), green. Half of them look at the
seeding; the other half **execute the generated script**, with `loop-ctl` and
`loop-watch` replaced by stubs ahead of `PATH` — testing only the text of the file
would step over everything that breaks in a shell.

**Six controls, six mutations:** turning off the seeding call drops **10** tests;
moving it ahead of the guards, **1** (the one demanding that a refused `armar`
leave no file behind); removing the never-overwrite guard, **2**; taking the root
from `pwd` instead of the script path, **2**; removing the session warning, **4**;
turning off `set -e`, **1**.

⛔ **Not measured:** whether the shortcut changes anything in the rate of rounds
armed against the wrong session. It makes adoption visible at the right instant,
but the one who closes the other chats is the operator — and that is behaviour,
not code.

### `0.3.3` — 2026-08-18 — the changelog matches the log again

The `0.3.1` bump was done with an unanchored `sed` and renamed the historical
`0.3.0` entry beyond its heading. The two following fixes stumbled: `1d36e61`
promised an entry in its message that it did not write, and `52898f8` truncated
the file. This entry closes all three.

### `0.3.1` — 2026-08-18 — the shutdown notice becomes a single act

The hook re-emitted the closing notice on every stop, over an already-finished
loop — four times in one round, one of them inside a session that did not belong
to the loop. Now `STATE.json` records `notificado` and the notice goes out once.

### `0.3.0` — 2026-08-17 — the queue was running the timed round, and that was never its job

The owner typed `loop-ctl armar --raiz ~/x/EOP --duracao 6h` over a 66/66 queue and
got `erro: nenhum item - [ ] na fila`. The question that came with it is the
shortest this project has received: *"why is the loop evaluating the queue? the
loop's job is kind of just to say continue"*. It is right, and the defect was in the
design: the queue was doing **two** things — the **content** of the continuation
(legitimate, irreplaceable) and **end condition #4** (wrong when there is a clock).
The `0.2.5` guardrail was the final consequence: born to block a dead round, it
ended up blocking the right path.

#### An empty queue with a clock does not end the round: the engine refills (ADR-015)

- `fila zerada` **only ends a round with no clock**. With `duracao_max_min` or
  `janela` declared, the empty queue leaves the chain and becomes a **refill turn**.
  A **derived** trigger (`diagnostico.tem_relogio`), not a new flag: whoever wrote
  `--duracao 6h` already declared that the clock is the mission. `STATE.json`
  **does not change contract**, and state from an earlier version falls back to the
  old behaviour.
- A second template, `prompts/reabastecimento.md` — the `reabastecer.md` the owner
  used to paste at the tail of the queue, turned into an engine prompt, with the
  same clauses as ADR-014. The hook chooses by the work at hand: `item is None` +
  clock → refill. Sending the continuation prompt with `(empty queue)` in place of
  the item would be an order to execute what does not exist.
- **Scope** of the refill: `.loop/SCOPE.md` **verbatim** when it exists; otherwise
  the `--objetivo`, and the prompt tells the turn the boundary **was not declared**
  and orders it to refuse anything doubtful. Whoever does not know where to stop
  needs to know they do not know.
- **A new ending — `escopo esgotado`**, condition #4, read from `.loop/SEM-ESCOPO`:
  the agent measures that there is no block in scope, writes the numbers, and
  `STATUS.md` quotes the verdict. A file separate from `STOP` because a single one
  would erase **who** decided to end it: the kill switch is the owner's order, this
  is the agent's measurement. `armar` deletes the file (after the guards); `retomar`
  does not, and `porque` warns that it is there.
- `armar --duracao`/`--janela` **stops refusing** an empty queue, and warns that the
  first stop is a refill — plus another warning if `SCOPE.md` is missing. With no
  clock, the `0.2.5` refusal stays intact, message included.
- `loop-watch` can no longer mark `fila zerada` as an ending under a clock: the queue
  line becomes informational (`fila (não encerra) · N pendente(s) → reabastece`,
  reason `None` on purpose) and `escopo esgotado` takes its place. It was this
  dashboard that, on 17/08, pointed `← encerrou aqui` at the queue with `resta 5h22`
  two lines below.
- `dur()` and the new `restante_da_rodada()` moved out of `loop_watch` into the lib:
  the prompt needs the same formatter, and two copies diverge at the first edge
  (`0` is not "0min", it is "exhausted").

#### What did **not** change, deliberately

- **Rounds by item count** — with no clock the queue remains the definition of done
  (ADR-006), the `armar` refusal stays, and `reabastecer.md` remains its mechanism.
- **The anti-infinite-loop is the same**: `sem progresso`. A turn that refills changes
  the queue count (which feeds the sha1 of the fingerprint) and resets the counter; a
  turn that produces nothing accumulates and ends at 3 — with a test proving it.
- **Order of the chain**: kill switch and ceilings stay ahead of the verdict. The
  owner's order above the agent's measurement, and the degeneration ceiling above
  everything the agent writes.

**228 tests green**, +21. Four controls, four mutations: turning off the derived
trigger drops 10 tests; the verdict, 5; the `armar` guard, 4; the dashboard line, 2.

⛔ **Not measured:** whether an engine-driven refill drifts less or more than one
driven by the item at the tail — two prompts with the same clauses and different
contexts. It joins P-05.

> ⚠️ **Numbering collision — the two `0.2.5` entries below are different
> deliveries.** On 18/08 this tree moved on to `0.3.x` without having received
> what `origin/master` published on 02/09, and the two lines allocated `0.2.5`
> unaware of each other. Nothing was renumbered, deliberately: each number is
> bound to the message of a published commit, and changing it here would break
> the match between changelog and log — which is the very defect `0.3.3` had just
> fixed. Reconciliation was by **merge** on 02/09; the line continues at `0.3.4`.
> Order below: by version, with the two `0.2.5` side by side.

### `0.2.6` — 2026-09-02 — session adoption stops being inherited by omission

**The first of P-09's three exits, and the only one that fit with the round still
alive.** `0.2.5` recorded the defect and did not fix it, following the rule
`0.2.4` had already written: touching `hooks/` or `lib/` with a round in flight
makes the hook exit fail-open and strands the round mid-way. **Measured now, and
this is what unblocked it:** `hooks/loop-stop.py` imports `classificador`,
`diagnostico`, `estado` and `transcricao` — all from `lib/` — and **does not
import `loop_ctl.py`**. `armar` is therefore off the hook's path, exactly as
`loop_watch.py` was in `0.2.4`. The other two exits (a marker for the arming
process, a tree lock) live in the hook and in `lib/`, and are still waiting for a
dead round.

**What changes:** `armar` refuses to arm with `bind_session: true` and no
`--sessao`, and it names the three exits — `--sessao <id>`,
`--adotar-primeira-parada` (new) and `--qualquer-sessao`.

⛔ **This is not the pure "loud failure" P-09 proposed, and the difference was
measured:** EOP's `loop.sh` arms with `loop-ctl armar --raiz ~/x/EOP --duracao
10h`, **without `--sessao`** — a flat refusal would break the owner's script, and
a guard that gets in the way becomes a `--force` the following week. Nor can the
id be required: ADR-008 already discarded that because **nobody knows their own by
heart**. So the historical behaviour stays reachable in one word; what it stops
being is **inherited by omission** — the only way in which it was expensive.

**The guard refuses WITHOUT WRITING STATE**, and that is the second control, not a
detail: a half-armed `.loop/` is the defect `0.2.3` paid for with the `¨¨` — state
written before a guard does not start obeying it afterwards, and a `retomar` would
reactivate it without passing through the choice. The test asserts `ler() is None`,
which is the strongest outcome available.

The `armar` summary now says **how** the session was chosen
(`a primeira que parar — ADOÇÃO PEDIDA` · `qualquer (não amarra)`): the old line
was true and ambiguous, and was read as a default for a whole round.

**Tests: 188 → 193.** ADR-008 gets an amendment; P-09 records the exit delivered
and the two that remain.

| Control turned off | Tests that fall |
|---|---|
| the door guard is removed (adoption goes back to being the silent default) | 2 |
| the summary goes back to not saying HOW the session was chosen | 2 |

### `0.2.5` — 2026-09-02 — auto-bind adopted the wrong session, and the ADR said "necessarily"

**The product audited itself while running for the second time, and the finding is
in the text of a decision, not in the code.** Only `docs/` changed: not one line of
`hooks/` or `lib/`, deliberately — the EOP round was alive, with **another** session
executing `L219`, and it is the same reason that in `0.2.4` postponed the `INDEX.md`
fix.

**ADR-008** states that the first stop *"is **necessarily** the one from the session
that armed"*, and the comment at `hooks/loop-stop.py:167` repeats it. **It is not.**
It is the first session that **finishes a turn** in the repository — any chat already
open there will do. At EOP the loop adopted a session the owner had opened to triage
Dependabot PRs, while `loop.sh` was arming from another. The `print` in `armar`
already told the truth (`sessão: a primeira que parar`): the defect is documentation,
and documentation that promises a guarantee that does not exist is worse than silence.

**Cost measured during the round** (which is what makes this a debt and not a
curiosity):

- **18 journal entries** (`0153`–`0160`, `0166`–`0172`) that are messages about PRs
  and about an artifact, filed under `L191`, `L201`, `L219` and `L220`;
- **4 spurious queue items**, harvested from truncated fragments of the message
  (`- [ ] a página como fonte`) — the **third** recurrence of the family the ADR-005
  amendment and the bare marker of `0.2.4` had already visited;
- **two sessions driven against the same tree**, the most expensive of all: two
  `version.md` collisions at EOP (`1.76.71` and `1.76.72`, the second in the commit
  that was fixing the first), two red `master` runs on the target repo's `G2` guard,
  and two commits that announced work the diff did not contain.

**Delivered:** **P-09** with the counterexample, the cost and three exits to evaluate
(refuse `armar` without `--sessao` when `bind_session: true`; a marker for the arming
process, checked by the hook and backward-compatible when absent; a tree lock that
makes the second session REFUSE an item instead of competing for it). And ADR-008
gets the caveat where the claim lives — the decision still stands, what falls is the
guarantee.

**Tests: 188, unchanged** — no behaviour changed, and that is the point.

### `0.2.5` — 2026-08-17 — the round that is born dead, and the refill promoted

EOP's 22-stop round ended by `fila zerada` at 16:30 — **correctly, and with a
verdict written**. What came afterwards is what was wrong: three `armar` calls over
an already 66/66 queue produced stops `#20`, `#21` and `#22`, each lasting **one**
stop with hours left on the clock, and each injecting the shutdown report into the
turn of whoever was doing something else. That is what the EOP agent named *"a stop
instruction injected into the wrong context"*.

#### Arming with nothing pending becomes an error, not a warning

- `armar` and `retomar` **refuse** a queue with no `- [ ]` at all (`--mesmo-sem-fila`
  forces it). The warning already existed that morning and stopped **none** of the
  three: text printed after the state is written is not a guardrail.
- The refusal leaves no effect behind: `armar` used to delete `.loop/STOP` **before**
  the guards, so a command that aborted had already disarmed the kill switch — the
  one lever the owner pulls without a terminal in the session.

#### A round born dead ends quietly

- `pendentes_ao_armar` (new, additive field) records how many items there were to do
  at arming time. Zero + first stop + zero pending now means **nothing happened**:
  the hook ends with a `systemMessage` and does **not** emit the report. `None`
  (state from an earlier version) reports as before — "I don't know" is never worth
  zero.
- The predicate started as `iteracao == 1 and feitos == feitos_ao_armar` and the
  suite charged for it: it silenced a **legitimate** ending on the first stop
  (ASK=stop policy, `--itens 1`), where there was a round and the report is the right
  thing. Measuring the fact at `armar` replaced the inference by two counters that
  could coincide.
- The record is unchanged: `STATUS.md`, entry and `INDEX.md` are still written.

#### Reading the record must not kill the reader

The dashboard died with a traceback at **16:39:57**, on the refresh after a screen
that had rendered correctly 30 s earlier: it read an entry mid-write and
`UnicodeDecodeError` — which is a `ValueError` — slipped underneath
`except (IOError, OSError)`.

- `errors="replace"` on record reads: entries and `STATUS.md` in the dashboard,
  `QUEUE.md` in the engine. The damaged entry **stays on screen**, with the bad byte
  as U+FFFD; surviving by hiding the stop would be the same lying dashboard by
  another route — and that is how the first version of the test passed with the
  control turned off (the mutation dropped 0 tests, and the test was rewritten).
- In the queue this is more than cosmetic: `QUEUE.md` is written by the **agent**,
  and the hook reads it at the instant of the `Stop` — the window is the refill turn.
  The exception would be swallowed by the fail-open and the stop would be lost **in
  silence**, precisely on the round where the queue grew.
- And harvesting stopped writing a skeleton over an unreadable queue: it reads
  `QUEUE.md` in order to **rewrite it**, and the `"# Fila do loop\n"` fallback applied
  to any read failure — with the file present, that erased the cycle's contract. Now
  the skeleton is only written when there is no file; any other failure gives up on
  harvesting, which is incidental.

#### The refill becomes a product artifact (ADR-014)

That morning's ⛔ said **not** to document the pattern before a round measured it.
The round measured it: **14 consecutive stops without ending** (`#6`…`#19`), **13
refills**, queue from **22 → 66 items**, intervals of 25 · 14 · 10 · 10 · 7 min. And
the finding that changed the design: on the 10th lap the agent **broke the
replenishment clause deliberately**, with the seven hypotheses tabulated (three
became blocks, three measured zero), because *"complying with it without input forces
you to fabricate a block"*.

- [prompts/reabastecer.md](prompts/reabastecer.md) — the canonical item, with the two
  normative clauses: **declared scope** (including what "stops and asks") and
  **replenishment escape**.
- `SKILL.md` §1.1, `SPEC.md` §5.2, ADR-014, and `armar` pointing at the file when it
  refuses an empty queue.
- It is stated what this is **not**: automatic. The promise of hours depends on
  someone pasting the item into the queue — that is a decision, not forgetfulness.
- ⛔ Still unmeasured: whether a queue written by the loop itself **drifts** over many
  laps (P-05). Counting the 44 new lines does not answer that; reading what they
  produced does.

**Tests: 184 → 200.** Mutation of each control:

| Control turned off | Tests that fall |
|---|---|
| `armar`/`retomar` go back to warning instead of refusing | 3 |
| the refusal goes back to deleting the kill switch before aborting | 1 |
| a round born dead goes back to emitting the rite | 1 |
| broad predicate (any 1st stop stays quiet) | 8 |
| `pendentes_ao_armar` stops being recorded | 1 |
| the dashboard goes back to dying on an invalid byte in an entry | 1 |
| the queue count goes back to blowing up on an invalid byte | 1 |
| harvesting goes back to writing a skeleton over an unreadable queue | 1 |

**The pending mutation from `0.2.4` was measured** — the EOP round ended and
`classificador.py` stopped being edited, so mutate-and-restore no longer risked
someone else's work. Each marker going back to bare (`\s*:` → `\b`):

| Marker back to bare | Tests that fall |
|---|---|
| `próxima rodada` | 2 |
| `próximo ciclo` | 1 |
| `não coberto` | 2 |
| all three together | 3 |

All three together drop **fewer** than the sum: the `0.2.4` regression tests use real
prose and one sentence can match more than one marker, so the same assertion falls to
any of them. What matters is that **none** of the three is untested — which is exactly
what the ⛔ had left open.

### `0.2.4` — 2026-08-17 — the bare marker, and when each stop happened

> Two deliveries in the same tree, and the record says whose each one is: the
> classifier fix was made **by the EOP agent**, inside the loop round, and the
> dashboard by this session. They are in a single commit only because that is how
> they happened.

#### The classifier was harvesting prose — found in operation, by the loop itself

The first time the product audited itself **while running**. Harvesting got it wrong
three times in the round of 17/08; on the third it reproduced on the first try, and
the cause was not a missing test — the suite already had nine negative assertions
dedicated to not harvesting prose. The cause was the **shape of the pattern**.

- **Bare marker** — a phrase with no deferral verb — matches narrative. *"the table
  stayed in QUEUE.md so the next round would not repeat the sweep"* talks about what a
  record is for, and became a queue item. Aggravating factor: since
  `colher_declarados` takes the first sentence of the paragraph when there is no list,
  **the item that was born was not even the sentence that matched**.
- Sweeping the five lists found **three** bare ones in the list that feeds the queue:
  `próxima rodada`, `próximo ciclo` and `não coberto` — the third discovered while
  fixing the first two, and confirmed against real prose before the change (*"that path
  ended up not covered by the database's immutability"*). The other twelve patterns
  carry a verb and never bit.
- The three now require `\s*:`. With a colon the expression **announces** items, which
  is the only use the harvester knows how to read.
- **Meta ratchet:** a test sweeps the whole of `DECLARADO_PENDENTE` and fails any
  marker that has neither a deferral verb nor a required `:` — with proof of execution
  in both directions, so the ratchet cannot acquit by accident.

#### The dashboard: when each stop happened, and how long it took

Requested by Samir during the third round, and the defect is the same one that misled
him that morning: the dashboard showed `09:32 · 09:03 · 21:19 · 20:24` for the last
stops, and the bottom two were from the **previous day** — nothing on screen said so.
In a record that crosses midnight, `hh:mm` alone misleads while looking like data.

- **`Últimas paradas` carries `DD/MM/YYYY-hh:mm`** (`carimbo()`). A timestamp that does
  not match the ISO format returns the raw text truncated instead of an invented date —
  the dashboard may fail to read a timestamp, it may not fabricate one.
- **The header gains the date** because of `--uma-vez >> registro.log`: in a file that
  accumulates over days, `12:57:11` alone does not say when it is from.
- **Each stop shows the interval since the previous one** (`+12min`). The date answers
  *when*; the interval answers *how long it took* — and that was the information the
  dashboard never had, not the one the date replaced. It is also the "work per
  iteration" P-05 asks for and that no round had measured. `ultimas_paradas` now reads
  **one stop more** than it displays: the interval of the oldest line on screen depends
  on the one before it, which has already left the window.
- The interval is labelled a **measured fact, not working time**: between `#5` and `#6`
  on 17/08 there is half an hour in which the loop was ended, waiting for a `retomar`.
  The dashboard measures the clock; inferring productivity from it is on the reader.

Change only in `loop_watch.py` — pure reading, off the hook's path — because the EOP
round was **running** at the time, and the hook runs from the symlink: an error in
`lib/` or in the hook would make it exit fail-open and strand the round mid-way.

**Tests: 172 → 184.** Six for the dashboard, six for the classifier (four regression,
two per marker in both directions, plus the meta ratchet and the proof it executes).

| Control turned off | Tests that fall |
|---|---|
| the dashboard stops computing the interval between stops | 2 |
| the timestamp goes back to just `hh:mm` (`ts[11:16]`) | 1 |
| it does not read the extra stop — the oldest line has no interval | 1 |
| the marker goes back to bare (no `\s*:`) | ⛔ **not measured** |

⛔ The mutation of the three markers **was not run**: the EOP agent was editing
`classificador.py` in that same minute, and mutate-and-restore would have erased
whatever it wrote in between. The meta ratchet covers the **shape** of the pattern;
what is missing is the number of tests each marker drops. Run it when the round ends.

⛔ **The same fix is missing in `INDEX.md`**, which is the durable record and today has
**no** timestamp at all — not even a time. Postponed deliberately: it touches
`estado.py::indexar`, which the hook consumes, and the round was alive.

### `0.2.3` — 2026-08-17 — the question was not an item, and the dashboard was not a witness

An EOP dashboard read at 09:42 about a round that died at 09:32. Four things wrong in
it, and the worst was not a display problem.

- **The question was becoming a queue item — and it was what ended the round.** The
  closing of stop `#0003` was *"**Pergunta:** sigo com esse discriminador…"*: `\bsigo
  (?:com|por|para|pra)\b` is HANDOFF, the paragraph has a `:`, and harvesting took what
  came after the last `:` into `QUEUE.md` — with the bold `**` broken off in front.
  Marked `- [x]`, it zeroed the pending count and triggered *"fila zerada"*: a correct
  end condition firing over a count that should not have existed. Now a candidate that
  **is** or **contains** a detected question is discarded, in all three zones and **in
  both verdicts** — ADR-005 still stands, because what changes is not *when* you
  harvest, it is *what* (amendment to ADR-005).
- **The dashboard went back to consuming the chain instead of keeping its own.**
  `0.2.2` took the condition list out of the hook and left `loop-watch`'s own aside: no
  kill switch, no no-progress, ordered by time remaining. On a round **already ended by
  an empty queue**, it marked `← primeira` on the window — with 2h18 left — with
  *"fila zerada, 0 pendente(s)"* printed two lines below. It was the fourth copy
  `diagnostico.py` had been written to prevent. The mark now answers whichever of the
  three questions applies: `← encerrou aqui` (recorded fact), `← já bateu: a próxima
  parada encerra` (a warning, on a live round), `← primeira` (clock — only when none
  has hit). Amendment to ADR-013.
- **The stop number comes from the file name.** The dashboard read `n:` from the
  front-matter, which until that morning was the iteration — and `armar` resets the
  iteration on every round. Four stops recorded as `0001`..`0004` showed up as
  `#4 #1 #2 #1`. A single ruler in `estado.NUM_DE_ENTRY`, for whoever writes and
  whoever reads.
- **An unreadable objective is refused on the way out too.** The `armar` guard was born
  in `0.2.2`, after EOP's `.loop/` was already armed with `"¨¨"` — and state written
  before a guard does not start obeying it afterwards. The dashboard announced the
  mojibake for a whole round. Door and shop window now measure with the same function
  (`estado.objetivo_legivel`), and the display says **what** is wrong and **with what**
  to fix it, instead of swapping the garbage for a `—` that would be confused with "did
  not declare an objective".
- **`encerrado_detalhe` in `STATE.json`** (additive field): the detail lived only in
  `STATUS.md`, in prose. It is what separates two conditions that share the same reason
  — `escopo concluído` by N items × by marker — and what answers "zeroed with how many?"
  without opening another file.
- The dashboard header says **how long ago** it ended: it stamps the time of the
  *reading*, and 09:42 over a round dead at 09:32 looked like a round happening now.

**16 new tests** (10 in `test_watch.py`, 6 in `test_classificador.py`, 1 in
`test_ciclo.py`), total **171**.

| Control turned off | Tests that fall |
|---|---|
| the dashboard goes back to ranking by clock (ignores `encerrado_por`) | 3 |
| a question goes back to becoming a queue item | 2 |
| `quem_encerra` does not consult `condicoes_de_fim` | 2 |
| the dashboard goes back to reading `n:` from the front-matter | 1 |
| an unreadable objective passes the ruler (door and shop window) | 1 |
| `_linha_do_motivo` ignores the detail (ambiguous scope) | 1 |
| the hook stops recording `encerrado_detalhe` | 1 |
| `_dedup` without stripping loose markup from the ends | 1 |

**Measurement this round yielded (P-05):** two real rounds at EOP, **both** ended by
`fila zerada` — none hit a window, clock, ceiling or no-progress. And the one on 17/08
zeroed on a spurious item: of its 2 iterations, **zero** real queue items were closed.
Two rounds are not a distribution, but the preliminary reading is that the queue runs
out before anything else does.

### `0.2.2` — 2026-08-17 — the fail-open was mute: `loop-ctl porque`

Today the "continue" typed at EOP did not continue, and investigating it by hand took a
morning. The hook was right: `ativo: false` since 16/08 at 21:19, and it exits at the
first gate with `exit 0` writing nothing (ADR-009). **There were three closed gates in
the same `.loop/`** and not one line of log about any of them: `ativo`, the previous
day's `session_id`, and a blown 2 h clock. The defect is not the gate — it is that
there is no way to ask (ADR-013).

- **`loop-ctl porque`** walks the gates in the order the hook tests them — hook
  installed, `.loop/`, `ativo`, `fase`, session binding — stops at the first that
  blocks, and moves on to the end conditions when none does. Exits `1` when something
  blocks, `0` when the loop would continue. Alias: `diagnostico`.
- **The chain of end conditions now has a single copy**
  (`lib/diagnostico.py::condicoes_de_fim`), consumed by the hook instead of its own
  `if/elif` chain. The list already lived in three places; a fourth would rot, and a
  diagnostic that lies about the order is worse than none.
- **`retomar` re-binds the session** (amendment to ADR-008): it clears `session_id`
  unless `--sessao` is given explicitly. Whoever resumes resumes the next day, in a new
  session — and the preserved id made the hook exit silently at the session gate.
  `retomar` also warns when the queue is empty or the clock has blown, the two facts
  that reactivating does **not** fix (the clock calls for `armar`).
- **The `loop-watch` dashboard says "hook inerte"** when the loop is stopped, with the
  bound-session line. "PARADO" was being read as "between two iterations".
- `--raiz` now works **before or after** the subcommand: the natural order was a usage
  error, precisely in the command that rescues whoever is in the dark.

**54 new tests** (49 in `tests/test_diagnostico.py`, 5 in `test_watch.py`), total
**155**. Among them the one that keeps the mirror from drifting: every state that makes
the hook go quiet is sent to the hook (subprocess) **and** to the diagnostic, and one's
silence must correspond to the gate the other names.

Mutation of each new control, with the number of tests each one drops:

| Control turned off | Tests that fall |
|---|---|
| `retomar` goes back to preserving `session_id` | 1 |
| dashboard without the inert-hook warning | 2 |
| dashboard without the bound-session line | 1 |
| the `ativo` gate informs instead of blocking | 4 |
| the session gate does not block | 3 |
| unreadable settings become a verdict of "hook absent" | 3 |
| the kill switch stops coming first in the chain | 5 |
| `condicoes_de_fim` recounts the queue instead of using the count it received | 1 |
| re-arm warnings (empty queue, clock) turned off | 3 |
| `--raiz` goes back to working only before the subcommand | 1 |

### `0.2.1` — 2026-08-16 — `loop-watch`: following from a distance

`watch -n 30 loop_ctl.py status` re-renders the same screen and **does not answer the
two questions of someone away from the monitor**: *did it move?* and *how much is
left?*.

`skill/loop/loop_watch.py` answers both:

- **delta between readings** — `+3 parada(s), +2 item(ns) fechado(s)`, or "sem
  mudança"; it is the one thing a repainted screen cannot give;
- **time remaining on each end condition**, with the one that will hit first marked
  (`← primeira`). `minutos_ate_fechar` was born in the engine for this; it crosses
  midnight and returns `None` for an invalid window — it never invents a number;
- a queue progress bar, the next item, and the last stops with **ASK flagged** (an
  assumption was recorded) and **partial closing flagged** (the ADR-012 defect, visible
  from a distance if it comes back);
- `--uma-vez` (cron/log), `--ate-encerrar` (exits with a bell when the loop stops),
  `--raiz`, `--sem-cor`. Colour off automatically when the output is not a terminal.

`install.sh` now creates the **`loop-watch`** and **`loop-ctl`** shortcuts in
`~/.local/bin` (a shim, not a symlink — it makes explicit which repository is serving),
and warns if the directory is not on `PATH`. `--uninstall` removes both.

**18 new tests** (`tests/test_watch.py`), total **101**.

### `0.2.0` — 2026-08-16 — the first real round, and the defect it revealed

**The loop ran on real work** (EOP, 20:11→21:19): armed with a 21-item queue and a
window until 22:00, it closed **21/21**, ended by the declared condition (empty queue),
told the agent to send the push notification and stopped. **Two stops in 68 minutes** —
a single continuation replaced the "continue" that would have cost 10 minutes of dark
screen. The balance on the other side: 72 files touched, EOP's `version.md` from
1.27.11 → 1.29.0, ADR-081 written there, and an `ASSUMPTIONS.md` recording the three
assumptions with the cost of undoing each one.

**And auditing the round found the product's central defect (ADR-012).** The two
archived `entries` were **fragments from the middle of the reasoning**, not reports:
the `Stop` hook fires before Claude Code writes the last text block to the JSONL. On
stop #2 it read, at 00:19:22, a text from **00:12:30** — 154 entries earlier — while
the true report was being written at that very second. Reading the return and
documenting it **is** the product, and it was documenting the wrong thing, silently:
the decision to continue does not depend on the text, so nothing gave it away. The only
signal was the `confianca: media` the classifier recorded on both.

**Fix:** the read now answers whether the text is the **closing of the turn** (nothing
from the main agent after it) and **waits** up to 3 s for that closing, re-reading every
100 ms. On timeout it proceeds anyway — but records `fecho_do_turno: PARCIAL`, drops
confidence to `baixa` and says in the evidence that this is not the report. A subagent
does not count as content after; `AskUserQuestion` closes the turn by itself and
generates no wait.

**11 new tests** (`tests/test_transcricao.py`), with the race actually reproduced: the
closing is written by another thread **during** the wait. Total **83**. Mutation:
turning off the wait drops both regressions and returns exactly the behaviour of 16/08.

**Not done yet:** the wait resolves the closing race, it does not measure how much of it
remains in larger sessions — the 3 s ceiling is a choice, not a measurement (P-07).

### `0.1.0` — 2026-08-16 — F0 and F1: proposal closed and a deterministic engine

The skill that makes the agent work without a "continue" every five minutes is born.
The proposal was closed with Samir in the conversation of 16/08, and the core delivered
the same day — documentation and code came out together because the classifier only
stood up after being calibrated against **two real messages** from his agent, published
anonymised (originals in `fixtures-reais/`, outside git).

**Decided** (ADR-001 to ADR-009): the trigger is a `Stop` hook, not a skill and not a
timer; `stop_hook_active` is no good as a latch; ASK always continues with the
assumption recorded; classification by **zone and direction**, not by punctuation;
closing items and declared pending work become the queue; `QUEUE.md` is the source of
the next step; fail-open; auto-binding to the session; push notification sent by the
agent itself.

**Delivered and tested** — 72 tests, controls verified by mutation:

- `skill/loop/lib/classificador.py` — ASK × DOC by closing zone, suppression of
  self-answered rhetoric, PT-BR/EN handoff lexicon, item harvesting with
  parenthesis-aware splitting, harvesting of declared pending work.
- `skill/loop/hooks/loop-stop.py` — the hook: it classifies, files, decides and returns
  `decision: block` with the next item. Fail-open on any error.
- `skill/loop/lib/estado.py` — the whole of `.loop/`: state, queue, entries, index,
  assumptions, status, progress fingerprint.
- `skill/loop/lib/transcricao.py` — tail reading of the JSONL, subagent filter.
- `skill/loop/loop_ctl.py` — arm/stop/resume/status/queue.
- `install.sh` — an idempotent global hook that coexists with the `Stop` hooks already
  installed; `--dry-run` and `--uninstall`.

**Two defects found by the tests themselves** before any use: the provenance comment
was entering the dedup key (the item was re-harvested at every stop) and leaking into
the prompt; and ending with `notificar: false` left the loop active.

**Not done yet:** operation on real work (F2) — no field number exists. See
`.continue/escopo-projeto.md`.
