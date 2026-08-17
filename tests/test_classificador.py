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

    def test_handoff_que_descreve_estado_para_o_loop_mas_nao_enche_a_fila(self):
        """QUINTA ocorrência — e a mensagem que a causou DESCREVIA o defeito.

        `"apertá-los continua sendo sua decisão"` casou
        `(sua|tua) (decisão|chamada|escolha)`, virou ASK e colheu um item — o
        custo que a própria frase chamava de hipotético.

        As duas metades do sinal têm direção de erro OPOSTA, e é por isso que
        elas se separam: parar demais custa uma interrupção (seguro); encher a
        fila custa trabalho fabricado que alguém apaga à mão (inseguro). O
        `ASK` fica, a colheita sai.
        """
        r = c.classificar(
            "Rodada fechada, 186 testes verdes.\n\n"
            "A HANDOFF ainda tem dois falsos positivos medidos, e apertá-los "
            "continua sendo sua decisão, porque troca falha segura por insegura.")
        self.assertEqual(r.kind, "ASK", "o loop deve seguir PARANDO — é o lado seguro")
        self.assertEqual(r.itens, [], "mas relatar de quem é a decisão não é item")

    def test_handoff_que_pede_acao_continua_enchendo_a_fila(self):
        """O aperto não pode matar o sinal legítimo: pedido continua colhendo."""
        r = c.classificar(
            "Fechei a fase 2.\n\n"
            "Fica do teu lado:\n"
            "- revisar o contrato do webhook\n"
            "- decidir o timeout do retry")
        self.assertEqual(r.kind, "ASK")
        self.assertEqual(len(r.itens), 2)

    def test_lista_de_trabalho_FEITO_no_fecho_nao_vira_fila(self):
        """QUARTA colheita errada da mesma rodada, e por um ramo novo.

        O ramo de LISTA do `colher_itens` disparava em qualquer bullet do
        fecho, sem exigir sinal nenhum — enquanto o ramo de PROSA logo abaixo
        sempre exigiu handoff. A assimetria era o defeito: um "Saldo da
        rodada:" com seis marcadores de trabalho **feito** virou seis itens de
        fila, que alguém teve de apagar à mão.

        Nenhum discriminador por CONTEÚDO do item resolveria — medido em 17/08:
        a lista `RELATO` casa zero tanto nos seis relatos quanto nos seis
        pendentes de verdade. O que separa é o parágrafo que INTRODUZ a lista.
        """
        r = c.classificar(
            "Rodada fechada.\n\n"
            "**Saldo da rodada:**\n"
            "- dois instrumentos que não provavam que rodavam agora provam\n"
            "- avisos 17 → 8, cada um com dono declarado\n"
            "- um bloco morto na triagem, que evitou uma guarda sem sinal")
        self.assertEqual(r.itens, [], "relato em bullets não é fila")

    def test_lista_de_trabalho_PENDENTE_no_fecho_continua_colhendo(self):
        """O aperto não pode matar o uso legítimo, que é o irmão exato."""
        r = c.classificar(
            "Rodada fechada.\n\n"
            "Fica do teu lado:\n"
            "- revisar o contrato do webhook\n"
            "- decidir o timeout do retry")
        self.assertEqual(len(r.itens), 2)

    # ── a catraca: forma do padrão, não cobertura ────────────────────────
    #
    # Três marcadores da DECLARADO_PENDENTE morderam em 17/08 — `próxima
    # rodada`, `próximo ciclo`, `não coberto` — e os três foram consertados um
    # a um. Conserto sem catraca volta no próximo padrão que alguém escrever, e
    # esta lista é a que alimenta a FILA DE TRABALHO: um marcador que casa
    # narrativa não gera aviso, gera item que um humano precisa reconhecer como
    # prosa e apagar à mão.

    #: Verbos e locuções de ADIAMENTO. Lista explícita de propósito — regex
    #: adivinhando "o que parece verbo" foi o erro que produziu quatro medições
    #: inúteis no EOP no mesmo dia. O que não estiver aqui não conta.
    #:
    #: Os tokens são comparados contra a FONTE do padrão, que é regex — por isso
    #: entram em pedaço curto (`declarado`, não `declarado e não feito`): o
    #: padrão real escreve `n[ãa]o`, e a locução inteira nunca casaria. O
    #: primeiro corte deste teste reprovou justamente o `declarado e não feito`,
    #: que é um dos marcadores BONS.
    VERBOS_DE_ADIAMENTO = (
        "fica", "ficam", "ficou", "ficaram", "vai", "vão", "deixo", "deixamos",
        "adiad", "entra", "entram", "sobra", "sobram", "resta", "restam",
        "falta", "faltam", "pend", "declarado", "candidato",
        "fora de", "fora do", "fora deste", "not done", "left", "follow",
        "next", "out of scope",
    )

    def test_todo_marcador_de_pendencia_tem_verbo_ou_exige_pontuacao(self):
        """Padrão NU é o modo de falha, e ele reincidiu três vezes em 17/08.

        A regra que os doze marcadores bons cumprem: ou o padrão carrega verbo
        de adiamento (`fica para a próxima`, `ficou de fora`), ou exige a
        pontuação que ANUNCIA itens (`:`). Sintagma solto casa narrativa — e
        como o `colher_declarados` pega a primeira frase do parágrafo quando
        não há lista, o item que nasce **nem é a frase que casou**.
        """
        nus = [p for p in c.DECLARADO_PENDENTE
               if not self._tem_verbo(p) and not self._exige_dois_pontos(p)]
        self.assertEqual(
            nus, [],
            "marcador sem verbo de adiamento e sem `:` casa prosa e vira item "
            "de fila: acrescente o verbo, exija `\\s*:`, ou entre na lista "
            "VERBOS_DE_ADIAMENTO com o motivo")

    def test_a_catraca_reprova_o_nu_e_absolve_os_dois_formatos_bons(self):
        """PROVA DE EXECUÇÃO da catraca acima, nos dois sentidos."""
        nu = r"\bsegunda etapa\b"
        com_verbo = r"\bfica para a segunda etapa\b"
        com_pontuacao = r"\bsegunda etapa\s*:"

        self.assertFalse(self._tem_verbo(nu) or self._exige_dois_pontos(nu),
                         "o sintagma nu tem de ser reprovado")
        self.assertTrue(self._tem_verbo(com_verbo), "verbo de adiamento absolve")
        self.assertTrue(self._exige_dois_pontos(com_pontuacao),
                        "exigir `:` absolve")
        self.assertFalse(self._exige_dois_pontos(r"\bfoo\b:bar"),
                         "`:` no meio do padrão não é exigência de anúncio — só "
                         "conta no FIM, que é onde o cabeçalho o põe")

    @classmethod
    def _tem_verbo(cls, padrao):
        alvo = padrao.lower()
        return any(v in alvo for v in cls.VERBOS_DE_ADIAMENTO)

    @staticmethod
    def _exige_dois_pontos(padrao):
        return padrao.rstrip().endswith(":")

    def test_narrativa_sobre_a_proxima_rodada_nao_vira_item(self):
        """O sintagma nu era o gatilho: TRÊS colheitas erradas em 17/08.

        A frase abaixo é a última linha de um relatório de fecho — ela fala
        sobre para que serve um REGISTRO, não declara trabalho. Sem os
        dois-pontos, `próxima rodada` é substantivo de narrativa, e o
        `colher_declarados` (que varre o texto inteiro, não só o fecho) puxava
        a primeira frase do parágrafo para a fila. O item que nasceu daí —
        "Proxy de palavra-chave errou em três dessas medições..." — foi para o
        QUEUE.md do EOP e teve de ser removido à mão.
        """
        r = c.classificar(
            "Fechei a conferência, 475 testes verdes.\n\n"
            "Proxy de palavra-chave errou em três dessas medições e no primeiro "
            "corte de uma quarta. A tabela das sete ficou no QUEUE.md para a "
            "próxima rodada não repetir a varredura.")
        self.assertEqual(r.kind, "DOC")
        self.assertEqual(r.itens, [], "narrativa não é declaração de pendência")

    def test_proxima_rodada_com_dois_pontos_continua_colhendo(self):
        """O aperto não pode matar o uso legítimo — que é ANUNCIAR itens."""
        r = c.classificar(
            "Entreguei o parser.\n\n"
            "Na próxima rodada:\n"
            "- extrair a máquina de estados da C6\n"
            "- cobrir a S4 com entrada sintética")
        self.assertEqual(len(r.itens), 2)

    def test_nao_coberto_como_adjetivo_de_narrativa_nao_vira_item(self):
        """O terceiro sintagma nu da lista, achado varrendo os outros dois.

        `não coberto` descreve ALCANCE ("o REVOKE não cobre o UPDATE"), e a
        frase inteira virava item. É o mesmo formato de `próxima rodada` e
        `próximo ciclo` — substantivo/adjetivo sem verbo de adiamento —, e os
        três eram os únicos assim na lista que alimenta a fila.
        """
        r = c.classificar(
            "Fechei a guarda, 475 testes verdes.\n\n"
            "O que o REVOKE não cobre é o UPDATE no lançamento, e esse caminho "
            "ficou não coberto pela imutabilidade do banco — é a metade que a "
            "cadeia de hash resolve.")
        self.assertEqual(r.itens, [], "alcance de um controle não é pendência")

    def test_nao_coberto_como_cabecalho_continua_colhendo(self):
        r = c.classificar(
            "Entreguei a fase 2.\n\n"
            "Não coberto:\n"
            "- o caminho de estorno sob concorrência\n"
            "- a régua com feriado bancário")
        self.assertEqual(len(r.itens), 2)

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
