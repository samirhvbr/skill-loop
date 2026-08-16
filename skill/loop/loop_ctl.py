#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`loop_ctl` — arma, desarma e inspeciona o loop no repositório atual.

    python3 loop_ctl.py armar   --objetivo "..." [--max 200] [--sessao ID]
    python3 loop_ctl.py status
    python3 loop_ctl.py parar   [--motivo "..."]
    python3 loop_ctl.py retomar
    python3 loop_ctl.py fila

O `.loop/` só nasce aqui: enquanto ele não existir, o hook `Stop` instalado
globalmente é inerte em todo repositório da máquina. Armar é o opt-in, e é
explícito de propósito (SECURITY.md T-01).

Python 3, stdlib apenas.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))

from estado import (Loop, PADRAO, achar_raiz, agora,   # noqa: E402
                    fora_da_janela, minutos_desde, parse_duracao)

ESQUELETO_FILA = """# Fila do loop

Uma linha por unidade de trabalho. O hook lê **o primeiro `- [ ]`** e é ele que
vai no `reason` da continuação — então cada item precisa ser executável sozinho,
sem depender de contexto que só existe no chat.

Fila vazia = o loop encerra. É o critério de pronto do ciclo inteiro.

## Trabalho

- [ ] (substitua por itens reais destilados da documentação)
"""


def _raiz(args):
    if args.raiz:
        return os.path.abspath(args.raiz)
    return achar_raiz(os.getcwd()) or os.getcwd()


def cmd_armar(args):
    raiz = _raiz(args)
    loop = Loop(raiz)
    os.makedirs(loop.entries, exist_ok=True)
    if not os.path.exists(loop.p("QUEUE.md")):
        with open(loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(ESQUELETO_FILA)
    if os.path.exists(loop.p("STOP")):
        os.remove(loop.p("STOP"))

    duracao = parse_duracao(args.duracao)
    if args.duracao and duracao is None:
        print("erro: --duracao inválida (%r). Use 6h, 90m, 2h30." % args.duracao)
        return 2

    st = loop.iniciar(
        objetivo=args.objetivo or "",
        session_id=args.sessao,
        bind_session=not args.qualquer_sessao,
        max_iteracoes=args.max,
        max_sem_progresso=args.max_sem_progresso,
        politica_ask=args.politica,
        colher_itens=not args.sem_colheita,
        notificar=not args.sem_notificar,
        janela=args.janela,
        dias=args.dias,
        duracao_max_min=duracao,
        escopo_itens=args.itens,
        escopo_ate=args.ate,
    )
    pend, feitos = loop.contagem_fila()
    print("loop armado em %s" % loop.dir)
    print("  objetivo   : %s" % (st["objetivo"] or "—"))
    print("  fila       : %d pendente(s), %d feito(s)" % (pend, feitos))
    print("  fim por    : %s" % _fim_por(st, pend))
    print("  teto       : %d iterações · %d paradas sem progresso"
          % (st["max_iteracoes"], st["max_sem_progresso"]))
    print("  política   : ASK=%s · colheita=%s · notificar=%s"
          % (st["politica_ask"], st["colher_itens"], st["notificar"]))
    print("  sessão     : %s" % (st["session_id"] or "a primeira que parar"))
    if pend == 0:
        print("\n⚠️  fila vazia: o loop encerra na primeira parada. "
              "Preencha .loop/QUEUE.md antes de começar.")
    if st["janela"] and fora_da_janela(st["janela"], st["dias"]):
        print("\n⚠️  agora está FORA da janela %s: o loop encerra na primeira "
              "parada." % st["janela"])
    return 0


def _fim_por(st, pendentes):
    """Todas as condições de fim ativas, na ordem em que o hook as testa."""
    partes = []
    if st.get("escopo_itens"):
        partes.append("%d itens desta rodada" % st["escopo_itens"])
    if st.get("escopo_ate"):
        partes.append("item %r marcado" % st["escopo_ate"][:40])
    if st.get("janela"):
        partes.append("fora de %s%s" % (st["janela"],
                                        " (%s)" % st["dias"] if st.get("dias") else ""))
    if st.get("duracao_max_min"):
        partes.append("%dh%02d de relógio" % divmod(st["duracao_max_min"], 60))
    partes.append("fila zerada (%d pendente(s))" % pendentes)
    partes.append("%d iterações" % st.get("max_iteracoes", 0))
    return " · ".join(partes)


def cmd_status(args):
    loop = Loop(_raiz(args))
    if not loop.existe:
        print("sem .loop/ neste repositório — hook inerte")
        return 1
    st = loop.ler() or {}
    pend, feitos = loop.contagem_fila()
    print("ativo      : %s (fase %s)" % (st.get("ativo"), st.get("fase")))
    print("objetivo   : %s" % (st.get("objetivo") or "—"))
    print("iteração   : %d / %d" % (st.get("iteracao", 0), st.get("max_iteracoes", 0)))
    print("fila       : %d pendente(s), %d feito(s)" % (pend, feitos))
    print("próximo    : %s" % (loop.proximo_item() or "—"))
    print("sem prog.  : %d / %d" % (st.get("sem_progresso", 0),
                                    st.get("max_sem_progresso", 0)))
    print("fim por    : %s" % _fim_por(st, pend))
    if st.get("escopo_itens"):
        print("escopo     : %d de %d item(ns) desta rodada"
              % (feitos - st.get("feitos_ao_armar", 0), st["escopo_itens"]))
    if st.get("janela"):
        print("janela     : %s — agora %s"
              % (st["janela"],
                 "FORA" if fora_da_janela(st["janela"], st.get("dias")) else "dentro"))
    if st.get("duracao_max_min"):
        print("relógio    : %d de %d min" % (minutos_desde(st.get("armado_em")),
                                             st["duracao_max_min"]))
    print("kill-switch: %s" % ("PRESENTE" if loop.kill_switch else "ausente"))
    if st.get("encerrado_por"):
        print("encerrado  : %s em %s" % (st["encerrado_por"], st.get("encerrado_em")))
    return 0


def cmd_parar(args):
    loop = Loop(_raiz(args))
    if not loop.existe:
        print("sem .loop/ neste repositório")
        return 1
    st = loop.ler() or dict(PADRAO)
    st["ativo"] = False
    st["fase"] = "rodando"
    st["encerrado_por"] = args.motivo or "parada manual"
    st["encerrado_em"] = agora()
    loop.gravar(st)
    loop.gravar_status(st, st["encerrado_por"])
    print("loop parado (%s)" % st["encerrado_por"])
    return 0


def cmd_retomar(args):
    loop = Loop(_raiz(args))
    if not loop.existe:
        print("sem .loop/ — use `armar`")
        return 1
    st = loop.ler() or dict(PADRAO)
    if os.path.exists(loop.p("STOP")):
        os.remove(loop.p("STOP"))
    st["ativo"] = True
    st["fase"] = "rodando"
    st["sem_progresso"] = 0
    st["encerrado_por"] = None
    st["encerrado_em"] = None
    if args.sessao:
        st["session_id"] = args.sessao
    if args.max:
        st["max_iteracoes"] = args.max
    loop.gravar(st)
    print("loop retomado na iteração %d — próximo: %s"
          % (st.get("iteracao", 0), loop.proximo_item() or "—"))
    return 0


def cmd_fila(args):
    loop = Loop(_raiz(args))
    pend, feitos = loop.contagem_fila()
    print("%d pendente(s), %d feito(s)" % (pend, feitos))
    print("próximo: %s" % (loop.proximo_item() or "—"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="loop_ctl", description=__doc__)
    ap.add_argument("--raiz", help="raiz do repositório alvo (default: procura .loop/)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("armar")
    a.add_argument("--objetivo", default="")
    a.add_argument("--max", type=int, default=PADRAO["max_iteracoes"])
    a.add_argument("--max-sem-progresso", dest="max_sem_progresso", type=int,
                   default=PADRAO["max_sem_progresso"])
    a.add_argument("--politica", default=PADRAO["politica_ask"],
                   choices=["continuar", "continuar-exceto-irreversivel", "parar"])
    a.add_argument("--sessao", default=None, help="session_id a que o loop se prende")
    a.add_argument("--qualquer-sessao", action="store_true",
                   help="não prender a uma sessão (qualquer chat no repo dirige o loop)")
    a.add_argument("--sem-colheita", action="store_true",
                   help="não colher itens do fecho para a fila")
    a.add_argument("--sem-notificar", action="store_true")
    # ── condições de fim (ADR-010) ──────────────────────────────────────────
    a.add_argument("--janela", default=None, metavar="HH:MM-HH:MM",
                   help="horário de produção, ex.: 08:00-18:00 (cruza meia-noite)")
    a.add_argument("--dias", default=None, metavar="seg-sex",
                   help="dias permitidos: seg-sex | seg,qua,sex")
    a.add_argument("--duracao", default=None, metavar="6h",
                   help="teto de relógio desde que armou: 6h, 90m, 2h30")
    a.add_argument("--itens", type=int, default=None, metavar="N",
                   help="fechar N itens nesta rodada e parar")
    a.add_argument("--ate", default=None, metavar="TEXTO",
                   help="parar quando o item que contém TEXTO for marcado [x]")
    a.set_defaults(func=cmd_armar)

    s = sub.add_parser("status"); s.set_defaults(func=cmd_status)
    f = sub.add_parser("fila"); f.set_defaults(func=cmd_fila)

    p = sub.add_parser("parar")
    p.add_argument("--motivo", default="")
    p.set_defaults(func=cmd_parar)

    r = sub.add_parser("retomar")
    r.add_argument("--sessao", default=None)
    r.add_argument("--max", type=int, default=None)
    r.set_defaults(func=cmd_retomar)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
