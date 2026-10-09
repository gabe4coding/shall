# Review inside this session

Same pipeline as `jrfc review`, with the reviewer as an in-session agent.

1. `jrfc select /tmp/pr.diff --out .jrfc-out/pr/selection.json`
2. `jrfc bundle /tmp/pr.diff --selection .jrfc-out/pr/selection.json --out .jrfc-out/pr/bundle.md`
3. For each chunk in the bundle, dispatch the `jrfc-reviewer` agent with that chunk's section
   (chunks are independent: dispatch in parallel). Collect the findings into
   `.jrfc-out/pr/findings.agent.json` as `{"findings": [{"chunk": "c0", ...}]}`.
4. `jrfc validate .jrfc-out/pr/findings.agent.json /tmp/pr.diff --selection .jrfc-out/pr/selection.json --out-dir .jrfc-out/pr/validated`
   (drops findings whose statement was not selected for the chunk or whose line is not changed,
   dedupes, recomputes blocking, caps comments)
5. `jrfc verify .jrfc-out/pr/validated/findings.json /tmp/pr.diff --selection .jrfc-out/pr/selection.json --out-dir .jrfc-out/pr`
   from the repository root (gathers evidence; refuted findings drop only with cited evidence,
   unknown ones stay advisory).
6. Present `review.md`. Mention dropped findings only if asked; refuted ones carry their evidence
   in `findings.json`.
