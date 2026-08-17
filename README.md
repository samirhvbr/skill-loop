# skill-LOOP

A Claude Code skill that keeps the main agent working for hours without anyone
typing "continue". A `Stop` hook fires the instant a turn ends, **reads the
agent's own report**, classifies it as **ASK** (it was waiting on a human
decision) or **DOC** (it was just reporting work done), files it under `.loop/`,
and hands the agent back the next item on the queue.

> 🇧🇷 **[README_br.md](README_br.md) is the canonical version** — this repository
> is written in Portuguese. This file is the English front door and is kept in
> sync with it.
>
> **Docs:** [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) (rules for whoever
> develops this repo) · [SECURITY.md](SECURITY.md) (threat model — required
> reading) · [SPEC.md](SPEC.md) (normative pipeline and `.loop/` format) ·
> [skill/loop/SKILL.md](skill/loop/SKILL.md) (the skill) ·
> [prompts/continuacao.md](prompts/continuacao.md) (the product prompt) ·
> [docs/decisoes.md](docs/decisoes.md) (ADRs).
>
> Sibling of [AUDITOR](https://github.com/samirhvbr/AUDITOR) and
> [skill-COMMITTER](https://github.com/samirhvbr/skill-COMMITTER).
> Status: **first real run done** (2026-08-16, 21/21 queue items closed in 68 min,
> two stops) — and its audit found the product's central defect, now fixed (ADR-012).
> 228 tests.

## The problem, measured

The agent produces for 5–10 minutes, ends its turn, and writes up what it did.
Whoever is away from the monitor sees that 10 minutes later, types "continue",
and the cycle repeats.

Two real messages from 2026-08-16, now the regression fixtures of the test suite
(**anonymised** for this public repository — internal names replaced, linguistic
structure preserved; both versions classify identically):

| Message | Production time | Any question? | Stopped |
|---|---|---|---|
| `tests/fixtures/relato-corrida-instancia.txt` | 9m16s | **none** | yes |
| `tests/fixtures/relato-fitness-schema.txt` | ~5min | none explicit — handed off in the closing paragraph | yes |

Across months of work, most of the calendar is a dark screen. **This is not a
slow agent; it is dead time between turns.**

## The thesis

A skill alone cannot fix it: a skill is an instruction the model *reads*, and it
still ends the turn when it judges a block delivered. What actually intercepts
that is the **`Stop` hook** — it receives the `transcript_path` and, by returning
`{"decision": "block", "reason": ...}`, puts the agent back to work with the
`reason` as its new instruction.

Better than a timer loop (`/loop 5m`): a timer wakes on the clock, so it can wake
mid-work or four minutes after the agent stopped. A hook wakes **when** it stops.

## The classifier — the signal is not in the punctuation

A `?` detector gets it wrong in **both** directions, and the two real messages
prove it:

**False ASK.** *"…it deserved the next question: how many others are like this?
I swept the migrations across the ten schemas — one was left."* There is a `?`,
but the text answers itself in the very next sentence.

**False DOC.** *"From here on, what's left of most value is on your side of the
table: the OpenAPI default convention, ✦A, the corrected ✦B, and the X1–Y2
voice-channel answers."* **Not a single question mark** — and that is exactly
where the agent stopped working and started waiting.

So signals are weighted by **zone** and by **direction**:

| Signal | Where it counts | Effect |
|---|---|---|
| Hand-off (`on your side`, `up to you`, `let me know`, `should I`, `waiting on you`) | closing zone only (last 2 paragraphs) | ASK |
| `?` in the closing zone | closing | ASK |
| Self-answered `?` (next sentence reports completed work) or announced (`the next question:`) | any zone | **suppressed** |
| `?` inside a code block | — | ignored |
| `AskUserQuestion` as the last tool call | — | ASK, short-circuit |
| Report markers (`435 tests · 434 ok`, `swept`, `committed`) | whole text | DOC |

And the most valuable part: **what becomes queue**. Prose enumerations are
harvested from the hand-off closing (with a parenthesis-aware split, so
`(version column in Cycle and Period)` doesn't become two items); and from **any**
zone, work the agent itself declared pending — the "Declared and not done"
section of the second real message named the next task, and a question-only
classifier would have lost it entirely.

## Per-stop pipeline

1. Hook receives `{session_id, transcript_path, cwd, stop_hook_active}`.
2. No `.loop/STATE.json` with `ativo: true` → **exit 0 in milliseconds**. The
   hook is global; the opt-in is per repository.
3. Reads the last **main-agent** message from the transcript (`isSidechain` is a
   subagent and is discarded — without this, every turn using `Explore` would
   look like an ASK).
4. Classifies ASK × DOC.
5. Files `.loop/entries/NNNN-{ASK,DOC}-slug.md` plus a row in `INDEX.md`.
6. Harvests closing items and declared pending work into `QUEUE.md`, deduped —
   and **never the question itself**: it already has an entry, an index row and a
   recorded assumption, and in the queue it would become a line someone can tick
   off as done.
7. Checks the end conditions. None fired → `decision: block` naming the next item.
8. One fired → writes `STATUS.md` and tells the agent to send **a push
   notification** before finishing. (The hook is a script; the notification tool
   belongs to the agent.)

> ⚠️ `stop_hook_active` is **not** used as the guard. It flips to `true` on the
> second stop and never goes back, so the documented pattern
> (`if stop_hook_active: allow stop`) yields exactly **one** continuation. The
> counters here are our own, in `STATE.json`.

## End conditions — the loop must cost a predictable amount

An engine that restarts the agent by itself and never ends is an unbounded bill.
There are **seven** independent conditions; the first one to trigger ends the run,
writes `STATUS.md` and fires the notification.

| Condition | Flag | Example |
|---|---|---|
| **Scope by item count** | `--itens N` | `--itens 10` — "close the first 10 and stop" |
| **Scope by marker** | `--ate TEXT` | `--ate "3.10 VoIP"` |
| **Time window** | `--janela` `--dias` | `--janela 08:00-18:00 --dias seg-sex` |
| **Wall clock** | `--duracao` | `--duracao 6h` |
| Empty queue | — | the definition of done — **only without a clock** |
| Scope exhausted | agent writes `.loop/SEM-ESCOPO` | the ending a timed run has |
| Iteration ceiling | `--max` (200) | final net |

Scope by item count measures **this run only** (`feitos_ao_armar` is the
denominator). The window may cross midnight (`22:00-06:00`) and **fails open**:
a malformed `--janela` never stops work silently.

> The loop **does not re-arm itself.** When the 18:00 window closes it ends; at
> 08:00 the next day, resuming is a command. Automatic re-arming needs cron and
> is a later phase.

Other guards: `.loop/STOP` kill-switch (a `touch` from anywhere, no terminal
needed), a degenerate-loop detector (identical worktree fingerprint + queue for
3 stops means the agent is talking without producing), and session binding.

**Fail-open by design:** any error in the hook → `exit 0`. The worst case
degrades to today's behaviour (you type "continue"), never to a stuck session.

## Install

```bash
./install.sh                 # global Stop hook + /loop-work skill
./install.sh --dry-run       # show what it would do
./install.sh --uninstall     # remove both; never touches any .loop/
```

The hook is appended as its **own group** in `~/.claude/settings.json`: any
`Stop` hooks already installed keep working and all of them run — only LOOP
returns `decision: block`.

## Usage

```
/loop-work <objective>    distil the queue from your docs and arm
/loop-work status         where it stands
/loop-work porque         why it did not continue
/loop-work parar          disarm
/loop-work retomar        re-arm from where it stopped (re-binds the session)
```

Arming with an empty queue does not work **for an item-bounded round** — and since
`0.2.5` the command **refuses**: `.loop/QUEUE.md` is what the hook injects into the
`reason`, and without it the continuation degrades to "carry on from where you left
off" — the agent re-plans every turn and drifts. The skill reads the documentation
and distils the queue **before** arming; that step decides whether the loop works
at all. (For a time-bounded round the refusal does not apply — see below.)

### A queue that refills itself — when you want hours, not items

Arming by time (`--duracao 6h`) declares that the **clock** is the mission and the
queue is scratch. Since `0.3.0` the engine treats it that way: with a clock on the
table, `empty queue` leaves the end-condition chain and an empty queue becomes a
**refill turn** — the hook tells the agent to pick the next uncovered block within
scope, read its documentation in full, distil `- [ ]` items at the end of
`QUEUE.md`, and carry on working (ADR-015). You paste nothing.

What you supply is the **boundary**, because it is yours: `.loop/SCOPE.md` with what
may enter and what "stops and asks" — the file goes into the prompt **verbatim**.
Without it, scope comes from `--objetivo`, and the prompt tells the turn that the
boundary was never declared, ordering it to refuse anything doubtful.

And the ending: when the measurement says there is **no** in-scope block left, the
agent writes the verdict with its numbers to `.loop/SEM-ESCOPO` and the round ends
as `escopo esgotado`. That escape is not a detail — honouring the refill clause with
no input forces it to **fabricate work**, which is worse than stopping.

Before this, the mechanism was a self-reproducing item at the tail of the queue
([prompts/reabastecer.md](prompts/reabastecer.md)), pasted by hand; it remains the
path for a round **without** a clock. It is what produced the measurement that
became the engine, on 2026-08-17: **14 consecutive stops without ending, 13 refills,
queue from 22 to 66 items**, ending by written verdict — seven hypotheses tabulated,
three became blocks, three measured zero (ADR-014).

## Watching it from a distance

```bash
loop-watch                    # refresh every 30s
loop-watch --ate-encerrar     # exit (with a bell) when the loop stops
loop-watch --uma-vez >> run.log

loop-ctl porque               # stopped and did not continue? this says why
```

`watch -n 30 status` repaints the same screen; this answers the two questions
you actually have when you are not looking: **did it move?** (delta since the
last read) and **how much is left?** (time remaining on every end condition,
with the one about to trigger marked). ASK stops and partial closes are flagged.

The **end-condition block** is printed in the order the hook tests them, not in
clock order, and the marker answers whichever of three questions actually
applies: `← encerrou aqui` on a run that already ended (the reason is recorded
fact, not a projection), `← já bateu: a próxima parada encerra` when the run is
alive but a condition is already true, and `← primeira` — the one arriving first
on the clock — only when none has triggered yet. Sorting by time remaining only
ranks the conditions that have **not** fired; which one governs is decided by the
chain, and the panel asks it rather than keeping a list of its own.

When the loop is stopped, the panel says so in as many words: the **hook is
inert**, and typing "continua" in the chat reactivates nothing. `loop-ctl porque`
walks the gates in the order the hook tests them — hook installed, `.loop/`,
`ativo`, `fase`, session binding, then every end condition — and names the one
that blocked plus its fix. It exists because the hook is fail-open and exits
silently by design: on 17/08 three gates were shut in the same `.loop/` and there
was not one line of log about any of them.

## What gets recorded

```
.loop/
├── STATE.json        run state
├── QUEUE.md          the queue — and measured progress
├── INDEX.md          one row per stop
├── ASSUMPTIONS.md    what was decided without you      ← read this first
├── STATUS.md         why it ended
├── STOP              kill-switch, yours (presence is enough)
├── SCOPE.md          refill boundary you declare — optional, read verbatim
├── SEM-ESCOPO        the agent's verdict: nothing in scope left
└── entries/NNNN-{ASK,DOC}-slug.md
```

Reviewing `ASSUMPTIONS.md` is not optional — it is the price of not having been
interrupted.

## Declared limitations of v1

- **The classifier is lexical, not semantic.** A hand-off phrased outside the
  PT-BR/EN lexicon reads as DOC and the loop continues without recording that the
  decision was yours. The fence is `ASSUMPTIONS.md` and `INDEX.md`, reviewed
  afterwards — not detector precision.
- **No field numbers.** The engine has 200 tests; real operation is the next phase.
- **The queue is written by a model** from your documentation. A bad queue means
  a bad loop, and the hook cannot detect that.
- **`.loop/entries/` stores the agent's full message.** If it echoes a secret in
  a report, that secret lands on disk (T-07 in `SECURITY.md`).

## License

MIT — see [LICENSE](LICENSE).
