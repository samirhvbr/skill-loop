#!/usr/bin/env bash
# Vendors this skill into a target repository as a committed copy.
#
# `install.sh` is the normal path: one symlink per Claude Code config dir, always
# current. This script is the other one — for people who want the skill committed
# **inside** the target repository, so a clone carries it and no global install is
# needed to read `/loop-work`.
#
#   ./vendor.sh <repo> [<repo> ...]   install or update the copy
#   ./vendor.sh --dry-run <repo>...   show what it would do
#
# Re-running is the update: the skill directory is replaced wholesale, so a copy
# never drifts. It prints `version-before -> version-after` per repository.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VER=$(grep -m1 -o '[0-9]\+\.[0-9]\+\.[0-9]\+' "$REPO/version.md")
SHA=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo "sem-git")

DRY=0
[[ "${1:-}" == "--dry-run" ]] && { DRY=1; shift; }
[[ $# -gt 0 ]] || { echo "uso: $0 [--dry-run] <repo> [<repo> ...]" >&2; exit 1; }
command -v rsync >/dev/null || { echo "erro: rsync não encontrado" >&2; exit 1; }

for D in "$@"; do
  if [[ ! -d "$D" ]]; then echo "  ?? $D não existe" >&2; continue; fi
  D=$(cd "$D" && pwd)
  DEST="$D/.claude/skills/loop-work"
  ANTES=$(grep -m1 -o '[0-9]\+\.[0-9]\+\.[0-9]\+' "$DEST/VERSION.md" 2>/dev/null || echo "-")

  if (( DRY )); then
    printf "  [dry-run] %-28s %s -> %s\n" "$(basename "$D")" "$ANTES" "$VER"
    continue
  fi

  mkdir -p "$DEST" "$D/.claude/prompts"
  # Wholesale replace, never merge: a leftover file from an older version would
  # outlive the copy it belonged to and there would be no way to tell.
  rm -rf "${DEST:?}"/*
  rsync -a --exclude='__pycache__' "$REPO/skill/loop/" "$DEST/"

  # `hooks/loop-stop.py` resolves its templates three levels up from `skill/loop/`.
  # From `.claude/skills/loop-work/` that lands in `<repo>/.claude/prompts/` — the
  # copy is broken without these two files, and the breakage is silent.
  cp "$REPO/prompts/continuacao.md" "$REPO/prompts/reabastecimento.md" "$D/.claude/prompts/"

  cat > "$DEST/VERSION.md" <<EOF
# loop-work — vendored copy

- **version:** $VER
- **source:** \`$REPO\` (commit \`$SHA\`)
- **installed:** $(date +%F)

A **snapshot** of \`skill/loop/\` from the skill-LOOP repository. Do not edit it
here — change it upstream and re-vendor with \`vendor.sh\`, or the next update
overwrites your change silently.

## Why \`.claude/prompts/\` exists next to it

\`hooks/loop-stop.py\` resolves its prompt templates three levels up from
\`skill/loop/\`, which from here lands in \`<repo>/.claude/prompts/\`. That is why
\`continuacao.md\` and \`reabastecimento.md\` are vendored there; the copy is
incomplete without them.

## No hook is registered per repository

The \`Stop\` hook is registered **globally**, by \`install.sh\`, in the Claude Code
config dir in use — and it points at the skill-LOOP repository, not at this copy.
It is inert in any repository without an active \`.loop/STATE.json\`, so there is
nothing to register here; registering it would fire the hook twice.

One consequence worth knowing: this copy takes precedence over the global symlink
for what the agent **reads** (\`SKILL.md\`, \`loop_ctl.py\`), while the hook that
drives the continuation is always the upstream one. After an upstream bump, this
copy is the stale half until \`vendor.sh\` runs again.
EOF
  printf "  ok %-28s %s -> %s\n" "$(basename "$D")" "$ANTES" "$VER"
done
