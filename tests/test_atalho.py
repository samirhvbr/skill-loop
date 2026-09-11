#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de `.loop/loop.sh` — o atalho que `armar` semeia no repositório alvo.

Duas metades. A primeira olha a **semeadura**: quem escreve, quando, e o que
nunca sobrescreve. A segunda **executa o script gerado**, com `loop-ctl` e
`loop-watch` substituídos por stubs à frente do `PATH` — é a única forma de
provar que a raiz derivada, o argumento de duração e o `set -e` fazem o que a
documentação promete. Testar só o texto do arquivo passaria por cima de tudo
que pode quebrar num shell.

Regra de aceite da casa: cada teste cai com o controle desligado.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTL = os.path.join(RAIZ, "skill", "loop", "loop_ctl.py")
MOLDE = os.path.join(RAIZ, "skill", "loop", "templates", "loop.sh")

FILA_COM_PENDENTE = "# Fila\n\n- [ ] item de verdade\n"
FILA_ZERADA = "# Fila\n\n- [x] item já feito\n"


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-atalho-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    @property
    def atalho(self):
        return os.path.join(self.tmp, ".loop", "loop.sh")

    def fila(self, texto):
        os.makedirs(os.path.join(self.tmp, ".loop"), exist_ok=True)
        with open(os.path.join(self.tmp, ".loop", "QUEUE.md"), "w",
                  encoding="utf-8") as f:
            f.write(texto)

    def armar(self, *extra):
        proc = subprocess.run(
            [sys.executable, CTL, "armar", "--raiz", self.tmp,
             "--qualquer-sessao"] + list(extra),
            capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout + proc.stderr


class TestSemeadura(Base):
    """Quem escreve o atalho, quando — e o que ele nunca faz."""

    def test_armar_cria_o_atalho_executavel(self):
        rc, saida = self.armar()
        self.assertEqual(rc, 0, saida)
        self.assertTrue(os.path.isfile(self.atalho),
                        "armar não semeou .loop/loop.sh")
        modo = os.stat(self.atalho).st_mode
        self.assertTrue(modo & stat.S_IXUSR,
                        "atalho sem bit de execução é atalho que ninguém chama")

    def test_o_armar_anuncia_o_atalho_so_quando_cria(self):
        _, primeira = self.armar()
        self.assertIn("loop.sh", primeira,
                      "criar o arquivo e não dizer é criar arquivo invisível")
        _, segunda = self.armar()
        self.assertNotIn("atalho     :", segunda,
                         "anunciar de novo faria parecer que reescreveu")

    def test_o_arquivo_gerado_e_bash_valido(self):
        self.armar()
        proc = subprocess.run(["bash", "-n", self.atalho],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_nenhum_placeholder_sobra_e_o_caminho_e_absoluto(self):
        self.armar()
        with open(self.atalho, encoding="utf-8") as f:
            texto = f.read()
        self.assertNotIn("@LOOP", texto,
                         "placeholder não substituído vira `python3 @LOOP_CTL_PY@`")
        self.assertIn(os.path.join(RAIZ, "skill", "loop", "loop_ctl.py"), texto)
        self.assertIn(os.path.join(RAIZ, "skill", "loop", "loop_watch.py"), texto)

    def test_a_raiz_NAO_e_escrita_literalmente(self):
        # O defeito do loop.sh do EOP: `--raiz ~/x/EOP` no corpo do arquivo, o
        # que o prende a um repositório e morre no primeiro clone.
        self.armar()
        with open(self.atalho, encoding="utf-8") as f:
            texto = f.read()
        self.assertNotIn(self.tmp, texto,
                         "a raiz tem de ser derivada do caminho do script")
        self.assertIn("BASH_SOURCE", texto)

    def test_nunca_sobrescreve_o_atalho_do_dono(self):
        self.armar()
        meu = "#!/usr/bin/env bash\n# editado pelo dono\necho meu\n"
        with open(self.atalho, "w", encoding="utf-8") as f:
            f.write(meu)
        rc, saida = self.armar()
        self.assertEqual(rc, 0, saida)
        with open(self.atalho, encoding="utf-8") as f:
            self.assertEqual(f.read(), meu,
                             "armar apagou a configuração do dono")

    def test_armar_recusado_nao_deixa_atalho_atras(self):
        # Fila zerada e sem relógio: a guarda recusa antes de gravar estado, e
        # comando que recusa não pode ter deixado arquivo no disco.
        self.fila(FILA_ZERADA)
        rc, saida = self.armar()
        self.assertEqual(rc, 2, saida)
        self.assertFalse(os.path.exists(self.atalho),
                         "a semeadura correu antes das guardas")

    def test_semeadura_nao_derruba_o_armar_quando_o_molde_some(self):
        # Fail-open: o estado já está gravado quando a semeadura acontece.
        molde_falso = os.path.join(self.tmp, "skill-sem-molde")
        shutil.copytree(os.path.join(RAIZ, "skill", "loop"), molde_falso)
        os.remove(os.path.join(molde_falso, "templates", "loop.sh"))
        proc = subprocess.run(
            [sys.executable, os.path.join(molde_falso, "loop_ctl.py"), "armar",
             "--raiz", self.tmp, "--qualquer-sessao"],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0,
                         proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(self.atalho))


class TestExecucao(Base):
    """O script gerado, rodando — com stubs no lugar de `loop-ctl`/`loop-watch`."""

    def setUp(self):
        super().setUp()
        self.armar()
        self.bin = tempfile.mkdtemp(prefix="loop-stub-bin-")
        self.addCleanup(shutil.rmtree, self.bin, ignore_errors=True)
        self.log_ctl = os.path.join(self.bin, "ctl.log")
        self.log_watch = os.path.join(self.bin, "watch.log")

    def armar(self, *extra):
        # o `armar` da semeadura roda de verdade; só a EXECUÇÃO usa stub
        return super().armar(*extra)

    def stub(self, nome, log, saida=0):
        caminho = os.path.join(self.bin, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "'
                    + log + '"\nexit ' + str(saida) + "\n")
        os.chmod(caminho, 0o755)

    #: um id com a FORMA de session_id — é ela que o script reconhece
    SESSAO = "8262d4a0-6680-4377-9f07-80418a8dc24c"

    def rodar(self, *args, **kw):
        self.stub("loop-ctl", self.log_ctl, kw.pop("saida_ctl", 0))
        self.stub("loop-watch", self.log_watch)
        cwd = kw.pop("cwd", self.tmp)
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"])
        # `LOOP_SESSAO` herdado do ambiente de quem roda a suíte mudaria o
        # resultado de metade destes testes — some sempre, e volta só quando o
        # teste o pede de propósito.
        env.pop("LOOP_SESSAO", None)
        env.update(kw.pop("env_extra", {}))
        if kw.pop("com_sessao", True) and not args:
            args = (self.SESSAO,)
        elif kw.pop("com_sessao_no_inicio", False):
            args = (self.SESSAO,) + tuple(args)
        return subprocess.run([self.atalho] + list(args), cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=30)

    def argv(self, log):
        if not os.path.exists(log):
            return None
        with open(log, encoding="utf-8") as f:
            return f.read().split("\n")

    def test_com_o_id_e_sem_mais_nada_arma_por_6h_e_abre_o_watch(self):
        proc = self.rodar()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        ctl = self.argv(self.log_ctl)
        self.assertEqual(ctl[0], "armar")
        self.assertIn("--duracao", ctl)
        self.assertEqual(ctl[ctl.index("--duracao") + 1], "6h")
        self.assertIn("--sessao", ctl)
        self.assertEqual(ctl[ctl.index("--sessao") + 1], self.SESSAO)
        self.assertNotIn("--adotar-primeira-parada", ctl,
                         "o atalho voltou a adotar a primeira parada (A66)")
        watch = self.argv(self.log_watch)
        self.assertIsNotNone(watch, "armou e não abriu o painel")
        self.assertEqual(watch[watch.index("--raiz") + 1], os.path.realpath(self.tmp))

    def test_o_segundo_argumento_troca_a_duracao(self):
        self.rodar(self.SESSAO, "10h")
        ctl = self.argv(self.log_ctl)
        self.assertEqual(ctl[ctl.index("--duracao") + 1], "10h")
        self.assertEqual(ctl[ctl.index("--sessao") + 1], self.SESSAO)

    def test_a_raiz_vem_do_script_e_nao_do_cwd(self):
        outro = tempfile.mkdtemp(prefix="loop-outro-cwd-")
        self.addCleanup(shutil.rmtree, outro, ignore_errors=True)
        self.rodar(cwd=outro)
        ctl = self.argv(self.log_ctl)
        self.assertEqual(ctl[ctl.index("--raiz") + 1], os.path.realpath(self.tmp))

    def test_armar_que_recusa_nao_abre_painel_de_rodada_que_nao_subiu(self):
        proc = self.rodar(saida_ctl=2)
        self.assertNotEqual(proc.returncode, 0,
                            "o script engoliu a recusa do armar")
        self.assertIsNone(self.argv(self.log_watch),
                          "abriu o painel de uma rodada que não foi armada")

    # ═══════════════ A66 — a recusa, nos DOIS sentidos ═══════════════
    #
    # ⛔ Veredito do dono em 11/09: o atalho RECUSA armar sem vínculo de sessão.
    # A adoção silenciosa é o defeito da `P-09` — 18 entradas de diário em itens
    # alheios em 01/09, e três reincidências numa rodada só em 10/09.

    def test_ACUSA_sem_id_o_atalho_RECUSA_e_nao_chama_o_armar(self):
        proc = self.rodar(com_sessao=False)
        self.assertEqual(proc.returncode, 1,
                         "armou sem vínculo de sessão — o defeito da P-09")
        # ⚠️ A asserção é sobre o VERBO, não sobre o `loop-ctl` ter sido tocado.
        # Até a `0.3.15` ela era `assertIsNone(argv(log_ctl))`, e aquilo era um
        # PROXY: valia enquanto a recusa não chamava nada. Desde a `0.3.16` ela
        # chama `loop-ctl sessoes` para imprimir os candidatos — leitura pura,
        # que não arma coisa alguma. Manter o proxy proibiria a recusa de
        # ajudar; o que nunca pode acontecer é `armar`, e é isso que se cobra.
        ctl = self.argv(self.log_ctl)
        if ctl is not None:
            self.assertNotEqual(ctl[0], "armar",
                                "chamou o `armar` mesmo recusando")
        self.assertIsNone(self.argv(self.log_watch),
                          "abriu painel de rodada que não foi armada")

    def test_ACUSA_a_recusa_DIZ_por_que_e_como_sair_dela(self):
        proc = self.rodar(com_sessao=False)
        for pedaco in ("--sessao", "LOOP_SESSAO", "--qualquer-sessao"):
            self.assertIn(pedaco, proc.stderr,
                          "a recusa não nomeia `%s` — recusa sem saída vira "
                          "`--force` na semana seguinte" % pedaco)

    def test_ACUSA_duracao_sozinha_nao_e_confundida_com_id(self):
        # `10h` não tem forma de session_id: o script tem de recusar, e não
        # tomar a duração como vínculo
        proc = self.rodar("10h", com_sessao=False)
        self.assertEqual(proc.returncode, 1,
                         "tomou `10h` como id de sessão")

    # ═════════ 0.3.16 — o argumento que não é nada é NOMEADO ═════════
    #
    # 🔴 Medido em 11/09, a primeira vez que alguém usou a recusa de verdade: o
    # operador digitou `./loop.sh EOP-b3building 16h`. O `case` frouxo não casou,
    # o argumento foi DESCARTADO EM SILÊNCIO e escorregou para a duração — e a
    # recusa acusou "não passaste vínculo", que não era o fato.

    #: o apelido real que o operador digitou. Não é id, não é duração.
    LIXO = "EOP-b3building"

    def test_ACUSA_argumento_que_nao_e_id_nem_duracao_e_NOMEADO(self):
        proc = self.rodar(self.LIXO, "16h", com_sessao=False)
        self.assertEqual(proc.returncode, 1, "engoliu um argumento sem sentido")
        self.assertIn(self.LIXO, proc.stderr,
                      "recusou sem dizer QUAL argumento é o problema — é a "
                      "recusa pelo motivo errado, o defeito de 11/09")
        self.assertIsNone(self.argv(self.log_watch),
                          "abriu painel de rodada que não foi armada")

    def test_ACUSA_lixo_nao_vira_duracao_quando_o_vinculo_vem_do_ambiente(self):
        # ⛔ O caso pior do `case` frouxo: com o vínculo no ambiente, o argumento
        # não reconhecido ia inteiro para `--duracao`.
        proc = self.rodar(self.LIXO, com_sessao=False,
                          env_extra={"LOOP_SESSAO": self.SESSAO})
        self.assertEqual(proc.returncode, 1,
                         "aceitou `%s` como duração" % self.LIXO)
        ctl = self.argv(self.log_ctl)
        if ctl is not None:
            self.assertNotIn(self.LIXO, ctl,
                             "mandou o lixo para o `loop-ctl`")

    def test_a_ordem_dos_dois_argumentos_nao_importa(self):
        # Reconhecidos pela FORMA, não pela posição.
        proc = self.rodar("10h", self.SESSAO, com_sessao=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        ctl = self.argv(self.log_ctl)
        self.assertEqual(ctl[ctl.index("--duracao") + 1], "10h")
        self.assertEqual(ctl[ctl.index("--sessao") + 1], self.SESSAO)

    def test_a_recusa_do_argumento_NOMEIA_as_duas_formas_aceitas(self):
        proc = self.rodar(self.LIXO, com_sessao=False)
        self.assertIn("8-4-4-4-12", proc.stderr,
                      "não diz a forma do id — recusa sem saída vira `--force`")
        self.assertIn("6h", proc.stderr, "não diz a forma da duração")

    def test_a_recusa_SOBREVIVE_a_skill_sem_o_subcomando_sessoes(self):
        # ⚠️ Degrada, nunca inventa: cópia antiga da skill não tem `sessoes` e
        # sai não-zero. A recusa tem de continuar de pé, só sem a lista.
        proc = self.rodar(self.LIXO, com_sessao=False, saida_ctl=2)
        self.assertEqual(proc.returncode, 1,
                         "a recusa passou a depender da listagem — guarda que "
                         "morre junto com o ajudante não é guarda")
        self.assertIn(self.LIXO, proc.stderr)

    def test_ABSOLVE_o_id_pode_vir_do_AMBIENTE(self):
        self.stub("loop-ctl", self.log_ctl)
        self.stub("loop-watch", self.log_watch)
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"],
                   LOOP_SESSAO=self.SESSAO)
        proc = subprocess.run([self.atalho, "10h"], cwd=self.tmp, env=env,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        ctl = self.argv(self.log_ctl)
        self.assertEqual(ctl[ctl.index("--sessao") + 1], self.SESSAO)
        self.assertEqual(ctl[ctl.index("--duracao") + 1], "10h",
                         "com o id no ambiente, o 1º argumento é a DURAÇÃO")


if __name__ == "__main__":
    unittest.main()
