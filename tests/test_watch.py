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

    def fila(self, conteudo):
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n" + conteudo)

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
        self.assertIn("kill-switch", texto)
        self.assertIn("PRESENTE", texto)
        # E ele não fica mais num canto do painel: kill-switch é o primeiro elo
        # da cadeia, então é ELE que decide a próxima parada — o painel diz isso.
        self.assertIn("já bateu", texto)

    def test_parado_avisa_que_o_hook_esta_inerte(self):
        # "PARADO" foi lido como "entre duas iterações", e o "continua" digitado
        # em 17/08 virou um turno de 2min30. Mutação: remover o aviso e o painel
        # volta a deixar o operador esperando por um loop que não existe.
        st = self.loop.ler()
        st["ativo"] = False
        texto, _ = self.render(st=st)
        self.assertIn("hook inerte", texto)
        self.assertIn("loop-ctl porque", texto)

    def test_encerrando_tambem_e_inercia(self):
        # `fase: encerrando` ainda tem ativo=true, mas a próxima parada encerra
        # sem classificar: para quem acompanha, é parada.
        st = self.loop.ler()
        st["fase"] = "encerrando"
        texto, _ = self.render(st=st)
        self.assertIn("hook inerte", texto)

    def test_loop_rodando_nao_avisa_nada(self):
        texto, _ = self.render()
        self.assertNotIn("hook inerte", texto)

    def test_mostra_a_sessao_amarrada(self):
        st = self.loop.ler()
        st["session_id"] = "6bd4ebd5-599f-4ccc-9e8a-a6e0933daf46"
        texto, _ = self.render(st=st)
        self.assertIn("6bd4ebd5…", texto)

    def test_sem_amarracao_nao_inventa_linha(self):
        st = self.loop.ler()
        st["bind_session"] = False
        st["session_id"] = "6bd4ebd5-599f"
        texto, _ = self.render(st=st)
        self.assertNotIn("6bd4ebd5", texto)

    # ── a cadeia manda no painel, não o relógio (ADR-013) ───────────────────

    def _marcada(self, texto, marca):
        """A linha do bloco `Fim por` que carrega esta marca."""
        return [l for l in texto.split("\n") if marca in l]

    def test_rodada_morta_marca_quem_encerrou_e_nao_quem_chegaria_primeiro(self):
        # O painel do EOP em 17/08, exato: encerrado por fila zerada às 09:32, e
        # o bloco marcando `← primeira` na janela porque faltavam 2h18 nela.
        # Mutação: voltar a ranquear por tempo e esta asserção cai — a marca
        # migra para a janela e o painel volta a apontar futuro em rodada morta.
        self.fila("- [x] tudo feito\n")
        st = self.loop.ler()
        st["ativo"] = False
        st["encerrado_por"] = "fila zerada"
        st["encerrado_detalhe"] = "22 item(ns) concluído(s)"
        st["encerrado_em"] = "2026-08-17T09:32:07-03:00"
        texto, _ = self.render(st=st)
        encerrou = self._marcada(texto, "← encerrou aqui")
        self.assertEqual(len(encerrou), 1)
        self.assertIn("fila zerada", encerrou[0])
        self.assertEqual(self._marcada(texto, "← primeira"), [])

    def test_rodada_viva_avisa_condicao_que_ja_bateu(self):
        # Viva, mas a fila já está em zero: a PRÓXIMA parada encerra. Isso é
        # fato medido, não previsão — e era o que o painel não dizia.
        self.fila("- [x] tudo feito\n")
        texto, _ = self.render()
        ja = self._marcada(texto, "← já bateu")
        self.assertEqual(len(ja), 1)
        self.assertIn("fila zerada", ja[0])
        self.assertEqual(self._marcada(texto, "← primeira"), [])

    def test_sem_condicao_batida_volta_a_valer_o_relogio(self):
        # A pergunta "quanto falta?" continua respondida quando nada bateu.
        st = self.loop.ler()
        st["duracao_max_min"] = 5
        texto, _ = self.render(st=st)
        primeira = self._marcada(texto, "← primeira")
        self.assertEqual(len(primeira), 1)
        self.assertIn("relógio", primeira[0])

    def test_ordem_do_bloco_e_a_da_cadeia_do_hook(self):
        # O anti-quarta-cópia: se alguém reordenar o painel "para ficar bonito",
        # ele volta a discordar da ordem em que o hook realmente testa.
        linhas = lw.condicoes(self.loop, self.loop.ler(), 2, 1)
        self.assertEqual([m for m, _r, _t, _x in linhas],
                         ["kill-switch", "teto de iterações", "sem progresso",
                          "fila zerada", "fora da janela de trabalho",
                          "duração máxima"])

    def test_motivo_sem_linha_propria_ainda_aparece(self):
        # `política ASK=parar` depende de classificar a mensagem, então o painel
        # não a mede — o que não o autoriza a omitir por que a rodada acabou.
        st = self.loop.ler()
        st["ativo"] = False
        st["encerrado_por"] = "política ASK=parar"
        st["encerrado_detalhe"] = "pergunta-direta"
        texto, _ = self.render(st=st)
        encerrou = self._marcada(texto, "← encerrou aqui")
        self.assertEqual(len(encerrou), 1)
        self.assertIn("política ASK=parar", encerrou[0])

    def test_escopo_por_marcador_marca_a_linha_do_marcador(self):
        # Duas condições dividem o motivo "escopo concluído"; só o detalhe as
        # separa. Sem ele, a marca cai na linha errada metade das vezes.
        st = self.loop.ler()
        st["ativo"] = False
        st["escopo_itens"] = 5
        st["escopo_ate"] = "D3. rodar o lint"
        st["encerrado_por"] = "escopo concluído"
        st["encerrado_detalhe"] = "marcador alcançado: D3. rodar o lint"
        texto, _ = self.render(st=st)
        encerrou = self._marcada(texto, "← encerrou aqui")
        self.assertEqual(len(encerrou), 1)
        self.assertIn("marcador", encerrou[0])

    def test_cabecalho_diz_ha_quanto_tempo_encerrou(self):
        # O painel carimba a hora da LEITURA; sem isto, 09:42 numa rodada morta
        # às 09:32 parece rodada de agora.
        st = self.loop.ler()
        st["ativo"] = False
        st["encerrado_por"] = "fila zerada"
        st["encerrado_em"] = "2026-08-17T09:32:07-03:00"
        texto, _ = self.render(st=st)
        self.assertIn("ENCERRADO · fila zerada há ", texto)

    # ── o número da parada e o objetivo ilegível ────────────────────────────

    def test_numero_da_parada_vem_do_nome_do_arquivo(self):
        # A entry 0003 do EOP tem `n: 1` dentro — escrita quando o hook ainda
        # numerava pela iteração, que `iniciar()` zera a cada rodada. O painel
        # mostrou `#4 #1 #2 #1` para 0001..0004. Mutação: voltar a confiar no
        # front-matter e o `#1` reaparece.
        self.entry(1, "DOC")
        nome = "0003-ASK-x.md"
        with open(os.path.join(self.loop.entries, nome), "w", encoding="utf-8") as f:
            f.write("---\nn: 1\nkind: ASK\nsinal: pergunta-direta\nconfianca: alta\n"
                    "ts: 2026-08-17T09:03:00-03:00\nsessao: x\nitem_da_fila: \"i\"\n"
                    "decisao: continuou\nfecho_do_turno: completo\n---\n\ncorpo\n")
        texto, _ = self.render()
        self.assertIn("#3", texto)
        self.assertNotIn("#1     ASK", texto)

    def test_parada_carrega_a_data_e_nao_so_a_hora(self):
        # Em 17/08 o painel mostrou `09:32 · 09:03 · 21:19 · 20:24` e as duas
        # últimas eram de ONTEM — nada na tela dizia isso. Mutação: voltar o
        # `ts[11:16]` e a data some, com a hora parecendo a mesma jornada.
        self.entry(1, "DOC")            # ts 2026-08-16T21:01
        texto, _ = self.render()
        self.assertIn("16/08/2026-21:01", texto)
        self.assertIn("─ %s-" % __import__("time").strftime("%d/%m/%Y"), texto)

    def test_parada_mostra_quanto_tempo_desde_a_anterior(self):
        # A data responde "quando"; o intervalo responde "quanto tempo levou".
        # Mutação: parar de calcular `intervalo` e o `+Nmin` some da tela.
        self.entry(1, "DOC")        # ts 21:01
        self.entry(2, "DOC")        # ts 21:02
        texto, _ = self.render()
        self.assertIn("+1min", texto)

    def test_linha_mais_antiga_da_tela_tambem_tem_intervalo(self):
        # `ultimas_paradas` lê uma parada a mais do que mostra: sem isso a
        # primeira linha visível nunca teria duração.
        for n in range(1, 7):
            self.entry(n, "DOC")
        paradas = lw.ultimas_paradas(self.loop, quantas=4)
        self.assertEqual(len(paradas), 4)
        self.assertEqual(paradas[0]["n"], "3")
        self.assertIsNotNone(paradas[0]["intervalo"])

    def test_intervalo_ilegivel_nao_vira_numero(self):
        self.assertIsNone(lw._minutos_entre(None, "2026-08-17T12:00:00-03:00"))
        self.assertIsNone(lw._minutos_entre("ontem", "2026-08-17T12:00:00-03:00"))

    def test_objetivo_ilegivel_nao_passa_na_vitrine(self):
        # `"¨¨"` foi armado no EOP antes de a guarda de `armar` existir. Estado
        # gravado antes de uma guarda não passa a obedecê-la — e o painel seguia
        # anunciando o mojibake a cada leitura, por rodada inteira.
        st = self.loop.ler()
        st["objetivo"] = "¨¨"
        texto, _ = self.render(st=st)
        self.assertIn("ilegível no STATE.json", texto)
        self.assertIn("loop-ctl armar", texto)


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

    def test_carimbo(self):
        self.assertEqual(lw.carimbo("2026-08-17T12:56:03-03:00"), "17/08/2026-12:56")
        self.assertEqual(lw.carimbo("2026-08-16T21:19:22-03:00"), "16/08/2026-21:19")

    def test_carimbo_nao_inventa_data(self):
        # Painel pode não saber ler um carimbo; não pode fabricar um.
        self.assertEqual(lw.carimbo(None), "?")
        self.assertEqual(lw.carimbo(""), "?")
        self.assertEqual(lw.carimbo("ontem de noite"), "ontem de noite")

    def test_barra(self):
        self.assertEqual(lw.barra(0, 4, 8), "░" * 8)
        self.assertEqual(lw.barra(4, 4, 8), "█" * 8)
        self.assertEqual(lw.barra(2, 4, 8), "█" * 4 + "░" * 4)
        self.assertEqual(len(lw.barra(1, 0, 8)), 8)      # fila vazia não quebra


if __name__ == "__main__":
    unittest.main(verbosity=2)
