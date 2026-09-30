| round | change (one line) | test prec@0.7 | test recall@0.7 | train prec@0.7 | train recall@0.7 | test prec@0.5 | $/file (Jev) | spend (Jev) |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline | 0.75 [0.57-0.92] | 0.75 | 0.61 | 0.69 | 0.39 | $0.00051 | $0.10 |
| 1 | JRFC-0003 applies only to service code | 0.82 (+0.07 [-0.04, +0.20]) | 0.75 (+0.00) | 0.77 | 0.67 | 0.45 | $0.00051 | $0.20 |
| 2 | breadth pass: criteria for 0004.1, 0006.1, 0007.4, 0010.2 (+0003.2 cue) | **0.96 (+0.21 [+0.06, +0.36])** | 0.72 (-0.03 [-0.09, 0.00]) | 1.00 | 0.67 | 0.60 | $0.00052 | $0.31 |
| 3 | *target -> recall*: one untyped public function breaks JRFC-0011.1 (reverted) | 0.90 (+0.15 [+0.03, +0.30]) | 0.78 (+0.03 [+0.00, +0.09]) | 0.89 | 0.89 | 0.58 | $0.00052 | $0.41 |
| 4 | v3 limited to module/class-level functions (reverted) | 0.90 | 0.78 | 0.89 | 0.89 | 0.58 | $0.00052 | $0.51 |

Deltas are paired bootstrap over the 50 test files versus baseline. Labelling (once, not per
round): $10.32. Analyzer (round 2): one subagent, ~132k tokens. Rounds 3-4 were written directly.

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

Rounds 3-4 (target switched to recall@0.7, precision held): telling Jev that one untyped public
function breaks JRFC-0011.1 raised test recall 0.72 -> 0.78 but lowered precision 0.96 -> 0.90;
on train the new flags were Jev errors, checked with Python's ast: nested helpers counted as
public, and a file with no untyped public function flagged at 0.82-0.91. Narrowing the line (v4)
moved scores by 0.016 on average and changed no flag. Jev judges "how typed does this file look",
it cannot count which functions lack hints. Both reverted; v2 stays the winner. JRFC-0011.1 is
mechanical, so JRFC-0001.5 applies: it should be `Enforcement: linter` (an ast or ruff ANN check),
which gives exact recall and precision for the rule that holds 30 of the 36 gold violations.
