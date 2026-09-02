#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do diagnóstico (`lib/diagnostico.py`) e do comando `loop-ctl porque`.

O hook é fail-open e **sai calado** (ADR-009) — certo para não travar a máquina,
e foi o que deixou uma parada de 17/08 sem explicação por uma manhã inteira.
Estes testes cobrem as duas metades do conserto:

1. `condicoes_de_fim` é a **fonte** da cadeia que o hook testa. Aqui prova-se a
   ordem (quem ganha de quem) e cada condição isolada; a fidelidade ao hook em
   si é provada pelos 46 testes de `test_ciclo.py`, que rodam o hook inteiro.
2. `portoes_de_inercia` é **espelho** dos portões anteriores a qualquer mutação.
   Espelho paga preço: `TestEspelhoDoHook` alimenta o mesmo estado ao hook (como
   subprocesso, contrato real) e ao espelho, e exige que o silêncio de um
   corresponda ao portão nomeado pelo outro.

O `~/.claude/settings.json` real **nunca** entra: todo teste aponta
`CLAUDE_SETTINGS` para um arquivo temporário (regra do CLAUDE.md).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(RAIZ, "skill", "loop", "hooks", "loop-stop.py")
CTL = os.path.join(RAIZ, "skill", "loop", "loop_ctl.py")
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

from diagnostico import (condicoes_de_fim, hook_instalado,   # noqa: E402
                         portoes_de_inercia)
from estado import Loop                                     # noqa: E402

FILA = """# Fila do loop

## Trabalho

- [ ] 3.1 Converter as observações do Billing em consulta ao banco
- [ ] 3.2 Nomear a unicidade do token de convite
- [x] 2.9 Já feito antes do loop
"""

FILA_ZERADA = """# Fila do loop

- [x] 1.1 tudo feito
- [x] 1.2 tudo feito
"""

COM_HOOK = {"hooks": {"Stop": [
    {"matcher": "", "hooks": [{"type": "command", "command": "outro/stop.sh"}]},
    {"matcher": "", "hooks": [{"type": "command",
                               "command": "python3 /x/skill/loop/hooks/loop-stop.py"}]},
]}}
SEM_HOOK = {"hooks": {"Stop": [
    {"matcher": "", "hooks": [{"type": "command", "command": "outro/stop.sh"}]},
]}}


class Res(object):
    """O bastante de um resultado de classificação para as duas últimas
    condições da cadeia — que são as únicas que dependem da mensagem."""

    def __init__(self, kind="DOC", sinal="relato"):
        self.kind, self.sinal = kind, sinal


def janela_fechada_agora():
    """Uma janela de um minuto, meia hora à frente: fechada agora, sempre.

    Janela literal ("08:00-18:00") faria o teste passar ou falhar conforme a
    hora em que a suíte roda — o tipo de teste que mente uma vez por dia.
    """
    daqui = datetime.now() + timedelta(minutes=30)
    fim = daqui + timedelta(minutes=1)
    return "%02d:%02d-%02d:%02d" % (daqui.hour, daqui.minute, fim.hour, fim.minute)


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-diag-")
        self.loop = Loop(self.tmp)
        os.makedirs(self.loop.entries)
        self.fila(FILA)
        self.sessao = "sessao-de-teste"
        self.settings = os.path.join(self.tmp, "settings.json")
        self.escrever_settings(COM_HOOK)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── helpers ─────────────────────────────────────────────────────────────
    def fila(self, texto):
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(texto)

    def escrever_settings(self, dados):
        with open(self.settings, "w", encoding="utf-8") as f:
            json.dump(dados, f)

    def armar(self, **kw):
        cfg = dict(objetivo="terminar a fase 3", session_id=self.sessao,
                   max_iteracoes=50, max_sem_progresso=3)
        cfg.update(kw)
        return self.loop.iniciar(**cfg)

    def portoes(self, sid=None, loop=None):
        alvo = loop or self.loop
        return portoes_de_inercia(alvo, alvo.ler() if alvo.existe else None,
                                  sid=sid, settings=self.settings)

    def barrado(self, sid=None, loop=None):
        """Nome do portão que barra, ou `None` se nenhum barra."""
        for p in self.portoes(sid=sid, loop=loop):
            if p.ok is False:
                return p.nome
        return None

    def fim(self, **kw):
        return condicoes_de_fim(self.loop, self.loop.ler(), **kw)


# ── o hook está instalado? ──────────────────────────────────────────────────
class TestHookInstalado(Base):

    def test_encontra_em_qualquer_grupo_do_stop(self):
        instalado, caminho = hook_instalado(self.settings)
        self.assertIs(instalado, True)
        self.assertEqual(caminho, self.settings)

    def test_stop_sem_o_loop_e_ausencia(self):
        self.escrever_settings(SEM_HOOK)
        self.assertIs(hook_instalado(self.settings)[0], False)

    def test_sem_hooks_nenhum_e_ausencia(self):
        self.escrever_settings({"model": "opus"})
        self.assertIs(hook_instalado(self.settings)[0], False)

    def test_arquivo_ausente_nao_e_ausencia_do_hook(self):
        # `None` e `False` são fatos diferentes: não ter lido não é ter medido
        # que não existe. Mutação: devolver False aqui e o diagnóstico passa a
        # acusar hook desinstalado em máquina onde ele está instalado.
        instalado, _ = hook_instalado(os.path.join(self.tmp, "nao-existe.json"))
        self.assertIsNone(instalado)

    def test_json_quebrado_nao_inventa_veredito(self):
        with open(self.settings, "w", encoding="utf-8") as f:
            f.write("{isto não é json")
        self.assertIsNone(hook_instalado(self.settings)[0])

    def test_lista_no_lugar_de_objeto(self):
        self.escrever_settings([1, 2, 3])
        self.assertIsNone(hook_instalado(self.settings)[0])

    def test_honra_claude_settings_do_ambiente(self):
        # É este caminho que mantém a suíte fora do settings real da máquina.
        antes = os.environ.get("CLAUDE_SETTINGS")
        os.environ["CLAUDE_SETTINGS"] = self.settings
        try:
            self.assertIs(hook_instalado()[0], True)
        finally:
            if antes is None:
                del os.environ["CLAUDE_SETTINGS"]
            else:
                os.environ["CLAUDE_SETTINGS"] = antes


# ── portões de inércia ──────────────────────────────────────────────────────
class TestPortoes(Base):

    def test_hook_desinstalado_barra_antes_de_tudo(self):
        self.escrever_settings(SEM_HOOK)
        self.armar()
        portoes = self.portoes(sid=self.sessao)
        self.assertEqual(portoes[0].nome, "hook instalado")
        self.assertIs(portoes[0].ok, False)
        # Sem hook, o resto é inalcançável — e listar como testado seria mentira.
        self.assertEqual(len(portoes), 1)

    def test_settings_ilegivel_nao_barra(self):
        # Fail-open também no diagnóstico: não conseguir ler o settings não pode
        # virar veredito de que o loop está quebrado.
        os.remove(self.settings)
        self.armar()
        self.assertIsNone(self.barrado(sid=self.sessao))

    def test_sem_state_barra_no_loop(self):
        vazio = Loop(tempfile.mkdtemp(prefix="loop-vazio-"))
        try:
            self.assertEqual(self.barrado(loop=vazio), ".loop/")
        finally:
            shutil.rmtree(vazio.raiz, ignore_errors=True)

    def test_state_ilegivel_barra_com_nome_proprio(self):
        self.armar()
        with open(self.loop.p("STATE.json"), "w", encoding="utf-8") as f:
            f.write("{quebrado")
        self.assertEqual(self.barrado(sid=self.sessao), "STATE.json")

    def test_inativo_barra_e_diz_por_que_encerrou(self):
        st = self.armar()
        st.update(ativo=False, encerrado_por="fila zerada",
                  encerrado_em="2026-08-16T21:19:22-03:00")
        self.loop.gravar(st)
        portao = [p for p in self.portoes(sid=self.sessao) if p.ok is False][0]
        self.assertEqual(portao.nome, "ativo")
        self.assertIn("fila zerada", portao.detalhe)
        self.assertIn("2026-08-16", portao.detalhe)
        self.assertIn("retomar", portao.conserto)

    def test_para_no_primeiro_portao_fechado(self):
        st = self.armar()
        st["ativo"] = False
        self.loop.gravar(st)
        nomes = [p.nome for p in self.portoes(sid="outra-sessao")]
        self.assertIn("ativo", nomes)
        # A sessão também está errada, mas o hook nunca chega lá.
        self.assertNotIn("amarração", nomes)
        self.assertNotIn("fase", nomes)

    def test_fase_encerrando_barra(self):
        st = self.armar()
        st["fase"] = "encerrando"
        self.loop.gravar(st)
        portao = [p for p in self.portoes(sid=self.sessao) if p.ok is False][0]
        self.assertEqual(portao.nome, "fase")

    def test_sessao_diferente_barra(self):
        self.armar()
        self.assertEqual(self.barrado(sid="outra-sessao"), "amarração")

    def test_ids_com_prefixo_igual_saem_inteiros(self):
        # Encurtar dois ids diferentes para a mesma coisa produz "preso a X;
        # esta é X" — mensagem ilegível justamente para quem já está no escuro.
        self.armar(session_id="a-sessao-de-ontem")
        portao = [p for p in self.portoes(sid="a-sessao-de-hoje")
                  if p.nome == "amarração"][0]
        self.assertIn("a-sessao-de-ontem", portao.detalhe)
        self.assertIn("a-sessao-de-hoje", portao.detalhe)

    def test_ids_bem_diferentes_saem_encurtados(self):
        self.armar(session_id="6bd4ebd5-599f-4ccc-9e8a-a6e0933daf46")
        portao = [p for p in self.portoes(sid="5dca3e33-817c-42ec-8ff8-f50f5d17bb27")
                  if p.nome == "amarração"][0]
        self.assertIn("6bd4ebd5…", portao.detalhe)
        self.assertIn("5dca3e33…", portao.detalhe)

    def test_sessao_igual_passa(self):
        self.armar()
        self.assertIsNone(self.barrado(sid=self.sessao))

    def test_sem_sid_a_amarracao_e_informativa_nao_veredito(self):
        # O session_id de hoje é dado da sessão viva. Adivinhá-lo pelo mtime dos
        # transcripts é o caminho que o ADR-008 descartou — então sem `--sessao`
        # o portão informa o fato e não julga.
        self.armar()
        amarracao = [p for p in self.portoes() if p.nome == "amarração"][0]
        self.assertIsNone(amarracao.ok)
        self.assertIn("sessão", amarracao.detalhe)
        self.assertIsNone(self.barrado())

    def test_bind_desligado_passa_com_qualquer_sessao(self):
        self.armar(bind_session=False)
        self.assertIsNone(self.barrado(sid="qualquer-uma"))

    def test_session_id_nulo_passa_porque_a_primeira_parada_amarra(self):
        self.armar(session_id=None)
        amarracao = [p for p in self.portoes(sid="a-que-armou")
                     if p.nome == "amarração"][0]
        self.assertIs(amarracao.ok, True)


# ── o espelho não pode desalinhar do hook ───────────────────────────────────
class TestEspelhoDoHook(Base):
    """Silêncio do hook ⇄ portão nomeado pelo espelho.

    `portoes_de_inercia` não é a fonte: o hook *muta* estado em dois destes
    portões (consome `fase: encerrando`, auto-amarra a sessão) e mutação não cabe
    num diagnóstico. O preço de ser espelho é este teste — cada estado vai aos
    dois, e a divergência quebra aqui, não na próxima parada silenciosa.
    """

    def transcript(self):
        caminho = os.path.join(self.tmp, "transcript.jsonl")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "isSidechain": False,
                                "message": {"content": [{
                                    "type": "text",
                                    "text": "Migrei o schema e rodei a suíte. "
                                            "212 testes, 0 falhas."}]}}) + "\n")
        return caminho

    def rodar(self, sessao, cwd=None):
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"session_id": sessao,
                              "transcript_path": self.transcript(),
                              "cwd": cwd or self.tmp,
                              "hook_event_name": "Stop",
                              "stop_hook_active": False}),
            capture_output=True, text=True, timeout=30)
        return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else None)

    def test_silencio_do_hook_tem_nome_no_espelho(self):
        def inativo():
            st = self.armar()
            st["ativo"] = False
            self.loop.gravar(st)
            return self.sessao, None, "ativo"

        def encerrando():
            st = self.armar()
            st["fase"] = "encerrando"
            self.loop.gravar(st)
            return self.sessao, None, "fase"

        def outra_sessao():
            self.armar()
            return "uma-sessao-que-nao-armou", None, "amarração"

        def sem_loop():
            self.armar()
            return self.sessao, tempfile.mkdtemp(prefix="loop-vazio-"), ".loop/"

        for preparar in (inativo, encerrando, outra_sessao, sem_loop):
            with self.subTest(preparar.__name__):
                shutil.rmtree(self.loop.dir, ignore_errors=True)
                os.makedirs(self.loop.entries)
                self.fila(FILA)
                sessao, cwd, esperado = preparar()
                alvo = Loop(cwd) if cwd else self.loop
                # Espelho ANTES do hook: o hook muta estado em dois destes
                # portões, e depois da mutação o estado já não é o que barrou.
                nome = self.barrado(sid=sessao, loop=alvo)
                rc, saida = self.rodar(sessao, cwd=cwd)
                if cwd:
                    shutil.rmtree(cwd, ignore_errors=True)
                self.assertEqual(rc, 0)
                self.assertIsNone(saida, "o hook falou onde devia calar")
                self.assertEqual(nome, esperado)

    def test_quando_nada_barra_o_hook_fala(self):
        # A direção que pega espelho otimista: se `portoes_de_inercia` disser
        # "passou" para estado em que o hook cala, o par acima quebra; se disser
        # "barrou" para estado em que o hook trabalha, quebra aqui.
        self.armar()
        self.assertIsNone(self.barrado(sid=self.sessao))
        _, saida = self.rodar(self.sessao)
        self.assertEqual(saida["decision"], "block")


# ── condições de fim: a cadeia, e quem ganha de quem ────────────────────────
class TestCondicoesDeFim(Base):

    def test_nada_barra_com_fila_e_estado_novos(self):
        self.armar()
        self.assertIsNone(self.fim())

    def test_kill_switch_ganha_de_todas(self):
        self.armar()
        self.fila(FILA_ZERADA)
        open(self.loop.p("STOP"), "w").close()
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "kill-switch")
        self.assertIn("STOP", detalhe)

    def test_teto_de_iteracoes_e_estritamente_maior(self):
        self.armar(max_iteracoes=50)
        self.assertIsNone(self.fim(iteracao=50))
        self.assertEqual(self.fim(iteracao=51)[0], "teto de iterações")

    def test_sem_progresso_no_limite_encerra(self):
        st = self.armar(max_sem_progresso=3)
        st["sem_progresso"] = 3
        self.loop.gravar(st)
        self.assertEqual(self.fim()[0], "sem progresso")

    def test_fila_zerada_conta_os_feitos(self):
        self.armar()
        self.fila(FILA_ZERADA)
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "fila zerada")
        self.assertIn("2", detalhe)

    def test_fila_zerada_sai_da_cadeia_quando_ha_relogio(self):
        # ADR-015. O relógio é a razão de a rodada existir; a fila é rascunho.
        # Mutação: tirar o `and not tem_relogio(st)` e a cadeia volta a encerrar
        # aqui — com horas sobrando, que é o defeito medido no EOP.
        self.armar(duracao_max_min=360)
        self.fila(FILA_ZERADA)
        self.assertIsNone(self.fim())

    def test_veredito_de_escopo_esgotado_encerra_e_leva_a_primeira_linha(self):
        self.armar(duracao_max_min=360)
        self.fila(FILA_ZERADA)
        with open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8") as f:
            f.write("\n\nNada em escopo: 7 hipóteses, 3 mediram zero.\ndetalhe\n")
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "escopo esgotado")
        self.assertEqual(detalhe, "Nada em escopo: 7 hipóteses, 3 mediram zero.")

    def test_veredito_vazio_nao_inventa_medicao(self):
        # Arquivo tocado sem texto ainda encerra — é ordem —, mas o detalhe não
        # pode fingir que houve medição escrita.
        self.armar(duracao_max_min=360)
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "escopo esgotado")
        self.assertIn("não escrito", detalhe)

    def test_sem_progresso_vence_o_veredito(self):
        # A ordem importa: o teto de degeneração manda em tudo que o agente
        # escreve, inclusive no veredito dele.
        st = self.armar(duracao_max_min=360, max_sem_progresso=3)
        st["sem_progresso"] = 3
        self.loop.gravar(st)
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        self.assertEqual(self.fim()[0], "sem progresso")

    def test_fora_da_janela(self):
        self.armar(janela=janela_fechada_agora())
        self.assertEqual(self.fim()[0], "fora da janela de trabalho")

    def test_relogio_estourado(self):
        st = self.armar(duracao_max_min=60)
        st["armado_em"] = (datetime.now().astimezone()
                           - timedelta(hours=2)).isoformat(timespec="seconds")
        self.loop.gravar(st)
        self.assertEqual(self.fim()[0], "duração máxima")

    def test_escopo_por_itens_conta_so_a_rodada(self):
        # A fila tem 1 feito de antes de armar, e é esse o denominador: sem ele,
        # trabalho de rodada anterior fecharia o escopo na primeira parada.
        # Fila sempre com pendente sobrando — senão "fila zerada" responde antes,
        # que é a ordem certa do hook e não o que este teste mede.
        self.armar(escopo_itens=2)
        self.fila(FILA.replace("- [ ] 3.2", "- [x] 3.2"))     # 2 feitos: 1 da rodada
        self.assertIsNone(self.fim())
        self.fila(FILA.replace("- [ ] 3.2", "- [x] 3.2")
                      + "- [x] 3.3 mais um da rodada\n- [ ] 3.4 ainda pendente\n")
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "escopo concluído")
        self.assertIn("2 item", detalhe)

    def test_escopo_por_marcador(self):
        self.armar(escopo_ate="unicidade do token")
        self.fila(FILA.replace("- [ ] 3.2", "- [x] 3.2"))
        motivo, detalhe = self.fim()
        self.assertEqual(motivo, "escopo concluído")
        self.assertIn("marcador", detalhe)

    def test_politica_ask_parar(self):
        self.armar(politica_ask="parar")
        self.assertEqual(self.fim(res=Res("ASK", "pergunta"))[0],
                         "política ASK=parar")
        self.assertIsNone(self.fim(res=Res("DOC")))

    def test_acao_irreversivel_so_com_a_politica_certa(self):
        self.armar(politica_ask="continuar-exceto-irreversivel")
        gatilhos = lambda t: ["drop table"] if "drop table" in (t or "") else []  # noqa: E731
        self.assertEqual(
            self.fim(res=Res("ASK", "pergunta"), texto="posso drop table x?",
                     irreversivel=gatilhos)[0], "ação irreversível")
        self.assertIsNone(self.fim(res=Res("ASK", "pergunta"),
                                   texto="posso seguir?", irreversivel=gatilhos))

    def test_sem_classificacao_as_duas_ultimas_saem_de_cena(self):
        # É o modo em que `porque` roda: não há mensagem para classificar, e
        # inventar veredito de ASK ali seria diagnóstico com opinião.
        self.armar(politica_ask="parar")
        self.assertIsNone(self.fim())

    def test_contagem_recebida_vence_a_do_disco(self):
        # O hook conta a fila DEPOIS da colheita; recontar aqui daria o número
        # de antes, e a condição de fila zerada erraria a rodada inteira.
        self.armar()
        self.assertEqual(condicoes_de_fim(self.loop, self.loop.ler(),
                                          contagem=(0, 9))[0], "fila zerada")


# ── o comando ───────────────────────────────────────────────────────────────
class TestComandoPorque(Base):

    def ctl(self, *args):
        proc = subprocess.run([sys.executable, CTL] + list(args),
                              capture_output=True, text=True, timeout=30,
                              env=dict(os.environ, CLAUDE_SETTINGS=self.settings))
        return proc.returncode, proc.stdout + proc.stderr

    def test_loop_parado_sai_1_e_nomeia_o_portao(self):
        st = self.armar()
        st.update(ativo=False, encerrado_por="fila zerada")
        self.loop.gravar(st)
        rc, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("ativo", saida)
        self.assertIn("continua", saida)     # o "continua" digitado não reativa

    def test_resumo_fim_por_segue_a_ordem_da_cadeia(self):
        # O `fim por` do status prometia "na ordem em que o hook as testa" e
        # entregava outra — escopo primeiro, iterações por último. Resumo que
        # promete ordem e entrega outra é pior que resumo sem ordem: quem lê tira
        # conclusão de qual bate antes. Mutação: reordenar e esta cai.
        st = self.armar()
        st.update(janela="08:00-18:00", duracao_max_min=360, escopo_itens=5)
        self.loop.gravar(st)
        _, saida = self.ctl("status", "--raiz", self.tmp)
        linha = [l for l in saida.split("\n") if l.startswith("fim por")][0]
        # `escopo esgotado` no lugar de `fila zerada` porque a rodada tem relógio
        # (ADR-015): sob relógio a fila não fecha a rodada, o veredito escrito
        # fecha — e o resumo não pode listar um fim que a cadeia não cumpre.
        posicoes = [linha.index(t) for t in
                    ("iterações", "escopo esgotado", "fora de", "de relógio",
                     "itens desta rodada")]
        self.assertEqual(posicoes, sorted(posicoes))
        self.assertNotIn("fila zerada", linha)

    def test_resumo_fim_por_sem_relogio_ainda_lista_a_fila(self):
        # A rodada por itens não mudou: sem relógio, fila zerada é o critério de
        # pronto do ciclo (ADR-006) e continua no resumo.
        self.armar()
        _, saida = self.ctl("status", "--raiz", self.tmp)
        linha = [l for l in saida.split("\n") if l.startswith("fim por")][0]
        self.assertIn("fila zerada", linha)
        self.assertNotIn("escopo esgotado", linha)

    def test_raiz_aceita_antes_e_depois_do_subcomando(self):
        # A ordem natural é depois, e era erro de uso — no comando que existe
        # justamente para socorrer quem está no escuro.
        self.armar()
        depois = self.ctl("porque", "--raiz", self.tmp)
        antes = self.ctl("--raiz", self.tmp, "porque")
        self.assertEqual(depois[0], 0)
        self.assertEqual(antes[0], 0)
        self.assertIn("Nada barra", depois[1])
        self.assertIn("Nada barra", antes[1])

    def test_loop_saudavel_sai_0_e_diz_o_proximo(self):
        self.armar()
        rc, saida = self.ctl("porque", "--raiz", self.tmp, "--sessao", self.sessao)
        self.assertEqual(rc, 0)
        self.assertIn("Nada barra", saida)
        self.assertIn("Billing", saida)

    def test_sessao_diferente_sai_1(self):
        self.armar()
        rc, saida = self.ctl("porque", "--raiz", self.tmp, "--sessao", "outra")
        self.assertEqual(rc, 1)
        self.assertIn("amarração", saida)

    def test_condicao_de_fim_com_o_conserto_da_condicao(self):
        self.armar()
        open(self.loop.p("STOP"), "w").close()
        rc, saida = self.ctl("porque", "--raiz", self.tmp, "--sessao", self.sessao)
        self.assertEqual(rc, 1)
        self.assertIn("kill-switch", saida)
        self.assertIn("rm ", saida)

    def test_fila_vazia_aparece_mesmo_com_o_loop_parado(self):
        # Reativar não conserta fila vazia: quem só lê "retomar" tenta, dura um
        # turno, e volta ao escuro. Sem relógio, porque com relógio a fila vazia
        # deixou de ser problema — ela vira reabastecimento (ADR-015).
        st = self.armar()
        st["ativo"] = False
        self.loop.gravar(st)
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("fila vazia", saida)

    def test_relogio_estourado_aparece_mesmo_com_o_loop_parado(self):
        # O outro fato que reativar não conserta, e que decide o verbo: `retomar`
        # não devolve relógio, só `armar` começa rodada nova.
        st = self.armar(duracao_max_min=60)
        st["ativo"] = False
        st["armado_em"] = (datetime.now().astimezone()
                           - timedelta(hours=2)).isoformat(timespec="seconds")
        self.loop.gravar(st)
        rc, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("relógio", saida)
        self.assertIn("armar", saida)

    def test_fila_vazia_com_relogio_nao_e_mais_aviso(self):
        # O aviso mandava preencher a fila antes de continuar — conselho errado
        # sob relógio, onde a primeira parada é justamente o turno que a preenche.
        # Mutação: tirar o `not tem_relogio(st)` do aviso e esta cai.
        st = self.armar(duracao_max_min=360)
        st["ativo"] = False
        self.loop.gravar(st)
        self.fila(FILA_ZERADA)
        _, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertNotIn("fila vazia", saida)

    def test_veredito_de_escopo_esgotado_vira_aviso_de_rearme(self):
        # `.loop/SEM-ESCOPO` de uma rodada anterior encerraria a próxima na
        # primeira parada citando medição velha. `armar` o apaga; `retomar` não —
        # então `porque` precisa dizer que ele está lá.
        st = self.armar(duracao_max_min=360)
        st["ativo"] = False
        self.loop.gravar(st)
        with open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8") as f:
            f.write("varri os 12 volumes: nenhum bloco fora de escopo declarado\n")
        rc, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("SEM-ESCOPO", saida)

    def test_porque_anuncia_reabastecimento_em_vez_de_continuar_para_nada(self):
        # "continua para '—'" é a resposta certa para a pergunta errada: com fila
        # vazia e relógio de pé, a próxima parada tem trabalho, e é outro trabalho.
        self.armar(duracao_max_min=360)
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("porque", "--raiz", self.tmp)
        self.assertEqual(rc, 0)
        self.assertIn("reabastecimento", saida)
        self.assertNotIn("continua para '—'", saida)
        self.assertIn("sem .loop/SCOPE.md", saida)

    def test_alias_diagnostico(self):
        self.armar()
        self.assertEqual(self.ctl("diagnostico", "--raiz", self.tmp)[0], 0)


class TestComandoRetomar(Base):

    def ctl(self, *args):
        proc = subprocess.run([sys.executable, CTL] + list(args),
                              capture_output=True, text=True, timeout=30,
                              env=dict(os.environ, CLAUDE_SETTINGS=self.settings))
        return proc.returncode, proc.stdout + proc.stderr

    def rodar_hook(self, sessao):
        caminho = os.path.join(self.tmp, "t.jsonl")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "assistant", "isSidechain": False,
                                "message": {"content": [{"type": "text",
                                                         "text": "Rodei a suíte: 0 falhas."}]}}) + "\n")
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"session_id": sessao, "transcript_path": caminho,
                              "cwd": self.tmp, "hook_event_name": "Stop",
                              "stop_hook_active": False}),
            capture_output=True, text=True, timeout=30)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_retomar_re_amarra_e_a_sessao_nova_dirige(self):
        # O teste de ponta a ponta do defeito de 17/08: retomar no dia seguinte,
        # de outra sessão. Mutação: voltar a `if args.sessao:` e o hook cala.
        st = self.armar(session_id="a-sessao-de-ontem")
        st.update(ativo=False, encerrado_por="fila zerada")
        self.loop.gravar(st)
        rc, saida = self.ctl("retomar", "--raiz", self.tmp)
        self.assertEqual(rc, 0)
        self.assertIsNone(self.loop.ler()["session_id"])
        self.assertIn("primeira que parar", saida)
        resposta = self.rodar_hook("a-sessao-de-hoje")
        self.assertEqual(resposta["decision"], "block")
        self.assertEqual(self.loop.ler()["session_id"], "a-sessao-de-hoje")

    def test_retomar_com_sessao_explicita_ainda_grava(self):
        self.armar(session_id="antiga")
        self.ctl("retomar", "--raiz", self.tmp, "--sessao", "escolhida-a-mao")
        self.assertEqual(self.loop.ler()["session_id"], "escolhida-a-mao")

    def test_retomar_reativa_e_zera_o_sem_progresso(self):
        st = self.armar()
        st.update(ativo=False, fase="encerrando", sem_progresso=3,
                  encerrado_por="sem progresso")
        self.loop.gravar(st)
        self.ctl("retomar", "--raiz", self.tmp)
        depois = self.loop.ler()
        self.assertTrue(depois["ativo"])
        self.assertEqual(depois["fase"], "rodando")
        self.assertEqual(depois["sem_progresso"], 0)
        self.assertIsNone(depois["encerrado_por"])

    def test_retomar_recusa_fila_vazia_e_nao_reativa(self):
        # Era aviso e virou recusa: o aviso existia em 17/08 e não impediu as
        # três rodadas mortas do EOP. Recusa que deixa o estado ativo seria o
        # mesmo aviso com outra cara — então o teste olha o disco, não a saída.
        st = self.armar()
        st["ativo"] = False
        self.loop.gravar(st)
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("retomar", "--raiz", self.tmp)
        self.assertEqual(rc, 2)
        self.assertIn("morre na primeira parada", saida)
        self.assertFalse(self.loop.ler()["ativo"])

    def test_retomar_com_mesmo_sem_fila_passa_e_avisa(self):
        self.armar()
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("retomar", "--raiz", self.tmp, "--mesmo-sem-fila")
        self.assertEqual(rc, 0)
        self.assertIn("fila vazia", saida)
        self.assertTrue(self.loop.ler()["ativo"])

    def test_retomar_avisa_relogio_estourado_e_manda_armar(self):
        st = self.armar(duracao_max_min=60)
        st["armado_em"] = (datetime.now().astimezone()
                           - timedelta(hours=2)).isoformat(timespec="seconds")
        self.loop.gravar(st)
        _, saida = self.ctl("retomar", "--raiz", self.tmp)
        self.assertIn("relógio", saida)
        self.assertIn("armar", saida)

    def test_retomar_apaga_o_kill_switch(self):
        self.armar()
        open(self.loop.p("STOP"), "w").close()
        self.ctl("retomar", "--raiz", self.tmp)
        self.assertFalse(self.loop.kill_switch)


class TestArmarSemFila(Base):
    """Armar com zero pendentes é rodada provadamente morta (#20/#21/#22 do EOP)."""

    def ctl(self, *args):
        # A escolha de sessão entrou como guarda de porta no `0.2.6`, e um
        # `armar` sem nenhuma das três flags passa a ser recusado antes de
        # chegar onde estes testes olham. Estes aqui são sobre a FILA: pedir a
        # adoção de propósito mantém cada um medindo o que foi escrito para
        # medir. A guarda de sessão tem os testes dela em `test_ciclo.py`.
        args = list(args)
        if args and args[0] == "armar" and not any(
                a in args for a in ("--sessao", "--qualquer-sessao",
                                    "--adotar-primeira-parada")):
            args.append("--adotar-primeira-parada")
        proc = subprocess.run([sys.executable, CTL] + args,
                              capture_output=True, text=True, timeout=30,
                              env=dict(os.environ, CLAUDE_SETTINGS=self.settings))
        return proc.returncode, proc.stdout + proc.stderr

    def test_recusa_e_nao_grava_estado(self):
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("armar", "--raiz", self.tmp, "--objetivo", "x")
        self.assertEqual(rc, 2)
        self.assertIn("morre na primeira parada", saida)
        self.assertFalse(self.loop.existe)

    def test_recusa_nao_apaga_o_kill_switch(self):
        # Comando que recusa não pode deixar efeito atrás: apagar o `.loop/STOP`
        # e então abortar desarmaria a única trava que o dono aciona sem terminal.
        self.armar()
        self.fila(FILA_ZERADA)
        open(self.loop.p("STOP"), "w").close()
        rc, _ = self.ctl("armar", "--raiz", self.tmp)
        self.assertEqual(rc, 2)
        self.assertTrue(self.loop.kill_switch)

    def test_mesmo_sem_fila_arma_e_avisa(self):
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("armar", "--raiz", self.tmp, "--mesmo-sem-fila")
        self.assertEqual(rc, 0)
        self.assertIn("--mesmo-sem-fila", saida)
        self.assertTrue(self.loop.ler()["ativo"])

    def test_duracao_arma_sobre_fila_vazia(self):
        # O comando que a guarda passou a barrar por engano — `armar --duracao 6h`
        # sobre fila 66/66, que é exatamente o uso do dono. Sob relógio a fila
        # vazia não encerra (ADR-015), então recusar ali é barrar o caminho certo.
        # Mutação: tirar o `_com_relogio(args)` da guarda e esta cai.
        self.fila(FILA_ZERADA)
        rc, saida = self.ctl("armar", "--raiz", self.tmp, "--duracao", "6h",
                             "--objetivo", "modelar a Onda 2")
        self.assertEqual(rc, 0)
        self.assertIn("reabastecimento", saida)
        self.assertTrue(self.loop.ler()["ativo"])

    def test_janela_tambem_arma_sobre_fila_vazia(self):
        self.fila(FILA_ZERADA)
        rc, _ = self.ctl("armar", "--raiz", self.tmp, "--janela", "08:00-18:00")
        self.assertEqual(rc, 0)

    def test_sem_scope_md_o_armar_avisa_de_onde_sai_o_escopo(self):
        # A fronteira do reabastecimento é decisão do dono (ADR-014 cláusula 1).
        # Se ela não existe, ele precisa saber disso na hora de armar — não na
        # primeira parada, quando o turno já começou a escolher trabalho.
        self.fila(FILA_ZERADA)
        _, saida = self.ctl("armar", "--raiz", self.tmp, "--duracao", "6h")
        self.assertIn("SCOPE.md", saida)

    def test_armar_apaga_veredito_da_rodada_anterior(self):
        # Veredito velho em disco encerraria a rodada nova na primeira parada,
        # citando medição de outra rodada.
        self.fila(FILA_ZERADA)
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        rc, _ = self.ctl("armar", "--raiz", self.tmp, "--duracao", "6h")
        self.assertEqual(rc, 0)
        self.assertFalse(self.loop.sem_escopo)

    def test_recusa_nao_apaga_o_veredito(self):
        # Mesmo princípio do kill-switch: comando que recusa não deixa efeito.
        self.fila(FILA_ZERADA)
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        rc, _ = self.ctl("armar", "--raiz", self.tmp)      # sem relógio → recusa
        self.assertEqual(rc, 2)
        self.assertTrue(self.loop.sem_escopo)

    def test_loop_novo_ainda_arma_pelo_esqueleto(self):
        # `.loop/` que nasce agora recebe o esqueleto com um `- [ ]`; a guarda não
        # pode transformar o primeiro uso do produto em erro.
        novo = tempfile.mkdtemp(prefix="loop-novo-")
        try:
            rc, saida = self.ctl("armar", "--raiz", novo, "--objetivo", "primeira vez")
            self.assertEqual(rc, 0)
            self.assertIn("loop armado", saida)
        finally:
            shutil.rmtree(novo, ignore_errors=True)

    def test_fila_com_pendente_passa(self):
        rc, _ = self.ctl("armar", "--raiz", self.tmp, "--objetivo", "fase 3")
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
