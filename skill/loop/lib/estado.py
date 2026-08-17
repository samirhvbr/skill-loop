#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estado do loop: `.loop/` no repositório alvo.

Tudo que o loop sabe mora em arquivo, e de propósito: o loop roda por horas sem
ninguém olhando, e o único jeito de auditar depois é ler o que ele escreveu na
hora. Estado em memória de processo morreria com a sessão.

    .loop/
    ├── STATE.json        estado do ciclo (ativo, iteração, guarda-corpos)
    ├── QUEUE.md          a fila — checklist `- [ ]` / `- [x]`
    ├── INDEX.md          uma linha por parada, na ordem
    ├── ASSUMPTIONS.md    premissas adotadas para não parar num ASK
    ├── STATUS.md         por que o loop encerrou (escrito só no fim)
    ├── STOP              kill-switch: se existe, o próximo Stop encerra
    └── entries/NNNN-{ASK,DOC}-slug.md

Python 3, stdlib apenas.
"""

import hashlib
import json
import os
import re
import subprocess
import unicodedata
from datetime import datetime

VERSAO_ESTADO = 1

PADRAO = {
    "versao": VERSAO_ESTADO,
    "ativo": False,
    "fase": "rodando",           # rodando | encerrando
    "objetivo": "",
    "armado_em": None,
    "session_id": None,
    "bind_session": True,
    "iteracao": 0,
    "max_iteracoes": 200,
    # ── condições de fim (ADR-010). Todas opcionais, todas independentes:
    # a primeira que bater encerra. `None` = sem limite naquela dimensão.
    "janela": None,              # "08:00-18:00" — horário de produção
    "dias": None,                # "seg-sex" | "seg,qua,sex" | None = todos
    "duracao_max_min": None,     # minutos de relógio desde que armou
    "escopo_itens": None,        # fechar N itens desta rodada e parar
    "escopo_ate": None,          # parar quando o item que contém este texto for marcado
    "feitos_ao_armar": 0,
    "politica_ask": "continuar",  # continuar | continuar-exceto-irreversivel | parar
    "sem_progresso": 0,
    "max_sem_progresso": 3,
    "ultima_impressao": None,
    "colher_itens": True,
    "notificar": True,
    "encerrado_por": None,
    "encerrado_em": None,
}


def agora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def _hhmm(txt):
    h, m = txt.strip().split(":")
    return int(h) * 60 + int(m)


def parse_duracao(txt):
    """"6h", "90m", "2h30", "45" → minutos. Erro de formato → None."""
    if not txt:
        return None
    t = str(txt).strip().lower().replace(" ", "")
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m?)?$", t)
    if not m or not any(m.groups()):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def dias_permitidos(spec):
    """"seg-sex" → {0,1,2,3,4} · "seg,qua" → {0,2} · None → todos."""
    if not spec:
        return set(range(7))
    spec = spec.strip().lower()
    if "-" in spec and "," not in spec:
        a, b = spec.split("-", 1)
        if a in DIAS and b in DIAS:
            ia, ib = DIAS.index(a), DIAS.index(b)
            return set(range(ia, ib + 1)) if ia <= ib else \
                set(list(range(ia, 7)) + list(range(0, ib + 1)))
    escolhidos = {DIAS.index(d) for d in re.split(r"[,\s]+", spec) if d in DIAS}
    return escolhidos or set(range(7))


def fora_da_janela(janela, dias=None, momento=None):
    """A hora atual está fora do horário de produção?

    Janela que cruza a meia-noite ("22:00-06:00") é suportada: dentro dela vale
    `agora >= inicio ou agora < fim`. Formato inválido nunca encerra o loop —
    um typo em `--janela` não pode parar o trabalho em silêncio (fail-open).
    """
    if not janela:
        return False
    agora_dt = momento or datetime.now()
    try:
        inicio, fim = [_hhmm(x) for x in str(janela).split("-", 1)]
    except (ValueError, AttributeError):
        return False
    if agora_dt.weekday() not in dias_permitidos(dias):
        return True
    minuto = agora_dt.hour * 60 + agora_dt.minute
    dentro = (inicio <= minuto < fim) if inicio < fim \
        else (minuto >= inicio or minuto < fim)
    return not dentro


def minutos_ate_fechar(janela, dias=None, momento=None):
    """Minutos até a janela de produção fechar.

    `None` = não há janela · `0` = já está fechada. É o número que importa a
    quem está longe do monitor: não "qual é a janela", e sim "quanto ainda
    tenho". Cruza a meia-noite pelo mesmo caminho de `fora_da_janela`.
    """
    if not janela:
        return None
    agora_dt = momento or datetime.now()
    if fora_da_janela(janela, dias, agora_dt):
        return 0
    try:
        inicio, fim = [_hhmm(x) for x in str(janela).split("-", 1)]
    except (ValueError, AttributeError):
        return None
    minuto = agora_dt.hour * 60 + agora_dt.minute
    return (fim - minuto) if minuto < fim else (24 * 60 - minuto + fim)


def minutos_desde(iso):
    if not iso:
        return 0.0
    try:
        t0 = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return 0.0
    agora_dt = datetime.now(t0.tzinfo) if t0.tzinfo else datetime.now()
    return (agora_dt - t0).total_seconds() / 60.0


def slug(texto, limite=48):
    texto = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                    if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return (texto[:limite].strip("-") or "sem-titulo")


def achar_raiz(inicio, niveis=6):
    """Sobe a árvore procurando `.loop/`. Sem `.loop/` → None (hook é inerte)."""
    p = os.path.abspath(inicio or ".")
    for _ in range(niveis + 1):
        if os.path.isdir(os.path.join(p, ".loop")):
            return p
        pai = os.path.dirname(p)
        if pai == p:
            break
        p = pai
    return None


class Loop(object):

    def __init__(self, raiz):
        self.raiz = os.path.abspath(raiz)
        self.dir = os.path.join(self.raiz, ".loop")
        self.entries = os.path.join(self.dir, "entries")

    # ── caminhos ────────────────────────────────────────────────────────────
    def p(self, *nome):
        return os.path.join(self.dir, *nome)

    @property
    def existe(self):
        return os.path.isfile(self.p("STATE.json"))

    @property
    def kill_switch(self):
        return os.path.exists(self.p("STOP"))

    # ── estado ──────────────────────────────────────────────────────────────
    def ler(self):
        try:
            with open(self.p("STATE.json"), encoding="utf-8") as f:
                st = json.load(f)
        except (IOError, OSError, ValueError):
            return None
        if not isinstance(st, dict):
            return None
        base = dict(PADRAO)
        base.update(st)
        return base

    def gravar(self, st):
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.p("STATE.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.p("STATE.json"))

    def iniciar(self, **kw):
        st = dict(PADRAO)
        st.update(kw)
        st["ativo"] = True
        st["fase"] = "rodando"
        st["armado_em"] = agora()
        os.makedirs(self.entries, exist_ok=True)
        # Denominador do escopo: quantos itens já estavam feitos quando armou.
        # Sem esta marca, "fechar 10 itens" contaria trabalho de rodadas
        # anteriores e o loop encerraria na primeira parada.
        st["feitos_ao_armar"] = self.contagem_fila()[1]
        self.gravar(st)
        return st

    # ── fila ────────────────────────────────────────────────────────────────
    _PEND = re.compile(r"^(\s*)- \[ \]\s+(.+?)\s*$")
    _FEITO = re.compile(r"^(\s*)- \[[xX]\]\s+(.+?)\s*$")
    _PROVENIENCIA = re.compile(r"\s*<!--.*?-->\s*")

    @classmethod
    def _texto_item(cls, linha_capturada):
        """Item sem o comentário de proveniência.

        O `<!-- colhido em #NNNN -->` é rastro de auditoria, não parte do item:
        se entrar na chave de dedup, o mesmo item é recolhido a cada parada; se
        entrar no `reason`, vaza para o prompt do agente."""
        return cls._PROVENIENCIA.sub(" ", linha_capturada).strip()

    def _linhas_fila(self):
        try:
            with open(self.p("QUEUE.md"), encoding="utf-8") as f:
                return f.read().split("\n")
        except (IOError, OSError):
            return []

    def contagem_fila(self):
        pend = feitos = 0
        for l in self._linhas_fila():
            if self._PEND.match(l):
                pend += 1
            elif self._FEITO.match(l):
                feitos += 1
        return pend, feitos

    def proximo_item(self):
        for l in self._linhas_fila():
            m = self._PEND.match(l)
            if m:
                return self._texto_item(m.group(2))
        return None

    def feito_contem(self, texto):
        """Algum item já marcado `- [x]` contém este texto? (marcador de escopo)"""
        if not texto:
            return False
        alvo = slug(texto, 200)
        for l in self._linhas_fila():
            m = self._FEITO.match(l)
            if m and alvo and alvo in slug(self._texto_item(m.group(2)), 400):
                return True
        return False

    def acrescentar_itens(self, itens, origem):
        """Anexa itens colhidos do fecho, sem duplicar.

        Dedup por texto normalizado contra a fila inteira (pendentes e feitos):
        item já entregue não pode voltar por citação no relatório seguinte.
        """
        if not itens:
            return []
        existentes = set()
        for l in self._linhas_fila():
            m = self._PEND.match(l) or self._FEITO.match(l)
            if m:
                existentes.add(slug(self._texto_item(m.group(2)), 60))
        novos = [i for i in itens if slug(i, 60) not in existentes]
        if not novos:
            return []
        cab = "\n## Colhidos automaticamente\n"
        try:
            with open(self.p("QUEUE.md"), encoding="utf-8") as f:
                conteudo = f.read()
        except (IOError, OSError):
            conteudo = "# Fila do loop\n"
        if cab.strip() not in conteudo:
            conteudo = conteudo.rstrip("\n") + "\n" + cab
        conteudo = conteudo.rstrip("\n") + "\n"
        for i in novos:
            conteudo += "- [ ] %s  <!-- colhido em %s -->\n" % (i, origem)
        with open(self.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(conteudo)
        return novos

    # ── entries e índice ────────────────────────────────────────────────────
    def gravar_entry(self, n, res, texto, meta):
        os.makedirs(self.entries, exist_ok=True)
        nome = "%04d-%s-%s.md" % (n, res.kind, slug(meta.get("titulo") or res.sinal))
        caminho = os.path.join(self.entries, nome)
        fm = [
            "---",
            "n: %d" % n,
            "kind: %s" % res.kind,
            "sinal: %s" % res.sinal,
            "confianca: %s" % res.confianca,
            "ts: %s" % agora(),
            "sessao: %s" % (meta.get("sessao") or "?"),
            "item_da_fila: %s" % json.dumps(meta.get("item") or "", ensure_ascii=False),
            "decisao: %s" % meta.get("decisao", "?"),
            "fecho_do_turno: %s" % ("PARCIAL" if meta.get("parcial") else "completo"),
            "respondida: false" if res.kind == "ASK" else "respondida: n/a",
            "---",
            "",
        ]
        corpo = []
        corpo.append("## Por que %s" % res.kind)
        for e in res.evidencias:
            corpo.append("- %s" % e)
        if res.perguntas:
            corpo.append("\n## Pergunta(s) detectada(s)")
            for q in res.perguntas:
                corpo.append("> %s" % q)
        if res.retoricas:
            corpo.append("\n## Retórica suprimida (não conta como pergunta)")
            for q in res.retoricas:
                corpo.append("> %s" % q)
        if meta.get("colhidos"):
            corpo.append("\n## Itens colhidos para a fila")
            for i in meta["colhidos"]:
                corpo.append("- [ ] %s" % i)
        corpo.append("\n## Mensagem original\n")
        corpo.append(texto.strip())
        corpo.append("")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(fm) + "\n".join(corpo) + "\n")
        return os.path.relpath(caminho, self.raiz)

    def indexar(self, n, res, caminho, decisao, item):
        # `caminho` vem relativo à raiz (".loop/entries/x.md"); o INDEX.md mora
        # dentro de .loop/, então o link é o que sobra depois do prefixo.
        link = caminho.split(".loop" + os.sep, 1)[-1].replace(os.sep, "/")
        linha = "| %04d | %s | %s | %s | %s | [entry](%s) |\n" % (
            n, res.kind, res.sinal, decisao,
            (item or "—").replace("|", "/")[:70], link,
        )
        idx = self.p("INDEX.md")
        if not os.path.exists(idx):
            with open(idx, "w", encoding="utf-8") as f:
                f.write("# Índice de paradas\n\n"
                        "Uma linha por vez que o agente encerrou o turno.\n\n"
                        "| # | tipo | sinal | decisão | item da fila | |\n"
                        "|---|---|---|---|---|---|\n")
        with open(idx, "a", encoding="utf-8") as f:
            f.write(linha)

    def registrar_premissa_pendente(self, n, perguntas):
        """Semente do ASSUMPTIONS.md — o agente completa com a decisão real."""
        if not perguntas:
            return
        arq = self.p("ASSUMPTIONS.md")
        if not os.path.exists(arq):
            with open(arq, "w", encoding="utf-8") as f:
                f.write("# Premissas adotadas para não parar\n\n"
                        "Cada linha é uma decisão que o loop tomou sozinho. "
                        "Revisar em lote é mais barato que ser interrompido — "
                        "mas revisar é obrigatório.\n\n")
        with open(arq, "a", encoding="utf-8") as f:
            f.write("\n## #%04d — %s\n" % (n, agora()))
            for q in perguntas:
                f.write("- **Pergunta:** %s\n" % q)
            f.write("- **Premissa:** ⛔ a preencher pelo agente nesta iteração\n")
            f.write("- **Como reverter:** ⛔ a preencher\n")

    def gravar_status(self, st, motivo, detalhe=""):
        pend, feitos = self.contagem_fila()
        with open(self.p("STATUS.md"), "w", encoding="utf-8") as f:
            f.write("# Status do loop\n\n")
            f.write("- **Encerrado em:** %s\n" % agora())
            f.write("- **Motivo:** %s\n" % motivo)
            if detalhe:
                f.write("- **Detalhe:** %s\n" % detalhe)
            f.write("- **Iterações:** %d de %d\n" % (st.get("iteracao", 0),
                                                     st.get("max_iteracoes", 0)))
            f.write("- **Fila:** %d feito(s), %d pendente(s)\n" % (feitos, pend))
            if st.get("escopo_itens"):
                f.write("- **Escopo da rodada:** %d de %d item(ns)\n"
                        % (feitos - st.get("feitos_ao_armar", 0), st["escopo_itens"]))
            f.write("- **Objetivo:** %s\n" % (st.get("objetivo") or "—"))
            if motivo == "fora da janela de trabalho" and st.get("janela"):
                f.write("\n> A janela %s reabre no próximo dia útil configurado. "
                        "O loop **não** se rearma sozinho: retomar é um comando "
                        "(ou um cron — ver ADR-010).\n" % st["janela"])
            f.write("\nRetomar: `/loop-work retomar`\n")

    # ── impressão digital de progresso ──────────────────────────────────────
    def _git(self, *args):
        try:
            out = subprocess.run(["git", "-C", self.raiz] + list(args),
                                 capture_output=True, timeout=5)
            return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    def impressao(self):
        """Hash do que conta como progresso: árvore + HEAD + fila.

        Sem git (ou fora de repo), a fila sozinha responde. Duas paradas com a
        mesma impressão = o agente falou e não moveu nada — é o sinal de loop
        degenerado, o modo de falha que mais custa caro aqui.
        """
        pend, feitos = self.contagem_fila()
        material = "|".join([
            self._git("status", "--porcelain"),
            self._git("rev-parse", "HEAD").strip(),
            str(pend), str(feitos),
        ])
        return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()
