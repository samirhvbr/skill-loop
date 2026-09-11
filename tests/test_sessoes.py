#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de `lib/sessoes.py` — quem são as sessões abertas num repositório.

A varredura é montada em `tmp_path` com `HOME` redirecionado: nenhum teste lê o
`~/.claude*` de quem roda a suíte. Sem isso o resultado dependeria da máquina, e
teste que depende da máquina não prova nada em CI.

Regra de aceite da casa: cada teste cai com o controle desligado.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTL = os.path.join(RAIZ, "skill", "loop", "loop_ctl.py")
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

import sessoes  # noqa: E402

UUID_A = "8262d4a0-6680-4377-9f07-80418a8dc24c"
UUID_B = "f7e03b4c-8d25-4d2d-aa10-ccd5b3bdf6e4"
UUID_C = "5dca3e33-817c-42ec-8ff8-f50f5d17bb27"


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-sessoes-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.casa = os.path.join(self.tmp, "casa")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self._home = os.environ.get("HOME")
        self._ccd = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["HOME"] = self.casa
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        if self._home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._home
        if self._ccd is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = self._ccd
        else:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)

    def transcript(self, sid, cwd, abertura="olá", config=".claude",
                   idade_s=0, dir_projeto=None):
        """Escreve um `.jsonl` plausível e devolve o caminho."""
        nome = dir_projeto or sessoes.codificar_raiz(cwd)
        pasta = os.path.join(self.casa, config, "projects", nome)
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, sid + ".jsonl")
        linhas = [
            # metadado antes da primeira fala, como o harness grava de verdade
            {"type": "system", "cwd": cwd, "sessionId": sid},
            {"type": "user", "cwd": cwd, "isMeta": True,
             "message": {"content": "<system-reminder>ruído</system-reminder>"}},
            {"type": "user", "cwd": cwd,
             "message": {"content": abertura}},
            {"type": "assistant", "cwd": cwd,
             "message": {"content": [{"type": "text", "text": "resposta"}]}},
        ]
        with open(caminho, "w", encoding="utf-8") as f:
            for d in linhas:
                f.write(json.dumps(d) + "\n")
        if idade_s:
            quando = time.time() - idade_s
            os.utime(caminho, (quando, quando))
        return caminho


class TestVarredura(Base):

    def test_acha_a_sessao_do_repositorio(self):
        self.transcript(UUID_A, self.repo, abertura="Assume o loop e roda")
        achadas = sessoes.sessoes_do_repo(self.repo)
        self.assertEqual([s["id"] for s in achadas], [UUID_A])
        self.assertEqual(achadas[0]["abertura"], "Assume o loop e roda")

    def test_ACUSA_o_cwd_manda_e_nao_o_nome_do_diretorio(self):
        # ⛔ O coração do módulo: um transcript de OUTRO repositório, plantado
        # num diretório cujo nome começa igual ao deste. Se a varredura
        # acreditasse no nome, ela o listaria — e o operador amarraria a rodada
        # à sessão errada, que é o defeito inteiro que isto existe para evitar.
        outro = self.repo + "-outro"
        os.makedirs(outro)
        self.transcript(UUID_B, outro,
                        dir_projeto=sessoes.codificar_raiz(self.repo) + "-outro")
        self.assertEqual(sessoes.sessoes_do_repo(self.repo), [])

    def test_sessao_aberta_em_subdiretorio_conta(self):
        sub = os.path.join(self.repo, "capabilities", "core", "billing")
        os.makedirs(sub)
        self.transcript(UUID_A, sub)
        self.assertEqual([s["id"] for s in sessoes.sessoes_do_repo(self.repo)],
                         [UUID_A])

    def test_varre_TODOS_os_diretorios_de_configuracao(self):
        # 📏 Medido no EOP: a sessão que dirige o loop mora no `.claude-blue3`,
        # não no `.claude` padrão. Varrer só o padrão devolveria lista vazia
        # justamente para quem precisa dela.
        self.transcript(UUID_A, self.repo, config=".claude")
        self.transcript(UUID_B, self.repo, config=".claude-blue3")
        self.assertEqual({s["id"] for s in sessoes.sessoes_do_repo(self.repo)},
                         {UUID_A, UUID_B})

    def test_a_ordem_e_da_mais_recente_para_a_mais_velha(self):
        self.transcript(UUID_A, self.repo, idade_s=3600)
        self.transcript(UUID_B, self.repo, idade_s=0)
        self.transcript(UUID_C, self.repo, idade_s=86400)
        self.assertEqual([s["id"] for s in sessoes.sessoes_do_repo(self.repo)],
                         [UUID_B, UUID_A, UUID_C])

    def test_a_abertura_pula_metadado_e_lembrete_do_harness(self):
        # A primeira linha `user` do arquivo é `isMeta` e abre em `<`. Se ela
        # passasse, toda sessão teria a MESMA abertura e a lista não
        # distinguiria nada — que é o único serviço que ela presta.
        self.transcript(UUID_A, self.repo, abertura="o texto de verdade")
        self.assertEqual(sessoes.sessoes_do_repo(self.repo)[0]["abertura"],
                         "o texto de verdade")

    def test_repositorio_sem_sessao_devolve_lista_vazia_e_nao_estoura(self):
        os.makedirs(os.path.join(self.casa, ".claude", "projects"))
        self.assertEqual(sessoes.sessoes_do_repo(self.repo), [])

    def test_arquivo_corrompido_nao_derruba_a_varredura(self):
        # Fail-open: um `.jsonl` truncado no meio (sessão viva sendo escrita) não
        # pode esconder as outras sessões do operador.
        self.transcript(UUID_A, self.repo)
        pasta = os.path.join(self.casa, ".claude", "projects",
                             sessoes.codificar_raiz(self.repo))
        with open(os.path.join(pasta, UUID_B + ".jsonl"), "w") as f:
            f.write('{"type": "user", "cwd": "trunca')
        self.assertEqual([s["id"] for s in sessoes.sessoes_do_repo(self.repo)],
                         [UUID_A])


class TestForma(Base):

    def test_parece_session_id_aceita_a_forma_8_4_4_4_12(self):
        self.assertTrue(sessoes.parece_session_id(UUID_A))
        self.assertTrue(sessoes.parece_session_id(UUID_A.upper()))

    def test_ACUSA_parece_session_id_recusa_o_apelido_de_11_09(self):
        # O argumento real que o operador digitou, e que o `case` frouxo
        # descartava em silêncio.
        for lixo in ("EOP-b3building", "16h", "", "8262d4a0", UUID_A + "x",
                     "8262d4a0-6680-4377-9f07-80418a8dc24"):
            self.assertFalse(sessoes.parece_session_id(lixo),
                             "aceitou `%s` como session_id" % lixo)

    def test_codificar_raiz_troca_barra_E_ponto(self):
        # Medido contra o disco: `/home/samir/.local/share` vira
        # `-home-samir--local-share`, com o traço dobrado.
        self.assertEqual(sessoes.codificar_raiz("/home/samir/x/EOP"),
                         "-home-samir-x-EOP")
        self.assertEqual(sessoes.codificar_raiz("/home/samir/.local/share"),
                         "-home-samir--local-share")


class TestComando(Base):
    """`loop-ctl sessoes` — o subcomando, rodando como subprocesso."""

    def rodar(self, *args):
        env = dict(os.environ, HOME=self.casa)
        env.pop("CLAUDE_CONFIG_DIR", None)
        return subprocess.run(
            [sys.executable, CTL, "sessoes", "--raiz", self.repo] + list(args),
            capture_output=True, text=True, timeout=30, env=env)

    def test_lista_com_id_recencia_e_abertura(self):
        self.transcript(UUID_A, self.repo, abertura="Assume o loop do EOP")
        proc = self.rodar()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(UUID_A, proc.stdout)
        self.assertIn("Assume o loop do EOP", proc.stdout)

    def test_ids_imprime_so_ids_um_por_linha(self):
        self.transcript(UUID_A, self.repo)
        self.transcript(UUID_B, self.repo)
        proc = self.rodar("--ids")
        linhas = [l for l in proc.stdout.strip().split("\n") if l]
        self.assertEqual(sorted(linhas), sorted([UUID_A, UUID_B]))

    def test_ACUSA_ids_NAO_filtra_pela_janela(self):
        # ⛔ `--ids` responde "existe?", e existir não tem prazo. Filtrar aqui
        # faria o atalho avisar "sessão desconhecida" sobre uma sessão que está
        # no disco — aviso falso é pior que aviso nenhum.
        self.transcript(UUID_A, self.repo, idade_s=90 * 86400)
        self.assertIn(UUID_A, self.rodar("--ids").stdout)

    def test_a_janela_esconde_as_velhas_e_DIZ_quantas(self):
        self.transcript(UUID_A, self.repo, idade_s=0)
        self.transcript(UUID_B, self.repo, idade_s=10 * 86400)
        saida = self.rodar().stdout
        self.assertIn(UUID_A, saida)
        self.assertNotIn(UUID_B, saida)
        self.assertIn("1 sessão(ões)", saida,
                      "escondeu sem contar — filtro que não se declara mente")

    def test_todas_traz_as_velhas_de_volta(self):
        self.transcript(UUID_B, self.repo, idade_s=10 * 86400)
        self.assertIn(UUID_B, self.rodar("--todas").stdout)

    def test_se_NADA_e_recente_a_janela_nao_esconde_tudo(self):
        # Janela que esconde tudo é janela que não ajuda: o mais recente ainda é
        # a melhor informação que existe.
        self.transcript(UUID_B, self.repo, idade_s=10 * 86400)
        self.assertIn(UUID_B, self.rodar().stdout)

    def test_ACUSA_sem_sessao_nenhuma_sai_ZERO(self):
        # ⛔ Não achar não é erro: pode ser repo recém-clonado, ou um
        # `CLAUDE_CONFIG_DIR` que a varredura não conhece. Sair não-zero faria o
        # chamador tratar "não sei" como "não existe".
        proc = self.rodar()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("nenhuma sessão", proc.stdout)

    def test_nao_escreve_nada_no_repositorio(self):
        # Read-only de verdade: o comando não pode semear `.loop/` nem tocar em
        # estado. Quem arma é o `armar`.
        self.transcript(UUID_A, self.repo)
        antes = sorted(os.listdir(self.repo))
        self.rodar()
        self.assertEqual(sorted(os.listdir(self.repo)), antes)


class TestAvisoDoArmar(Base):
    """`armar --sessao <id>` avisa quando o id não é sessão deste repo."""

    def armar(self, sessao):
        os.makedirs(os.path.join(self.repo, ".loop"), exist_ok=True)
        with open(os.path.join(self.repo, ".loop", "QUEUE.md"), "w") as f:
            f.write("# Fila\n\n- [ ] item de verdade\n")
        env = dict(os.environ, HOME=self.casa)
        env.pop("CLAUDE_CONFIG_DIR", None)
        return subprocess.run(
            [sys.executable, CTL, "armar", "--raiz", self.repo,
             "--sessao", sessao, "--duracao", "6h"],
            capture_output=True, text=True, timeout=30, env=env)

    def test_ACUSA_id_desconhecido_AVISA_e_arma_assim_mesmo(self):
        # ⚠️ Aviso, nunca recusa: o id pode ser de sessão nascida há segundos.
        # Recusar sobre medição que pode estar cega é guarda que se desliga.
        self.transcript(UUID_A, self.repo)
        proc = self.armar(UUID_B)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("não é uma sessão vista", proc.stdout)
        self.assertIn(UUID_B, proc.stdout)

    def test_id_conhecido_arma_sem_aviso(self):
        self.transcript(UUID_A, self.repo)
        proc = self.armar(UUID_A)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("não é uma sessão vista", proc.stdout)

    def test_ACUSA_varredura_vazia_nao_gera_aviso(self):
        # Sem nenhuma sessão no disco a varredura não sabe de nada, e "não sei"
        # não é motivo para avisar. Avisar aqui treinaria o operador a ignorar.
        proc = self.armar(UUID_A)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("não é uma sessão vista", proc.stdout)


if __name__ == "__main__":
    unittest.main()
