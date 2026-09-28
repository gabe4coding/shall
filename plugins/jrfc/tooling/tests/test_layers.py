"""Corpus layers: org corpus pinned by git ref + repository-local .jrfc/ (no network)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from jrfc.artifact import Chunk
from jrfc.config import load_config
from jrfc.corpus import load_corpus
from jrfc.index import build_index, render_catalog
from jrfc.select import Selector

ORG = Path(__file__).resolve().parents[4]  # the jrfc repo: jrfc.yaml + corpus/


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True,
                   capture_output=True)


@pytest.fixture
def org_repo(tmp_path):
    """A git copy of the org corpus with tag v1."""
    repo = tmp_path / "org"
    (repo / "corpus").mkdir(parents=True)
    shutil.copy(ORG / "jrfc.yaml", repo / "jrfc.yaml")
    shutil.copytree(ORG / "corpus" / "rfcs", repo / "corpus" / "rfcs")
    shutil.copy(ORG / "corpus" / "domains.yaml", repo / "corpus" / "domains.yaml")
    git("init", "-q", "-b", "main", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "v1", cwd=repo)
    git("tag", "v1", cwd=repo)
    return repo


RFC = """---
id: {id}
title: Booking lifecycle events
status: enforced
domain: {domain}
artifacts: [diff, code]
languages: [any]
owner: bookings
review_by: 2099-01-01
supersedes: [{supersedes}]
summary: Events for booking status changes.
applies_when: The content changes a booking status.
not_applies_when: No booking status change.
---

# {id}: Booking lifecycle events

## Requirements

### {id}.1 Publish an event
Code that changes a booking status MUST enqueue a booking event in the same transaction.

- Applies when: the content changes a booking status.
- Enforcement: agent
"""


def workspace(tmp_path, monkeypatch, org_repo, prefix="BOOK", rid="BOOK-0001", domain="delivery",
              supersedes="", extra_domains=None):
    app = tmp_path / "app"
    dot = app / ".jrfc"
    (dot / "rfcs").mkdir(parents=True)
    (dot / "jrfc.yaml").write_text(
        f"prefix: {prefix}\nextends:\n  repo: org/standards\n  url: file://{org_repo}\n  ref: v1\n")
    (dot / "rfcs" / f"{rid}-events.md").write_text(RFC.format(id=rid, domain=domain, supersedes=supersedes))
    if extra_domains:
        (dot / "domains.yaml").write_text(extra_domains)
    monkeypatch.setenv("JRFC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("JRFC_CONFIG", raising=False)
    monkeypatch.delenv("JRFC_EXTENDS", raising=False)
    monkeypatch.chdir(app)
    return app


def test_extends_fetches_pinned_ref_and_merges_layers(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo)
    cfg = load_config()
    assert [layer.name for layer in cfg.layers] == ["org/standards@v1", "local"]
    assert cfg.parent.parent.sha and (cfg.parent.root / ".jrfc-resolved").is_file()
    corpus = load_corpus(cfg)
    assert corpus.all_errors == []
    assert "BOOK-0001" in corpus.rfcs and "JRFC-0003" in corpus.rfcs
    assert corpus.rfcs["JRFC-0003"].layer == "org/standards@v1"
    # settings are inherited from the org jrfc.yaml
    assert cfg.get("conflicts.exclude_domains") == ["governance"]
    assert cfg.get("selection.always_domains") == ["security"]


def test_new_commits_upstream_do_not_move_a_pinned_workspace(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo)
    first = load_config().parent.parent.sha
    (org_repo / "corpus" / "rfcs" / "JRFC-0003-logging-personal-data.md").write_text("changed")
    git("commit", "-qam", "later", cwd=org_repo)
    assert load_config().parent.parent.sha == first
    assert load_corpus(load_config()).all_errors == []


def test_local_ids_must_use_the_local_prefix(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo, rid="JRFC-0099")
    corpus = load_corpus(load_config())
    assert any(i.code == "rfc-id" for i in corpus.errors)


def test_local_prefix_cannot_reuse_the_org_prefix(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo, prefix="JRFC", rid="JRFC-0099")
    assert any(i.code == "prefix-collision" for i in load_corpus(load_config()).errors)


def test_local_domains_add_but_cannot_redefine(tmp_path, monkeypatch, org_repo):
    domains = ("domains:\n  booking-events:\n    title: t\n    description: d\n    applies_when: a\n"
               "    not_applies_when: n\n  security:\n    title: t\n    description: d\n"
               "    applies_when: a\n    not_applies_when: n\n")
    workspace(tmp_path, monkeypatch, org_repo, domain="booking-events", extra_domains=domains)
    corpus = load_corpus(load_config())
    assert "booking-events" in corpus.domains
    assert [i.code for i in corpus.errors] == ["domain-redefined"]


def test_local_rfc_cannot_supersede_an_org_rfc(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo, supersedes="JRFC-0003")
    assert any(i.code == "cross-layer-ref" for i in load_corpus(load_config()).errors)


def test_committed_index_is_local_only_catalog_is_merged(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo)
    corpus = load_corpus(load_config())
    index = build_index(corpus)
    assert [r["id"] for r in index["rfcs"]] == ["BOOK-0001"]
    assert index["extends"][0]["ref"] == "v1"
    assert all(s["source"].startswith(".jrfc/rfcs/") for s in index["statements"])
    merged = render_catalog(build_index(corpus, {layer.name for layer in corpus.layers}))
    assert "BOOK-0001.1" in merged and "JRFC-0003.1" in merged


def test_selection_candidates_include_both_layers(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo)
    cfg = load_config()
    selector = Selector(cfg, load_corpus(cfg), jev=None)
    chunk = Chunk(id="c0", kind="diff", path="src/a.ts", language="typescript", rendered="")
    ids = {s.id for _, s in selector.eligible(chunk)}
    assert "BOOK-0001.1" in ids and "JRFC-0007.2" in ids and "JRFC-0011.1" not in ids  # draft excluded


def test_jrfc_extends_env_gives_org_corpus_without_local_layer(tmp_path, monkeypatch, org_repo):
    app = tmp_path / "plain-app"
    app.mkdir()
    monkeypatch.chdir(app)
    monkeypatch.setenv("JRFC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("JRFC_EXTENDS", str(org_repo))  # a path works too
    monkeypatch.delenv("JRFC_CONFIG", raising=False)
    corpus = load_corpus(load_config())
    assert corpus.errors == [] and corpus.local_statements() == []
    assert "JRFC-0003" in corpus.rfcs


def test_github_parent_sources_are_permalinks(tmp_path, monkeypatch, org_repo):
    workspace(tmp_path, monkeypatch, org_repo)
    cfg = load_config()
    cfg.parent.parent.url_base = f"https://github.com/org/standards/blob/{cfg.parent.parent.sha}"
    corpus = load_corpus(cfg)
    rfc = corpus.rfcs["JRFC-0003"]
    assert corpus.source(rfc, 31) == (f"https://github.com/org/standards/blob/{cfg.parent.parent.sha}"
                                      "/corpus/rfcs/JRFC-0003-logging-personal-data.md#L31")


def test_jev_cache_merges_parallel_writers(tmp_path, monkeypatch):
    from jrfc.jev import Jev

    class Cfg:
        cache_file = tmp_path / "jev.json"

        def get(self, key):
            return {"jev.model": "m", "jev.max_request_tokens": 1000, "jev.concurrency": 1}[key]

    a, b = Jev(Cfg()), Jev(Cfg())  # both start from an empty cache
    a.cache["k1"] = {"p": 0.1}
    b.cache["k2"] = {"p": 0.2}
    a.save()
    b.save()
    assert set(Jev(Cfg()).cache) == {"k1", "k2"}
