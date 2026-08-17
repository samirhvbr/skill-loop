#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes da leitura do transcript — e da corrida contra ele (ADR-012).

O defeito que originou este arquivo foi medido em produção, no EOP, na primeira
rodada real do loop (16/08/2026): o hook `Stop` disparou às 00:19:22 e leu texto
de **00:12:30** — 154 entradas e 7 minutos atrás. O relato verdadeiro
("Fila zerada — 21/21…") tinha timestamp 00:19:22, o mesmo segundo da parada:
ele estava sendo escrito enquanto o hook lia.

Consequência: as duas `entries` daquela rodada arquivaram fragmentos de meio de
raciocínio ("Vou fechar:", "D1 — releitura: conferindo…") e os classificaram
como se fossem o relatório. A promessa central do produto — ler o retorno e
documentá-lo — estava documentando a coisa errada, em silêncio.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

from transcricao import ultima_mensagem, _varrer   # noqa: E402


def ass(texto=None, tool=None, sidechain=False):
    blocos = []
    if texto is not None:
        blocos.append({"type": "text", "text": texto})
    if tool is not None:
        blocos.append({"type": "tool_use", "name": tool, "input": {}})
    return json.dumps({"type": "assistant", "isSidechain": sidechain,
                       "message": {"content": blocos}})


def resultado_de_tool(sidechain=False):
    return json.dumps({"type": "user", "isSidechain": sidechain,
                       "message": {"content": [{"type": "tool_result",
                                                "content": "ok"}]}})


def metadado(tipo):
    return json.dumps({"type": tipo})


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-transcricao-")
        self.arq = os.path.join(self.tmp, "transcript.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def escrever(self, linhas):
        with open(self.arq, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")

    def acrescentar(self, linhas):
        with open(self.arq, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")


class TestFrescor(Base):
    """`fresco` é a pergunta que decide tudo: isto é o fecho, ou resto velho?"""

    def test_texto_por_ultimo_e_fresco(self):
        self.escrever([ass("Fila zerada — 21/21.")])
        texto, tool, parcial = ultima_mensagem(self.arq, espera_max_s=0.2)
        self.assertEqual(texto, "Fila zerada — 21/21.")
        self.assertFalse(parcial)

    def test_tool_use_depois_do_texto_e_resto_velho(self):
        # Exatamente a forma medida no EOP: texto, e 7 pares de tool depois.
        self.escrever([ass("Vou fechar:")]
                      + [ass(tool="Edit"), resultado_de_tool()] * 7)
        with open(self.arq, encoding="utf-8") as f:
            _, _, fresco = _varrer(f.read().split("\n"))
        self.assertFalse(fresco)

    def test_metadado_do_harness_nao_conta_como_conteudo(self):
        # attachment/system/mode aparecem AOS MONTES depois do texto final e
        # não dizem nada sobre o turno ter fechado — 44 de cada, no caso real.
        self.escrever([ass("Relato final.")]
                      + [metadado(t) for t in ("attachment", "system", "mode",
                                               "last-prompt", "ai-title",
                                               "permission-mode")])
        texto, _, parcial = ultima_mensagem(self.arq, espera_max_s=0.2)
        self.assertEqual(texto, "Relato final.")
        self.assertFalse(parcial)

    def test_subagente_depois_do_texto_nao_torna_velho(self):
        # Sidechain é outro turno. Se contasse, todo uso de Explore faria o
        # hook esperar o teto inteiro à toa.
        self.escrever([ass("Relato final."),
                       ass("Explore: acabei.", sidechain=True),
                       resultado_de_tool(sidechain=True)])
        texto, _, parcial = ultima_mensagem(self.arq, espera_max_s=0.2)
        self.assertEqual(texto, "Relato final.")
        self.assertFalse(parcial)

    def test_askuserquestion_fecha_o_turno_e_nao_espera(self):
        # O turno para NA tool, esperando o humano: não há texto de fecho para
        # aguardar. Sem esta regra o hook gastaria o teto em toda pergunta.
        self.escrever([ass("Levantei as opções."), ass(tool="AskUserQuestion")])
        t0 = time.time()
        texto, tool, parcial = ultima_mensagem(self.arq, espera_max_s=5.0)
        self.assertLess(time.time() - t0, 1.0)
        self.assertEqual(tool, "AskUserQuestion")
        self.assertFalse(parcial)


class TestCorrida(Base):
    """A regressão do defeito de 16/08."""

    def test_espera_o_fecho_que_chega_durante_a_leitura(self):
        # Estado no instante do Stop: fragmento antigo + trabalho depois.
        self.escrever([ass("D1 — releitura: conferindo cada afirmação."),
                       ass(tool="Edit"), resultado_de_tool(),
                       ass(tool="Bash"), resultado_de_tool()])

        final = "**Fila zerada — 21/21.** Os três blocos fecharam no rito."

        def escreve_depois():
            time.sleep(0.35)
            self.acrescentar([ass(final)])

        t = threading.Thread(target=escreve_depois)
        t.start()
        try:
            texto, _, parcial = ultima_mensagem(self.arq, espera_max_s=3.0)
        finally:
            t.join()

        # mutação: remover a espera → volta o fragmento e parcial=False,
        # que é exatamente o defeito silencioso de produção.
        self.assertEqual(texto, final)
        self.assertFalse(parcial)

    def test_estoura_a_espera_e_ROTULA_como_parcial(self):
        # O fecho nunca chega. Seguir é certo (fail-open), mentir não é.
        self.escrever([ass("Vou fechar:"), ass(tool="Edit"), resultado_de_tool()])
        t0 = time.time()
        texto, _, parcial = ultima_mensagem(self.arq, espera_max_s=0.4)
        self.assertGreaterEqual(time.time() - t0, 0.4)
        self.assertTrue(parcial)
        self.assertEqual(texto, "Vou fechar:")

    def test_teto_da_espera_e_respeitado(self):
        self.escrever([ass("x"), ass(tool="Edit")])
        t0 = time.time()
        ultima_mensagem(self.arq, espera_max_s=0.3)
        self.assertLess(time.time() - t0, 2.0)   # bem abaixo do timeout do hook


class TestRobustez(Base):

    def test_arquivo_inexistente(self):
        texto, tool, parcial = ultima_mensagem(os.path.join(self.tmp, "nada.jsonl"),
                                               espera_max_s=0.2)
        self.assertEqual((texto, tool, parcial), ("", None, False))

    def test_linha_corrompida_no_meio(self):
        self.escrever(["{lixo", ass("Relato final."), "não é json"])
        texto, _, parcial = ultima_mensagem(self.arq, espera_max_s=0.2)
        self.assertEqual(texto, "Relato final.")

    def test_transcript_so_de_subagente(self):
        self.escrever([ass("Explore: achei.", sidechain=True)])
        texto, _, _ = ultima_mensagem(self.arq, espera_max_s=0.2)
        self.assertEqual(texto, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
