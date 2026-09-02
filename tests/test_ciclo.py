#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de ponta a ponta do hook `Stop`.

O hook é executado como **subprocesso**, com o mesmo contrato que o Claude Code
usa: JSON no stdin, JSON no stdout, código de saída 0. Testar a função Python
direto esconderia justamente o que quebra em produção — import, path do template,
serialização e o fail-open.

Regra de aceite: cada teste falha com o controle desligado (ver `test_mutacao`
no fim, que desliga os guarda-corpos um a um).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(RAIZ, "skill", "loop", "hooks", "loop-stop.py")
CTL = os.path.join(RAIZ, "skill", "loop", "loop_ctl.py")
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

from estado import Loop   # noqa: E402

FIXTURE_REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "relato-fitness-schema.txt")

DOC = ("Migrei o schema de billing e rodei a suíte.\n\n"
       "212 testes · 212 ok · 0 falhas. Commitei em 2.3.1.")
ASK = ("Refiz o mapeamento de erro.\n\n"
       "Mantenho o fallback de senha ou removo de vez?")

FILA = """# Fila do loop

## Trabalho

- [ ] 3.1 Converter as observações do Billing em consulta ao banco
- [ ] 3.2 Nomear a unicidade do token de convite
- [x] 2.9 Já feito antes do loop
"""


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-test-")
        self.loop = Loop(self.tmp)
        os.makedirs(self.loop.entries)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA)
        self.sessao = "sessao-de-teste"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── helpers ─────────────────────────────────────────────────────────────
    def armar(self, **kw):
        cfg = dict(objetivo="terminar a fase 3", session_id=self.sessao,
                   max_iteracoes=50, max_sem_progresso=3)
        cfg.update(kw)
        return self.loop.iniciar(**cfg)

    def transcript(self, texto, tool=None, com_sidechain=True):
        caminho = os.path.join(self.tmp, "transcript.jsonl")
        linhas = [
            json.dumps({"type": "user",
                        "message": {"role": "user", "content": "vai"}}),
            json.dumps({"type": "assistant", "isSidechain": False,
                        "message": {"content": [{"type": "text", "text": texto}]}}),
        ]
        if tool:
            linhas.append(json.dumps({"type": "assistant", "isSidechain": False,
                                      "message": {"content": [
                                          {"type": "tool_use", "name": tool,
                                           "input": {}}]}}))
        if com_sidechain:
            # Subagente falando DEPOIS do agente principal: a leitura é de trás
            # para frente, então este é o primeiro que a busca encontra.
            linhas.append(json.dumps({"type": "assistant", "isSidechain": True,
                                      "message": {"content": [{
                                          "type": "text",
                                          "text": "Explore: devo procurar mais?"}]}}))
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        return caminho

    def zerar_a_fila(self):
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [x] tudo pronto\n")

    def rodar(self, texto=DOC, tool=None, sessao=None, cwd=None, bruto=None):
        payload = bruto if bruto is not None else {
            "session_id": sessao or self.sessao,
            "transcript_path": self.transcript(texto, tool),
            "cwd": cwd or self.tmp,
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        }
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps(payload) if isinstance(payload, dict) else payload,
            capture_output=True, text=True, timeout=30)
        saida = None
        if proc.stdout.strip():
            saida = json.loads(proc.stdout)
        return proc.returncode, saida


class TestInercia(Base):
    """Sem opt-in, o hook não pode existir para o resto da máquina."""

    def test_sem_loop_e_inerte(self):
        vazio = tempfile.mkdtemp(prefix="loop-vazio-")
        try:
            rc, saida = self.rodar(cwd=vazio)
            self.assertEqual(rc, 0)
            self.assertIsNone(saida)
        finally:
            shutil.rmtree(vazio, ignore_errors=True)

    def test_loop_inativo_e_inerte(self):
        st = self.armar()
        st["ativo"] = False
        self.loop.gravar(st)
        rc, saida = self.rodar()
        self.assertEqual(rc, 0)
        self.assertIsNone(saida)

    def test_sessao_diferente_e_ignorada(self):
        self.armar()
        rc, saida = self.rodar(sessao="outra-sessao")
        self.assertIsNone(saida)
        self.assertEqual(self.loop.ler()["iteracao"], 0)

    def test_auto_amarra_na_primeira_parada(self):
        # A skill arma de dentro da sessão e não conhece o próprio session_id;
        # quem fixa é a primeira parada. Mutação: remover a auto-amarração →
        # o loop nunca se prende e qualquer chat no repo passa a dirigi-lo.
        self.armar(session_id=None)
        _, saida = self.rodar(sessao="a-que-armou")
        self.assertEqual(saida["decision"], "block")
        self.assertEqual(self.loop.ler()["session_id"], "a-que-armou")
        _, outra = self.rodar(sessao="uma-terceira")
        self.assertIsNone(outra)

    def test_qualquer_sessao_quando_desamarrado(self):
        self.armar(bind_session=False)
        rc, saida = self.rodar(sessao="outra-sessao")
        self.assertEqual(saida["decision"], "block")


class TestContinuacao(Base):

    def test_doc_continua_apontando_o_proximo_item(self):
        self.armar()
        rc, saida = self.rodar(DOC)
        self.assertEqual(rc, 0)
        self.assertEqual(saida["decision"], "block")
        self.assertIn("3.1 Converter as observações", saida["reason"])
        self.assertIn("LOOP-WORK", saida["reason"])
        self.assertIn("Ninguém está lendo o chat", saida["reason"])

    def test_reason_carrega_contagem_e_objetivo(self):
        self.armar()
        _, saida = self.rodar(DOC)
        self.assertIn("1 feito(s), 2 pendente(s)", saida["reason"])
        self.assertIn("terminar a fase 3", saida["reason"])

    def test_ask_ganha_bloco_de_premissa(self):
        self.armar()
        _, saida = self.rodar(ASK)
        self.assertIn("ASSUMPTIONS.md", saida["reason"])
        self.assertIn("reversível", saida["reason"])
        self.assertTrue(os.path.exists(self.loop.p("ASSUMPTIONS.md")))

    def test_askuserquestion_no_transcript_vira_ask(self):
        self.armar()
        _, saida = self.rodar("Levantei as opções.", tool="AskUserQuestion")
        self.assertIn("AskUserQuestion", saida["reason"])

    def test_subagente_nao_e_confundido_com_o_agente_principal(self):
        # O sidechain termina em "?" — sem o filtro, todo turno com Explore
        # seria classificado como ASK.
        self.armar()
        _, saida = self.rodar(DOC)
        entry = self._entry(1)
        self.assertIn("kind: DOC", entry)
        self.assertNotIn("devo procurar mais", entry)

    def test_iteracao_avanca(self):
        self.armar()
        self.rodar(DOC)
        self.rodar(DOC)
        self.assertEqual(self.loop.ler()["iteracao"], 2)

    # ── auxiliares ──────────────────────────────────────────────────────────
    def _entry(self, n):
        alvo = [f for f in os.listdir(self.loop.entries)
                if f.startswith("%04d-" % n)]
        self.assertEqual(len(alvo), 1, "esperava 1 entry #%d, achei %s" % (n, alvo))
        with open(os.path.join(self.loop.entries, alvo[0]), encoding="utf-8") as f:
            return f.read()


class TestArquivo(Base):

    def test_entry_e_indice_sao_escritos(self):
        self.armar()
        self.rodar(DOC)
        entries = os.listdir(self.loop.entries)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].startswith("0001-DOC-"))
        with open(self.loop.p("INDEX.md"), encoding="utf-8") as f:
            idx = f.read()
        self.assertIn("| 0001 | DOC | relato | continuou |", idx)

    def test_entry_guarda_a_mensagem_original(self):
        self.armar()
        self.rodar(DOC)
        nome = os.listdir(self.loop.entries)[0]
        with open(os.path.join(self.loop.entries, nome), encoding="utf-8") as f:
            corpo = f.read()
        self.assertIn("212 testes · 212 ok", corpo)
        self.assertIn("## Mensagem original", corpo)

    def test_retorica_suprimida_fica_registrada(self):
        with open(FIXTURE_REAL, encoding="utf-8") as f:
            real = f.read()
        self.armar()
        self.rodar(real)
        nome = os.listdir(self.loop.entries)[0]
        with open(os.path.join(self.loop.entries, nome), encoding="utf-8") as f:
            corpo = f.read()
        self.assertIn("Retórica suprimida", corpo)
        self.assertIn("quantas outras estão assim?", corpo)


class TestColheita(Base):

    def setUp(self):
        super().setUp()
        with open(FIXTURE_REAL, encoding="utf-8") as f:
            self.real = f.read()

    def test_colhe_os_itens_do_fecho_para_a_fila(self):
        self.armar()
        _, saida = self.rodar(self.real)
        pend, _ = self.loop.contagem_fila()
        self.assertEqual(pend, 6)                    # 2 originais + 4 colhidos
        self.assertIn("entraram na fila", saida["reason"])
        with open(self.loop.p("QUEUE.md"), encoding="utf-8") as f:
            fila = f.read()
        self.assertIn("Colhidos automaticamente", fila)
        self.assertIn("respostas X1–Y2 do canal de voz", fila)

    def test_fila_ilegivel_nao_e_sobrescrita_por_esqueleto(self):
        # A colheita lê a fila para **reescrevê-la**. O fallback assumia
        # "# Fila do loop\n" em qualquer falha de leitura: com o arquivo
        # existindo e ilegível, isso gravava esqueleto por cima do contrato do
        # ciclo. Colheita é acessória; a fila não. Mutação: voltar o fallback
        # incondicional e a fila desaparece aqui.
        self.armar()
        with open(self.loop.p("QUEUE.md"), encoding="utf-8") as f:
            antes = f.read()
        os.chmod(self.loop.p("QUEUE.md"), 0o000)
        try:
            if os.access(self.loop.p("QUEUE.md"), os.R_OK):
                self.skipTest("processo lê arquivo sem permissão (root?)")
            self.loop.acrescentar_itens(["um item colhido"], "#0001")
        finally:
            os.chmod(self.loop.p("QUEUE.md"), 0o644)
        with open(self.loop.p("QUEUE.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)

    def test_nao_duplica_item_ja_colhido(self):
        self.armar()
        self.rodar(self.real)
        self.rodar(self.real)
        pend, _ = self.loop.contagem_fila()
        self.assertEqual(pend, 6)

    def test_proveniencia_nao_vaza_para_o_prompt(self):
        # O `<!-- colhido em #NNNN -->` é rastro de auditoria. Se entra na chave
        # de dedup o item é recolhido a cada parada; se entra no `reason`, vira
        # ruído no prompt. Os dois vazamentos aconteceram de verdade.
        self.armar()
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [ ] revisar o contrato  <!-- colhido em #0007 -->\n")
        _, saida = self.rodar(DOC)
        self.assertIn("revisar o contrato", saida["reason"])
        self.assertNotIn("colhido em", saida["reason"])

    def test_colheita_desligada(self):
        self.armar(colher_itens=False)
        self.rodar(self.real)
        self.assertEqual(self.loop.contagem_fila()[0], 2)


class TestGuardaCorpos(Base):

    def _encerrou(self, saida, motivo):
        self.assertIsNotNone(saida, "esperava aviso de encerramento")
        self.assertIn("LOOP-WORK ENCERROU", saida["reason"])
        self.assertIn(motivo, saida["reason"])
        # O aviso continua APONTANDO o caminho de notificar o dono...
        self.assertIn("avisar o Samir", saida["reason"])
        # ...mas em 17/08 deixou de MANDAR. O texto antigo dizia "**Não retome
        # o trabalho** … não resuma o histórico no chat", e como o loop e a
        # sessão compartilham tempo de vida essa ordem caía na parada de
        # qualquer turno — inclusive de trabalho que o loop não conduziu. Hook
        # que dá ordem sobre trabalho alheio tem autoridade aparente e pode
        # abortar rodada boa; hook que RELATA devolve a decisão a quem sabe o
        # que o turno era.
        self.assertIn("relatório, não uma instrução", saida["reason"])
        self.assertNotIn("Não retome o trabalho", saida["reason"])
        self.assertTrue(os.path.exists(self.loop.p("STATUS.md")))
        self.assertEqual(self.loop.ler()["fase"], "encerrando")

    def test_o_aviso_de_fim_e_ato_UNICO_por_rodada(self):
        """Em 17/08 a mesma rodada anunciou o próprio fim TRÊS vezes.

        As guardas de fase dependem de uma sequência de paradas acontecer. Se a
        sessão morre no meio, ou se a fila zera de novo depois de ganhar itens,
        a condição de fim é recalculada e o aviso sai outra vez — e a terceira
        caiu no meio de trabalho que não era do loop, com autoridade aparente
        de instrução do sistema.

        `notificado` é o único estado que não depende de sequência.
        """
        self.armar()
        self.zerar_a_fila()
        _, primeiro = self.rodar(DOC)
        self._encerrou(primeiro, "fila zerada")
        self.assertTrue(self.loop.ler()["notificado"],
                        "emitir o aviso tem de marcar a rodada como notificada")

        # o estado é forçado de volta ao que era ANTES da parada seguinte
        # consumir a fase — é exatamente o que uma sessão morta deixa para trás
        st = self.loop.ler()
        st["ativo"] = True
        st["fase"] = "encerrando"
        self.loop.gravar(st)

        _, segundo = self.rodar(DOC)
        self.assertIsNone(segundo,
                          "o segundo aviso não pode existir: o fim é ato único")

    def test_rodada_nova_tem_direito_ao_proprio_aviso(self):
        """O aperto não pode emudecer a rodada seguinte."""
        self.armar()
        st = self.loop.ler()
        st["notificado"] = True
        self.loop.gravar(st)

        self.armar()
        self.assertFalse(self.loop.ler()["notificado"],
                         "`armar` limpa a marca — rodada nova, aviso novo")

    def test_kill_switch_encerra(self):
        self.armar()
        open(self.loop.p("STOP"), "w").close()
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "kill-switch")

    def test_fila_zerada_encerra(self):
        # Sem relógio, a fila continua sendo o critério de pronto do ciclo
        # (ADR-006): quem armou por itens declarou onde a rodada acaba.
        self.armar()
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "fila zerada")

    # ── fila vazia sob relógio: reabastecer, não encerrar (ADR-015) ─────────

    def test_fila_zerada_com_relogio_reabastece(self):
        # O defeito medido: três rodadas do EOP armadas com `--duracao 6h` sobre
        # fila cheia de `- [x]` morreram na iteração 1, com ~5h50 sobrando, porque
        # `fila zerada` vinha antes do relógio na cadeia. Sob relógio a fila vazia
        # não é fim — é o gatilho do turno que enche a fila.
        # Mutação: tirar o `and not tem_relogio(st)` da cadeia e esta cai.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        self.assertEqual(saida["decision"], "block")
        self.assertNotIn("ENCERROU", saida["reason"])
        self.assertIn("REABASTECIMENTO", saida["reason"])
        self.assertIn("SEM-ESCOPO", saida["reason"])     # o escape, sempre à mão
        self.assertTrue(self.loop.ler()["ativo"])

    def test_janela_tambem_conta_como_relogio(self):
        # `--janela 08:00-18:00` declara tempo do mesmo jeito que `--duracao`;
        # ligar o reabastecimento só num dos dois seria arbitrário.
        self.armar(janela="00:00-23:59")
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        self.assertIn("REABASTECIMENTO", saida["reason"])

    def test_prompt_de_reabastecimento_diz_quanto_resta(self):
        # Um turno que não sabe quanto resta trata 8 minutos como trata 4 horas.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        self.assertIn("**6h00** de rodada", saida["reason"])

    def test_prompt_promete_o_menor_entre_janela_e_relogio(self):
        # Quando os dois estão de pé vale o MENOR: prometer 30h para um turno que
        # tem até o fim do dia faz ele começar leitura que não termina. Relógio
        # absurdo de propósito — a janela fecha no mesmo dia, qualquer que seja a
        # hora em que a suíte rode.
        self.armar(duracao_max_min=1800, janela="00:00-23:59")
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        resta = saida["reason"].split("e ainda há **")[1].split("**")[0]
        self.assertNotEqual(resta, "30h00")
        self.assertLess(int(resta.split("h")[0]), 24)

    def test_escopo_do_scope_md_vai_verbatim_no_prompt(self):
        # É onde mora o "para e pergunta" (ADR-014 cláusula 1). Reescrever a
        # fronteira do dono é a única coisa que o hook não pode fazer com ela.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        with open(self.loop.p("SCOPE.md"), "w", encoding="utf-8") as f:
            f.write("Entra: modelagem dos volumes 20-39.\n"
                    "Para e pergunta: qualquer coisa que toque cobrança.\n")
        _, saida = self.rodar(DOC)
        self.assertIn("volumes 20-39", saida["reason"])
        self.assertIn("Para e pergunta: qualquer coisa que toque cobrança",
                      saida["reason"])

    def test_sem_scope_md_o_prompt_diz_que_a_fronteira_nao_foi_declarada(self):
        # "Não sei onde parar" precisa chegar ao turno como fato. Senão ele infere
        # uma fronteira e chama de escopo.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        _, saida = self.rodar(DOC)
        self.assertIn("Nenhum escopo declarado", saida["reason"])
        self.assertIn("terminar a fase 3", saida["reason"])   # o objetivo responde

    def test_veredito_de_escopo_esgotado_encerra_a_rodada(self):
        # O escape da reposição (ADR-014 cláusula 2), agora com um fim próprio:
        # o agente mede que não há bloco em escopo, escreve os números, e a
        # rodada morre por veredito em vez de fabricar trabalho.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        with open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8") as f:
            f.write("Varri os 12 volumes e os 84 ADRs: 3 hipóteses, 3 mediram "
                    "zero.\nNada fora do já entregue.\n")
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "escopo esgotado")
        st = self.loop.ler()
        self.assertEqual(st["encerrado_por"], "escopo esgotado")
        self.assertIn("3 hipóteses", st["encerrado_detalhe"])
        with open(self.loop.p("STATUS.md"), encoding="utf-8") as f:
            status = f.read()
        self.assertIn("Veredito do agente", status)
        self.assertIn("3 mediram zero", status)

    def test_veredito_vence_a_fila_cheia(self):
        # O veredito é ordem de parar, não consequência de fila vazia: se o agente
        # o escreveu com itens ainda pendentes, é porque mediu que o que sobrou
        # não está em escopo. Encerrar depende dele, não da contagem.
        self.armar(duracao_max_min=360)
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "escopo esgotado")

    def test_kill_switch_ainda_vence_o_veredito(self):
        # Ordem do dono na frente de medição do agente — a cadeia não inverteu.
        self.armar(duracao_max_min=360)
        open(self.loop.p("STOP"), "w").close()
        open(self.loop.p("SEM-ESCOPO"), "w", encoding="utf-8").close()
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "kill-switch")

    def test_reabastecimento_improdutivo_encerra_por_sem_progresso(self):
        # A prova de que tirar a fila da cadeia não abriu loop infinito: três
        # turnos de reabastecimento que não mexem em nada — nem na fila, nem na
        # árvore — encerram pelo teto de degeneração, sozinhos.
        self.armar(duracao_max_min=360, max_sem_progresso=2)
        self.zerar_a_fila()
        _, s1 = self.rodar(DOC)
        self.assertIn("REABASTECIMENTO", s1["reason"])
        _, s2 = self.rodar(DOC)
        self.assertIn("REABASTECIMENTO", s2["reason"])
        _, s3 = self.rodar(DOC)
        self._encerrou(s3, "sem progresso")

    def test_reabastecer_de_verdade_devolve_o_prompt_normal(self):
        # A volta completa: o turno encheu a fila, então a parada seguinte já é
        # trabalho de item — com o item nomeado, como em qualquer outra parada.
        self.armar(duracao_max_min=360)
        self.zerar_a_fila()
        self.rodar(DOC)
        with open(self.loop.p("QUEUE.md"), "a", encoding="utf-8") as f:
            f.write("- [ ] 4.1 Modelar o inventário de fatos do VoIP\n")
        _, saida = self.rodar(DOC)
        self.assertNotIn("REABASTECIMENTO", saida["reason"])
        self.assertIn("4.1 Modelar o inventário", saida["reason"])

    def test_teto_de_iteracoes_encerra(self):
        st = self.armar(max_iteracoes=1)
        self.rodar(DOC)                      # iteração 1 — passa
        _, saida = self.rodar(DOC)           # iteração 2 — estoura
        self._encerrou(saida, "teto de iterações")

    def test_sem_progresso_encerra(self):
        # Nada muda entre as paradas: sem git, sem mexer na fila. É o agente
        # falando sem produzir — o modo de falha mais caro do loop.
        self.armar(max_sem_progresso=1)
        _, s1 = self.rodar(DOC)
        self.assertEqual(s1["decision"], "block")
        self.assertNotIn("ENCERROU", s1["reason"])
        _, s2 = self.rodar(DOC)
        self._encerrou(s2, "sem progresso")

    def test_progresso_na_fila_zera_o_contador(self):
        self.armar(max_sem_progresso=1)
        self.rodar(DOC)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA.replace("- [ ] 3.1", "- [x] 3.1"))
        _, saida = self.rodar(DOC)
        self.assertNotIn("ENCERROU", saida["reason"])
        self.assertEqual(self.loop.ler()["sem_progresso"], 0)

    def test_politica_parar_encerra_no_primeiro_ask(self):
        self.armar(politica_ask="parar")
        _, saida = self.rodar(ASK)
        self._encerrou(saida, "política ASK=parar")

    def test_politica_irreversivel_deixa_passar_pergunta_comum(self):
        self.armar(politica_ask="continuar-exceto-irreversivel")
        _, saida = self.rodar(ASK)
        self.assertNotIn("ENCERROU", saida["reason"])

    def test_politica_irreversivel_barra_acao_sem_volta(self):
        self.armar(politica_ask="continuar-exceto-irreversivel")
        _, saida = self.rodar("Preparei tudo.\n\n"
                              "Rodo o DROP TABLE nos dez schemas agora?")
        self._encerrou(saida, "ação irreversível")

    def test_politica_padrao_continua_mesmo_em_acao_sem_volta(self):
        # Decisão do Samir (16/08): o default é continuar sempre e registrar a
        # premissa. Quem quiser a cerca liga a política explicitamente.
        self.armar()
        _, saida = self.rodar("Preparei tudo.\n\n"
                              "Rodo o DROP TABLE nos dez schemas agora?")
        self.assertNotIn("ENCERROU", saida["reason"])

    def test_rodada_que_nasceu_morta_encerra_calada(self):
        # 17/08: três `armar` sobre uma fila 66/66 no EOP (paradas #20, #21, #22)
        # e três relatórios de encerramento injetados no turno de quem estava
        # fazendo outra coisa — cada rodada durou uma parada, com horas de
        # relógio sobrando. Nada aconteceu, então não há o que relatar.
        # Mutação: remover o `nada_aconteceu` e o `block` volta a sair.
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [x] tudo isto já era feito antes de armar\n")
        self.armar()
        self.assertEqual(self.loop.ler()["pendentes_ao_armar"], 0)
        rc, saida = self.rodar(DOC)
        self.assertEqual(rc, 0)
        self.assertIsNone(saida.get("reason") if saida else None)
        self.assertIn("nada a relatar", saida["systemMessage"])
        # O registro continua: encerrar calado não é encerrar sem rastro.
        self.assertTrue(os.path.exists(self.loop.p("STATUS.md")))
        self.assertEqual(self.loop.ler()["encerrado_por"], "fila zerada")
        self.assertFalse(self.loop.ler()["ativo"])

    def test_encerrar_na_primeira_parada_depois_de_trabalho_relata(self):
        # O outro lado da moeda: `--itens 1` fecha o escopo na primeira parada, e
        # ali houve rodada. Predicado largo demais silenciaria este relatório.
        self.armar(escopo_itens=1)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA.replace("- [ ] 3.1", "- [x] 3.1"))
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "escopo concluído")

    def test_estado_de_versao_anterior_relata(self):
        # `pendentes_ao_armar` ausente é "não sei", e "não sei" nunca vale zero:
        # `.loop/` armado por versão antiga continua relatando como antes.
        st = self.armar()
        del st["pendentes_ao_armar"]
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write("# Fila\n\n- [x] pronto\n")
        self.loop.gravar(st)
        _, saida = self.rodar(DOC)
        self._encerrou(saida, "fila zerada")

    def test_parada_seguinte_ao_aviso_encerra_de_verdade(self):
        self.armar()
        open(self.loop.p("STOP"), "w").close()
        self.rodar(DOC)                                  # avisa e pede push
        rc, saida = self.rodar("Notifiquei o Samir.")     # turno da notificação
        self.assertIsNone(saida)
        self.assertFalse(self.loop.ler()["ativo"])

    def test_encerramento_sem_notificacao(self):
        self.armar(notificar=False)
        open(self.loop.p("STOP"), "w").close()
        rc, saida = self.rodar(DOC)
        self.assertNotIn("decision", saida or {})
        self.assertIn("loop-work", (saida or {}).get("systemMessage", ""))
        self.assertFalse(self.loop.ler()["ativo"])


class TestCondicoesDeFim(Base):
    """Gatilhos de fim (ADR-010) — o que impede o loop de custar sem teto."""

    def test_escopo_por_numero_de_itens(self):
        self.armar(escopo_itens=1)
        _, s1 = self.rodar(DOC)
        self.assertNotIn("ENCERROU", s1["reason"])
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA.replace("- [ ] 3.1", "- [x] 3.1"))
        _, s2 = self.rodar(DOC)
        self.assertIn("escopo concluído", s2["reason"])

    def test_escopo_nao_conta_trabalho_de_rodadas_anteriores(self):
        # A fila já nasce com um `- [x]`. Sem `feitos_ao_armar` como
        # denominador, "fechar 1 item" encerraria na primeira parada.
        self.armar(escopo_itens=1)
        self.assertEqual(self.loop.ler()["feitos_ao_armar"], 1)
        _, saida = self.rodar(DOC)
        self.assertNotIn("ENCERROU", saida["reason"])

    def test_estado_guarda_o_detalhe_do_encerramento(self):
        # O detalhe morava só no STATUS.md, em prosa. Ele é o que separa duas
        # condições que dividem o mesmo motivo ("escopo concluído" por N itens ×
        # por marcador) — sem ele, quem lê o estado sabe QUE acabou e não sabe
        # POR QUAL das duas. Mutação: parar de gravar e o painel volta a marcar
        # a linha errada quando as duas condições estão armadas juntas.
        self.armar(escopo_itens=1)
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA.replace("- [ ] 3.1", "- [x] 3.1"))
        self.rodar(DOC)
        st = self.loop.ler()
        self.assertEqual(st["encerrado_por"], "escopo concluído")
        self.assertIn("fechados nesta rodada", st["encerrado_detalhe"])

    def test_escopo_por_marcador(self):
        self.armar(escopo_ate="Nomear a unicidade do token")
        _, s1 = self.rodar(DOC)
        self.assertNotIn("ENCERROU", s1["reason"])
        with open(self.loop.p("QUEUE.md"), "w", encoding="utf-8") as f:
            f.write(FILA.replace("- [ ] 3.2", "- [x] 3.2"))
        _, s2 = self.rodar(DOC)
        self.assertIn("escopo concluído", s2["reason"])
        self.assertIn("marcador alcançado", s2["reason"])

    def test_fora_da_janela_encerra(self):
        agora = __import__("datetime").datetime.now()
        # Janela de 1 minuto que já passou hoje: garante "fora" em qualquer hora.
        fim = (agora - __import__("datetime").timedelta(minutes=5))
        ini = fim - __import__("datetime").timedelta(minutes=1)
        self.armar(janela="%02d:%02d-%02d:%02d" % (ini.hour, ini.minute,
                                                   fim.hour, fim.minute))
        _, saida = self.rodar(DOC)
        self.assertIn("fora da janela", saida["reason"])
        with open(self.loop.p("STATUS.md"), encoding="utf-8") as f:
            self.assertIn("reabre", f.read())

    def test_dentro_da_janela_continua(self):
        self.armar(janela="00:00-23:59")
        _, saida = self.rodar(DOC)
        self.assertNotIn("ENCERROU", saida["reason"])

    def test_janela_invalida_nao_encerra(self):
        # Fail-open: typo em --janela não pode parar o trabalho em silêncio.
        self.armar(janela="oito às seis")
        _, saida = self.rodar(DOC)
        self.assertNotIn("ENCERROU", saida["reason"])

    def test_duracao_maxima_encerra(self):
        self.armar()
        st = self.loop.ler()
        st["duracao_max_min"] = 1
        st["armado_em"] = "2020-01-01T00:00:00+00:00"
        self.loop.gravar(st)
        _, saida = self.rodar(DOC)
        self.assertIn("duração máxima", saida["reason"])

    def test_duracao_dentro_do_teto_continua(self):
        self.armar(duracao_max_min=600)
        _, saida = self.rodar(DOC)
        self.assertNotIn("ENCERROU", saida["reason"])


class TestJanela(unittest.TestCase):
    """Aritmética da janela, isolada do ciclo."""

    def setUp(self):
        from datetime import datetime
        self.dt = datetime

    def _em(self, dia, hora, minuto=0):
        return self.dt(2026, 8, dia, hora, minuto)   # 10/08/2026 = segunda

    def test_dentro_e_fora_do_horario_comercial(self):
        from estado import fora_da_janela
        self.assertFalse(fora_da_janela("08:00-18:00", momento=self._em(10, 9)))
        self.assertTrue(fora_da_janela("08:00-18:00", momento=self._em(10, 19)))
        self.assertTrue(fora_da_janela("08:00-18:00", momento=self._em(10, 7, 59)))
        self.assertFalse(fora_da_janela("08:00-18:00", momento=self._em(10, 17, 59)))

    def test_janela_que_cruza_a_meia_noite(self):
        from estado import fora_da_janela
        self.assertFalse(fora_da_janela("22:00-06:00", momento=self._em(10, 23)))
        self.assertFalse(fora_da_janela("22:00-06:00", momento=self._em(10, 2)))
        self.assertTrue(fora_da_janela("22:00-06:00", momento=self._em(10, 12)))

    def test_dias_da_semana(self):
        from estado import fora_da_janela
        self.assertFalse(fora_da_janela("08:00-18:00", "seg-sex", self._em(14, 9)))
        self.assertTrue(fora_da_janela("08:00-18:00", "seg-sex", self._em(15, 9)))
        self.assertFalse(fora_da_janela("08:00-18:00", "sab,dom", self._em(15, 9)))

    def test_sem_janela_nunca_encerra(self):
        from estado import fora_da_janela
        self.assertFalse(fora_da_janela(None, momento=self._em(10, 3)))

    def test_parse_duracao(self):
        from estado import parse_duracao
        self.assertEqual(parse_duracao("6h"), 360)
        self.assertEqual(parse_duracao("90m"), 90)
        self.assertEqual(parse_duracao("2h30"), 150)
        self.assertEqual(parse_duracao("45"), 45)
        self.assertIsNone(parse_duracao("seis horas"))
        self.assertIsNone(parse_duracao(None))


class TestFailOpen(Base):
    """Hook quebrado nunca pode travar a sessão (SECURITY.md T-05)."""

    def test_stdin_invalido(self):
        rc, saida = self.rodar(bruto="isto não é json")
        self.assertEqual(rc, 0)
        self.assertIsNone(saida)

    def test_stdin_vazio(self):
        rc, saida = self.rodar(bruto="")
        self.assertEqual(rc, 0)
        self.assertIsNone(saida)

    def test_transcript_inexistente(self):
        self.armar()
        rc, saida = self.rodar(bruto=json.dumps({
            "session_id": self.sessao,
            "transcript_path": "/caminho/que/nao/existe.jsonl",
            "cwd": self.tmp, "hook_event_name": "Stop"}))
        self.assertEqual(rc, 0)
        # Sem mensagem legível, classifica como DOC vazio e segue: perder o
        # transcript não pode significar perder o loop.
        self.assertEqual(saida["decision"], "block")

    def test_state_json_corrompido(self):
        self.armar()
        with open(self.loop.p("STATE.json"), "w", encoding="utf-8") as f:
            f.write("{quebrado")
        rc, saida = self.rodar(DOC)
        self.assertEqual(rc, 0)
        self.assertIsNone(saida)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ── a porta: a adoção de sessão é escolhida, nunca herdada ──────────────────
class TestArmarNaoAdotaSessaoPorOmissao(Base):
    """A guarda de 02/09, e ela mora na PORTA porque o hook já é tarde.

    `bind_session: true` com `session_id: null` amarra à PRIMEIRA sessão que
    para no repositório — qualquer chat já aberto ali serve. Numa rodada real do
    EOP isso adotou a sessão que o dono havia aberto para outra coisa, e o custo
    foi 18 entradas de diário no item errado, 4 itens espúrios colhidos de
    fragmentos daquelas mensagens e duas sessões dirigindo a mesma árvore.

    A guarda **não proíbe** — quem arma de um shell não sabe o próprio
    `session_id`, e recusar sem saída viraria `--force` na semana seguinte. Ela
    exige que a adoção seja **dita**.
    """

    def ctl(self, *args):
        proc = subprocess.run([sys.executable, CTL] + list(args),
                              capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout + proc.stderr

    def armar_pelo_cli(self, *extra):
        return self.ctl("armar", "--raiz", self.tmp,
                        "--objetivo", "fechar a fase 3", *extra)

    def test_sem_flag_nenhuma_recusa_e_nomeia_as_TRES_saidas(self):
        rc, saida = self.armar_pelo_cli()
        self.assertEqual(rc, 2, saida)
        for saida_esperada in ("--sessao", "--adotar-primeira-parada",
                               "--qualquer-sessao"):
            self.assertIn(saida_esperada, saida,
                          "recusar sem nomear as saídas é guarda que atrapalha")

    def test_a_recusa_NAO_deixa_loop_meio_armado(self):
        # Metade do defeito que ela previne é estado gravado antes da escolha:
        # um `.loop/` armado com adoção pendente não passa a obedecer a guarda
        # depois (foi a lição do `¨¨` do EOP, no `0.2.3`).
        self.armar_pelo_cli()
        st = self.loop.ler()
        # `None` é o desfecho mais forte: não gravou NADA. Aceitar também
        # "gravou e não ativou" seria absolver um meio-armar que o `retomar`
        # depois reativaria sem passar pela escolha.
        self.assertIsNone(st, "o armar recusou e ainda assim gravou estado")

    def test_com_sessao_explicita_arma_e_grava_o_id(self):
        rc, saida = self.armar_pelo_cli("--sessao", "sessao-123")
        self.assertEqual(rc, 0, saida)
        st = self.loop.ler()
        self.assertTrue(st["ativo"])
        self.assertEqual(st["session_id"], "sessao-123")
        self.assertTrue(st["bind_session"])

    def test_adotar_primeira_parada_arma_com_o_comportamento_ANTIGO(self):
        # o padrão histórico continua alcançável — o que mudou é ele ser dito
        rc, saida = self.armar_pelo_cli("--adotar-primeira-parada")
        self.assertEqual(rc, 0, saida)
        st = self.loop.ler()
        self.assertTrue(st["bind_session"])
        self.assertIsNone(st["session_id"])
        self.assertIn("ADOÇÃO PEDIDA", saida,
                      "o resumo tem de dizer que a adoção foi escolhida, senão "
                      "a linha `a primeira que parar` volta a parecer default")

    def test_qualquer_sessao_arma_sem_amarrar(self):
        rc, saida = self.armar_pelo_cli("--qualquer-sessao")
        self.assertEqual(rc, 0, saida)
        st = self.loop.ler()
        self.assertFalse(st["bind_session"])
        self.assertIn("não amarra", saida)
