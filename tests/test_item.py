#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stops per item (ADR-019): the guard for the agent that moves and never closes.

`sem_progresso` asks whether the agent MOVED. These tests are about a different
question — whether the item at the head of the queue CLOSED — and they run the
hook as a subprocess, like `test_ciclo.py`, because the thing that matters is the
queue file and the prompt the agent actually receives.

Each test fails with the control switched off; the mutations are listed in
ADR-019.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ciclo import ASK, CTL, DOC, Base   # noqa: E402

from estado import chave_do_item, limiar_aviso_item, mesmo_item   # noqa: E402


class BaseItem(Base):
    def armar(self, **kw):
        # Isolate this guard from the other brake and from harvesting: the DOC
        # text is not what is under test, and `sem_progresso` would end the round
        # long before 15 stops on an unchanged queue.
        kw.setdefault("max_sem_progresso", 99)
        kw.setdefault("colher_itens", False)
        return super().armar(**kw)

    def fila(self):
        with open(self.loop.p("QUEUE.md"), encoding="utf-8") as f:
            return f.read()

    def reescrever(self, antigo, novo):
        conteudo = self.fila()
        self.assertIn(antigo, conteudo)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(conteudo.replace(antigo, novo, 1))


class TestRegua(unittest.TestCase):
    """The two small rulers the counter stands on."""

    def test_mesmo_item_aceita_nota_acrescentada_e_recusa_o_resto(self):
        a = chave_do_item("3.1 Converter as observações do Billing em consulta")
        self.assertTrue(mesmo_item(a, a))
        self.assertTrue(mesmo_item(a, chave_do_item(
            "3.1 Converter as observações do Billing em consulta — passo 1 feito")))
        self.assertFalse(mesmo_item(a, chave_do_item(
            "3.2 Nomear a unicidade do token de convite")))
        self.assertFalse(mesmo_item(a, None))
        self.assertFalse(mesmo_item(None, None))

    def test_prefixo_curto_demais_nao_vale(self):
        # A one-word item must not match everything that starts with it.
        self.assertFalse(mesmo_item(chave_do_item("Billing"),
                                    chave_do_item("Billing: refazer tudo")))

    def test_aviso_vem_antes_da_trava(self):
        self.assertEqual(limiar_aviso_item(15), 6)
        self.assertEqual(limiar_aviso_item(5), 2)
        self.assertIsNone(limiar_aviso_item(0))
        self.assertIsNone(limiar_aviso_item(None))


class TestParadasNoItem(BaseItem):

    def test_aviso_primeiro_e_depois_a_trava(self):
        self.armar(max_paradas_item=5)                    # warning from stop 2
        _, s1 = self.rodar(DOC)
        self.assertNotIn("paradas seguidas", s1["reason"])
        _, s2 = self.rodar(DOC)
        self.assertIn("2 paradas seguidas", s2["reason"])
        self.assertIn("Troque-o por sub-itens", s2["reason"])
        for _ in range(2):                                # stops 3 and 4
            self.rodar(DOC)
        self.assertIn("- [ ] 3.1 Converter", self.fila(),
                      "antes do teto o item continua pendente")

        _, s5 = self.rodar(DOC)                           # stop 5: the lock
        fila = self.fila()
        self.assertIn("- 🔒 3.1 Converter", fila)
        self.assertIn("travado pelo loop após 5 paradas", fila)
        self.assertIn("- [ ] 3.2 Nomear", fila, "só o item da frente é travado")
        self.assertIn("O loop travou o item anterior", s5["reason"])
        self.assertIn("> 3.2 Nomear", s5["reason"], "a rodada segue no próximo")

        st = self.loop.ler()
        self.assertEqual(st["itens_travados"], 1)
        self.assertEqual(st["paradas_no_item"], 1,
                         "o item seguinte começa a contar nesta parada")
        self.assertTrue(st["ativo"], "travar um item não encerra a rodada")

    def test_a_trava_fica_registrada_na_entry_e_no_indice(self):
        self.armar(max_paradas_item=2)
        self.rodar(DOC)
        self.rodar(DOC)
        with open(self.loop.p("INDEX.md"), encoding="utf-8") as f:
            ultima = f.read().strip().splitlines()[-1]
        self.assertIn("continuou · item 🔒", ultima)
        entries = sorted(os.listdir(self.loop.entries))
        with open(os.path.join(self.loop.entries, entries[-1]),
                  encoding="utf-8") as f:
            corpo = f.read()
        self.assertIn("## Item travado pelo loop (ADR-019)", corpo)
        self.assertIn("3.1 Converter", corpo)

    def test_fechar_o_item_zera_a_contagem(self):
        self.armar(max_paradas_item=5)
        self.rodar(DOC)
        self.rodar(DOC)
        self.assertEqual(self.loop.ler()["paradas_no_item"], 2)
        self.reescrever("- [ ] 3.1 Converter", "- [x] 3.1 Converter")
        _, saida = self.rodar(DOC)
        st = self.loop.ler()
        self.assertEqual(st["paradas_no_item"], 1, "o 3.2 é outro item")
        self.assertNotIn("paradas seguidas", saida["reason"])
        self.assertEqual(st["itens_travados"], 0)

    def test_item_com_nota_acrescentada_continua_sendo_o_mesmo(self):
        # The agent writes progress on the line it is working. If that made a new
        # item, the guard would be switched off by the agent it exists to catch.
        self.armar(max_paradas_item=5)
        self.rodar(DOC)
        self.reescrever("consulta ao banco",
                        "consulta ao banco (passo 1 de 3 feito)")
        self.rodar(DOC)
        self.assertEqual(self.loop.ler()["paradas_no_item"], 2)

    def test_reescrever_o_inicio_do_item_e_outro_item(self):
        # Replacing the item by sub-items is what the warning asks for, and it
        # has to restart the count.
        self.armar(max_paradas_item=5)
        self.rodar(DOC)
        self.rodar(DOC)
        self.reescrever("3.1 Converter as observações do Billing em consulta ao banco",
                        "3.1a Mapear as observações do Billing que ainda são comentário")
        self.rodar(DOC)
        self.assertEqual(self.loop.ler()["paradas_no_item"], 1)

    def test_zero_desliga_aviso_e_trava(self):
        # The other direction: a guard that fires on a round that turned it off
        # is a guard nobody can trust.
        self.armar(max_paradas_item=0)
        antes = self.fila()
        for _ in range(20):
            _, saida = self.rodar(DOC)
            self.assertNotIn("paradas seguidas", saida["reason"])
        self.assertEqual(self.fila(), antes)
        self.assertEqual(self.loop.ler()["itens_travados"], 0)

    def test_a_trava_nao_conta_como_progresso(self):
        # Locking changes `pend`, which is part of the imprint. Without retaking
        # it, the stop AFTER the lock reads that change as progress and resets
        # `sem_progresso` — the loop crediting itself for its own bookkeeping.
        self.armar(max_paradas_item=3)
        for _ in range(3):                                # stop 3 locks
            self.rodar(DOC)
        self.assertEqual(self.loop.ler()["sem_progresso"], 2)
        self.rodar(DOC)                                   # stop 4: nothing moved
        self.assertEqual(self.loop.ler()["sem_progresso"], 3)

    def test_travar_o_ultimo_pendente_leva_ao_reabastecimento(self):
        # ADR-018 consequence 2, reached through the new door: a queue with only
        # locked items counts as empty, and an empty queue is a refuelling turn.
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [ ] 3.1 Converter as observações do Billing\n")
        self.armar(max_paradas_item=2)
        self.rodar(DOC)
        _, saida = self.rodar(DOC)
        self.assertIn("🔒 3.1 Converter", self.fila().replace("- ", "", 1))
        self.assertIn("REABASTECIMENTO", saida["reason"])
        self.assertTrue(self.loop.ler()["ativo"])

    def test_estado_de_versao_anterior_roda_com_os_padroes(self):
        # A `.loop/` armed before ADR-019 has none of the new fields. Merging the
        # defaults is what lets the hook read it — and it means those rounds pick
        # up the default ceiling of 15, which the ADR states.
        st = self.armar()
        for campo in ("max_paradas_item", "item_cabeca", "paradas_no_item",
                      "itens_travados"):
            st.pop(campo, None)
        self.loop.gravar(st)
        with open(self.loop.p("STATE.json"), encoding="utf-8") as f:
            self.assertNotIn("max_paradas_item", json.load(f))
        rc, saida = self.rodar(DOC)
        self.assertEqual(rc, 0)
        self.assertEqual(saida["decision"], "block")
        novo = self.loop.ler()
        self.assertEqual(novo["max_paradas_item"], 15)
        self.assertEqual(novo["paradas_no_item"], 1)


class TestCtl(BaseItem):
    """The operator's side: the flag, the status line, and `retomar`."""

    def ctl(self, *args):
        return subprocess.run([sys.executable, CTL] + list(args),
                              capture_output=True, text=True, timeout=30)

    def test_armar_grava_o_teto_e_o_status_o_mostra(self):
        proc = self.ctl("armar", "--raiz", self.tmp, "--sessao", self.sessao,
                        "--max-paradas-item", "7", "--objetivo", "terminar a fase 3")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.loop.ler()["max_paradas_item"], 7)
        self.assertIn("trava na 7ª", proc.stdout)
        self.assertIn("aviso na 3ª", proc.stdout)
        status = self.ctl("status", "--raiz", self.tmp).stdout
        self.assertIn("neste item", status)
        self.assertIn("trava na 7ª", status)

    def test_zero_aparece_como_desligado(self):
        self.ctl("armar", "--raiz", self.tmp, "--sessao", self.sessao,
                 "--max-paradas-item", "0", "--objetivo", "terminar a fase 3")
        self.assertIn("desligado", self.ctl("status", "--raiz", self.tmp).stdout)

    def test_retomar_zera_a_contagem_do_item(self):
        # A resumed round starts clean on the head item, the same as it does for
        # `sem_progresso`; a stale count would lock the first item on the first
        # stop of a round that has not run yet.
        st = self.armar(max_paradas_item=5)
        st.update(ativo=False, fase="encerrando", paradas_no_item=4,
                  item_cabeca=chave_do_item("3.1 Converter as observações"),
                  encerrado_por="sem progresso")
        self.loop.gravar(st)
        self.ctl("retomar", "--raiz", self.tmp)
        depois = self.loop.ler()
        self.assertEqual(depois["paradas_no_item"], 0)
        self.assertIsNone(depois["item_cabeca"])


class TestTravarItem(BaseItem):
    """`Loop.travar_item` in isolation: it rewrites a file the agent wrote."""

    def escrever_bytes(self, dados):
        with open(self.loop.p("QUEUE.md"), "wb") as f:
            f.write(dados)

    def bytes_da_fila(self):
        with open(self.loop.p("QUEUE.md"), "rb") as f:
            return f.read()

    def test_so_a_linha_da_frente_muda_e_o_resto_sobrevive_byte_a_byte(self):
        # A cut multi-byte character on another line (the agent writes this file
        # and the hook can read it mid-write) must survive the round trip.
        # `replace` would turn it into U+FFFD for good.
        cortado = b"- [x] ja feito \xe2\x82\n"
        self.escrever_bytes(
            b"# Fila\n\n"
            b"- [ ] 3.1 Converter as observacoes do Billing  <!-- colhido em #0007 -->\n"
            b"- [ ] 3.2 Nomear a unicidade do token\n" + cortado)
        chave = chave_do_item("3.1 Converter as observacoes do Billing")
        texto = self.loop.travar_item(chave, "motivo de teste")
        self.assertEqual(texto, "3.1 Converter as observacoes do Billing",
                         "o texto devolvido não carrega o comentário de proveniência")
        depois = self.bytes_da_fila()
        self.assertTrue(depois.endswith(cortado))
        linhas = depois.decode("utf-8", "surrogateescape").split("\n")
        self.assertTrue(linhas[2].startswith("- 🔒 3.1 Converter"))
        self.assertIn("<!-- colhido em #0007 -->", linhas[2])
        self.assertTrue(linhas[2].endswith("motivo de teste"))
        self.assertEqual(linhas[3], "- [ ] 3.2 Nomear a unicidade do token")

    def test_cabeca_que_mudou_nao_toca_em_nada(self):
        # The hook decided to lock the head it counted. If the head is a
        # different item by now, locking a look-alike below would hide work nobody
        # asked to hide.
        self.escrever_bytes(b"- [ ] 3.2 Nomear a unicidade do token\n"
                            b"- [ ] 3.1 Converter as observacoes do Billing\n")
        antes = self.bytes_da_fila()
        self.assertIsNone(self.loop.travar_item(
            chave_do_item("3.1 Converter as observacoes do Billing"), "x"))
        self.assertEqual(self.bytes_da_fila(), antes)

    def test_fila_ausente_nao_levanta(self):
        os.remove(self.loop.p("QUEUE.md"))
        self.assertIsNone(self.loop.travar_item(chave_do_item("3.1 Converter"), "x"))


if __name__ == "__main__":
    unittest.main()
