| round | change (one line) | test prec@0.7 | test recall@0.7 | train prec@0.7 | train recall@0.7 | test prec@0.5 | $/file (Jev) | spend (Jev) |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline | 0.75 [0.57-0.92] | 0.75 | 0.61 | 0.69 | 0.39 | $0.00051 | $0.10 |
| 1 | JRFC-0003 applies only to service code | 0.82 (+0.07 [-0.04, +0.20]) | 0.75 (+0.00) | 0.77 | 0.67 | 0.45 | $0.00051 | $0.20 |
| 2 | breadth pass: criteria for 0004.1, 0006.1, 0007.4, 0010.2 (+0003.2 cue) | **0.96 (+0.21 [+0.06, +0.36])** | 0.72 (-0.03 [-0.09, 0.00]) | 1.00 | 0.67 | 0.60 | $0.00052 | $0.31 |

Deltas are paired bootstrap over the 50 test files versus baseline. Labelling (once, not per
round): $10.32. Analyzer (round 2): one subagent, ~132k tokens.

v2 is the winner. v1 moved the scope of JRFC-0003 to services (the user's ruling that CLI tools
are not services); on its own it removed most JRFC-0003.2 wrong flags but stayed inside the test
noise at 0.7. After v1 no single cause was big enough to see, so v2 fixed the four remaining
independent causes at once with one criteria line each: demo or self-generated credentials,
subprocess or stdio children taken as network calls, developer env switches taken as feature
flags, and catch handlers that read no error property. Train went to 0 wrong flags at 0.7 and
the held-out test half followed (9 -> 1 wrong-flag rows), so the fixes generalize beyond the
files the analyzer read. Recall at 0.7 held within noise (one row of 36 lost). The one remaining
test false positive at 0.7 is JRFC-0011.1. The precision target has little headroom left
(0.96); the largest remaining room is recall at 0.7 (0.72): the missed violations are mostly
JRFC-0011.1 files where only one or two public functions lack type hints (violates p 0.5-0.7).
Caveats: v1 was chosen from full-set counts before the split; the gold labels are Claude
Opus 5.5's with 3 human rulings; every corpus change needs its RFC owner's approval.
