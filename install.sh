#!/usr/bin/env bash
# Instala o LOOP: hook `Stop` global + skill `/loop-work`.
#
# O hook é global de propósito — ele precisa existir antes de você decidir usar
# o loop em algum repositório. A guarda não é a instalação, é o opt-in: sem
# `.loop/STATE.json` com `ativo: true` no repositório, o hook sai em
# milissegundos e não faz nada (SECURITY.md T-01).
#
#   ./install.sh              instala/atualiza
#   ./install.sh --dry-run    mostra o que faria
#   ./install.sh --uninstall  remove hook e skill (não toca em nenhum .loop/)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$REPO/skill/loop/hooks/loop-stop.py"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
SKILLS="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
MODO="${1:-install}"

command -v python3 >/dev/null || { echo "erro: python3 não encontrado" >&2; exit 1; }
[[ -f "$HOOK" ]] || { echo "erro: hook não encontrado em $HOOK" >&2; exit 1; }

python3 - "$SETTINGS" "$HOOK" "$MODO" <<'PY'
import json, os, shutil, sys, time

settings, hook, modo = sys.argv[1], sys.argv[2], sys.argv[3]
comando = 'python3 "%s"' % hook
dados = {}
if os.path.exists(settings):
    with open(settings, encoding="utf-8") as f:
        dados = json.load(f)

hooks = dados.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])

def entradas():
    for grupo in stop:
        for h in grupo.get("hooks", []):
            yield grupo, h

ja_esta = [(g, h) for g, h in entradas() if "loop-stop.py" in h.get("command", "")]

if modo == "--uninstall":
    for grupo, h in ja_esta:
        grupo["hooks"].remove(h)
    hooks["Stop"] = [g for g in stop if g.get("hooks")]
    if not hooks["Stop"]:
        hooks.pop("Stop")
    acao = "removido" if ja_esta else "não estava instalado"
elif ja_esta:
    for _, h in ja_esta:
        h["command"] = comando
        h["timeout"] = 15
    acao = "atualizado"
else:
    # Grupo próprio: os outros hooks Stop do ambiente (ai-memory, committer)
    # continuam intactos e todos rodam. Só o LOOP devolve `decision: block`.
    stop.append({"matcher": "", "hooks": [{
        "type": "command",
        "command": comando,
        "timeout": 15,
        "statusMessage": "loop-work: classificando a parada",
    }]})
    acao = "instalado"

if modo == "--dry-run":
    print("[dry-run] Stop hook seria %s em %s" % (acao, settings))
    print(json.dumps(dados.get("hooks", {}).get("Stop", []), ensure_ascii=False, indent=2))
    sys.exit(0)

os.makedirs(os.path.dirname(settings), exist_ok=True)
if os.path.exists(settings):
    shutil.copy2(settings, "%s.bak-loop-%d" % (settings, int(time.time())))
tmp = settings + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False, indent=2)
    f.write("\n")
os.replace(tmp, settings)
print("hook Stop %s em %s" % (acao, settings))
PY

if [[ "$MODO" == "--dry-run" ]]; then
  echo "[dry-run] skill seria ligada em $SKILLS/loop-work -> $REPO/skill/loop"
  exit 0
fi

if [[ "$MODO" == "--uninstall" ]]; then
  rm -f "$SKILLS/loop-work"
  echo "skill /loop-work removida (nenhum .loop/ foi tocado)"
  exit 0
fi

mkdir -p "$SKILLS"
ln -sfn "$REPO/skill/loop" "$SKILLS/loop-work"
echo "skill /loop-work ligada em $SKILLS/loop-work"
echo
echo "Pronto. O hook está inerte em todo repositório sem .loop/."
echo "Para começar, no repositório alvo:  /loop-work <objetivo>"
