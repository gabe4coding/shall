# v1: JRFC-0003 applies only to service code

JRFC-0003's statements say "Services MUST ...", but its `applies_when` criteria (RFC level and
.1, .2, .4) said only "the content writes log lines / adds a log call". Jev's applies question
therefore scored CLI tools, scripts and benchmarks as in scope, and the violation question then
flagged their `print`/`console.error` lines. The user ruled (2026-09-30) that CLI tools, scripts
and local developer tools are not services. This round writes that scope into the criteria, at
the RFC level and on .1, .2 and .4 (statement-level criteria override the RFC's). No statement
text changes, so the gold labels stay valid.

Evidence: at p >= 0.7, 12 of the 25 baseline false-positive rows are JRFC-0003.2.

Leak note: this change was chosen from full-set false-positive counts before the train/test
split was drawn, and from the user's ruling on two pilot files (sgm-020, pw-081). The test delta
of this round is therefore not a fully held-out number. Later rounds use train traces only.

Owner: sre (JRFC-0003 is enforced); the change must be approved by the owner before merge.
Expected: JRFC-0003.x applies p on non-service files drops; test precision@0.7 up, recall flat
(JRFC-0003 has no gold positives on these files once CLI tools are out of scope).
