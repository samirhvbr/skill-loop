#!/usr/bin/env bash
# .loop/loop.sh — start a timed round in this repository, then watch it.
#
#   ./.loop/loop.sh <session-id>       arm for 6h and open the panel
#   ./.loop/loop.sh <session-id> 10h   same, with a 10h clock  (6h | 90m | 2h30)
#   LOOP_SESSAO=<id> ./.loop/loop.sh   the id may come from the environment
#
# The two arguments are recognised by SHAPE, not by position, so the order does
# not matter: `<id> 10h` and `10h <id>` are the same command.
#
# Seeded by `loop-ctl armar` when absent, and NEVER overwritten: this copy is
# yours. Add --objetivo, --janela, --dias, --itens below and they survive every
# future `armar`. Delete the file and the next `armar` writes a fresh one.
#
# Under a clock an empty queue does not end the round — it becomes a refill
# turn (ADR-015). Declare the boundary in .loop/SCOPE.md; it goes verbatim into
# the refill prompt.
set -euo pipefail

# The root is derived, never written down: move the repo, clone it, rename it —
# this still points at the right tree. Do not replace it with a literal path.
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Prefer whatever is on PATH (install.sh puts loop-ctl / loop-watch in
# ~/.local/bin); fall back to the skill copy that seeded this file, so the
# script works before the PATH is set up — and says which copy is serving.
#
# ⚠️ Resolved BEFORE the refusals below, and that order is load-bearing: the
# refusal prints the list of sessions, and the list comes from `loop-ctl`.
CTL=(loop-ctl)
WATCH=(loop-watch)
command -v loop-ctl   >/dev/null 2>&1 || CTL=(python3 "@LOOP_CTL_PY@")
command -v loop-watch >/dev/null 2>&1 || WATCH=(python3 "@LOOP_WATCH_PY@")

# The candidate list, or an honest line saying it could not be produced.
#
# ⚠️ DEGRADES, NEVER INVENTS. An older copy of the skill has no `sessoes`
# subcommand and exits non-zero; the refusal still stands on its own, it just
# loses the list. A refusal that depended on the list would stop refusing the
# day the helper broke.
listar_sessoes() {
    "${CTL[@]}" sessoes --raiz "$RAIZ" 2>/dev/null | sed 's/^/  /' && return 0
    echo "  (could not enumerate sessions: \`loop-ctl sessoes\` is missing or"
    echo "   failed — a skill-LOOP older than 0.3.16 does not have it)"
}

# ⛔ THE SESSION BINDING IS REQUIRED, AND THIS SCRIPT REFUSES WITHOUT IT.
#
# Owner's verdict, 2026-09-11 (box `A66`, after `A65` settled the same question
# inside EOP): the shortcut refuses to arm without an explicit session binding.
# Exit non-zero and say why, instead of adopting the first stop.
#
# 🔴 What this replaces, measured twice and never guessed. The script used to
# pass `--adotar-primeira-parada`, which binds the round to the FIRST session
# that ends a turn in this tree — any chat left open will do.
#
#   · 2026-09-01, EOP: the round adopted a session the owner had open to triage
#     Dependabot PRs. 18 journal entries filed under unrelated items, 4 spurious
#     queue items, two sessions driving one tree, four `version.md` collisions
#     and two red `master` (P-09).
#   · 2026-09-10, EOP: it fired again THREE times inside a single round, each
#     time erasing a binding that had been set correctly — and each time
#     silently, because adopting looks exactly like working.
#
# ⚠️ A shell genuinely does not know its own session_id. That is why the id is
# handed in rather than guessed: the agent knows its own, the operator can read
# it, and a wrong guess is the defect above.
#
# ⚠️ Not re-arming is an inconvenience; re-arming on the wrong process is the bug.
SESSAO="${LOOP_SESSAO:-}"
DURACAO=""

# 🔴 EVERY ARGUMENT IS CLASSIFIED, AND WHAT IS NOT RECOGNISED IS NAMED —
# measured on 2026-09-11, the first real use of the refusal above.
#
# The operator typed `./loop.sh EOP-b3building 16h`. The old `case` matched the
# glob `*[0-9a-fA-F]-*[0-9a-fA-F]*`, which `EOP-b3building` fails (the character
# before the `-` is `P`), so the argument was SILENTLY DISCARDED, slid into the
# duration slot, and the refusal said *"you passed no binding"* when the fact
# was *"what you passed is not an id"*. A guard that refuses for the wrong
# reason teaches the wrong lesson.
#
# ⛔ And there was a worse case, reachable at the time: with `LOOP_SESSAO` set in
# the environment, `./loop.sh EOP-b3building` sent `--duracao EOP-b3building`
# straight to `loop-ctl`.
#
# ⚠️ The id shape is strict on purpose (8-4-4-4-12). The old glob was so loose
# that plenty of non-ids passed as bindings — and a binding that can never match
# produces a round that never continues, whose symptom is SILENCE. Refusing
# loudly beats arming quietly on something that cannot work.
for arg in "$@"; do
    if [[ "$arg" =~ ^[0-9]+(h|m|h[0-9]+)$ ]]; then
        DURACAO="$arg"
    elif [[ "$arg" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
        SESSAO="$arg"
    else
        cat >&2 <<RECUSA
✗ loop.sh: \`$arg\` is neither a session id nor a duration.

  a session id has the shape 8-4-4-4-12
              (e.g. 8262d4a0-6680-4377-9f07-80418a8dc24c)
  a duration  is 6h | 90m | 2h30

$(listar_sessoes)

  Pick one and repeat:  ./.loop/loop.sh <session-id> [duration]
RECUSA
        exit 1
    fi
done
DURACAO="${DURACAO:-6h}"

if [ -z "$SESSAO" ]; then
    cat >&2 <<RECUSA
✗ loop.sh: refusing to arm without a session binding.

  Pass the id of the session that will drive the round:
      ./.loop/loop.sh <session-id> [duration]
      LOOP_SESSAO=<session-id> ./.loop/loop.sh [duration]

  Why a refusal and not a guess: without \`--sessao\` the round adopts the FIRST
  session that ends a turn in this tree — any open chat will do. On 2026-09-01
  that adopted the session the owner was using to triage PRs: 18 journal
  entries filed under unrelated items, 4 spurious queue items, two sessions on
  one tree, four \`version.md\` collisions and two red \`master\`. On 2026-09-10 it
  fired three times inside one round, erasing a binding that was correct.

  Not re-arming is an inconvenience; re-arming on the wrong process is the bug.

$(listar_sessoes)

  Deliberately adopting the first stop is still reachable, and now has to be
  said out loud:
      loop-ctl armar --raiz . --duracao 6h --qualquer-sessao
RECUSA
    exit 1
fi

# Your flags. Uncomment what you want; they survive every future `armar`,
# because this file is never overwritten.
EXTRA=(
    # --objetivo "one line, reported at every stop"
    # --janela 08:00-18:00 --dias seg-sex
    # --itens 10
)

"${CTL[@]}" armar \
    --raiz "$RAIZ" \
    --duracao "$DURACAO" \
    --sessao "$SESSAO" \
    ${EXTRA[@]+"${EXTRA[@]}"}

# No --ate-encerrar on purpose: a turn that dies without emitting `Stop` leaves
# the round pinned at ativo:true, and a script blocked on it would hang forever
# (P-08). Ctrl+C leaves the panel; the round keeps running.
exec "${WATCH[@]}" --raiz "$RAIZ"
