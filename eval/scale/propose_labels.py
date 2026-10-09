"""Propose selection labels for eval cases with Claude (independent of Jev), then diff with Jev flat.

Usage: propose_labels.py LABELS.yaml OUT.json
For each case: every statement the code prefilter keeps is shown to Claude with the label
definition; Claude returns the ids that govern the artifact. Output is for human review.
"""
import asyncio, json, sys
from pathlib import Path
import yaml
from shall.config import load_config
from shall.corpus import load_corpus
from shall.jev import Jev
from shall.artifact import build_artifact, detect_kind, read_source
from shall.select import Selector, classify_document
from shall.review import run_claude

SYSTEM = """You label an evaluation set for a classifier that selects engineering standards.
A statement is APPLICABLE to an artifact when the artifact contains (or, for a task, the work will
produce) the kind of code or text the statement governs, WHETHER OR NOT the artifact follows it.
Not applicable: the statement is about something the artifact does not contain.
Examples: a diff that makes an HTTP call -> the timeout rule applies even if a timeout is set.
A CSS-only diff -> backend logging rules do not apply. Be literal and precise: include a statement
only when a reviewer would reasonably check this artifact against it. Output only ids from the list."""
SCHEMA = {"type": "object", "properties": {"applicable": {"type": "array", "items": {"type": "string"}}},
          "required": ["applicable"]}

async def main(labels_path, out_path):
    cfg = load_config("eval/scale/.shall/shall.yaml"); corpus = load_corpus(cfg)
    labels = yaml.safe_load(Path(labels_path).read_text()); base = Path(labels_path).parent
    sem = asyncio.Semaphore(4)
    async with Jev(cfg) as jev:
        async def one(case):
            name, raw = read_source(str(base / case["file"]), None)
            kind = case.get("kind") or detect_kind(name, raw)
            if kind == "document":
                kind, _ = await classify_document(jev, name, raw)
            art = build_artifact(name, raw, kind, int(cfg.get("jev.max_chunk_chars")))
            sel = Selector(cfg, corpus, jev, strategy="flat")
            elig = {}
            for c in art.chunks:
                for r, s in sel.eligible(c):
                    elig[s.id] = f"{s.id} [{r.domain}] {r.title} / {s.title}: {s.text}"
            results = await sel.select(art)
            p = {}
            for r in results:
                for sid, v in r.statements.items():
                    p[sid] = max(p.get(sid, 0), v)
            prompt = (f"<artifact kind=\"{kind}\" file=\"{name}\">\n{raw[:60000]}\n</artifact>\n\n<statements>\n"
                      + "\n".join(elig[k] for k in sorted(elig)) + "\n</statements>\n\nList the applicable statement ids.")
            res, meta = await run_claude(cfg, prompt, SYSTEM, SCHEMA, sem)
            claude = sorted(set((res or {}).get("applicable", [])) & set(elig))
            return {"case": case["file"], "kind": kind, "eligible": len(elig), "claude": claude,
                    "jev_p": {k: round(v, 2) for k, v in sorted(p.items()) if v >= 0.2},
                    "current": case.get("expected", []), "cost": meta.get("cost_usd"), "error": meta.get("error")}
        rows = await asyncio.gather(*(one(c) for c in labels["cases"]))
    Path(out_path).write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(r["case"], "eligible", r["eligible"], "claude", len(r["claude"]), "jev>=.5",
              sum(1 for v in r["jev_p"].values() if v >= .5), "err", r["error"])

asyncio.run(main(sys.argv[1], sys.argv[2]))
