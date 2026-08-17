#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes do classificador ASK × DOC.

Regra de aceite herdada do AUDITOR: **cada teste precisa falhar com o controle
desligado.** Os dois controles que importam aqui são a supressão de retórica e a
zona de fecho — neutralizar qualquer um derruba os testes marcados com
`# mutação:`.

O caso `fixtures/relato-fitness-schema.txt` é uma mensagem **real** do agente
(16/08/2026), colada pelo Samir como o exemplo do problema. Ela quebra o detector
ingênuo nos dois sentidos ao mesmo tempo — por isso é regressão, não sintético.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "skill", "loop", "lib"))

import classificador as c   # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(nome):
    with open(os.path.join(FIXTURES, nome), encoding="utf-8") as f:
        return f.read()


class TestMensagemReal(unittest.TestCase):
    """Regressão: a mensagem que originou o projeto."""

    def setUp(self):
        self.r = c.classificar(fixture("relato-fitness-schema.txt"))

    def test_e_ask_por_handoff_e_nao_por_pontuacao(self):
        # O fecho não tem um único `?`. Detector de pontuação diria DOC e o
        # Samir ficaria 10 minutos parado com a lista pronta na mesa.
        self.assertEqual(self.r.kind, "ASK")
        self.assertEqual(self.r.sinal, "handoff")
        self.assertNotIn("?", "\n".join(self.r.fecho))

    def test_retorica_da_narrativa_nao_vira_pergunta(self):
        # mutação: desligar a supressão de retórica → sinal vira
        # "pergunta-narrativa" e este teste falha.
        self.assertEqual(len(self.r.retoricas), 1)
        self.assertIn("quantas outras estão assim?", self.r.retoricas[0])
        self.assertEqual(self.r.perguntas, [])

    def test_colhe_os_quatro_itens_do_fecho(self):
        self.assertEqual(len(self.r.itens), 4)
        self.assertTrue(self.r.itens[0].startswith("a convenção do default no OpenAPI"))
        self.assertIn("✦A", self.r.itens[1])
        self.assertIn("X1–Y2", self.r.itens[3])

    def test_parenteses_nao_sao_partidos(self):
        # "(coluna versao na Etapa e no Intervalo)" tem " e no " dentro —
        # mutação: split ingênuo por " e " racha o item em dois.
        self.assertIn("(coluna versao na Etapa e no Intervalo)", self.r.itens[2])

    def test_zona_de_fecho_sao_os_dois_ultimos_paragrafos(self):
        self.assertEqual(len(self.r.fecho), 2)
        self.assertTrue(self.r.fecho[-1].startswith("Daqui pra frente"))


class TestMensagemRealSemPergunta(unittest.TestCase):
    """Regressão 2: 9m16s de produção, zero perguntas, parada mesmo assim.

    O caso puro do problema — não há nada a decidir, o agente só encerrou o
    turno. E o item mais valioso da mensagem não é pergunta nenhuma: é a seção
    "Declarado e não feito", onde ele mesmo nomeia o próximo trabalho.
    """

    def setUp(self):
        self.r = c.classificar(fixture("relato-corrida-instancia.txt"))

    def test_e_doc(self):
        self.assertEqual(self.r.kind, "DOC")
        self.assertEqual(self.r.sinal, "relato")
        self.assertEqual(self.r.confianca, "alta")

    def test_nao_inventa_pergunta(self):
        self.assertEqual(self.r.perguntas, [])
        self.assertEqual(self.r.retoricas, [])

    def test_colhe_a_pendencia_que_o_agente_declarou(self):
        # mutação: esvaziar DECLARADO_PENDENTE → o loop segue sem fila nova e
        # o único trabalho nomeado na mensagem se perde.
        self.assertEqual(len(self.r.itens), 1)
        self.assertIn("sem teste para a guarda deles", self.r.itens[0])

    def test_rotulo_em_negrito_nao_entra_no_item(self):
        self.assertFalse(self.r.itens[0].startswith("**"))
        self.assertNotIn("Declarado e não feito", self.r.itens[0])


class TestDoc(unittest.TestCase):

    def test_relato_puro(self):
        r = c.classificar(
            "Migrei os três schemas e rodei a suíte.\n\n"
            "412 testes · 412 ok · 0 falhas. Commitei em 2.3.1 e pushei.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(r.sinal, "relato")
        self.assertEqual(r.confianca, "alta")

    def test_retorica_seguida_de_resposta_no_mesmo_paragrafo(self):
        # mutação: remover a regra R2 (respondida no mesmo parágrafo) →
        # vira ASK e o loop registra pergunta que ninguém fez.
        r = c.classificar(
            "Corrigi o índice. Faltava saber: quantos outros estavam assim? "
            "Varri os dez schemas e não sobrou nenhum.\n\n"
            "Suíte verde, 88 testes.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(len(r.retoricas), 1)

    def test_pergunta_dentro_de_bloco_de_codigo_nao_conta(self):
        # mutação: não remover fences → ASK.
        r = c.classificar(
            "Ajustei o parser.\n\n"
            "```python\nif x:  # e se vier vazio?\n    pass\n```\n\n"
            "Cobri com 4 casos, 12 testes ok.")
        self.assertEqual(r.kind, "DOC")

    def test_texto_vazio(self):
        r = c.classificar("")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(r.sinal, "vazio")


class TestAsk(unittest.TestCase):

    def test_pergunta_direta_no_fecho(self):
        r = c.classificar(
            "Refiz o mapeamento de erro nas 140 operações.\n\n"
            "Mantenho o fallback de senha ou removo de vez?")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(r.sinal, "pergunta-direta")
        self.assertEqual(r.confianca, "alta")

    def test_pergunta_no_fecho_vale_mesmo_seguida_de_frase(self):
        # No fecho não há supressão: "?" seguido de texto continua sendo
        # pergunta aberta — mutação: aplicar R2 também no fecho derruba isto.
        r = c.classificar(
            "Fiz o levantamento.\n\n"
            "Removo o endpoint antigo? Fico esperando para não quebrar o app.")
        self.assertEqual(r.kind, "ASK")

    def test_tool_askuserquestion_curto_circuita(self):
        r = c.classificar("Levantei as opções.", ultimo_tool="AskUserQuestion")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(r.sinal, "tool")

    def test_handoff_sem_interrogacao(self):
        r = c.classificar(
            "Fechei os dois ajustes e a suíte está verde.\n\n"
            "O resto fica do teu lado: a revisão do contrato e o aval do deploy.")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(r.sinal, "handoff")

    def test_espera_explicita(self):
        r = c.classificar(
            "Preparei a migração em staging.\n\n"
            "Aguardo teu ok antes de aplicar em produção.")
        self.assertEqual(r.kind, "ASK")

    def test_pergunta_na_narrativa_nao_respondida(self):
        r = c.classificar(
            "Comecei pelo billing. Devo tratar o legado de 2019 também?\n\n"
            "Enquanto isso segui pelos schemas novos.\n\n"
            "Mais nada por ora, 30 testes ok.")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(r.sinal, "pergunta-narrativa")
        self.assertEqual(r.confianca, "media")


class TestColheita(unittest.TestCase):

    def test_lista_markdown_no_fecho(self):
        r = c.classificar(
            "Terminei a fase 2.\n\n"
            "Fica do teu lado:\n"
            "- revisar o contrato do webhook\n"
            "- decidir o timeout do retry\n"
            "- aprovar o schema novo")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(len(r.itens), 3)
        self.assertIn("timeout do retry", r.itens[1])

    def test_declarado_pendente_em_lista(self):
        r = c.classificar(
            "Entreguei a fase 2, 90 testes ok.\n\n"
            "Fica para a próxima rodada:\n"
            "- cobrir o Contrato com teste de guarda\n"
            "- cobrir o Produto com teste de guarda")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(len(r.itens), 2)

    def test_declarado_pendente_fora_do_fecho(self):
        # A seção pode vir no meio: a varredura de declarados é do texto todo.
        r = c.classificar(
            "Comecei pela borda.\n\n"
            "Ficou de fora o retry do webhook, que depende do contrato novo.\n\n"
            "Segui pelos schemas e fechei os três. 40 testes ok.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(len(r.itens), 1)
        self.assertIn("retry do webhook", r.itens[0])

    def test_sem_handoff_nao_colhe_prosa(self):
        # Enumeração em prosa só vira item quando o parágrafo é handoff —
        # senão todo relato com dois-pontos viraria fila.
        r = c.classificar(
            "Entreguei três coisas.\n\n"
            "O saldo: a migração, o índice e o teste de regressão.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(r.itens, [])


class TestAPerguntaNaoEItem(unittest.TestCase):
    """Emenda ao ADR-005: colher segue independente do veredito; o que muda é
    **o quê** se colhe. Pergunta não é trabalho declarado pendente."""

    def test_pergunta_do_fecho_nao_vira_item(self):
        # O caso real do EOP (17/08): `\\bsigo (?:com|por|para|pra)\\b` é HANDOFF,
        # o parágrafo tem `:`, e o `rsplit(':')` da colheita transformou a
        # própria pergunta em item — com o `**` do negrito partido na frente.
        # Ela foi marcada `- [x]`, zerou a fila e encerrou a rodada.
        # Mutação: desligar `_sem_as_perguntas` e o item volta.
        r = c.classificar(
            "Fechei o discriminador e os 12 testes passam.\n\n"
            "**Pergunta:** sigo com esse discriminador, ou você quer a guarda "
            "de fato-sem-listener mesmo assim?")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(len(r.perguntas), 1)
        self.assertEqual(r.itens, [])

    def test_pergunta_nao_engole_o_trabalho_declarado_ao_lado(self):
        # O filtro tira a pergunta, não a colheita: o que é item continua item.
        r = c.classificar(
            "Fechei o parser.\n\n"
            "Ficou para a próxima rodada:\n"
            "- cobrir o Contrato com teste de guarda\n"
            "- revisar o timeout do retry\n\n"
            "**Pergunta:** sigo com esse discriminador, ou prefere a guarda?")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(len(r.itens), 2)
        self.assertTrue(any("teste de guarda" in i for i in r.itens))
        self.assertFalse(any("sigo com esse discriminador" in i for i in r.itens))

    def test_retorica_tambem_nao_vira_item(self):
        # Retórica é pergunta que o próprio texto responde. Mandá-la para a fila
        # seria pedir ao agente que refizesse o que ele acabou de concluir.
        r = c.classificar(
            "Por que o índice não entrou? Porque a tabela ainda não existe — "
            "criei a migração antes e o índice foi junto.\n\n"
            "Fica do teu lado: aprovar o schema novo.")
        self.assertEqual(r.kind, "ASK")
        self.assertFalse(any("por que o indice" in c._norm(i) for i in r.itens))
        self.assertTrue(any("aprovar o schema" in i for i in r.itens))

    def test_colheita_segue_valendo_para_doc(self):
        # ADR-005 intacto: o filtro roda nos dois vereditos, não só em ASK.
        r = c.classificar(
            "Entreguei a fase 2, 90 testes ok.\n\n"
            "Ficou de fora o retry do webhook, que depende do contrato novo.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(len(r.itens), 1)

    def test_item_curto_passa_em_vez_de_sumir(self):
        # Contenção com alvo curto acha qualquer coisa dentro de pergunta longa.
        # Errar colhendo a mais deixa uma linha extra na fila; errar colhendo a
        # menos apaga trabalho declarado — e só o segundo é silencioso.
        self.assertFalse(c._e_a_pergunta("subir", ["subir o índice agora?"]))

    def test_marcacao_solta_nao_entra_na_fila(self):
        # `**Pendente:** rodar o lint` deixava `** rodar o lint` na fila.
        r = c.classificar(
            "Fechei o parser.\n\n"
            "**Fica do teu lado:** revisar o contrato do webhook")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(len(r.itens), 1)
        self.assertFalse(r.itens[0].startswith("*"))


class TestZonaDeFecho(unittest.TestCase):

    def test_mensagem_de_um_paragrafo_e_toda_fecho(self):
        self.assertEqual(len(c.zona_de_fecho(["só isso aqui"])), 1)

    def test_sao_sempre_os_dois_ultimos(self):
        paras = ["a" * 200, "b" * 200, "c" * 200, "d" * 200]
        self.assertEqual(c.zona_de_fecho(paras), paras[-2:])

    def test_fecho_curto_nao_engole_a_narrativa(self):
        # Regressão do bug de desenho original: acumular por caractere fazia o
        # fecho crescer até tomar o texto inteiro, desligando a leitura de zona.
        paras = ["a" * 400, "b" * 400, "ok", "fim"]
        self.assertEqual(c.zona_de_fecho(paras), ["ok", "fim"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
