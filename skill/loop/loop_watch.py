#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`loop-watch` — acompanhar o loop de longe.

    python3 loop_watch.py                 # atualiza a cada 30 s
    python3 loop_watch.py -n 10           # outro intervalo
    python3 loop_watch.py --uma-vez       # imprime uma vez e sai (para cron/CI)
    python3 loop_watch.py --ate-encerrar  # sai quando o loop encerrar
    python3 loop_watch.py --raiz ~/x/EOP  # de qualquer lugar

Existe porque `watch -n 30 loop_ctl.py status` re-renderiza a mesma tela e
**não responde as duas perguntas de quem está longe do monitor**: *andou?* e
*quanto falta?*. Aqui as duas ficam explícitas — delta desde a última leitura,
e o tempo restante de cada condição de fim, com a que vai bater primeiro
marcada.

Python 3, stdlib apenas. Sem cor quando a saída não é terminal, então
`loop_watch.py --uma-vez >> registro.log` sai limpo.
"""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))

from diagnostico import curto                             # noqa: E402
from estado import (Loop, achar_raiz, fora_da_janela,      # noqa: E402
                    minutos_ate_fechar, minutos_desde)

# ── cor ─────────────────────────────────────────────────────────────────────
class C(object):
    RESET = "\033[0m"; DIM = "\033[2m"; NEG = "\033[1m"
    VERDE = "\033[32m"; AMAR = "\033[33m"; VERM = "\033[31m"
    AZUL = "\033[36m"; ROXO = "\033[35m"

    @classmethod
    def desligar(cls):
        for k in list(vars(cls)):
            if k.isupper():
                setattr(cls, k, "")


def dur(minutos):
    """Minutos → '3h07' | '24min' | '—'."""
    if minutos is None:
        return "—"
    m = int(round(minutos))
    if m <= 0:
        return "esgotado"
    return "%dh%02d" % divmod(m, 60) if m >= 60 else "%dmin" % m


def barra(feitos, total, largura=22):
    if total <= 0:
        return "·" * largura
    cheio = int(round(largura * feitos / float(total)))
    return "█" * cheio + "░" * (largura - cheio)


# ── leitura das entries ─────────────────────────────────────────────────────
_CAMPO = re.compile(r"^(\w+):\s*(.*)$")


def ultimas_paradas(loop, quantas=4):
    try:
        nomes = sorted(os.listdir(loop.entries))[-quantas:]
    except (IOError, OSError):
        return []
    out = []
    for nome in nomes:
        dados = {"arquivo": nome}
        try:
            with open(os.path.join(loop.entries, nome), encoding="utf-8") as f:
                dentro = False
                for linha in f:
                    if linha.strip() == "---":
                        if dentro:
                            break
                        dentro = True
                        continue
                    m = _CAMPO.match(linha.strip()) if dentro else None
                    if m:
                        dados[m.group(1)] = m.group(2).strip().strip('"')
        except (IOError, OSError):
            continue
        out.append(dados)
    return out


# ── render ──────────────────────────────────────────────────────────────────
def condicoes(st, pendentes, feitos):
    """[(rótulo, restante_legível, minutos_para_bater_ou_None)] — ordenadas
    pela que bate primeiro. `None` em minutos = não é medida em tempo."""
    linhas = []
    if st.get("janela"):
        falta = minutos_ate_fechar(st["janela"], st.get("dias"))
        rot = "janela %s%s" % (st["janela"],
                               " (%s)" % st["dias"] if st.get("dias") else "")
        linhas.append((rot, "fecha em %s" % dur(falta), falta))
    if st.get("duracao_max_min"):
        resta = st["duracao_max_min"] - minutos_desde(st.get("armado_em"))
        linhas.append(("relógio %s" % dur(st["duracao_max_min"]),
                       "resta %s" % dur(resta), resta))
    if st.get("escopo_itens"):
        fechados = feitos - st.get("feitos_ao_armar", 0)
        falta_n = st["escopo_itens"] - fechados
        linhas.append(("escopo %d itens" % st["escopo_itens"],
                       "faltam %d" % max(0, falta_n), None))
    if st.get("escopo_ate"):
        linhas.append(("marcador %r" % st["escopo_ate"][:28], "—", None))
    linhas.append(("fila zerada", "%d pendente(s)" % pendentes, None))
    restam_it = st.get("max_iteracoes", 0) - st.get("iteracao", 0)
    linhas.append(("iterações %d" % st.get("max_iteracoes", 0),
                   "restam %d" % max(0, restam_it), None))
    com_tempo = [x for x in linhas if x[2] is not None]
    primeira = min(com_tempo, key=lambda x: x[2])[0] if com_tempo else None
    return linhas, primeira


def render(loop, st, anterior):
    pend, feitos = loop.contagem_fila()
    total = pend + feitos
    it = st.get("iteracao", 0)
    ativo = st.get("ativo")
    fase = st.get("fase")

    if not ativo:
        cor, estado = C.DIM, "PARADO"
        if st.get("encerrado_por"):
            estado = "ENCERRADO · %s" % st["encerrado_por"]
            cor = C.AMAR
    elif fase == "encerrando":
        cor, estado = C.AMAR, "ENCERRANDO · %s" % (st.get("encerrado_por") or "")
    else:
        cor, estado = C.VERDE, "RODANDO"

    L = []
    L.append("%s%s╭─ loop-work · %s ─ %s%s" % (
        C.NEG, C.AZUL, os.path.basename(loop.raiz), time.strftime("%H:%M:%S"), C.RESET))
    L.append("  %s%s%s   iteração %d/%d"
             % (cor + C.NEG, estado, C.RESET, it, st.get("max_iteracoes", 0)))
    # O painel dizia "PARADO" e o operador lia "está entre duas iterações".
    # Parado é inerte: o hook sai no primeiro portão e o chat não tem como
    # reativá-lo — foi assim que um "continua" digitado em 17/08 virou um turno
    # de 2min30 e mais nada. `porque` no lugar de `armar`/`retomar` porque o
    # verbo certo depende do portão, e só ele sabe qual é.
    if not ativo or fase == "encerrando":
        L.append("  %s%s⚠ hook inerte — \"continua\" no chat não reativa%s"
                 % (C.VERM, C.NEG, C.RESET))
        L.append("    %so que fazer: loop-ctl porque --raiz %s%s"
                 % (C.VERM, loop.raiz, C.RESET))
    if st.get("bind_session") and st.get("session_id"):
        L.append("  %ssessão %s — outra sessão no mesmo repo é ignorada%s"
                 % (C.DIM, curto(st["session_id"]), C.RESET))
    if st.get("objetivo"):
        L.append("  %s%s%s" % (C.DIM, st["objetivo"][:96], C.RESET))
    L.append("")
    L.append("  Fila   %s  %d/%d" % (barra(feitos, total), feitos, total)
             + ("  (%d%%)" % round(100.0 * feitos / total) if total else ""))
    prox = loop.proximo_item()
    L.append("  Agora  %s→ %s%s" % (C.NEG, (prox or "—")[:88], C.RESET))
    L.append("")

    linhas, primeira = condicoes(st, pend, feitos)
    L.append("  %sFim por%s" % (C.DIM, C.RESET))
    for rot, resta, _ in linhas:
        marca = "  %s← primeira%s" % (C.AMAR, C.RESET) if rot == primeira else ""
        L.append("    %-30s %s%s" % (rot, resta, marca))

    sp = st.get("sem_progresso", 0)
    ks = "PRESENTE" if loop.kill_switch else "ausente"
    alerta = C.VERM if (sp or loop.kill_switch) else C.DIM
    L.append("    %ssem progresso %d/%d · kill-switch %s%s"
             % (alerta, sp, st.get("max_sem_progresso", 0), ks, C.RESET))

    paradas = ultimas_paradas(loop)
    if paradas:
        L.append("")
        L.append("  %sÚltimas paradas%s" % (C.DIM, C.RESET))
        for p in reversed(paradas):
            k = p.get("kind", "?")
            cor_k = C.ROXO if k == "ASK" else C.DIM
            aviso = ""
            if p.get("fecho_do_turno") == "PARCIAL":
                aviso = "  %s⚠ fecho parcial%s" % (C.VERM, C.RESET)
            elif k == "ASK":
                aviso = "  %s⚠ premissa registrada%s" % (C.AMAR, C.RESET)
            L.append("    #%-5s %s%-4s%s %-16s %-22s %s%s"
                     % (p.get("n", "?"), cor_k, k, C.RESET, p.get("sinal", "")[:16],
                        p.get("decisao", "")[:22], (p.get("ts", "")[11:16]), aviso))

    if anterior:
        d_it = it - anterior["it"]
        d_feitos = feitos - anterior["feitos"]
        if d_it or d_feitos:
            L.append("")
            L.append("  %s%sDesde a última leitura: +%d parada(s), +%d item(ns) fechado(s)%s"
                     % (C.VERDE, C.NEG, d_it, d_feitos, C.RESET))
        elif ativo:
            L.append("")
            L.append("  %ssem mudança desde a última leitura%s" % (C.DIM, C.RESET))

    L.append("%s╰%s" % (C.AZUL, C.RESET))
    return "\n".join(L), {"it": it, "feitos": feitos}


def imprimir_status_final(loop):
    caminho = loop.p("STATUS.md")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            print("\n" + f.read())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="loop-watch", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--intervalo", type=float, default=30.0)
    ap.add_argument("--raiz", default=None)
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--ate-encerrar", action="store_true",
                    help="sai (código 0) quando o loop encerrar")
    ap.add_argument("--sem-cor", action="store_true")
    ap.add_argument("--sem-limpar", action="store_true",
                    help="não limpa a tela — o histórico rola, útil para log")
    args = ap.parse_args(argv)

    if args.sem_cor or not sys.stdout.isatty():
        C.desligar()

    raiz = os.path.abspath(os.path.expanduser(args.raiz)) if args.raiz \
        else achar_raiz(os.getcwd())
    if not raiz:
        print("sem .loop/ aqui nem acima — use --raiz, ou arme com /loop-work")
        return 1
    loop = Loop(raiz)

    anterior = None
    while True:
        st = loop.ler()
        if not st:
            print("sem .loop/STATE.json em %s" % loop.dir)
            return 1
        texto, anterior = render(loop, st, anterior)
        if not args.sem_limpar and sys.stdout.isatty() and not args.uma_vez:
            sys.stdout.write("\033[H\033[J")
        print(texto, flush=True)

        encerrou = not st.get("ativo") or st.get("fase") == "encerrando"
        if args.uma_vez:
            return 0
        if encerrou and args.ate_encerrar:
            if sys.stdout.isatty():
                sys.stdout.write("\a")      # sino: você pode estar em outra janela
                sys.stdout.flush()
            imprimir_status_final(loop)
            return 0
        try:
            time.sleep(max(1.0, args.intervalo))
        except KeyboardInterrupt:
            print()
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
