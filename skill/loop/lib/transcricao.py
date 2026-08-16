#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Leitura do transcript JSONL da sessão.

O hook `Stop` não recebe a mensagem do agente — recebe o **caminho** do
transcript. Ler o arquivo inteiro seria caro numa sessão de meses, então a
leitura é pela cauda: os últimos `MAX_BYTES`, descartando a primeira linha
(quase sempre partida no meio de um JSON).

Python 3, stdlib apenas.
"""

import json
import os

MAX_BYTES = 2 * 1024 * 1024


def _linhas_da_cauda(caminho, max_bytes=MAX_BYTES):
    tamanho = os.path.getsize(caminho)
    with open(caminho, "rb") as f:
        if tamanho > max_bytes:
            f.seek(tamanho - max_bytes)
            f.readline()          # a primeira linha da janela está partida
        bruto = f.read()
    return bruto.decode("utf-8", "replace").split("\n")


def ultima_mensagem(caminho, max_bytes=MAX_BYTES):
    """(texto, ultimo_tool) da última mensagem do agente principal.

    - `isSidechain` é descartado: aquilo é subagente, e o turno que encerrou é
      o do agente principal. Sem esse filtro o loop leria o relatório de um
      Explore e classificaria a coisa errada.
    - `ultimo_tool` é a última tool do turno, quando veio depois do texto —
      é o que permite reconhecer `AskUserQuestion` como pergunta declarada.
    """
    try:
        linhas = _linhas_da_cauda(caminho, max_bytes)
    except (IOError, OSError):
        return "", None

    ultimo_tool = None
    for linha in reversed(linhas):
        linha = linha.strip()
        if not linha or not linha.startswith("{"):
            continue
        try:
            obj = json.loads(linha)
        except ValueError:
            continue
        if obj.get("type") != "assistant" or obj.get("isSidechain"):
            continue
        blocos = (obj.get("message") or {}).get("content") or []
        if not isinstance(blocos, list):
            continue
        textos, tools = [], []
        for b in blocos:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and (b.get("text") or "").strip():
                textos.append(b["text"])
            elif b.get("type") == "tool_use" and b.get("name"):
                tools.append(b["name"])
        if tools and ultimo_tool is None:
            ultimo_tool = tools[-1]
        if textos:
            return "\n".join(textos).strip(), ultimo_tool
    return "", ultimo_tool
