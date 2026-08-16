# Perfil de modelo Claude Code — skill-LOOP

`.claude/` deste projeto segue o padrão dos repos Blue3/samirhvbr: **perfil de
modelo + postura de permissões**. Núcleo em Python 3 sem dependência externa;
allow-list enxuta.

| Arquivo | Papel |
|---------|-------|
| `settings.json` | Perfil **ativo** (versionado). Opus-only `opus[1m]`, `effortLevel: xhigh`, `defaultMode: plan`, deny-list de segurança. |
| `README.md` | Este arquivo. |

## Regras que valem lembrar

- **Não adicionar `CLAUDE_CODE_DISABLE_1M_CONTEXT`** — é ela que derruba a janela
  para 200K.
- **Effort `max` vai por sessão** (`/effort max`); o campo do JSON aceita até
  `xhigh`.
- **`./install.sh` fica em `ask`** e o `--dry-run` em `allow`. O instalador
  escreve no `~/.claude/settings.json` **global** — ninguém instala hook na
  máquina do Samir sem ele ver. Mesma postura de `crontab`/`systemctl` no irmão
  AUDITOR.
- `git filter-branch`/`filter-repo` negados: o auto-pusher de `~/x` faz
  `pull --rebase` e desfaz reescrita.

## Distinção importante: o produto é um hook, este diretório não

Este `.claude/` **não** instala hook nenhum. O produto do repositório é um hook
`Stop` **global**, que o `install.sh` anexa ao `~/.claude/settings.json`.

Testar o hook mexendo no `settings.json` real é proibido (`CLAUDE.md`): use

```bash
CLAUDE_SETTINGS=/tmp/fake.json CLAUDE_SKILLS_DIR=/tmp/skills ./install.sh
```

A suíte já faz isso — ela executa o hook como subprocesso, com `.loop/` em
diretório temporário, e nunca toca no ambiente real.

## Modelo do produto vs modelo do desenvolvimento

- Desenvolvimento deste repo: Opus (perfil acima).
- **O produto não usa modelo nenhum.** O classificador é léxico e determinístico;
  o hook não chama rede, modelo ou dependência externa. Desempate por modelo em
  caso ambíguo é v2 (P-03) e ainda não existe.
