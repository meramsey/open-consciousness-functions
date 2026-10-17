# Approved cue migration: quality, coverage and performance

Status: approved editorial migration implemented; repository-wide 100% coverage remains incomplete.

Predecessor: `21e63ac6f8bf5a7bce9506f033330df967aa4f97`. Exact measured source fingerprints and every remaining statement range/branch arc are in [the gap report](OCF_APPROVED_CUE_COVERAGE_GAPS.json). Measurement uses the isolated candidate and excludes pending user drafts.

## Full-suite measurements

Plain: 2058 passed / 2 skipped; wall 220.70s.
Instrumented: 2058 passed / 2 skipped; pytest phase 517.15s, reporting 85.04s, total external wall 602.46s.

Environment: Python 3.12.3 / linux, two loadfile workers. Versions: {"coverage": "7.16.2", "mcp": "1.30.0", "pytest": "9.1.1", "pytest-cov": "7.1.0"}.

Warm filesystem/import caches after focused verification; no cache clearing. Plain first, instrumented second on the same unchanged tree.
Identical collected nodes and taxonomy were checked. The normal pytest selection is the entire suite in both modes. The two skips retain the existing explicit Piper/full-session smoke opt-ins; actual bounded auditions ran separately.

- combined: statements 16450/18218 (90.29531233%); branches 6269/7360 (85.17663043%); remaining 1768 statements / 1091 branches.
- unit: statements 10685/18218 (58.65078494%); branches 4706/7360 (63.94021739%); remaining 7533 statements / 2654 branches.
- integration: statements 9659/18218 (53.01899221%); branches 4132/7360 (56.14130435%); remaining 8559 statements / 3228 branches.

Existing source denominator preserved and expanded, no omissions/exclusions. Root/delegating entrypoint wrappers remain outside this established application/tool scope. Unit/integration are overlapping attributed contexts, not independent complete runs.
No floor was lowered. Independent floors remain combined 89.5% statements / 84% branches and unit 57% statements / 62% branches; all pass. Coverage does not establish correctness.

## Comparable timing/resource scope

Serial warm runs, plain first/instrumented second, same source/interpreter/dependencies/two workers and identical collected nodes/taxonomy. GNU time resource figures are process-tree accounting, not summed simultaneous-worker peak. Shared host load is reported, not controlled. No speedup claim against historical runs.

Plain maximum resident set: 1244792 KiB; user/system CPU 397.65/56.31s.
Instrumented maximum resident set: 5177904 KiB; user/system CPU 1000.31/66.12s.

Slow-test reports are retained in both pytest logs under the local benchmark directory. Instrumentation and reporting overhead are distinguished; no worker-count change is inferred from these two runs.

## Verified migration and follow-up

See [the implementation/evidence checkpoint](OCF_APPROVED_CUE_MIGRATION.md). Exact approved English values, 21-entry allowlist, immutable 001 artifacts, current 002 lock, locale bindings and historical-only aliases are covered by meaningful unit/integration regressions. Selected stale recordings never fall back silently, changed speech misses cache and unchanged speech remains reusable. Existing CLI/MCP/LSP protocol boundaries are tested, not merely parser acceptance.

The first plain run found unrelated partial-locale overvalidation, legacy unbound-composition fixture compatibility and one expected display-versus-spoken assertion change. Those causes were corrected. Nested LSP fixture environments initially could not see dependencies inherited via a .pth file; the isolated environment now directly exposes the already-installed dev packages without reinstalling servers or changing the active environment. Failed diagnostics remain local. Passing measurements come from the corrected same-tree pair.

## Remaining coverage queue

- `scripts/ocf_tools/complete_session.py`: 149 statements / 88 branches; ranges `58,63,69,83,88,139,152,166,173,183,189,196,200,209,215,221,231,235,240,335,353,359,378,390,397,475,482,488,501-504,509-510,531,580,584,592,633,644-646,667,730-731,743-744,748,752-753,769,789,793-794,801-812,816,834-845,853-854,863,928,930,992,1021,1025-1026,1030-1031,1034,1074,1107,1110-1116,1123,1130-1133,1135-1136,1138-1146,1149-1152,1155,1158,1164-1166,1171-1172,1175,1177,1179,1194-1195,1297-1298,1303-1309,1312-1316,1318-1319,1322`.
- `scripts/ocf_tools/cli.py`: 120 statements / 70 branches; ranges `847-848,850,862,1199,1201,1203-1204,1208-1209,1211,1221-1222,1224,1231-1232,1235-1236,1239-1240,1242,1252-1253,1261-1262,1264,1278,1280,1319,1325,1439,1441,1458,1460,1465,1467,1469,1476,1478,1480,1482-1485,1487,1489,1491-1493,1503-1504,1506,1508,1510-1516,1518,1524,1526-1527,1530,1537-1538,1540,1542,1544-1548,1550-1552,1557-1559,1561-1563,1594,1641-1642,1672,1674,1676-1679,1687-1688,1740,1743,1776,1778,1780-1781,1806,1808-1809,1811-1812,1820-1823,1826-1827,1837-1838,1841-1844,1846-1848`.
- `scripts/ocf_tools/agent_api.py`: 98 statements / 49 branches; ranges `27,65,95,106-107,121,141,144,174,176,299,302,304,313-316,347,363,380,386-387,389-390,418-421,443,475-476,478-484,496,502,504,519,521,538-539,541-542,545-546,570,572-575,595,597,604,606-608,634-635,637-638,646,667,672,674,690-691,693-694,696-697,722,726,754,762-763,804-808,811-813,902,904,909,911-916,998,1012`.
- `scripts/ocf_tools/dev_jobs.py`: 92 statements / 57 branches; ranges `36,59,61,71,79,123,125,129,131-133,138-141,151,155,160,164,168,181-182,184-185,188,195,252,254,256-258,260-261,263-265,267,316,323,331,349,394-395,399,425,436-438,449,463,474,523-524,528,536,551-553,556-557,639,641-642,650,652-653,655-656,682,684-685,687-688,690,695-700,702,704,706-707,712,714-715,717,726,738,800,807`.
- `scripts/ocf_tools/custom_voices.py`: 80 statements / 51 branches; ranges `58,64,69,71,74,80,123-124,133,135,141,147,151,154,156,158,160-162,233,238,247,275,297,342,348,352,373,381,396-399,411,416,420,437-438,474,478,495,499,507,522,540-546,556-567,570-574,583-591,601,610-611`.
- `scripts/ocf_tools/narration_cli.py`: 77 statements / 41 branches; ranges `102-103,136-137,139-140,142,144-151,157-179,184-186,198-207,217-223,231-234,240-243,257,259-261,266-267,273-276,281`.
- `scripts/ocf_tools/narration_first.py`: 66 statements / 46 branches; ranges `72,74-76,84-89,92,95,98-99,106-113,133,141,148,178,183,189,221,295,397,420,435,442,451,454,463,467,472,478,499,501,531,533,554,575-576,606,621-622,625-626,655,657,669,738,741,743,747-749,752-755,759`.
- `scripts/tools/verify_development_v2.py`: 65 statements / 14 branches; ranges `145-153,156-164,167-183,185-186,191,201-202,205-211,218,224-225,228-229,234-243,250,266-267`.
- `scripts/ocf_tools/authoring.py`: 56 statements / 45 branches; ranges `80,82,139,155,158,214,228,306,319,323,326,328,330,332,334,336,342,344,347-351,355,365-367,375,441,449,462,512,656-657,683,708,730,755-756,834,894-896,899-900,903,906,968-970,975-977,986-987,1019`.
- `scripts/ocf_tools/artwork.py`: 54 statements / 32 branches; ranges `30,55,60,67-68,70,88,185,241-242,251,260-261,268,333,336-339,341,351-358,365-367,370-374,376,415,417,420,430,432,496,548,591-594,598,620-621,642,648,687`.

Next tests: complete-session failure publication/rollback, CLI and agent argument failures, job identity/cancellation/crash races, recording specificity and stale-source boundaries, and cache corruption. Frozen listening-dependent acceptance is not fabricated to reach a percentage. Exact-final-commit CI and native platform results are verified separately after publication.
