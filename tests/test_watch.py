#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do acompanhamento (`loop_watch.py`) e do tempo restante da janela.

O watcher existe para responder de longe as duas perguntas que o `status` cru
não responde: **andou?** e **quanto falta?**. As duas viram teste aqui — a
primeira pelo delta entre leituras, a segunda por `minutos_ate_fechar`.
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

from estado import Loop, minutos_ate_fechar     # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "loop_watch", os.path.join(RAIZ, "skill", "loop", "loop_watch.py"))
lw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lw)
lw.C.desligar()


class TestMinutosAteFechar(unittest.TestCase):

    def em(self, dia, hora, minuto=0):
        return datetime(2026, 8, dia, hora, minuto)     # 10/08/2026 = segunda

    def test_dentro_da_janela(self):
        self.assertEqual(minutos_ate_fechar("08:00-18:00", momento=self.em(10, 17, 30)), 30)
        self.assertEqual(minutos_ate_fechar("08:00-18:00", momento=self.em(10, 8)), 600)

    def test_fora_da_janela_e_zero(self):
        self.assertEqual(minutos_ate_fechar("08:00-18:00", momento=self.em(10, 19)), 0)
        self.assertEqual(minutos_ate_fechar("08:00-18:00", momento=self.em(10, 7)), 0)

    def test_janela_que_cruza_a_meia_noite(self):
        # 23:30 dentro de 22:00-06:00 → faltam 6h30 até as 06:00
        self.assertEqual(minutos_ate_fechar("22:00-06:00", momento=self.em(10, 23, 30)), 390)
        # 02:00 → faltam 4h
        self.assertEqual(minutos_ate_fechar("22:00-06:00", momento=self.em(10, 2)), 240)

    def test_dia_nao_permitido_conta_como_fechada(self):
        self.assertEqual(minutos_ate_fechar("08:00-18:00", "seg-sex", self.em(15, 9)), 0)

    def test_sem_janela(self):
        self.assertIsNone(minutos_ate_fechar(None, momento=self.em(10, 9)))

    def test_janela_invalida_nao_inventa_numero(self):
        self.assertIsNone(minutos_ate_fechar("oito às seis", momento=self.em(10, 9)))


class TestRender(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-watch-")
        self.loop = Loop(self.tmp)
        os.makedirs(self.loop.entries)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [x] feito\n- [ ] A fazer agora\n- [ ] depois\n")
        self.st = self.loop.iniciar(objetivo="demo", max_iteracoes=40,
                                    janela="00:00-23:59", duracao_max_min=360)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def entry(self, n, kind, sinal="relato", decisao="continuou", parcial="completo"):
        nome = "%04d-%s-x.md" % (n, kind)
        with open(os.path.join(self.loop.entries, nome), "w", encoding="utf-8") as f:
            f.write("---\nn: %d\nkind: %s\nsinal: %s\nconfianca: alta\n"
                    "ts: 2026-08-16T21:%02d:00-03:00\nsessao: x\n"
                    "item_da_fila: \"i\"\ndecisao: %s\nfecho_do_turno: %s\n---\n\ncorpo\n"
                    % (n, kind, sinal, min(n, 59), decisao, parcial))

    def render(self, anterior=None, st=None):
        return lw.render(self.loop, st or self.loop.ler(), anterior)

    def test_mostra_proximo_item_e_progresso(self):
        texto, estado = self.render()
        self.assertIn("A fazer agora", texto)
        self.assertIn("1/3", texto)
        self.assertEqual(estado["feitos"], 1)

    def test_delta_entre_leituras(self):
        # A pergunta "andou?" — mutação: remover o bloco de delta e o watcher
        # vira o `watch` que ele existe para substituir.
        _, agora = self.render()
        texto, _ = self.render({"it": agora["it"] - 3, "feitos": agora["feitos"] - 2})
        self.assertIn("+3 parada(s), +2 item(ns)", texto)

    def test_sem_movimento_diz_que_nao_mudou(self):
        _, agora = self.render()
        texto, _ = self.render(agora)
        self.assertIn("sem mudança", texto)

    def test_marca_a_condicao_que_bate_primeiro(self):
        st = self.loop.ler()
        st["duracao_max_min"] = 5          # relógio bate antes da janela larga
        texto, _ = self.render(st=st)
        linhas = [l for l in texto.split("\n") if "← primeira" in l]
        self.assertEqual(len(linhas), 1)
        self.assertIn("relógio", linhas[0])

    def test_entry_ask_e_sinalizada(self):
        self.entry(1, "ASK", sinal="handoff")
        texto, _ = self.render()
        self.assertIn("premissa registrada", texto)

    def test_fecho_parcial_e_sinalizado(self):
        # O defeito do ADR-012, visível de longe: se voltar, aparece na tela.
        self.entry(2, "DOC", parcial="PARCIAL")
        texto, _ = self.render()
        self.assertIn("fecho parcial", texto)

    def test_encerrado_aparece_com_o_motivo(self):
        st = self.loop.ler()
        st["ativo"] = False
        st["encerrado_por"] = "fila zerada"
        texto, _ = self.render(st=st)
        self.assertIn("ENCERRADO", texto)
        self.assertIn("fila zerada", texto)

    def test_kill_switch_visivel(self):
        open(self.loop.p("STOP"), "w").close()
        texto, _ = self.render()
        self.assertIn("kill-switch PRESENTE", texto)


class TestCli(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-watch-cli-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sem_loop_sai_com_erro_e_explica(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = lw.main(["--raiz", self.tmp, "--uma-vez"])
        self.assertEqual(rc, 1)
        self.assertIn("STATE.json", buf.getvalue())

    def test_uma_vez_imprime_e_sai(self):
        import io
        from contextlib import redirect_stdout
        loop = Loop(self.tmp)
        os.makedirs(loop.entries)
        with open(loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [ ] alguma coisa\n")
        loop.iniciar(objetivo="x", max_iteracoes=10)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = lw.main(["--raiz", self.tmp, "--uma-vez", "--sem-cor"])
        self.assertEqual(rc, 0)
        self.assertIn("alguma coisa", buf.getvalue())


class TestFormatacao(unittest.TestCase):

    def test_dur(self):
        self.assertEqual(lw.dur(None), "—")
        self.assertEqual(lw.dur(0), "esgotado")
        self.assertEqual(lw.dur(-5), "esgotado")
        self.assertEqual(lw.dur(25), "25min")
        self.assertEqual(lw.dur(90), "1h30")
        self.assertEqual(lw.dur(360), "6h00")

    def test_barra(self):
        self.assertEqual(lw.barra(0, 4, 8), "░" * 8)
        self.assertEqual(lw.barra(4, 4, 8), "█" * 8)
        self.assertEqual(lw.barra(2, 4, 8), "█" * 4 + "░" * 4)
        self.assertEqual(len(lw.barra(1, 0, 8)), 8)      # fila vazia não quebra


if __name__ == "__main__":
    unittest.main(verbosity=2)
