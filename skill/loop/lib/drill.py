#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`loop-ctl drill` — does the INSTALLED hook do what the loop promises? (ADR-021)

The suite proves the code in this repository. It cannot prove the copy that runs
on this machine, and that copy is a different thing: a line in a `settings.json`,
an interpreter found on a `PATH`, a symlink, a vendored tree. The hook is also
fail-open by design (ADR-009) — when any of that is wrong it exits 0 and says
nothing, so a loop that never continues looks exactly like a loop that has
nothing to do. `loop-ctl porque` checks the gates in order; what it cannot do is
**fire the hook**. This does.

It takes the command registered under `hooks.Stop` — the same string Claude Code
runs — and fires it, with synthetic Stop payloads, inside a throwaway git
repository armed through the installed tree's own `loop_ctl.py`. Every guard is
drilled in BOTH directions, because only one is easy:

- **sensitivity** — the fault is caught: a stalled round ends by `sem progresso`,
  an item that never closes is locked, the kill switch stops the round;
- **specificity** — benign input is NOT caught: a round that commits is not
  braked, an item that closes is not locked, a repo without `.loop/` is left
  alone. A brake that fires on everything passes every sensitivity drill while
  being useless.

A drill is credited only for the rule under test: the brake drill checks the
*reason the round ended*, read from `STATE.json`, not merely that it ended. The
idea is `loop-drill`'s (cobusgreyling/loop-engineering, MIT: "present is not
proven"); the scenarios are ours.

Safety: it runs only a command of the exact shape `install.sh` writes —
`python3 "<abs path>/loop-stop.py"` — and executes it without a shell, so a
`settings.json` line that merely *mentions* the hook is reported, never run. All
work happens in a temporary directory with its own `HOME`; nothing outside it is
written, and no `settings.json` is ever modified.

Limit, stated: it runs with the environment of whoever typed the command, not the
one Claude Code gives the hook. A `python3` that resolves here and not under the
desktop app's `PATH` is a fault this cannot see.

Python 3, stdlib only. No network, no model.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from datetime import datetime, timezone

# `modo`: passou | falhou | pulou.
Resultado = namedtuple("Resultado", "id direcao falha modo detalhe")

# The only command shape that is executed — what install.sh writes, no shell.
_COMANDO = re.compile(r'^(python3?)\s+"?(/[^"`$;&|<>\n]*loop-stop\.py)"?\s*$')

TIMEOUT_S = 20

FILA = ("# Fila do drill\n\n"
        "- [ ] Item A do drill: o primeiro da fila\n"
        "- [ ] Item B do drill: o segundo da fila\n"
        "- [ ] Item C do drill: o terceiro da fila\n"
        "- [ ] Item D do drill: o quarto da fila\n"
        "- [ ] Item E do drill: o quinto da fila\n"
        "- [ ] Item F do drill: o sexto da fila\n")

RELATO = "Concluí o que a fila pedia e rodei as verificações. 12 ok, 0 falhas."


# ── which command is registered, and where ──────────────────────────────────
def interpretar_comando(comando):
    """`(interpretador, caminho_do_hook)`, or `None` if it is not the install shape."""
    m = _COMANDO.match((comando or "").strip())
    return (m.group(1), m.group(2)) if m else None


def settings_padrao():
    """Every `settings.json` that could carry the hook on this machine.

    Three config homes live here (`.claude`, `.claude-blue3`, `.claude-pessoal`),
    and the one that matters is whichever the session runs under.
    """
    if os.environ.get("CLAUDE_SETTINGS"):
        return [os.environ["CLAUDE_SETTINGS"]]
    candidatos = []
    for d in (os.environ.get("CLAUDE_CONFIG_DIR") or "").split(os.pathsep):
        if d:
            candidatos.append(os.path.join(d, "settings.json"))
    candidatos.extend(sorted(glob.glob(
        os.path.join(os.path.expanduser("~"), ".claude*", "settings.json"))))
    vistos, saida = set(), []
    for c in candidatos:
        real = os.path.realpath(c)
        if real not in vistos and os.path.isfile(c):
            vistos.add(real)
            saida.append(c)
    return saida


def comandos_registrados(caminhos):
    """`({comando: [settings...]}, sem_hook, ilegiveis)` — reading only.

    `sem_hook` lists readable files that do not register the hook, and
    `ilegiveis` those that could not be read: "not registered" and "could not
    look" are different facts and the report keeps them apart.
    """
    por_comando, sem_hook, ilegiveis = {}, [], []
    for caminho in caminhos:
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (IOError, OSError, ValueError) as e:
            ilegiveis.append((caminho, str(e)))
            continue
        achou = False
        hooks = dados.get("hooks") if isinstance(dados, dict) else None
        for grupo in (hooks.get("Stop") if isinstance(hooks, dict) else None) or []:
            for h in (grupo.get("hooks") if isinstance(grupo, dict) else None) or []:
                cmd = str(h.get("command", "")) if isinstance(h, dict) else ""
                if "loop-stop.py" in cmd:
                    por_comando.setdefault(cmd, []).append(caminho)
                    achou = True
        if not achou:
            sem_hook.append(caminho)
    return por_comando, sem_hook, ilegiveis


# ── the throwaway world each drill runs in ──────────────────────────────────
class Ambiente:
    def __init__(self, interp, hook, base):
        self.interp, self.hook, self.base = interp, hook, base
        # `loop_ctl.py` is the hook's sibling in every tree this ships in.
        self.ctl = os.path.join(os.path.dirname(os.path.dirname(hook)),
                                "loop_ctl.py")
        self.env = dict(os.environ, HOME=base,
                        GIT_AUTHOR_NAME="drill", GIT_AUTHOR_EMAIL="drill@localhost",
                        GIT_COMMITTER_NAME="drill", GIT_COMMITTER_EMAIL="drill@localhost",
                        GIT_CONFIG_NOSYSTEM="1")
        self._n = 0

    def _roda(self, args, entrada=None, cwd=None):
        return subprocess.run(args, input=entrada, capture_output=True, text=True,
                              timeout=TIMEOUT_S, env=self.env, cwd=cwd)

    def repo(self, git=True, fila=True):
        self._n += 1
        raiz = os.path.join(self.base, "r%d" % self._n)
        os.makedirs(raiz)
        if git:
            self._roda(["git", "init", "-q"], cwd=raiz)
            with open(os.path.join(raiz, "README.md"), "w", encoding="utf-8") as f:
                f.write("# alvo do drill\n")
            self._roda(["git", "add", "README.md"], cwd=raiz)
            self._roda(["git", "commit", "-qm", "base"], cwd=raiz)
        if fila:
            os.makedirs(os.path.join(raiz, ".loop"))
            with open(os.path.join(raiz, ".loop", "QUEUE.md"), "w",
                      encoding="utf-8") as f:
                f.write(FILA)
        return raiz

    def armar(self, raiz, *flags):
        proc = self._roda([self.interp, self.ctl, "armar", "--raiz", raiz,
                           "--objetivo", "drill", "--qualquer-sessao",
                           "--sem-colheita"] + list(flags))
        if proc.returncode != 0:
            raise ErroDeCenario("`loop-ctl armar` falhou (rc=%d): %s"
                                % (proc.returncode,
                                   (proc.stdout + proc.stderr).strip()[-300:]))

    def produzir(self, raiz, n):
        """Real work: a new file, committed — what moves HEAD and the worktree."""
        arq = "trabalho-%d.txt" % n
        with open(os.path.join(raiz, arq), "w", encoding="utf-8") as f:
            f.write("entrega %d\n" % n)
        self._roda(["git", "add", arq], cwd=raiz)
        self._roda(["git", "commit", "-qm", "entrega %d" % n], cwd=raiz)

    def turno(self, raiz, mid="m", usage=None, copias=1, texto=RELATO):
        """Append one closed turn to the repo's transcript."""
        caminho = os.path.join(raiz, "transcript.jsonl")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        linhas = [json.dumps({"type": "user",
                              "message": {"role": "user", "content": "vai"}})]
        for i in range(copias):
            ultimo = i == copias - 1
            bloco = ({"type": "text", "text": texto} if ultimo
                     else {"type": "tool_use", "name": "Bash", "input": {}})
            msg = {"id": mid, "content": [bloco]}
            if usage:
                msg["usage"] = usage
            linhas.append(json.dumps({"type": "assistant", "isSidechain": False,
                                      "timestamp": ts, "requestId": "req-" + mid,
                                      "message": msg}))
        with open(caminho, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        return caminho

    def parar(self, raiz, bruto=None, usage=None, mid=None):
        """Fire the hook the way Claude Code does. `(rc, saida_json, stderr)`."""
        if bruto is None:
            self._n += 1
            transcript = self.turno(raiz, mid=mid or "m%d" % self._n, usage=usage)
            bruto = json.dumps({"session_id": "drill", "transcript_path": transcript,
                                "cwd": raiz, "hook_event_name": "Stop",
                                "stop_hook_active": False})
        proc = self._roda([self.interp, self.hook], entrada=bruto, cwd=raiz)
        saida = None
        if proc.stdout.strip():
            try:
                saida = json.loads(proc.stdout)
            except ValueError:
                saida = {"_nao_json": proc.stdout[:200]}
        return proc.returncode, saida, proc.stderr

    def estado(self, raiz):
        with open(os.path.join(raiz, ".loop", "STATE.json"), encoding="utf-8") as f:
            return json.load(f)

    def fila(self, raiz):
        with open(os.path.join(raiz, ".loop", "QUEUE.md"), encoding="utf-8") as f:
            return f.read()

    def marcar_o_primeiro_como_feito(self, raiz):
        conteudo = self.fila(raiz)
        with open(os.path.join(raiz, ".loop", "QUEUE.md"), "w",
                  encoding="utf-8") as f:
            f.write(conteudo.replace("- [ ] ", "- [x] ", 1))


class ErroDeCenario(Exception):
    """The scenario itself could not be set up — a failure of the installation."""


# ── the drills. Each returns `(passou, detalhe)`. ───────────────────────────
def _quebrou(rc, err):
    return "exit %s%s" % (rc, (" — stderr: " + err.strip()[-200:]) if err.strip() else "")


def d_inerte(a):
    raiz = a.repo(git=False, fila=False)
    rc, saida, err = a.parar(raiz)
    if rc != 0 or saida is not None:
        return False, "num repositório sem .loop/ esperava silêncio e exit 0; veio %s, saída=%r" % (_quebrou(rc, err), saida)
    if os.path.exists(os.path.join(raiz, ".loop")):
        return False, "criou .loop/ sozinho"
    return True, "exit 0, sem saída, sem criar .loop/"


def d_continua(a):
    raiz = a.repo()
    a.armar(raiz)
    rc, saida, err = a.parar(raiz)
    if rc != 0 or not saida or saida.get("decision") != "block":
        return False, "rodada armada: esperava `decision: block`; veio %s, saída=%r" % (_quebrou(rc, err), saida)
    if "Item A do drill" not in saida.get("reason", ""):
        return False, "continuou, mas o `reason` não traz o item da frente da fila"
    return True, "devolveu `block` com o item da frente no `reason`"


def d_freio_dispara(a):
    raiz = a.repo()
    a.armar(raiz, "--max-sem-progresso", "2", "--max-paradas-item", "0")
    st = {}
    paradas = 0
    for paradas in range(1, 7):
        a.parar(raiz)
        st = a.estado(raiz)
        if st.get("encerrado_por"):
            break
    motivo = st.get("encerrado_por")
    if motivo != "sem progresso":
        return False, ("rodada parada (nada mudou entre as paradas): esperava encerrar por "
                       "`sem progresso`; %s após %d paradas"
                       % ("encerrou por %r" % motivo if motivo else "NÃO encerrou", paradas))
    return True, "encerrou por `sem progresso` na parada %d" % paradas


def d_freio_calado(a):
    raiz = a.repo()
    a.armar(raiz, "--max-sem-progresso", "2", "--max-paradas-item", "0")
    for i in range(1, 7):
        a.produzir(raiz, i)
        a.parar(raiz)
    st = a.estado(raiz)
    if st.get("encerrado_por") or not st.get("ativo") or st.get("sem_progresso"):
        return False, ("rodada que comita a cada parada: esperava seguir com `sem_progresso` 0; "
                       "veio encerrado_por=%r, ativo=%r, sem_progresso=%r"
                       % (st.get("encerrado_por"), st.get("ativo"), st.get("sem_progresso")))
    return True, "6 paradas com commit, nenhuma freada (`sem_progresso` 0)"


def d_kill_switch(a):
    raiz = a.repo()
    a.armar(raiz)
    with open(os.path.join(raiz, ".loop", "STOP"), "w", encoding="utf-8"):
        pass
    a.parar(raiz)
    motivo = a.estado(raiz).get("encerrado_por")
    if motivo != "kill-switch":
        return False, "com `.loop/STOP` esperava encerrar por `kill-switch`; encerrou por %r" % motivo
    return True, "`.loop/STOP` encerrou a rodada por `kill-switch`"


def d_trava_dispara(a):
    raiz = a.repo()
    a.armar(raiz, "--max-paradas-item", "3", "--max-sem-progresso", "50")
    for i in range(1, 4):
        a.produzir(raiz, i)          # moving, so the brake stays out of the way
        a.parar(raiz)
    st, fila = a.estado(raiz), a.fila(raiz)
    if "- 🔒 Item A do drill" not in fila or st.get("itens_travados") != 1:
        return False, ("item da frente preso por 3 paradas (com commits): esperava travá-lo "
                       "(`- 🔒`); itens_travados=%r" % st.get("itens_travados"))
    if not st.get("ativo") or st.get("encerrado_por"):
        return False, "travou o item, mas encerrou a rodada (%r) — travar não é fim" % st.get("encerrado_por")
    return True, "o item A foi travado na 3ª parada e a rodada seguiu"


def d_trava_calada(a):
    raiz = a.repo()
    a.armar(raiz, "--max-paradas-item", "3", "--max-sem-progresso", "50")
    for i in range(1, 5):
        a.marcar_o_primeiro_como_feito(raiz)     # every item closes in one stop
        a.produzir(raiz, i)
        a.parar(raiz)
    st, fila = a.estado(raiz), a.fila(raiz)
    if "🔒" in fila or st.get("itens_travados"):
        return False, "cada item fechou em 1 parada e algum foi travado (itens_travados=%r)" % st.get("itens_travados")
    return True, "4 itens fechados em 4 paradas, nenhum travado"


def d_medidor(a):
    raiz = a.repo()
    a.armar(raiz, "--max-paradas-item", "0")
    usage = {"input_tokens": 2, "output_tokens": 777,
             "cache_creation_input_tokens": 10, "cache_read_input_tokens": 100}
    a.parar(raiz, usage=usage, mid="msg-drill")
    uso = a.estado(raiz).get("uso") or {}
    if uso.get("saida") != 777 or uso.get("mensagens") != 1:
        return False, ("uma mensagem de 777 tokens de saída: esperava saida=777 e 1 mensagem; "
                       "veio %r" % (uso or None))
    return True, "777 tokens de saída contados uma vez"


def d_medidor_sem_duplicar(a):
    raiz = a.repo()
    a.armar(raiz, "--max-paradas-item", "0")
    usage = {"input_tokens": 2, "output_tokens": 777,
             "cache_creation_input_tokens": 10, "cache_read_input_tokens": 100}
    # Claude Code writes one line per content block: the same message, 3 times.
    transcript = a.turno(raiz, mid="msg-drill", usage=usage, copias=3)
    bruto = json.dumps({"session_id": "drill", "transcript_path": transcript,
                        "cwd": raiz, "hook_event_name": "Stop",
                        "stop_hook_active": False})
    a.parar(raiz, bruto=bruto)
    uso = a.estado(raiz).get("uso") or {}
    if uso.get("saida") != 777 or uso.get("mensagens") != 1:
        return False, ("a mesma mensagem em 3 linhas: esperava contar uma vez (777, 1 mensagem); "
                       "veio %r" % (uso or None))
    return True, "3 linhas da mesma mensagem contadas uma vez"


def d_fail_open_entrada(a):
    raiz = a.repo()
    a.armar(raiz)
    rc, saida, err = a.parar(raiz, bruto="isto não é json {")
    if rc != 0 or saida is not None:
        return False, "entrada ilegível: esperava exit 0 e silêncio; veio %s, saída=%r" % (_quebrou(rc, err), saida)
    return True, "entrada ilegível → exit 0, sem saída"


def d_fail_open_estado(a):
    raiz = a.repo()
    a.armar(raiz)
    with open(os.path.join(raiz, ".loop", "STATE.json"), "w", encoding="utf-8") as f:
        f.write("{")
    rc, saida, err = a.parar(raiz)
    if rc != 0 or saida is not None:
        return False, "STATE.json corrompido: esperava exit 0 e silêncio; veio %s, saída=%r" % (_quebrou(rc, err), saida)
    return True, "STATE.json corrompido → exit 0, sem travar a sessão"


# id, direction, the failure it exists to catch, function, needs git, partner.
#
# A specificity drill ("it must NOT fire") passes on a hook that does nothing at
# all — a crashed hook never brakes, never locks, never touches a repo. So each
# one names its sensitivity partner and only counts when that partner passed;
# otherwise it is reported as skipped, not as green. Without this the report of a
# dead hook still showed three ticks.
DRILLS = [
    ("inerte-fora-do-loop", "especificidade", "o hook global age onde ninguém armou o loop (T-01)", d_inerte, False, "continua-a-rodada"),
    ("continua-a-rodada", "sensibilidade", "o loop não continua — e o fail-open não diz nada (ADR-013)", d_continua, False, None),
    ("freio-dispara", "sensibilidade", "o freio que nunca dispara (0.4.3)", d_freio_dispara, True, None),
    ("freio-calado", "especificidade", "o freio dispara em quem está produzindo", d_freio_calado, True, "freio-dispara"),
    ("kill-switch", "sensibilidade", "`.loop/STOP` ignorado", d_kill_switch, False, None),
    ("trava-dispara", "sensibilidade", "o item que se move e nunca fecha come a rodada (ADR-019)", d_trava_dispara, True, None),
    ("trava-calada", "especificidade", "a trava corta item que fecha (ADR-019)", d_trava_calada, True, "trava-dispara"),
    ("medidor", "sensibilidade", "o medidor não lê o uso (ADR-020)", d_medidor, False, None),
    ("medidor-sem-duplicar", "especificidade", "o medidor conta a mensagem uma vez por linha — 3× demais (ADR-020)", d_medidor_sem_duplicar, False, "medidor"),
    ("fail-open-entrada", "contrato", "o hook trava a sessão numa entrada ruim (ADR-009)", d_fail_open_entrada, False, None),
    ("fail-open-estado", "contrato", "o hook trava a sessão num STATE.json corrompido (ADR-009)", d_fail_open_estado, False, None),
]


def _parear(resultados, pares):
    """A specificity drill whose sensitivity partner did not pass is not a pass."""
    por_id = {r.id: r for r in resultados}
    saida = []
    for r in resultados:
        par = pares.get(r.id)
        if par and r.modo == "passou" and por_id[par].modo != "passou":
            r = r._replace(modo="pulou", detalhe=(
                "sem valor: o par de sensibilidade (%s) %s — um hook que não faz "
                "nada também 'passa' em não disparar" % (
                    par, "falhou" if por_id[par].modo == "falhou" else "não rodou")))
        saida.append(r)
    return saida


def rodar(interp, hook):
    """Run every drill against one hook. `[Resultado]`. Never raises."""
    base = tempfile.mkdtemp(prefix="loop-drill-")
    resultados = []
    try:
        if not os.path.isfile(hook):
            return [Resultado("hook-existe", "contrato", "o comando registrado aponta para nada",
                              "falhou", "arquivo não existe: %s" % hook)]
        tem_git = shutil.which("git") is not None
        a = Ambiente(interp, hook, base)
        for id_, direcao, falha, fn, precisa_git, _par in DRILLS:
            if precisa_git and not tem_git:
                resultados.append(Resultado(id_, direcao, falha, "pulou", "git não encontrado"))
                continue
            try:
                passou, detalhe = fn(a)
                modo = "passou" if passou else "falhou"
            except ErroDeCenario as e:
                modo, detalhe = "falhou", str(e)
            except subprocess.TimeoutExpired:
                modo, detalhe = "falhou", "estourou %ds — o hook travou" % TIMEOUT_S
            except Exception as e:                       # noqa: BLE001
                modo, detalhe = "falhou", "erro inesperado do drill: %r" % e
            resultados.append(Resultado(id_, direcao, falha, modo, detalhe))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return _parear(resultados, {d[0]: d[5] for d in DRILLS if d[5]})


def codigo_de_saida(resultados):
    """0 all passed · 1 something was skipped · 2 a guard failed to do its job."""
    if any(r.modo == "falhou" for r in resultados):
        return 2
    if not resultados or any(r.modo == "pulou" for r in resultados):
        return 1
    return 0
