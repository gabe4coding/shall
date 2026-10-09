# Review inside this session

Same pipeline as `shall review`, with the reviewer as an in-session agent.

1. `shall select /tmp/pr.diff --out .shall-out/pr/selection.json`
2. `shall bundle /tmp/pr.diff --selection .shall-out/pr/selection.json --out .shall-out/pr/bundle.md`
3. For each chunk in the bundle, dispatch the `shall-reviewer` agent with that chunk's section
   (chunks are independent: dispatch in parallel). Collect the findings into
   `.shall-out/pr/findings.agent.json` as `{"findings": [{"chunk": "c0", ...}]}`.
4. `shall validate .shall-out/pr/findings.agent.json /tmp/pr.diff --selection .shall-out/pr/selection.json --out-dir .shall-out/pr/validated`
   (drops findings whose statement was not selected for the chunk or whose line is not changed,
   dedupes, recomputes blocking, caps comments)
5. `shall verify .shall-out/pr/validated/findings.json /tmp/pr.diff --selection .shall-out/pr/selection.json --out-dir .shall-out/pr`
   from the repository root (gathers evidence; refuted findings drop only with cited evidence,
   unknown ones stay advisory).
6. Present `review.md`. Mention dropped findings only if asked; refuted ones carry their evidence
   in `findings.json`.
