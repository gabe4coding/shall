# Scan eval: proposed inputs

100 files, one Jev request each (all fit in one chunk). Rules asked per file: the code prefilter's candidates, all statuses (draft included).

## sca-gap-map @ fc89f0d (39 files)

| id | path | lang | area | lines | rules |
|---|---|---|---|---|---|
| sgm-001 | `.github/workflows/daily-report.yml` | yaml | github | 244 | 30 |
| sgm-002 | `investigations/2026-09-17/claude-verification/report-fixed-code-2026-09-17-cold/compare_today.py` | python | investigations | 90 | 31 |
| sgm-003 | `investigations/2026-09-17/claude-verification/report-fixed-code-2026-09-17-cold/manual_vs_fixed.py` | python | investigations | 105 | 31 |
| sgm-004 | `investigations/2026-09-17/claude-verification/scripts/assemble.py` | python | investigations | 722 | 31 |
| sgm-005 | `investigations/2026-09-17/claude-verification/scripts/build_summary.py` | python | investigations | 51 | 31 |
| sgm-006 | `investigations/2026-09-17/claude-verification/scripts/check_lock.py` | python | investigations | 137 | 31 |
| sgm-007 | `investigations/2026-09-17/claude-verification/scripts/check_protobufjs.py` | python | investigations | 432 | 31 |
| sgm-008 | `sca_gap_map/__init__.py` | python | package | 7 | 31 |
| sgm-009 | `sca_gap_map/__main__.py` | python | package | 8 | 31 |
| sgm-010 | `sca_gap_map/advisories.py` | python | package | 184 | 31 |
| sgm-011 | `sca_gap_map/alerts.py` | python | package | 130 | 31 |
| sgm-012 | `sca_gap_map/audit_source.py` | python | package | 61 | 31 |
| sgm-013 | `sca_gap_map/cache.py` | python | package | 54 | 31 |
| sgm-014 | `sca_gap_map/cli.py` | python | package | 392 | 31 |
| sgm-015 | `sca_gap_map/deep_sweep.py` | python | package | 338 | 31 |
| sgm-016 | `sca_gap_map/fix_prs.py` | python | package | 226 | 31 |
| sgm-017 | `sca_gap_map/github_api.py` | python | package | 63 | 31 |
| sgm-018 | `sca_gap_map/manifests.py` | python | package | 158 | 31 |
| sgm-019 | `sca_gap_map/naming.py` | python | package | 342 | 31 |
| sgm-020 | `sca_gap_map/osv.py` | python | package | 102 | 31 |
| sgm-021 | `sca_gap_map/ownership.py` | python | package | 110 | 31 |
| sgm-022 | `sca_gap_map/pipeline/__init__.py` | python | pipeline | 30 | 31 |
| sgm-023 | `sca_gap_map/pipeline/alerts_discovery.py` | python | pipeline | 81 | 31 |
| sgm-024 | `sca_gap_map/pipeline/audit_ingestion.py` | python | pipeline | 136 | 31 |
| sgm-025 | `sca_gap_map/pipeline/ghost_alerts.py` | python | pipeline | 49 | 31 |
| sgm-026 | `sca_gap_map/pipeline/installed_scan.py` | python | pipeline | 135 | 31 |
| sgm-027 | `sca_gap_map/pipeline/inventory.py` | python | pipeline | 83 | 31 |
| sgm-028 | `sca_gap_map/pipeline/long_rows.py` | python | pipeline | 528 | 31 |
| sgm-029 | `sca_gap_map/pipeline/scoreboards.py` | python | pipeline | 270 | 31 |
| sgm-030 | `sca_gap_map/pipeline/state.py` | python | pipeline | 207 | 31 |
| sgm-031 | `sca_gap_map/pipeline/summary.py` | python | pipeline | 217 | 31 |
| sgm-032 | `sca_gap_map/pipeline/triage.py` | python | pipeline | 562 | 31 |
| sgm-033 | `sca_gap_map/pipeline/unplaced.py` | python | pipeline | 374 | 31 |
| sgm-034 | `sca_gap_map/repos.py` | python | package | 57 | 31 |
| sgm-035 | `sca_gap_map/sbom.py` | python | package | 270 | 31 |
| sgm-036 | `sca_gap_map/util.py` | python | package | 12 | 31 |
| sgm-037 | `sca_gap_map/versions.py` | python | package | 103 | 31 |
| sgm-038 | `tools/compare_reports.py` | python | tools | 171 | 31 |
| sgm-039 | `tools/leadership_summary.py` | python | tools | 430 | 31 |

## plainwright @ b18d4e3 (61 files)

| id | path | lang | area | lines | rules |
|---|---|---|---|---|---|
| pw-040 | `bin/plainwright-computer.mjs` | javascript | bin | 3 | 30 |
| pw-041 | `bin/plainwright-mobile.mjs` | javascript | bin | 3 | 30 |
| pw-042 | `bin/plainwright.mjs` | javascript | bin | 25 | 30 |
| pw-043 | `examples/hooks/login-dataset.mjs` | javascript | examples | 13 | 30 |
| pw-044 | `examples/hooks/mobile-fixture.mjs` | javascript | examples | 13 | 30 |
| pw-045 | `scripts/benchmark-agent.mjs` | javascript | scripts | 94 | 30 |
| pw-046 | `scripts/benchmark-mcp.mjs` | javascript | scripts | 70 | 30 |
| pw-047 | `scripts/benchmark-picks.mjs` | javascript | scripts | 57 | 30 |
| pw-048 | `scripts/benchmark-planner.mjs` | javascript | scripts | 64 | 30 |
| pw-049 | `scripts/benchmark-read.mjs` | javascript | scripts | 45 | 30 |
| pw-050 | `scripts/benchmark-snapshots.mjs` | javascript | scripts | 46 | 30 |
| pw-051 | `scripts/benchmark-steps.mjs` | javascript | scripts | 79 | 30 |
| pw-052 | `scripts/build-plugins.mjs` | javascript | scripts | 34 | 30 |
| pw-053 | `scripts/capture-read-states.mjs` | javascript | scripts | 32 | 30 |
| pw-054 | `scripts/mobile-fixture.mjs` | javascript | scripts | 97 | 30 |
| pw-055 | `scripts/plugin-launcher.mjs` | javascript | scripts | 27 | 30 |
| pw-056 | `scripts/smoke-computer-macos.mjs` | javascript | scripts | 66 | 30 |
| pw-057 | `scripts/smoke-mobile-android.mjs` | javascript | scripts | 107 | 30 |
| pw-058 | `scripts/smoke-mobile-ios.mjs` | javascript | scripts | 112 | 30 |
| pw-059 | `scripts/smoke-mobile.mjs` | javascript | scripts | 20 | 30 |
| pw-060 | `scripts/smoke-plugins.mjs` | javascript | scripts | 63 | 30 |
| pw-061 | `scripts/workflow-benchmark/accounting.mjs` | javascript | scripts | 20 | 30 |
| pw-062 | `scripts/workflow-benchmark/analyze.mjs` | javascript | scripts | 69 | 30 |
| pw-063 | `scripts/workflow-benchmark/artifacts.mjs` | javascript | scripts | 14 | 30 |
| pw-064 | `scripts/workflow-benchmark/fixtures.mjs` | javascript | scripts | 89 | 30 |
| pw-065 | `scripts/workflow-benchmark/jev-usage.mjs` | javascript | scripts | 19 | 30 |
| pw-066 | `scripts/workflow-benchmark/plot.py` | python | scripts | 62 | 31 |
| pw-067 | `scripts/workflow-benchmark/report.mjs` | javascript | scripts | 101 | 30 |
| pw-068 | `scripts/workflow-benchmark/run.mjs` | javascript | scripts | 149 | 30 |
| pw-069 | `src/aria-changes.ts` | typescript | src | 43 | 33 |
| pw-070 | `src/automation.ts` | typescript | src | 92 | 33 |
| pw-071 | `src/cli.ts` | typescript | src | 118 | 33 |
| pw-072 | `src/computer-adapter.ts` | typescript | src | 174 | 33 |
| pw-073 | `src/computer-cli.ts` | typescript | src | 46 | 33 |
| pw-074 | `src/computer-mcp.ts` | typescript | src | 51 | 33 |
| pw-075 | `src/computer-spec.ts` | typescript | src | 28 | 33 |
| pw-076 | `src/computer.ts` | typescript | src | 41 | 33 |
| pw-077 | `src/hooks-child.ts` | typescript | src | 41 | 33 |
| pw-078 | `src/hooks.ts` | typescript | src | 72 | 33 |
| pw-079 | `src/jev.ts` | typescript | src | 358 | 33 |
| pw-080 | `src/mcp-result.ts` | typescript | src | 30 | 33 |
| pw-081 | `src/mcp.ts` | typescript | src | 318 | 33 |
| pw-082 | `src/mobile-adapter.ts` | typescript | src | 155 | 33 |
| pw-083 | `src/mobile-cli.ts` | typescript | src | 11 | 33 |
| pw-084 | `src/mobile-discovery.ts` | typescript | src | 132 | 33 |
| pw-085 | `src/mobile-mcp.ts` | typescript | src | 52 | 33 |
| pw-086 | `src/mobile-spec.ts` | typescript | src | 64 | 33 |
| pw-087 | `src/mobile-tree.ts` | typescript | src | 122 | 33 |
| pw-088 | `src/mobile.ts` | typescript | src | 44 | 33 |
| pw-089 | `src/native-mcp.ts` | typescript | src | 162 | 33 |
| pw-090 | `src/native.ts` | typescript | src | 214 | 33 |
| pw-091 | `src/page.ts` | typescript | src | 384 | 33 |
| pw-092 | `src/planner.ts` | typescript | src | 209 | 33 |
| pw-093 | `src/read.ts` | typescript | src | 127 | 33 |
| pw-094 | `src/results.ts` | typescript | src | 75 | 33 |
| pw-095 | `src/runner.ts` | typescript | src | 300 | 33 |
| pw-096 | `src/serial-queue.ts` | typescript | src | 8 | 33 |
| pw-097 | `src/snapshot-view.ts` | typescript | src | 160 | 33 |
| pw-098 | `src/spec.ts` | typescript | src | 178 | 33 |
| pw-099 | `src/step-kind.ts` | typescript | src | 10 | 33 |
| pw-100 | `src/steps.ts` | typescript | src | 596 | 33 |

## Left out

- `sca-gap-map/sca_gap_map/baseline_data.py`: embedded BlackDuck audit data (vulnerability rows); must not go to TypeSafe
- `tests, fixtures, generated`: not the code a scan must judge first
- `plainwright/examples/*.yaml, examples/mobile/`: plainwright test specs, not code
- `plainwright/plugins/*/bin/launch.mjs`: 3 byte-identical copies of scripts/plugin-launcher.mjs
