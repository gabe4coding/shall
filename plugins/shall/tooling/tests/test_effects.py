"""Known effects (effects.py) and run health (health.py): no network, no model."""

import subprocess
from pathlib import Path

import pytest

from shall.artifact import build_artifact
from shall.codegraph import RepoIndex, treesitter_available
from shall.config import load_config
from shall.corpus import load_corpus
from shall.effects import chunk_facts, load_effects
from shall.health import build_health

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def effects():
    return load_corpus(load_config(str(ROOT / "shall.yaml"))).effects


def facts_for(effects, path: str, code: str, index=None) -> list[str]:
    art = build_artifact(path, code, "code", 40000)
    return chunk_facts(effects, art, index).get("c0", [])


@pytest.mark.parametrize("path, code, expected", [
    ("a.py", "import requests\nrequests.post(url, json=body)\n", "`requests.post` (requests)"),
    ("a.py", "from confluent_kafka import Consumer\nc = Consumer({})\n", "`Consumer` (confluent_kafka)"),
    ("a.kt", 'import java.net.URL\nval body = URL("https://x").readText()\n', "`URL.readText` (java.net)"),
    ("a.go", 'import (\n\t"database/sql"\n)\ntype H struct{ DB *sql.DB }\nfunc (h *H) f() { h.DB.Query("q") }\n',
     "`h.DB.Query` (database/sql)"),
    ("a.cs", "using System.Net.Http;\nusing Booking.Http;\nclass S { private readonly HttpClient _c = Make();\n"
             "  void F() { _c.PutAsync(u, b); } }\n", "`_c.PutAsync` (System.Net.Http)"),
    ("a.rb", 'require "faraday"\nconn = Faraday.new(url: "https://x")\n', "`Faraday.new` (faraday)"),
    ("a.rs", "pub fn c() { reqwest::blocking::Client::builder().build() }\n", "reqwest.blocking.Client"),
    ("a.ts", "const r = await fetch(url);\n", "`fetch` (built-in)"),
    ("a.py", "from tree_sitter_language_pack import get_parser\nget_parser(lang).parse(src)\n",
     "`get_parser` (tree_sitter_language_pack)"),
])
def test_direct_facts_across_languages(effects, path, code, expected):
    assert any(expected in f for f in facts_for(effects, path, code)), facts_for(effects, path, code)


@pytest.mark.parametrize("path, code", [
    # `Query` on a receiver that is not from database/sql: URL query parameters
    ("a.go", 'import (\n\t"database/sql"\n\t"net/http"\n)\nfunc f(r *http.Request) { r.URL.Query().Get("c") }\n'),
    ("a.ts", "const v = cache.fetch(key);\n"),              # a method named fetch, not the built-in
    ("a.py", "import requests\nvalue = mapping.get(key)\n"),  # dict.get after importing requests
    ("a.rb", 'require "net/http"\nx = Foo.new\n'),        # Ruby net/http entry is for `Net::HTTP`
])
def test_no_false_facts(effects, path, code):
    assert not [f for f in facts_for(effects, path, code) if "database" in f or "HTTP" in f or "network" in f]


@pytest.mark.skipif(not treesitter_available(), reason="tree-sitter not installed")
def test_indirect_fact_through_wrapper(effects, tmp_path):
    (tmp_path / "payments").mkdir()
    (tmp_path / "payments" / "__init__.py").write_text("")
    (tmp_path / "payments" / "http.py").write_text(
        "import requests\n\n\ndef make_session():\n    return requests.Session()\n")
    (tmp_path / "payments" / "provider.py").write_text(
        "from payments.http import make_session\n\n\ndef charge(x):\n    return make_session().post('/c', json=x)\n")
    (tmp_path / "job.py").write_text("from payments import provider\n\n\ndef run(b):\n    provider.charge(b)\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    facts = facts_for(effects, "job.py", (tmp_path / "job.py").read_text(), RepoIndex(tmp_path))
    assert any("requests.Session" in f and "payments/http.py" in f for f in facts), facts


def test_registry_lint(tmp_path):
    f = tmp_path / "effects.yaml"
    f.write_text("effects:\n  - id: a\n    effect: x\n    calls: [c]\n"          # no module, no languages
                 "  - id: b\n    module: m\n    effect: x\n"                        # no calls/methods
                 "  - id: ok\n    module: m\n    calls: [c]\n    effect: does x\n")
    issues = []
    assert [e.id for e in load_effects([f], issues)] == ["ok"]
    assert len(issues) == 2 and all(i.code == "effects" for i in issues)


def test_grammar_download_is_reported_or_blocked(tmp_path, monkeypatch):
    if not treesitter_available():
        pytest.skip("tree-sitter not installed")
    import tree_sitter_language_pack
    monkeypatch.setattr(tree_sitter_language_pack, "downloaded_languages", lambda: [])
    (tmp_path / "a.py").write_text("x = 1\n")
    index = RepoIndex(tmp_path, download_grammars=False)
    assert index.file("a.py").lang is None
    assert index.events == [{"kind": "grammar_missing", "lang": "python"}]


def test_health_warnings():
    class Cfg:
        def get(self, key, default=None):
            return {"selection.thresholds": {"statement": 0.5}, "selection.near_margin": 0.15}.get(key, default)
    selection = {"chunks": [{"id": "c0", "path": "a.py", "eligible": 30, "known_effects": ["x"],
                             "statements": {"A.1": 0.9, "A.2": 0.4, "A.3": 0.1}, "selected": ["A.1"]}]}
    stats = {"agent_calls": 1, "errors": [], "verification": {"verified": 2, "confirmed": 0, "refuted": 0,
                                                             "unknown": 2, "downgraded": 1}}
    h = build_health(Cfg(), selection, stats, [], [], [{"kind": "parse_error", "path": "b.go", "error": "x"}])
    assert h["selection"]["near_threshold"] == [{"id": "A.2", "chunk": "c0", "path": "a.py", "p": 0.4}]
    assert h["verification"]["unknown_rate"] == 1.0
    text = " | ".join(h["warnings"])
    assert "downgraded" in text and "could not decide 2 of 2" in text and "b.go" in text
    assert "A.2" not in text  # near-threshold is information, not a warning
