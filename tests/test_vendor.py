#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`vendor.sh` — every prompt `SKILL.md` links must exist in the vendored copy.

Why this test exists: the `cp` in `vendor.sh` named its files by hand and listed
**two**. The comment above it said "these two files" and was right about the
*hook* — `loop-stop.py` loads `continuacao.md` and `reabastecimento.md`. But
`SKILL.md`, which the **agent** reads, links a third: `../../prompts/reabastecer.md`.
In a vendored copy `SKILL.md` sits at `<repo>/.claude/skills/loop-work/`, so
`../../prompts/` resolves to `<repo>/.claude/prompts/` — the directory the script
creates and was populating without it.

Measured 07/10/2026: **68 of the 69 vendored copies on this machine** carried
that dead link.

The assertion is not "reabastecer.md got copied". It is **every prompt link in
SKILL.md resolves**, which is the real rule and which fails again the day someone
links a fourth file and forgets the `cp`.

Runs under pytest, and standalone (`python3 tests/test_vendor.py`) because this
machine has no venv.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_MD = REPO / "skill" / "loop" / "SKILL.md"

# `[text](../../prompts/thing.md)` and a bare `../../prompts/thing.md` alike
LINK = re.compile(r"\.\./\.\./prompts/([A-Za-z0-9._-]+\.md)")


def _linked_prompts() -> set[str]:
    return set(LINK.findall(SKILL_MD.read_text(encoding="utf-8")))


def _vendor_into(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["bash", str(REPO / "vendor.sh"), str(target)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"vendor.sh failed:\n{r.stdout}\n{r.stderr}"


def test_skill_md_actually_links_prompts() -> None:
    """A guard on the test itself: if `SKILL.md` stopped linking prompts, the
    test below would pass vacuously and nobody would notice."""
    assert _linked_prompts(), (
        "SKILL.md links no ../../prompts/*.md — the copy test would be green "
        "while measuring nothing"
    )


def test_vendor_copies_every_prompt_skill_md_links(tmp_path: Path) -> None:
    target = tmp_path / "target-repo"
    _vendor_into(target)

    copied = target / ".claude" / "skills" / "loop-work" / "SKILL.md"
    assert copied.is_file(), "SKILL.md did not reach the copy"

    # `../../prompts/` from .claude/skills/loop-work/ is .claude/prompts/
    prompts = target / ".claude" / "prompts"
    missing = sorted(p for p in _linked_prompts() if not (prompts / p).is_file())
    assert not missing, (
        "the vendored SKILL.md links prompts the copy does not have, so the link "
        f"is dead: {missing}. Add them to the `cp` in vendor.sh."
    )


def test_the_hook_also_has_the_templates_it_loads(tmp_path: Path) -> None:
    """The `cp` serves two readers and the test above covers one. The
    `loop-stop.py` hook loads its own templates by name."""
    target = tmp_path / "target-repo"
    _vendor_into(target)

    hook = (REPO / "skill" / "loop" / "hooks" / "loop-stop.py").read_text(
        encoding="utf-8"
    )
    loaded = set(re.findall(r"['\"]([A-Za-z0-9._-]+\.md)['\"]", hook))
    prompts = target / ".claude" / "prompts"
    missing = sorted(
        p
        for p in loaded
        if p.startswith(("continuacao", "reabastec")) and not (prompts / p).is_file()
    )
    assert not missing, f"the hook loads templates the copy does not have: {missing}"


if __name__ == "__main__":  # standalone: this machine has no venv
    import sys
    import tempfile

    failures = 0
    for name, fn in sorted(
        (n, f) for n, f in list(globals().items()) if n.startswith("test_")
    ):
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
        except AssertionError as e:
            print(f"  [FAILED] {name}\n           {e}")
            failures += 1
        else:
            print(f"  [ok]     {name}")
    print()
    print("all passed." if not failures else f"{failures} failure(s).")
    sys.exit(1 if failures else 0)
