# v2: breadth pass - criteria for four small false-positive causes (+ one near-miss cue)

After v1 no single cause explained enough train false positives to clear the noise floor
(7 FP rows at p >= 0.7 over 4 rules), so this round fixes each independent cause with a minimal
criteria line (Step 4.5 breadth pass). Analyzer read train traces and train files only.

| cause (train evidence) | statement | lever | FP rows >= 0.7 / 0.5-0.7 |
|---|---|---|---|
| demo logins, placeholders, self-generated throwaway keystore passwords read as real secrets | JRFC-0004.1 | Violated when | 2 / 2 |
| subprocess of a local command or a stdio child process read as an outbound network call | JRFC-0006.1 | Not applies when | 2 / 2 |
| developer-tool env switch (turn a behavior off for testing/measurement) read as a feature flag | JRFC-0010.2 | Not applies when | 2 / 2 |
| catch handler that reads no error property still scored as violating | JRFC-0007.4 | Violated when | 1 / 3 |
| CLI progress output still near the line after v1 | JRFC-0003.2 | Not applies when cue | 0 / 10 |

No statement text changes. All 24 train TPs are JRFC-0011.1, untouched by this diff.
Judgment call for the owner (sre): the JRFC-0006.1 line puts code that shells out to a network
CLI (the subprocess makes the call) out of scope of the timeout rule, as the gold labels do.
Owners: security (0004), sre (0003, 0006), frontend (0007), platform (0010).
