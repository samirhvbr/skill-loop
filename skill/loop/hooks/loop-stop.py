#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook `Stop` do LOOP — o motor.

Dispara no instante exato em que o agente encerra o turno. Lê a última mensagem
no transcript, classifica ASK × DOC, arquiva em `.loop/entries/`, e devolve
`{"decision": "block", "reason": ...}` para o agente voltar ao trabalho — ou
`exit 0` quando um guarda-corpo mandou encerrar de verdade.

Contrato do hook (Claude Code):
  stdin  → {"session_id", "transcript_path", "cwd", "hook_event_name",
            "stop_hook_active"}
  stdout → {"decision": "block", "reason": "..."} para continuar
           nada (exit 0) para deixar parar

⚠️  `stop_hook_active` NÃO é usado como trava. Ele vira `true` já na segunda
parada e nunca volta a `false`; o padrão da documentação
(`if stop_hook_active: allow`) daria **uma** continuação e encerraria o loop.
Quem limita aqui é `max_iteracoes` + `sem_progresso` + fila + kill-switch, todos
em `.loop/STATE.json` (SPEC.md §5, ADR-002).

**Fail-open por desenho:** qualquer erro inesperado → `exit 0`. O pior caso vira
o comportamento de hoje (você digita "continua"), nunca uma sessão travada.

Python 3, stdlib apenas.
"""

import json
import os
import re
import sys

_AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), "lib"))

from classificador import classificar          # noqa: E402
from diagnostico import condicoes_de_fim       # noqa: E402
from estado import (Loop, achar_raiz, agora,   # noqa: E402
                    objetivo_para_exibir)
from transcricao import ultima_mensagem        # noqa: E402

# repo/skill/loop/hooks → repo
_RAIZ_SKILL = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
TEMPLATE = os.environ.get(
    "LOOP_TEMPLATE",
    os.path.join(_RAIZ_SKILL, "prompts", "continuacao.md"),
)

# Ações sem volta. Só consultadas quando politica_ask =
# "continuar-exceto-irreversivel" — no default ("continuar") o loop segue e a
# premissa fica registrada (ADR-003).
IRREVERSIVEL = [
    r"\bdrop (?:table|database|schema)\b",
    r"\bdelete from\b",
    r"\btruncate\b",
    r"\bapagar (?:os |as |o |a )?(?:dados|banco|tabela|produ)",
    r"\bpush --force\b|\bforce[- ]push\b",
    r"\bfilter-(?:branch|repo)\b",
    r"\brm -rf\b",
    r"\bprodu[çc][ãa]o\b",
    r"\bderrubar\b",
    r"\brevogar\b",
    r"\bmigra[çc][ãa]o (?:destrutiva|irrevers[íi]vel|sem volta)\b",
    r"\bcobran[çc]a\b|\bpagamento\b|\bfatura\b",
    r"\benviar (?:e-?mail|mensagem|whatsapp) (?:para|ao|à)\b",
]

FALLBACK = """[LOOP-WORK · iteração {iteracao}] Não pare para resumir — seu relato
já foi arquivado em {entry} e ninguém está lendo o chat agora.

Item atual da fila (.loop/QUEUE.md): {item}

{bloco_ask}Execute o item até o fim, marque `- [x]` no QUEUE.md e siga direto para o
próximo, sem pedir confirmação. Só encerre se a fila zerar, se existir
`.loop/STOP`, ou se a próxima ação for destrutiva/irreversível.
"""


def _preencher(gabarito, campos):
    """`str.replace` em vez de `str.format`: o template é markdown editável à
    mão, e uma chave solta em exemplo de código não pode derrubar o hook."""
    for k, v in campos.items():
        gabarito = gabarito.replace("{%s}" % k, str(v))
    return gabarito


def _template():
    try:
        with open(TEMPLATE, encoding="utf-8") as f:
            corpo = f.read()
        # descarta o comentário HTML de cabeçalho, que é doc, não prompt
        return re.sub(r"^<!--.*?-->\s*", "", corpo, flags=re.DOTALL)
    except (IOError, OSError):
        return FALLBACK


def _irreversivel(texto):
    alvo = (texto or "").lower()
    return [p for p in IRREVERSIVEL if re.search(p, alvo)]


def _bloco_ask(res):
    if res.kind != "ASK":
        return ""
    if res.sinal == "handoff":
        cabeca = ("Sua última mensagem **entregou o bastão** sem fazer pergunta "
                  "explícita — o loop leu isso como espera por mim.")
    elif res.sinal == "tool":
        cabeca = "Você usou `AskUserQuestion`. Não vou responder agora."
    else:
        cabeca = "Sua última mensagem terminou com pergunta aberta."
    return (
        "**Decisão pendente (%s):** %s\n"
        "Adote o default mais razoável e **reversível**, registre em "
        "`.loop/ASSUMPTIONS.md` (pergunta · decisão · alternativa descartada · "
        "como reverter) e siga. Não repita a pergunta.\n\n" % (res.sinal, cabeca)
    )


def _bloco_colhidos(colhidos):
    if not colhidos:
        return ""
    linhas = "\n".join("  - %s" % c for c in colhidos)
    return ("**%d item(ns) do seu fecho entraram na fila** (revise a redação se "
            "ficou truncada):\n%s\n\n" % (len(colhidos), linhas))


def _responder(decisao, reason=None, aviso=None):
    saida = {}
    if decisao == "block":
        saida["decision"] = "block"
        saida["reason"] = reason
    if aviso:
        saida["systemMessage"] = aviso
    if saida:
        sys.stdout.write(json.dumps(saida, ensure_ascii=False))
    sys.exit(0)


def principal():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, IOError):
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    raiz = achar_raiz(payload.get("cwd") or os.getcwd())
    if not raiz:
        sys.exit(0)
    loop = Loop(raiz)
    if not loop.existe:
        sys.exit(0)
    st = loop.ler()
    if not st or not st.get("ativo"):
        sys.exit(0)

    # A parada seguinte ao aviso de encerramento é o fim de verdade.
    if st.get("fase") == "encerrando":
        st["ativo"] = False
        loop.gravar(st)
        sys.exit(0)

    sid = payload.get("session_id")
    if st.get("bind_session") and sid:
        if not st.get("session_id"):
            # Auto-amarração: quem arma é a skill, de dentro da sessão, e ela
            # não tem como saber o próprio session_id. A primeira parada é
            # necessariamente a da sessão que armou — é ela que fica dona.
            st["session_id"] = sid
            loop.gravar(st)
        elif sid != st["session_id"]:
            sys.exit(0)  # outra sessão no mesmo repo não é dirigida por este loop

    texto, tool, parcial = ultima_mensagem(payload.get("transcript_path") or "")
    res = classificar(texto, tool)
    if parcial:
        # O fecho do turno não chegou ao transcript a tempo. Seguimos, mas a
        # classificação vale menos e a entry precisa dizer isso (ADR-012).
        res.confianca = "baixa"
        res.evidencias.insert(0, "⚠️ texto PARCIAL — o fecho do turno não estava "
                                 "no transcript quando o hook leu; isto é resto "
                                 "de meio de raciocínio, não o relatório")

    # ITERAÇÃO e NÚMERO DE ENTRY são coisas diferentes, e eram a mesma.
    # A iteração conta esta rodada (e zera na próxima); o número da entry
    # identifica a parada para sempre, no INDEX e no ASSUMPTIONS. Enquanto os
    # dois eram `iteracao + 1`, cada rodada nova renumerava do 0001 por cima da
    # anterior — o `INDEX.md` acabou com `0001-DOC` e `0001-ASK`.
    st["iteracao"] = iteracao = st.get("iteracao", 0) + 1
    n = loop.proximo_numero_de_entry()

    impressao = loop.impressao()
    st["sem_progresso"] = (st.get("sem_progresso", 0) + 1
                           if impressao == st.get("ultima_impressao") else 0)
    st["ultima_impressao"] = impressao

    colhidos = []
    if st.get("colher_itens", True) and res.itens:
        colhidos = loop.acrescentar_itens(res.itens, "#%04d" % n)

    pendentes, feitos = loop.contagem_fila()
    item = loop.proximo_item()

    # A cadeia de condições mora em `lib/diagnostico.py`, e não aqui, para que
    # `loop-ctl porque` mostre **a** ordem em que este hook decide — e não uma
    # cópia dela, que apodreceria na primeira condição nova. `contagem` vai
    # pronta porque a colheita de itens acabou de mexer na fila: recontar lá
    # daria o número de antes.
    fim = condicoes_de_fim(loop, st, res=res, texto=texto,
                           irreversivel=_irreversivel,
                           contagem=(pendentes, feitos))
    motivo, detalhe = fim if fim else (None, None)

    decisao = "encerrou: %s" % motivo if motivo else "continuou"
    caminho = loop.gravar_entry(n, res, texto, {
        "sessao": sid,
        "item": item,
        "titulo": (item or res.sinal),
        "colhidos": colhidos,
        "decisao": decisao,
        "parcial": parcial,
    })
    loop.indexar(n, res, caminho, decisao, item)
    if res.kind == "ASK" and not motivo:
        loop.registrar_premissa_pendente(n, res.perguntas or ["(handoff sem pergunta explícita)"])

    if motivo:
        st["encerrado_por"] = motivo
        # O detalhe morava só no STATUS.md, em prosa. Ele é o que separa duas
        # condições que compartilham motivo ("escopo concluído" por N itens ×
        # por marcador) e o que responde "zerada com quantos?" sem abrir outro
        # arquivo. Campo aditivo: estado antigo lê `None` e nada quebra.
        st["encerrado_detalhe"] = detalhe or ""
        st["encerrado_em"] = agora()
        loop.gravar_status(st, motivo, detalhe or "")
        if st.get("notificar"):
            st["fase"] = "encerrando"
            loop.gravar(st)
            _responder("block", reason=(
                "[LOOP-WORK ENCERROU · %s — %s]\n\n"
                "**Não retome o trabalho.** O loop parou depois de %d iteração(ões); "
                "a fila está em %d feito(s) / %d pendente(s).\n\n"
                "Faça só isto e encerre o turno:\n"
                "1. Envie uma push notification ao Samir com uma linha: motivo do "
                "encerramento, o que avançou e o que ficou pendente.\n"
                "2. Não continue nenhum item, não resuma o histórico no chat — "
                "está tudo em `.loop/STATUS.md` e `.loop/INDEX.md`."
                % (motivo, detalhe or "", iteracao, feitos, pendentes)))
        # Sem notificação não há turno seguinte para consumir a fase
        # "encerrando" — o loop precisa morrer aqui mesmo.
        st["ativo"] = False
        loop.gravar(st)
        _responder("allow", aviso="loop-work: encerrado (%s)" % motivo)

    loop.gravar(st)
    reason = _preencher(_template(), {
        "iteracao": iteracao,
        "max_iteracoes": st.get("max_iteracoes", 200),
        "kind": res.kind,
        "sinal": res.sinal,
        "entry": caminho,
        "item": item or "(fila vazia)",
        "pendentes": pendentes,
        "feitos": feitos,
        "objetivo": objetivo_para_exibir(st.get("objetivo")),
        "bloco_ask": _bloco_ask(res),
        "bloco_colhidos": _bloco_colhidos(colhidos),
    })
    _responder("block", reason=reason)


if __name__ == "__main__":
    try:
        principal()
    except SystemExit:
        raise
    except Exception:                                    # noqa: BLE001
        # Fail-open: hook quebrado nunca pode travar a sessão (SECURITY.md T-05).
        sys.exit(0)
