#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Token use as the transcript recorded it — measured, never enforced (ADR-020).

The Stop hook already holds the one thing needed to measure a round honestly:
the path of the session transcript, where every assistant message carries the
`usage` the API reported. This module folds that into `STATE.json` at each stop.

Three things the first version of a meter gets wrong, all measured on a real
session before this was written:

- **Summing lines overcounts about 3×.** Claude Code writes one JSONL line per
  content block, so a message with thinking, text and a tool call appears three
  times with the *same* `message.id` and the *same* `usage`. A 940-line session
  summed to 315,106 output tokens; deduplicated by id it is 98,827. Everything
  here is deduplicated by id, and the ids of the last chunk are kept so a message
  split across two stops is counted once.
- **A subagent's tokens are not in the main transcript.** They live in
  `<session>/subagents/agent-*.jsonl` and are tagged `isSidechain`. A meter that
  skips them undercounts exactly the loops that spend the most.
- **Reading the whole file every stop does not scale.** Each file is read from a
  saved byte offset, and only up to its last complete line: a line the harness is
  still writing is left for the next stop, not parsed half.

Not measured, and said so rather than guessed: calls the transcript does not see
(a tool that calls a model by itself), and money. Prices differ by model and
change, and a dollar figure built from mixed units would be an estimate wearing an
observation's clothes — the exact trap `loop-run-log` fell into upstream, with a
`tokens_estimate` that was a constant 52,000.

Python 3, stdlib only. No network, no model. Fail-open: any error returns `None`
and leaves the state as it was.
"""

import glob
import json
import os
from datetime import datetime

CAMPOS = ("saida", "entrada_nova", "cache_lido")

# Per file, per stop. A transcript bigger than this since the last read is
# sampled from its tail and the round's meter is flagged `parcial` — a number
# labelled as incomplete is worth more than one that silently is.
MAX_VARREDURA = 16 * 1024 * 1024

# Ids kept between stops, to count once a message split across two chunks. The
# turn that just ended wrote at most a few dozen messages.
MAX_IDS = 256


def _zero():
    return {c: 0 for c in CAMPOS}


def _de_usage(u):
    """The three components, from one API `usage` block.

    `entrada_nova` is what the model had to read that was not already cached
    (`input_tokens` + `cache_creation_input_tokens`); `cache_lido` is the cached
    prefix it re-read. They are kept apart because they dominate in opposite
    ways — in the session measured, cache reads were 100× the output — and
    adding them would make one number that means nothing.
    """
    def n(chave):
        v = u.get(chave)
        return v if isinstance(v, int) and v > 0 else 0
    return {
        "saida": n("output_tokens"),
        "entrada_nova": n("input_tokens") + n("cache_creation_input_tokens"),
        "cache_lido": n("cache_read_input_tokens"),
    }


def _ts(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _antes_de(ts_linha, desde):
    """True only when both are comparable and the line predates `desde`."""
    if desde is None or ts_linha is None:
        return False
    try:
        return ts_linha < desde
    except TypeError:                       # naive vs aware: do not guess
        return False


def varrer_arquivo(caminho, offset, desde, vistos):
    """Read one transcript from `offset`. `(novo_offset, delta, ids, parcial)`.

    `delta` has the three components plus `mensagens`. Only complete lines are
    consumed, and the returned offset sits right after the last one.
    """
    tamanho = os.path.getsize(caminho)
    if offset is not None and offset > tamanho:
        # The file got shorter: rewritten, or replaced. There is no way to place
        # what is in it against what was already counted, and recounting it all
        # is the one error worse than skipping.
        return tamanho, dict(_zero(), mensagens=0), [], True
    inicio = offset or 0
    parcial = False
    if tamanho - inicio > MAX_VARREDURA:
        inicio, parcial = tamanho - MAX_VARREDURA, True
    with open(caminho, "rb") as f:
        f.seek(inicio)
        if parcial:
            f.readline()                     # the window starts mid-line
        base = f.tell()
        bruto = f.read()
    fim = bruto.rfind(b"\n")
    delta = dict(_zero(), mensagens=0)
    if fim < 0:
        return base, delta, [], parcial     # nothing complete yet
    ids, locais = [], set()
    for linha in bruto[:fim + 1].split(b"\n"):
        # Cheap filter before the parse: most lines are not usage records.
        if b'"usage"' not in linha:
            continue
        try:
            d = json.loads(linha.decode("utf-8", "replace"))
        except ValueError:
            continue
        m = d.get("message") if isinstance(d, dict) else None
        if not isinstance(m, dict) or d.get("type") != "assistant":
            continue
        u = m.get("usage")
        if not isinstance(u, dict):
            continue
        chave = m.get("id") or d.get("requestId") or d.get("uuid")
        if chave:
            if chave in vistos or chave in locais:
                continue
        if _antes_de(_ts(d.get("timestamp")), desde):
            continue
        if chave:
            ids.append(chave)
            locais.add(chave)
        for c, v in _de_usage(u).items():
            delta[c] += v
        delta["mensagens"] += 1
    return base + fim + 1, delta, ids, parcial


def _arquivos(caminho):
    """The main transcript, then the subagents' (`<session>/subagents/*.jsonl`)."""
    pasta = caminho[:-len(".jsonl")] if caminho.endswith(".jsonl") else caminho
    return [caminho] + sorted(glob.glob(os.path.join(pasta, "subagents", "*.jsonl")))


def _somar(a, b):
    return {c: (a or {}).get(c, 0) + b.get(c, 0) for c in CAMPOS}


def atualizar(st, caminho):
    """Fold what the transcript recorded since the last stop into `st`.

    Returns this stop's delta (`saida`, `entrada_nova`, `cache_lido`,
    `mensagens`), or `None` when nothing could be read. Mutates only `st["uso"]`,
    `st["uso_item"]`, `st["uso_offsets"]` and `st["uso_ids"]`, and only after
    every file was read — a failure half-way leaves the state exactly as it was.

    `uso_item` is the meter of the item at the head of the queue (ADR-019): the
    hook resets it when the head changes. It is credited here, before the head is
    re-read, because the turn that just ended worked on the item delivered at the
    PREVIOUS stop.
    """
    try:
        if not caminho or not os.path.isfile(caminho):
            return None
        desde = _ts(st.get("uso_desde") or st.get("armado_em"))
        offsets = dict(st.get("uso_offsets") or {})
        vistos = set(st.get("uso_ids") or [])
        total = dict(_zero(), mensagens=0)
        ids_novos, parcial = [], False
        for arq in _arquivos(caminho):
            chave_arq = os.path.basename(arq)
            antes = offsets.get(chave_arq)
            if antes is None and arq != caminho and desde is not None:
                # A subagent file nobody has read, untouched since the round was
                # armed, cannot hold a line from this round.
                try:
                    if os.path.getmtime(arq) < desde.timestamp():
                        continue
                except OSError:
                    continue
            novo, delta, ids, p = varrer_arquivo(arq, antes, desde, vistos)
            offsets[chave_arq] = novo
            ids_novos.extend(ids)
            parcial = parcial or p
            for c in CAMPOS + ("mensagens",):
                total[c] += delta[c]
    except Exception:                                    # noqa: BLE001
        return None

    uso = dict(st.get("uso") or {})
    st["uso"] = dict(_somar(uso, total),
                     mensagens=uso.get("mensagens", 0) + total["mensagens"],
                     parcial=bool(uso.get("parcial")) or parcial)
    st["uso_item"] = _somar(st.get("uso_item"), total)
    st["uso_offsets"] = offsets
    st["uso_ids"] = (list(st.get("uso_ids") or []) + ids_novos)[-MAX_IDS:]
    return total


# ── how it is shown ─────────────────────────────────────────────────────────
def humano(n):
    n = int(n or 0)
    if n >= 1000000:
        return "%.1fM" % (n / 1e6)
    if n >= 1000:
        return "%.1fk" % (n / 1e3)
    return str(n)


def resumo(uso):
    """`saída 98.8k · entrada nova 492k · cache lido 11.4M`."""
    uso = uso or {}
    return "saída %s · entrada nova %s · cache lido %s" % (
        humano(uso.get("saida")), humano(uso.get("entrada_nova")),
        humano(uso.get("cache_lido")))
