#!/usr/bin/env bash
# .loop/loop.sh — start a timed round in this repository, then watch it.
#
#   ./.loop/loop.sh <session-id>       arm for 6h and open the panel
#   ./.loop/loop.sh <session-id> 10h   same, with a 10h clock  (6h | 90m | 2h30)
#   LOOP_SESSAO=<id> ./.loop/loop.sh   the id may come from the environment
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
CTL=(loop-ctl)
WATCH=(loop-watch)
command -v loop-ctl   >/dev/null 2>&1 || CTL=(python3 "@LOOP_CTL_PY@")
command -v loop-watch >/dev/null 2>&1 || WATCH=(python3 "@LOOP_WATCH_PY@")

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
if [ -n "${1:-}" ] && [ -z "${SESSAO}" ]; then
    case "$1" in
        *[0-9a-fA-F]-*[0-9a-fA-F]*) SESSAO="$1"; shift ;;
    esac
fi

if [ -z "$SESSAO" ]; then
    cat >&2 <<'RECUSA'
✗ loop.sh: refusing to arm without a session binding.

  Pass the id of the session that will drive the round:
      ./.loop/loop.sh <session-id> [duration]
      LOOP_SESSAO=<session-id> ./.loop/loop.sh [duration]

  Why a refusal and not a guess: without `--sessao` the round adopts the FIRST
  session that ends a turn in this tree — any open chat will do. On 2026-09-01
  that adopted the session the owner was using to triage PRs: 18 journal
  entries filed under unrelated items, 4 spurious queue items, two sessions on
  one tree, four `version.md` collisions and two red `master`. On 2026-09-10 it
  fired three times inside one round, erasing a binding that was correct.

  Not re-arming is an inconvenience; re-arming on the wrong process is the bug.

  The id: an agent knows its own; in a terminal, the live transcript at
  ~/.claude*/projects/<repo>/<id>.jsonl is named after it.

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

DURACAO="${1:-6h}"

"${CTL[@]}" armar \
    --raiz "$RAIZ" \
    --duracao "$DURACAO" \
    --sessao "$SESSAO" \
    ${EXTRA[@]+"${EXTRA[@]}"}

# No --ate-encerrar on purpose: a turn that dies without emitting `Stop` leaves
# the round pinned at ativo:true, and a script blocked on it would hang forever
# (P-08). Ctrl+C leaves the panel; the round keeps running.
exec "${WATCH[@]}" --raiz "$RAIZ"
