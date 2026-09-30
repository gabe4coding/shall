# v4: v3's JRFC-0011.1 line, limited to module- and class-level functions

v3 (one untyped public function breaks JRFC-0011.1) raised test recall@0.7 0.72 -> 0.78 but
cost precision 0.96 -> 0.90: on train the new false positives were two files (checked with
Python's ast, not a model): one whose only untyped functions are nested helpers, which are not
public; one with no untyped public function at all (Jev over-eager). This round keeps the rule
of v3 and says which functions are public (module level or directly in a class, not nested) and
that a file whose public functions are all fully hinted follows the requirement. Same meaning
as the statement. Compared against v2 (the best so far); revert to v2 if precision does not hold.
