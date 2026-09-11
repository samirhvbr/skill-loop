#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enumera as sessões do Claude Code abertas em um repositório.

⛔ **Por que isto existe, e o defeito que o criou.** Desde a `0.3.14` o atalho
`loop.sh` recusa armar sem `--sessao`, porque adotar a primeira parada custou
caro duas vezes (01/09 e 10/09 no EOP). A recusa estava certa e a saída que ela
oferecia, não: mandava o operador ler `~/.claude*/projects/<repo>/<id>.jsonl` e
tirar dali o nome do arquivo. Medido em 11/09, na primeira vez que alguém
precisou disso de verdade: o operador digitou **um apelido** — `EOP-b3building`,
que não existe em lugar nenhum do disco. Instrução que manda garimpar não é
instrução.

⚠️ **Não é o `transcricao.py`, e a diferença não é estilo.** Aquele lê a
**cauda** de UM transcript cujo caminho o hook entregou, para saber o que o
agente acabou de dizer. Este varre **muitos** arquivos de que ninguém deu o
caminho, e só precisa da **cabeça** de cada um — `cwd` e primeira mensagem. Ler a
cauda de todos custaria 2 MB por sessão; a maior aqui tem 62 MB.

Python 3, stdlib apenas.
"""

import glob
import json
import os
import re

# Teto de linhas lidas por transcript. O `cwd` está na primeira linha e a
# primeira mensagem de usuário logo atrás; 200 linhas cobrem com folga o
# preâmbulo de metadado que algumas sessões gravam antes dela.
MAX_LINHAS_CABECA = 200

# Janela padrão da listagem, em horas.
#
# 📏 Medida, não escolhida: a primeira execução real neste repositório devolveu
# **10 sessões, e 8 eram de 13 a 25 dias atrás**. Uma lista em que 80% das linhas
# são ruído não ajuda a escolher — ela empurra o leitor de volta ao palpite, que
# é o defeito que este comando existe para matar. Sessão que não é tocada há dois
# dias não vai dirigir uma rodada que começa agora.
#
# ⚠️ As escondidas são CONTADAS na saída, nunca sumidas em silêncio, e
# `--todas` traz tudo. Filtro que não se declara é filtro que mente.
JANELA_H = 48

# 8-4-4-4-12. É a forma que o Claude Code usa para `session_id`, e é o que o
# hook `Stop` recebe em `payload["session_id"]` — o mesmo valor que vira nome do
# arquivo de transcript.
RE_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
                     r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def parece_session_id(txt):
    return bool(txt) and bool(RE_UUID.match(txt.strip()))


def codificar_raiz(raiz):
    """`/home/samir/x/EOP` → `-home-samir-x-EOP`.

    ⚠️ É atalho de BUSCA, nunca prova: quem decide se a sessão é deste
    repositório é o `cwd` gravado dentro do arquivo. O nome do diretório só diz
    onde vale a pena procurar.

    Medido contra o disco em 11/09 — `/` e `.` viram `-`, e é por isso que
    `/home/samir/.local/share/…` aparece como `-home-samir--local-share-…`, com
    o traço dobrado.
    """
    return re.sub(r"[/.]", "-", os.path.abspath(raiz))


def homes():
    """Diretórios de configuração do Claude Code que têm `projects/`.

    Nesta máquina são três (`.claude`, `.claude-blue3`, `.claude-pessoal`) e a
    sessão que interessa pode estar em qualquer um: o EOP é dirigido do
    `.claude-blue3`, não do `.claude` padrão. Varrer só o padrão devolveria
    lista vazia justamente para quem precisa dela.
    """
    vistos, saida = [], []
    candidatos = []
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        candidatos.extend(os.environ["CLAUDE_CONFIG_DIR"].split(os.pathsep))
    candidatos.extend(sorted(glob.glob(os.path.join(
        os.path.expanduser("~"), ".claude*"))))
    for d in candidatos:
        if not os.path.isdir(os.path.join(d, "projects")):
            continue
        real = os.path.realpath(d)
        if real in vistos:
            continue
        vistos.append(real)
        saida.append(d)
    return saida


def _cabeca(caminho, max_linhas=MAX_LINHAS_CABECA):
    with open(caminho, "r", encoding="utf-8", errors="replace") as f:
        for n, linha in enumerate(f):
            if n >= max_linhas:
                return
            linha = linha.strip()
            if not linha:
                continue
            try:
                yield json.loads(linha)
            except ValueError:
                continue


def _texto_da_mensagem(d):
    """A mensagem de usuário como texto, ou `None` se a linha não for uma.

    Descarta o que não foi digitado por gente: `isMeta`, `isSidechain`
    (subagente) e todo conteúdo que abre em `<` — `<system-reminder>`,
    `<command-name>`, `<local-command-stdout>`. Sem esse filtro a "primeira
    mensagem" de quase toda sessão seria um bloco de lembrete do harness, que é
    igual em todas e não distingue nada.
    """
    if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
        return None
    conteudo = (d.get("message") or {}).get("content")
    if isinstance(conteudo, list):
        conteudo = " ".join(b.get("text", "") for b in conteudo
                            if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(conteudo, str):
        return None
    conteudo = conteudo.strip()
    if not conteudo or conteudo.startswith("<"):
        return None
    return " ".join(conteudo.split())


def _ler_sessao(caminho, raiz):
    """`{id, cwd, abertura, mtime, tamanho}` — ou `None` se não for deste repo."""
    sid = os.path.basename(caminho)[:-len(".jsonl")]
    cwd, abertura = None, None
    for d in _cabeca(caminho):
        if cwd is None and d.get("cwd"):
            cwd = d["cwd"]
        if abertura is None:
            abertura = _texto_da_mensagem(d)
        if cwd and abertura:
            break
    if not cwd:
        return None
    # A prova de pertencer ao repositório: o `cwd` é a raiz ou desce dela.
    # Sessão aberta em `capabilities/core/billing` é sessão deste repositório.
    raiz = os.path.abspath(raiz)
    if cwd != raiz and not cwd.startswith(raiz + os.sep):
        return None
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return {"id": sid, "cwd": cwd, "abertura": abertura,
            "mtime": st.st_mtime, "tamanho": st.st_size,
            "caminho": caminho}


def sessoes_do_repo(raiz, teto=None):
    """As sessões deste repositório, **mais recente primeiro**.

    A recência é a última escrita no transcript (`mtime`), e é deliberadamente
    tudo o que se afirma.

    ⛔ **Não tente dizer "está rodando".** Medido em 11/09: varrer
    `/proc/*/fd` em busca de quem tem o transcript aberto deu **falso negativo
    na sessão que estava trabalhando** — o processo abre, grava e fecha, então a
    varredura só acerta se cair no instante da escrita. Afirmar processo vivo
    seria inventar; relatar última escrita é o que se mede.
    """
    prefixo = codificar_raiz(raiz)
    achadas = {}
    for home in homes():
        base = os.path.join(home, "projects")
        for nome in sorted(os.listdir(base)):
            # `startswith` e não igualdade: sessão aberta num subdiretório do
            # repositório mora num `projects/` de nome mais longo.
            if not nome.startswith(prefixo):
                continue
            for caminho in glob.glob(os.path.join(base, nome, "*.jsonl")):
                s = _ler_sessao(caminho, raiz)
                if not s:
                    continue
                s["home"] = home
                # Mesmo id em dois homes: fica o mais recente. Não é hipótese —
                # o `.claude` e o `.claude-blue3` têm diretórios de projeto com
                # o mesmo nome para o mesmo repositório.
                if s["id"] not in achadas or s["mtime"] > achadas[s["id"]]["mtime"]:
                    achadas[s["id"]] = s
    ordenadas = sorted(achadas.values(), key=lambda s: s["mtime"], reverse=True)
    return ordenadas[:teto] if teto else ordenadas


def _idade(segundos):
    """Segundos → `agora` | `há 7 min` | `há 3h20` | `há 13 d`.

    ⚠️ Não usa o `dur()` do `estado.py` de propósito, e a razão está no
    docstring dele: aquele formata **quanto resta de rodada**, onde `0` não é
    "0min" e sim `esgotado`. Aqui `0` é `agora`, e 13 dias precisam ser 13 dias,
    não `312h00`. São duas grandezas, não duas cópias de uma.
    """
    m = int(segundos // 60)
    if m < 1:
        return "agora"
    if m < 60:
        return "há %d min" % m
    if m < 60 * 24:
        return "há %dh%02d" % divmod(m, 60)
    return "há %d d" % (m // (60 * 24))


def _tamanho(n):
    for unidade in ("B", "K", "M", "G"):
        if n < 1024 or unidade == "G":
            if unidade == "B":
                return "%dB" % n
            return ("%.1f%s" if n < 10 else "%.0f%s") % (n, unidade)
        n /= 1024.0


def formatar(sessoes, raiz, largura_abertura=88, ocultas=0):
    """O bloco que o operador lê para escolher. Lista vazia devolve `[]`."""
    if not sessoes:
        return []
    import time
    agora = time.time()
    linhas = ["sessões deste repositório (%s), mais recente primeiro:"
              % os.path.abspath(raiz), ""]
    for s in sessoes:
        linhas.append("  %s   %-10s %6s   %s"
                      % (s["id"], _idade(agora - s["mtime"]),
                         _tamanho(s["tamanho"]), s["home"]))
        abertura = s["abertura"] or "(sem mensagem de usuário no início)"
        if len(abertura) > largura_abertura:
            abertura = abertura[:largura_abertura - 1] + "…"
        linhas.append('      "%s"' % abertura)
        linhas.append("")
    if ocultas:
        linhas.append("(%d sessão(ões) sem escrita há mais de %dh não listada(s)"
                      " — `--todas` mostra)" % (ocultas, JANELA_H))
        linhas.append("")
    linhas.append('⚠️ a recência é a ÚLTIMA ESCRITA no transcript, não prova de')
    linhas.append("   processo vivo. Escolha pelo prompt de abertura: é ele que")
    linhas.append("   distingue a sessão que trabalha da que está lendo isto.")
    return linhas
