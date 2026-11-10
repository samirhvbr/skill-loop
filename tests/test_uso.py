#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measured token use (ADR-020): the meter reads the transcript, honestly.

The cases here are the three ways a first meter lies, each measured on a real
session before this was written: lines counted instead of messages (about 3×
too many), subagents left out, and a re-read of the whole file at every stop.
Each test fails with its control switched off; the mutations are in ADR-020.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ciclo import CTL, DOC, Base   # noqa: E402

import uso   # noqa: E402
from estado import Loop   # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "loop_watch", os.path.join(RAIZ, "skill", "loop", "loop_watch.py"))
lw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lw)

ARMADO = "2026-11-04T10:00:00+00:00"


def u(i=0, o=0, cc=0, cr=0):
    return {"input_tokens": i, "output_tokens": o,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}


def msg(mid, usage, ts="2026-11-04T10:30:00.000Z", texto=None, lado=False):
    """One transcript line the way Claude Code writes it: one per content block."""
    bloco = ({"type": "text", "text": texto} if texto
             else {"type": "tool_use", "name": "Bash", "input": {}})
    return json.dumps({"type": "assistant", "isSidechain": lado,
                       "timestamp": ts, "requestId": "req-" + mid,
                       "message": {"id": mid, "content": [bloco], "usage": usage}})


def escrever(caminho, *linhas, fim="\n"):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + fim)


class BaseUso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-uso-")
        self.arq = os.path.join(self.tmp, "sessao.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def estado(self, **kw):
        st = {"armado_em": ARMADO}
        st.update(kw)
        return st


class TestMedidor(BaseUso):

    def test_a_mesma_mensagem_em_varias_linhas_conta_uma_vez(self):
        # The defect that makes the naive sum 3× too big: one JSONL line per
        # content block, same message.id, same usage on every one.
        escrever(self.arq, msg("m1", u(o=100)), msg("m1", u(o=100)),
                 msg("m1", u(o=100)), msg("m2", u(o=7)))
        st = self.estado()
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 107)
        self.assertEqual(delta["mensagens"], 2)

    def test_os_tres_componentes_ficam_separados(self):
        escrever(self.arq, msg("m1", u(i=3, o=10, cc=100, cr=1000)))
        delta = uso.atualizar(self.estado(), self.arq)
        self.assertEqual((delta["saida"], delta["entrada_nova"],
                          delta["cache_lido"]), (10, 103, 1000))

    def test_valor_que_nao_e_inteiro_positivo_vale_zero(self):
        escrever(self.arq, msg("m1", {"input_tokens": "9", "output_tokens": -4,
                                      "cache_read_input_tokens": None}))
        delta = uso.atualizar(self.estado(), self.arq)
        self.assertEqual((delta["saida"], delta["entrada_nova"],
                          delta["cache_lido"]), (0, 0, 0))

    def test_o_que_veio_antes_de_armar_nao_conta(self):
        escrever(self.arq,
                 msg("antes", u(o=900), ts="2026-11-04T09:59:00.000Z"),
                 msg("depois", u(o=5), ts="2026-11-04T10:01:00.000Z"))
        delta = uso.atualizar(self.estado(), self.arq)
        self.assertEqual(delta["saida"], 5)

    def test_leitura_incremental_so_le_o_que_chegou(self):
        escrever(self.arq, msg("m1", u(o=10)), msg("m2", u(o=20)))
        st = self.estado()
        uso.atualizar(st, self.arq)
        self.assertEqual(st["uso"]["saida"], 30)
        escrever(self.arq, msg("m3", u(o=5)))
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 5, "só a mensagem nova")
        self.assertEqual(st["uso"]["saida"], 35)
        self.assertEqual(st["uso"]["mensagens"], 3)
        delta = uso.atualizar(st, self.arq)
        self.assertEqual((delta["saida"], delta["mensagens"]), (0, 0),
                         "sem linha nova, nada a somar")
        self.assertEqual(st["uso"]["saida"], 35)

    def test_linha_ainda_sendo_escrita_fica_para_a_proxima_parada(self):
        # The hook fires while the harness may still be writing the last line.
        # Parsing half a JSON would drop it; consuming it would lose it for good.
        escrever(self.arq, msg("m1", u(o=10)))
        inteira = msg("m2", u(o=40))
        escrever(self.arq, inteira[:len(inteira) // 2], fim="")
        st = self.estado()
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 10)
        with open(self.arq, "a", encoding="utf-8") as f:
            f.write(inteira[len(inteira) // 2:] + "\n")
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 40, "a linha completa é contada uma vez")
        self.assertEqual(st["uso"]["saida"], 50)

    def test_mensagem_partida_entre_duas_varreduras_conta_uma_vez(self):
        # Another content block of a message already counted arrives after the
        # stop. The ids of the last chunk are kept for exactly this.
        escrever(self.arq, msg("m1", u(o=100)))
        st = self.estado()
        uso.atualizar(st, self.arq)
        escrever(self.arq, msg("m1", u(o=100)))
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 0)
        self.assertEqual(st["uso"]["saida"], 100)

    def test_subagentes_entram_na_conta(self):
        # Their tokens are NOT in the main transcript: they live in
        # `<session>/subagents/agent-*.jsonl`. Without them the meter undercounts
        # exactly the loops that spend the most.
        escrever(self.arq, msg("main", u(o=10)))
        sub = os.path.join(self.tmp, "sessao", "subagents", "agent-a.jsonl")
        escrever(sub, msg("s1", u(o=300), lado=True),
                 msg("s1", u(o=300), lado=True), msg("s2", u(o=50), lado=True))
        delta = uso.atualizar(self.estado(), self.arq)
        self.assertEqual(delta["saida"], 360)
        self.assertEqual(delta["mensagens"], 3)

    def test_subagente_parado_antes_de_armar_nem_e_aberto(self):
        sub = os.path.join(self.tmp, "sessao", "subagents", "agent-velho.jsonl")
        escrever(sub, msg("v1", u(o=999), ts="2026-11-04T10:30:00.000Z", lado=True))
        antigo = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc).timestamp()
        os.utime(sub, (antigo, antigo))
        escrever(self.arq, msg("main", u(o=1)))
        st = self.estado()
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 1,
                         "arquivo sem escrita desde o armar não pode ter linha da rodada")
        self.assertNotIn("agent-velho.jsonl", st["uso_offsets"])

    def test_arquivo_que_encolheu_nao_e_recontado(self):
        escrever(self.arq, msg("m1", u(o=100)), msg("m2", u(o=100)))
        st = self.estado()
        uso.atualizar(st, self.arq)
        with open(self.arq, "w", encoding="utf-8") as f:   # rewritten, shorter
            f.write(msg("m9", u(o=1)) + "\n")
        delta = uso.atualizar(st, self.arq)
        self.assertEqual(delta["saida"], 0)
        self.assertTrue(st["uso"]["parcial"])
        self.assertEqual(st["uso"]["saida"], 200)

    def test_transcript_maior_que_a_janela_marca_parcial(self):
        escrever(self.arq, *[msg("m%d" % i, u(o=1)) for i in range(200)])
        antigo, uso.MAX_VARREDURA = uso.MAX_VARREDURA, 2000
        try:
            st = self.estado()
            delta = uso.atualizar(st, self.arq)
        finally:
            uso.MAX_VARREDURA = antigo
        self.assertTrue(st["uso"]["parcial"])
        self.assertTrue(0 < delta["mensagens"] < 200,
                        "só a cauda, sem contar a linha partida da janela")

    def test_falha_nao_levanta_e_nao_mexe_no_estado(self):
        st = self.estado()
        antes = json.dumps(st, sort_keys=True)
        self.assertIsNone(uso.atualizar(st, os.path.join(self.tmp, "nao-existe")))
        self.assertIsNone(uso.atualizar(st, ""))
        self.assertIsNone(uso.atualizar(st, None))
        self.assertEqual(json.dumps(st, sort_keys=True), antes)

    def test_excecao_dentro_da_varredura_vira_none_e_nao_mexe_no_estado(self):
        # The fail-open contract (ADR-009), exercised where it matters: not the
        # missing-file shortcut, an exception RAISED while reading. And the
        # state is written only after every file was read, so a failure on the
        # second one must leave nothing from the first.
        escrever(self.arq, msg("m1", u(o=10)))
        sub = os.path.join(self.tmp, "sessao", "subagents", "agent-a.jsonl")
        escrever(sub, msg("s1", u(o=5), lado=True))
        real = uso.varrer_arquivo
        chamadas = []

        def falha_na_segunda(*a, **kw):
            chamadas.append(a[0])
            if len(chamadas) == 2:
                raise RuntimeError("disco sumiu")
            return real(*a, **kw)

        st = self.estado()
        antes = json.dumps(st, sort_keys=True)
        with mock.patch.object(uso, "varrer_arquivo", side_effect=falha_na_segunda):
            self.assertIsNone(uso.atualizar(st, self.arq))
        self.assertEqual(len(chamadas), 2, "o primeiro arquivo chegou a ser lido")
        self.assertEqual(json.dumps(st, sort_keys=True), antes)

    def test_lixo_no_arquivo_e_ignorado(self):
        escrever(self.arq, "{ isto nao e json \"usage\"", "[1,2,3]",
                 '{"type":"assistant","message":"texto","usage":1}',
                 msg("ok", u(o=8)))
        delta = uso.atualizar(self.estado(), self.arq)
        self.assertEqual(delta["saida"], 8)

    def test_estado_nao_compartilha_o_default_mutavel(self):
        # PADRAO carries `{}` and `[]` as defaults and `dict(PADRAO)` is shallow:
        # mutating in place would leak one round's cursor into the next.
        from estado import PADRAO
        st = dict(PADRAO)
        st["armado_em"] = ARMADO
        escrever(self.arq, msg("m1", u(o=1)))
        uso.atualizar(st, self.arq)
        self.assertEqual(PADRAO["uso_offsets"], {})
        self.assertEqual(PADRAO["uso_ids"], [])
        self.assertIsNone(PADRAO["uso"])


class TestApresentacao(unittest.TestCase):
    def test_humano_e_resumo(self):
        self.assertEqual(uso.humano(950), "950")
        self.assertEqual(uso.humano(98827), "98.8k")
        self.assertEqual(uso.humano(11369545), "11.4M")
        self.assertEqual(uso.resumo({"saida": 98827, "entrada_nova": 492254,
                                     "cache_lido": 11369545}),
                         "saída 98.8k · entrada nova 492.3k · cache lido 11.4M")


class TestNoHook(Base):
    """The meter inside the hook: credited per stop, per item, in the state."""

    def setUp(self):
        super().setUp()
        self.arq = os.path.join(self.tmp, "transcript-uso.jsonl")

    def agora(self, minutos=1):
        return (datetime.now(timezone.utc) + timedelta(minutes=minutos)
                ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def turno(self, mid, saida, texto=DOC):
        """A closed turn: the agent's report, carrying this turn's usage."""
        escrever(self.arq,
                 json.dumps({"type": "user", "message": {"role": "user",
                                                         "content": "vai"}}),
                 msg(mid, u(i=2, o=saida, cc=10, cr=100), ts=self.agora(),
                     texto=texto))

    def parar(self):
        return self.rodar(bruto={
            "session_id": self.sessao, "transcript_path": self.arq,
            "cwd": self.tmp, "hook_event_name": "Stop",
            "stop_hook_active": False})

    def armar(self, **kw):
        kw.setdefault("max_sem_progresso", 99)
        kw.setdefault("colher_itens", False)
        return super().armar(**kw)

    def test_a_parada_grava_o_uso_no_estado_e_na_entry(self):
        self.armar()
        self.turno("m1", 500)
        self.parar()
        st = self.loop.ler()
        self.assertEqual(st["uso"]["saida"], 500)
        self.assertEqual(st["uso"]["entrada_nova"], 12)
        self.assertEqual(st["uso"]["cache_lido"], 100)
        entry = os.path.join(self.loop.entries, sorted(os.listdir(self.loop.entries))[-1])
        with open(entry, encoding="utf-8") as f:
            self.assertIn("uso_turno: saida=500 entrada_nova=12 cache_lido=100 mensagens=1",
                          f.read())

    def test_o_uso_acumula_entre_paradas_sem_recontar(self):
        self.armar()
        self.turno("m1", 500)
        self.parar()
        self.turno("m2", 200)
        self.parar()
        self.assertEqual(self.loop.ler()["uso"]["saida"], 700)
        self.assertEqual(self.loop.ler()["uso"]["mensagens"], 2)

    def test_o_item_da_frente_tem_o_proprio_medidor(self):
        self.armar(max_paradas_item=0)
        self.turno("m1", 500)
        self.parar()
        self.assertEqual(self.loop.ler()["uso_item"]["saida"], 500,
                         "o trabalho desde o armar é do primeiro item")
        self.turno("m2", 200)
        self.parar()
        self.assertEqual(self.loop.ler()["uso_item"]["saida"], 700)

    def test_item_novo_zera_o_medidor_do_item(self):
        self.armar(max_paradas_item=0)
        self.turno("m1", 500)
        self.parar()
        with open(self.loop.p("QUEUE.md"), encoding="utf-8") as f:
            conteudo = f.read()
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(conteudo.replace("- [ ] 3.1 Converter", "- [x] 3.1 Converter", 1))
        self.turno("m2", 200)
        self.parar()
        st = self.loop.ler()
        self.assertIsNone(st["uso_item"],
                          "os 200 são do 3.1, que fechou; o 3.2 começa do zero")
        self.assertEqual(st["uso"]["saida"], 700, "a rodada continua somando")

    def test_o_status_do_fim_traz_o_uso(self):
        self.armar()
        self.turno("m1", 500)
        self.parar()
        with open(self.loop.p("STOP"), "w") as f:
            f.write("")
        self.turno("m2", 1)
        self.parar()
        with open(self.loop.p("STATUS.md"), encoding="utf-8") as f:
            status = f.read()
        self.assertIn("**Uso observado:**", status)
        self.assertIn("saída 501", status)

    def test_estado_de_versao_anterior_roda_e_passa_a_medir(self):
        st = self.armar()
        for campo in ("uso", "uso_item", "uso_desde", "uso_offsets", "uso_ids"):
            st.pop(campo, None)
        self.loop.gravar(st)
        self.turno("m1", 300)
        rc, saida = self.parar()
        self.assertEqual(rc, 0)
        self.assertEqual(saida["decision"], "block")
        self.assertEqual(self.loop.ler()["uso"]["saida"], 300)

    def test_parada_sem_registro_de_uso_nao_escreve_uso_na_entry(self):
        # "No usage record was read" and "the turn used nothing" are different
        # facts. A zero printed for the first would be a number nobody measured.
        self.armar()
        self.rodar(DOC)                      # the base transcript has no usage
        entry = os.path.join(self.loop.entries, sorted(os.listdir(self.loop.entries))[-1])
        with open(entry, encoding="utf-8") as f:
            self.assertNotIn("uso_turno", f.read())
        self.assertEqual(Loop._linha_uso(None), [])
        self.assertEqual(Loop._linha_uso({"saida": 0, "entrada_nova": 0,
                                          "cache_lido": 0, "mensagens": 0}), [])

    def test_transcript_que_nao_existe_nao_derruba_a_parada(self):
        self.armar()
        self.arq = os.path.join(self.tmp, "nao-existe.jsonl")
        rc, saida = self.parar()
        self.assertEqual(rc, 0)
        self.assertIsNotNone(self.loop.ler()["iteracao"])
        self.assertIsNone(self.loop.ler()["uso"])


class TestNoCtlEPainel(Base):
    def ctl(self, *args):
        return subprocess.run([sys.executable, CTL] + list(args),
                              capture_output=True, text=True, timeout=30)

    def test_status_mostra_o_uso_so_quando_medido(self):
        self.armar()
        self.assertNotIn("uso        :", self.ctl("status", "--raiz", self.tmp).stdout)
        st = self.loop.ler()
        st["uso"] = {"saida": 98827, "entrada_nova": 492254, "cache_lido": 11369545,
                     "mensagens": 62, "parcial": False}
        st["uso_item"] = {"saida": 12300, "entrada_nova": 0, "cache_lido": 0}
        self.loop.gravar(st)
        saida = self.ctl("status", "--raiz", self.tmp).stdout
        self.assertIn("saída 98.8k · entrada nova 492.3k · cache lido 11.4M", saida)
        self.assertIn("62 mensagens", saida)
        self.assertIn("saída 12.3k neste item", saida)

    def test_retomar_recomeca_o_medidor_e_guarda_o_total(self):
        st = self.armar()
        st.update(ativo=False, fase="encerrando", encerrado_por="sem progresso",
                  uso={"saida": 5, "entrada_nova": 0, "cache_lido": 0, "mensagens": 1},
                  uso_item={"saida": 5, "entrada_nova": 0, "cache_lido": 0},
                  uso_offsets={"x.jsonl": 123}, uso_ids=["m1"],
                  uso_desde="2026-01-01T00:00:00+00:00")
        self.loop.gravar(st)
        self.ctl("retomar", "--raiz", self.tmp)
        depois = self.loop.ler()
        self.assertEqual(depois["uso"]["saida"], 5, "o total da rodada fica")
        self.assertEqual(depois["uso_offsets"], {})
        self.assertEqual(depois["uso_ids"], [])
        self.assertIsNone(depois["uso_item"])
        self.assertNotEqual(depois["uso_desde"], "2026-01-01T00:00:00+00:00",
                            "o que a sessão gastou com o loop desligado não é da rodada")

    def test_o_painel_so_ganha_a_linha_depois_de_medir(self):
        self.armar()
        st = self.loop.ler()
        informativas = lambda: [r for m, r, _t, _x
                                in lw.condicoes(self.loop, st, 2, 1) if m is None]
        self.assertNotIn("uso da rodada", informativas())
        st["uso"] = {"saida": 1, "entrada_nova": 2, "cache_lido": 3, "mensagens": 1}
        self.assertIn("uso da rodada", informativas())
        # An informative row: it can never be marked as the reason a round ended.
        self.assertEqual([m for m, r, _t, _x in lw.condicoes(self.loop, st, 2, 1)
                          if r == "uso da rodada"], [None])


if __name__ == "__main__":
    unittest.main()
