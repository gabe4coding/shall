# v3: JRFC-0011.1 is broken by one untyped public function

Target switched to recall@0.7 (precision@0.7 held). On train, 8 of the 12 missed rows at 0.7
are JRFC-0011.1 on files that are mostly typed but have one or two public functions without a
parameter or return hint: applies ~0.97, violates 0.51-0.69 (round-2 analyzer, train only). Jev's
default violation question asks whether the code "clearly breaks" the rule, and a mostly typed
file does not read as clearly breaking it. The statement says all public functions SHOULD be
typed, so one untyped public function is a violation; this round adds a `Violated when:` line
that says exactly that. No statement text changes. Owner: data-platform (JRFC-0011 is a draft).
Risk to precision: files where every public function is typed could now score higher; the one
remaining test false positive at 0.7 is already JRFC-0011.1.
