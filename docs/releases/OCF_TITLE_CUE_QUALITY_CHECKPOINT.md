# Title–cue quality and coverage checkpoint

Status: proposal/tooling checkpoint delivered; repository-wide 100% coverage remains incomplete.

Baseline source: `fb66fbce11dd3d71e57fac4d5784365128d41c82`. Measurements use an isolated committed checkout plus only this task's staged source changes, excluding existing user proposals. Exact candidate source hashes and every uncovered statement/branch region are in [the gap report](OCF_TITLE_CUE_COVERAGE_GAPS.json).

## Current measurements

Linux / Python 3.12.3, two loadfile workers. Baseline 1910 passed / 2 skipped in 552.37s. Final 1942 passed / 2 skipped in 566.15s. No unexpected deselection or ambiguous classification.

- Baseline combined: statements 15539/17382 (89.39707744%); branches 5904/7004 (84.29468875%); remaining 1843 statements / 1100 branches.
- Baseline unit: statements 9797/17382 (56.36290415%); branches 4326/7004 (61.76470588%); remaining 7585 statements / 2678 branches.
- Baseline integration: statements 9394/17382 (54.04441376%); branches 4009/7004 (57.23872073%); remaining 7988 statements / 2995 branches.
- Final combined: statements 15846/17656 (89.74852741%); branches 6019/7112 (84.63160855%); remaining 1810 statements / 1093 branches.
- Final unit: statements 10088/17656 (57.13638423%); branches 4435/7112 (62.35939258%); remaining 7568 statements / 2677 branches.
- Final integration: statements 9607/17656 (54.41209787%); branches 4105/7112 (57.71934758%); remaining 8049 statements / 3007 branches.

Unit/integration are strict, overlapping per-test-context contributions, not independent complete runs; startup/unattributed subprocess work is combined-only. Do not sum them. Coverage does not establish correctness. No exclusions/omissions were added and no test was reclassified to improve percentages.

## Verified independent improvements

- Complete proposal/contextual teaching review for 55 functions/97 commands; no active vocabulary, aliases or protected narration edits.
- Source closure and read-only report regressions cover nested whole phrases, exact excerpts/line evidence, source drift, locale-manifest changes, unexpected dependencies, CWD template shadowing, history failures and separate control resources/nonspoken markers.
- Complete-session preflight reports missing pacing/voice intentionally, honors explicit pacing overrides even without template pacing, and uses the documented sys.byteorder API. Valid default plans and source voice forwarding remain protected; no DSP, timing, repetitions or locked configuration changed.
- Executed session-plan wizard enters real CLI/prompts/generator with isolated output, verifies schema/shared hash and no release promotion, and refuses manually owned output without partial publication.
- Existing Seeing documentation is corrected to reflect currently aligned PLUS-SEE BETTER, without altering that cue or manufacturing modes.

## Validation and limitations

Measured regression floors are raised to combined 89.5% statements / 84% branches and unit 57% statements / 62% branches. The existing summary passes all four independent gates; these are regression guards, not the 100% target. No floor is lowered.

make check and make lint pass in isolation. Function validation retains six preexisting warnings (partial Spanish and legacy/canonical vocabulary length); English validation has zero errors/warnings. Indexes and all 55 en-US source plans are fresh; all 177 protected narration fingerprints pass. Ruff/format, internal links, README artwork/badges, interface inventory and twelve safe executions pass. markdownlint-cli2 separately validates all tracked Markdown because make lint's optional markdownlint wrapper is absent.

Committed inventory: 98 CLI leaves, 36 MCP tools, seven resources, one prompt, 40 schemas, 14 LSP methods. The existing uncommitted search feature advertises 99 leaves; it is preserved and excluded from this checkpoint. Parser/schema checks, executed workflows and real protocol tests remain distinct. No full-session render, listening, cloning/training or release approval is claimed.

The two skips retain their existing explicit Piper and complete-session smoke opt-ins. An interrupted final coverage launch and recursive scratch-inclusive Markdown glob were retained as diagnostics; successful results come from the completed resumed measurement and bounded tracked-document lint, not those interrupted attempts.

## Remaining technical queue

- Source/recording containment, stale fingerprints and hybrid selection precedence with synthetic manifests.
- Job identity/cancellation/crash-report races using genuine worker integration.
- Template inheritance cycles and cache corruption/invalidation.
- Artwork and release publication/rollback failures with small real-codec fixtures.
- Locale critical-dependency coherence using existing resolution records, explicit cue bindings and script variants.
- LSP unsaved-buffer/reference invalidation and cross-platform launcher failure propagation.
- Per-channel stereo quality acceptance: inspect left-dead/right-dead verification counterexample without altering DSP.

Highest remaining combined statement gaps (exact regions and all scopes in JSON):

- `scripts/ocf_tools/complete_session.py`: 213 statements / 117 branches; statement ranges `58,63,69,83,88,139,152,166,173,183,189,196,200,209,215,221,231,235,240,335,353,359,378,390,397,475,482,488,501-504,509-510,520,531,542,544,578,582,590,596-601,604-605,622,633-635,643-657,659-660,667-675,677-679,681,699,701-707,717-720,727,731-733,736-737,740-742,749-752,757-758,762-764,772-773,777-779,785-796,800,818-829,837-838,847,912,914,976,1005,1009-1010,1014-1015,1018,1058,1091,1094-1100,1107,1114-1117,1119-1120,1122-1130,1133-1136,1139,1142,1148-1150,1155-1156,1159,1161,1163,1178-1179,1281-1282,1287-1293,1296-1300,1302-1303,1306`.
- `scripts/ocf_tools/cli.py`: 120 statements / 70 branches; statement ranges `839-840,842,854,1191,1193,1195-1196,1200-1201,1203,1213-1214,1216,1223-1224,1227-1228,1231-1232,1234,1244-1245,1253-1254,1256,1270,1272,1311,1317,1410,1412,1429,1431,1436,1438,1440,1447,1449,1451,1453-1456,1458,1460,1462-1464,1474-1475,1477,1479,1481-1487,1489,1495,1497-1498,1501,1508-1509,1511,1513,1515-1519,1521-1523,1528-1530,1532-1534,1565,1612-1613,1643,1645,1647-1650,1658-1659,1711,1714,1747,1749,1751-1752,1777,1779-1780,1782-1783,1791-1794,1797-1798,1808-1809,1812-1815,1817-1819`.
- `scripts/ocf_tools/agent_api.py`: 98 statements / 49 branches; statement ranges `27,65,95,106-107,121,141,144,174,176,299,302,304,313-316,345,361,378,384-385,387-388,416-419,441,473-474,476-482,494,500,502,517,519,536-537,539-540,543-544,568,570-573,593,595,602,604-606,632-633,635-636,644,665,670,672,688-689,691-692,694-695,720,724,752,760-761,802-806,809-811,900,902,907,909-914,996,1010`.
- `scripts/ocf_tools/dev_jobs.py`: 92 statements / 57 branches; statement ranges `36,59,61,71,79,123,125,129,131-133,138-141,151,155,160,164,168,181-182,184-185,188,195,252,254,256-258,260-261,263-265,267,316,323,331,349,394-395,399,425,436-438,449,463,474,523-524,528,536,551-553,556-557,639,641-642,650,652-653,655-656,682,684-685,687-688,690,695-700,702,704,706-707,712,714-715,717,726,738,800,807`.
- `scripts/ocf_tools/custom_voices.py`: 80 statements / 51 branches; statement ranges `58,64,69,71,74,80,123-124,133,135,141,147,151,154,156,158,160-162,233,238,247,275,297,342,348,352,373,381,396-399,411,416,420,437-438,474,478,495,499,507,522,540-546,556-567,570-574,583-591,601,610-611`.
- `scripts/ocf_tools/narration_cli.py`: 77 statements / 41 branches; statement ranges `102-103,136-137,139-140,142,144-151,157-179,184-186,198-207,217-223,231-234,240-243,257,259-261,266-267,273-276,281`.
- `scripts/ocf_tools/narration_first.py`: 65 statements / 45 branches; statement ranges `72,74-76,84-89,92,95,98-99,106-113,133,141,148,175,180,186,218,382,405,420,427,436,439,448,452,457,463,484,486,516,518,539,560-561,591,606-607,610-611,640,642,654,723,726,728,732-734,737-740,744`.
- `scripts/tools/verify_development_v2.py`: 65 statements / 14 branches; statement ranges `145-153,156-164,167-183,185-186,191,201-202,205-211,218,224-225,228-229,234-243,250,266-267`.
- `scripts/ocf_tools/authoring.py`: 59 statements / 46 branches; statement ranges `80,82,139,155,158,214,228,306,319,323,326,328,330,332,334,336,342,344,347-351,355,365-367,375,439,447,460,510,654-655,681,706,728,753-754,821-823,832,892-894,897-898,901,904,966-968,973-975,984-985,1017`.
- `scripts/ocf_tools/artwork.py`: 54 statements / 32 branches; statement ranges `30,55,60,67-68,70,88,185,241-242,251,260-261,268,333,336-339,341,351-358,365-367,370-374,376,415,417,420,430,432,496,548,591-594,598,620-621,642,648,687`.
- `scripts/tools/benchmark_agent_tools.py`: 52 statements / 8 branches; statement ranges `3,5-8,10-15,18-22,27,35-36,42-44,47-49,76,81-82,87-88,98-106,114,119,121-125,130,135-137,140-141`.
- `scripts/ocf_tools/command_docs.py`: 51 statements / 36 branches; statement ranges `85-86,92,114,116,139,176,213,304,320,348-349,356,384,393,422,431,447,537-540,542-543,548-551,555,563-566,568-574,576-580,585-587,589-591`.

Native Windows/macOS results and exact-commit CI must be checked separately after publication; this local measurement is Linux only. Earlier successful CI is not evidence for this candidate. Editorial approval, localized vocabulary/prefix policy and identifier migration remain human decisions.
