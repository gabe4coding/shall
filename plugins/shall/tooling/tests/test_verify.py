"""Verification of findings: code picks what is verified and applies verdicts; severity only goes down."""

import asyncio
import subprocess
from types import SimpleNamespace

from shall.artifact import build_artifact
from shall.verify import apply_verdict, gather_excerpts, needs_verification, search_terms, verify_findings


def finding(**kw):
    base = {"statement_id": "JTOOL-0002.1", "level": "MUST", "blocking": True, "path": "shall.yaml",
            "line": 2, "quote": "command: [claude, -p]", "message": "agent runs with tools",
            "statement_text": "The review agent MUST run with no tools.", "depends_on": [], "chunk": "c0"}
    return {**base, **kw}


def test_what_gets_verified_is_decided_by_code():
    assert needs_verification(finding())                                    # blocking: always
    assert needs_verification(finding(blocking=False, depends_on=["x"]))    # advisory with depends_on
    assert not needs_verification(finding(blocking=False))                  # advisory, self-contained


def test_search_terms_use_depends_on_first_and_skip_noise():
    terms = search_terms(finding(depends_on=["review.command", "RetryPolicy defaults"]))
    assert terms[:4] == ["review.command", "review", "command", "RetryPolicy"]
    assert "claude" in terms and "defaults" not in terms


def test_yaml_key_path_and_statement_code_spans_become_terms():
    from shall.verify import yaml_key_path
    lines = {1: "jev:", 2: "  model: jev-1.13.0", 3: "review:", 4: "  # comment", 5: "  command: [claude, -p]"}
    assert yaml_key_path(lines, 5) == "review.command" and yaml_key_path(lines, 3) is None
    terms = search_terms(finding(statement_text='The agent MUST run with no tools (`--tools ""`).'),
                         key_path="review.command")
    assert terms[:2] == ["review.command", "--tools"]


def test_code_ranks_before_docs(tmp_path):
    (tmp_path / "README.md").write_text("Run claude with review.command.\n")
    (tmp_path / "run.py").write_text("x = cfg.get('review.command')\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert [e.path for e in gather_excerpts(tmp_path, ["review.command"], set())] == ["run.py", "README.md"]


def test_gather_excerpts_finds_other_files_and_skips_own_file_and_standards(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "corpus").mkdir()
    (tmp_path / "shall.yaml").write_text("review:\n  command: [claude, -p]\n")
    (tmp_path / "src" / "review.py").write_text(
        "def run():\n    cmd = list(cfg.get('review.command')) + [\n        '--tools', '',\n    ]\n")
    (tmp_path / "corpus" / "rule.md").write_text("The review.command MUST run with no tools.\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    ex = gather_excerpts(tmp_path, ["review.command", "claude"], {"shall.yaml", "corpus"})
    assert [e.path for e in ex] == ["src/review.py"]
    assert "'--tools', ''" in ex[0].text and ex[0].start == 1


def test_excerpts_stay_small_on_one_line_files(tmp_path):
    # an untracked one-line JSON cache once made a 155k-token Jev state and crashed the review
    (tmp_path / "cache.json").write_text('{"review.command": "' + "x" * 400_000 + '"}\n')
    (tmp_path / "run.py").write_text("\n".join(f"cmd{i} = cfg.get('review.command')  # {'y' * 300}"
                                              for i in range(200)) + "\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    ex = {e.path: e for e in gather_excerpts(tmp_path, ["review.command"], set())}
    assert set(ex) == {"cache.json", "run.py"}
    assert len(ex["cache.json"].text) < 500 and "…[cut " in ex["cache.json"].text
    assert all(len(e.text) <= 12_100 for e in ex.values())


def test_code_graph_windows_cut_long_lines():
    from shall.codegraph import MAX_EXCERPT_CHARS, numbered_lines
    lines = ["a" * 10_000] + [f"line {i} " + "b" * 390 for i in range(100)]
    text = numbered_lines(lines, range(1, 101))
    assert text.startswith("    1 | " + "a" * 400 + "…[cut 9600 chars]")
    assert len(text) <= MAX_EXCERPT_CHARS + 30 and text.endswith("[excerpt cut]")
    assert numbered_lines(["x = 1", "y = 2"], [1, 2]) == "    1 | x = 1\n    2 | y = 2"


def test_refuted_with_evidence_is_dropped():
    kept, dropped = apply_verdict(finding(), {"verdict": "refuted", "reason": "review.py adds --tools ''",
                                              "evidence": ["e0"]}, [SimpleNamespace(id="e0", path="src/review.py",
                                                                                     start=1, end=4)])
    assert kept is None and dropped["verification"]["evidence"] == ["src/review.py:1-4"]


def test_refuted_without_evidence_is_kept_but_not_blocking():
    kept, dropped = apply_verdict(finding(), {"verdict": "refuted", "reason": "trust me", "evidence": ["e9"]}, [])
    assert dropped is None and kept["blocking"] is False and kept["verification"]["verdict"] == "unknown"


def test_unknown_downgrades_a_blocking_finding():
    kept, _ = apply_verdict(finding(), {"verdict": "unknown", "reason": "SDK default not shown", "evidence": []}, [])
    assert kept["blocking"] is False and kept["downgraded"] is True


def test_confirmed_keeps_blocking_and_never_upgrades_an_advisory():
    kept, _ = apply_verdict(finding(), {"verdict": "confirmed", "reason": "r", "evidence": ["chunk"]}, [])
    assert kept["blocking"] is True
    kept, _ = apply_verdict(finding(blocking=False, depends_on=["x"]),
                            {"verdict": "confirmed", "reason": "r", "evidence": ["chunk"]}, [])
    assert kept["blocking"] is False


def test_confirmed_without_existing_evidence_does_not_block():
    kept, _ = apply_verdict(finding(), {"verdict": "confirmed", "reason": "r", "evidence": ["e7"]}, [])
    assert kept["blocking"] is False and kept["verification"]["verdict"] == "unknown"


def test_missing_verdict_counts_as_unknown():
    kept, _ = apply_verdict(finding(), None, [])
    assert kept["blocking"] is False and kept["verification"]["verdict"] == "unknown"


class FakeJev:
    async def gather(self, aws):
        return list(await asyncio.gather(*aws))

    async def ask(self, state, questions):
        return {"relevant": {"p": 0.9 if "--tools" in state["excerpt"] else 0.1}}


def test_end_to_end_only_verifies_what_code_selects(tmp_path):
    (tmp_path / "review.py").write_text("cmd = [*cfg.get('review.command'), '--tools', '']\n")
    (tmp_path / "shall.yaml").write_text("review:\n  command: [claude, -p]\n")
    art = build_artifact("shall.yaml", (tmp_path / "shall.yaml").read_text(), "code", 40000)
    prompts = []

    async def agent(prompt, sem):
        prompts.append(prompt)
        return {"verdict": "refuted", "reason": "review.py appends --tools ''", "evidence": ["e0"]}, {"cost_usd": 0.01}

    cfg = SimpleNamespace(get=lambda key: 2)
    corpus = SimpleNamespace(layers=[])
    blocking = finding(depends_on=["review.command"])
    advisory = finding(statement_id="JTOOL-0001.4", blocking=False, line=1, quote="review:")
    kept, dropped, stats = asyncio.run(verify_findings(cfg, corpus, art, FakeJev(), [blocking, advisory],
                                                       search_root=tmp_path, agent=agent))
    assert len(prompts) == 1 and "review.py" in prompts[0]      # only the blocking one was verified
    assert [k["statement_id"] for k in kept] == ["JTOOL-0001.4"]
    assert dropped[0]["statement_id"] == "JTOOL-0002.1"
    assert stats["refuted"] == 1 and stats["verified"] == 1
