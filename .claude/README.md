# Claude Code settings — skill-LOOP

This project's `.claude/` follows the pattern of the Blue3/samirhvbr repos:
**permission posture**, and nothing beyond it. Core in Python 3 with no external
dependency; a lean allow-list.

| File | Role |
|---------|-------|
| `settings.json` | The project's settings (versioned). `effortLevel: xhigh`, `defaultMode: plan`, security deny-list. **No model key of any kind.** |
| `README.md` | This file. |

## The model is not chosen here

**This repository chooses no model.** `settings.json` carries no `model`, no
`fallbackModel`, no `availableModels`, and nothing in `env` that steers one — no
`ANTHROPIC_MODEL`, no `ANTHROPIC_DEFAULT_*_MODEL`, no
`CLAUDE_CODE_SUBAGENT_MODEL` (repodocs ADR-027, 24/09/2026).

The model is the **user's choice**, made per session with `/model`, and a
**subagent inherits the session's model**. There is no stand-by profile to copy
over `settings.json` in order to change it, and the context window is whatever
the chosen model gives — nothing here promises one.

## Rules worth remembering

- **Effort `max` goes per session** (`/effort max`); the JSON field accepts up to
  `xhigh`.
- **`./install.sh` stays in `ask`** and `--dry-run` in `allow`. The installer
  writes to the **global** `~/.claude/settings.json` — nobody installs a hook on
  Samir's machine without him seeing it. Same posture as `crontab`/`systemctl`
  in the sibling AUDITOR.
- `git filter-branch`/`filter-repo` denied: the `~/x` auto-pusher does
  `pull --rebase` and undoes a rewrite.

## An important distinction: the product is a hook, this directory is not

This `.claude/` installs **no** hook. The repository's product is a **global**
`Stop` hook, which `install.sh` appends to `~/.claude/settings.json`.

Testing the hook by touching the real `settings.json` is forbidden
(`CLAUDE.md`): use

```bash
CLAUDE_SETTINGS=/tmp/fake.json CLAUDE_SKILLS_DIR=/tmp/skills ./install.sh
```

The suite already does this — it runs the hook as a subprocess, with `.loop/` in
a temporary directory, and never touches the real environment.

## The product's model vs. the development model

- Developing this repo: whatever model the session is on — the user's choice via
  `/model`. This repository does not pick one.
- **The product uses no model at all.** The classifier is lexical and
  deterministic; the hook makes no network, model or external-dependency call. A
  model tiebreak for the ambiguous case is v2 (P-03) and does not exist yet.
