# Progress

## 2026-08-28

- Default Social World migrated from Suzhou to Guiyang without modifying the legacy SWM repository,
  Zeabur project, services, domains, variables or volumes.
- The Guiyang world runs 5,000 weighted prototypes representing 6,668,900 synthetic residents and
  exposes seven product scenes: Guiyang International Conference and Exhibition Center, Guiyang
  Big Data City, Guizhou University West Campus, Jiaxiu riverfront, Qingyan Ancient Town, Guiyang
  North Railway Station and Huaguoyuan community.
- Frontend map anchors, guided stories, weather, search, persona fixtures, scene generators and
  event templates now use Guiyang semantics. MapLibre fallback converts GCJ-02 product anchors to
  WGS-84 instead of shifting the city layer.
- Added a Guikesong peak-flow scenario, regenerated JSON Schemas and created an isolated Git history
  plus the `swm-guizhou` Zeabur project. Per the project owner's 2026-08-28 decision, the new project
  shares the existing 4C/8GB server while retaining independent services and domains. The public
  Web and API are running at `swm-guizhou.zeabur.app` and `swm-api-guizhou.zeabur.app`.
- The desktop L2/L3 experience now uses OpenFlipbook-inspired 2.5D illustrated pages for all seven
  locations, building interiors, rooms, floors and persona hotspots. The old Three.js renderer and
  dependency were removed. The local reference repository is excluded from Git and deployment
  contexts; the adapted implementation retains the upstream MIT notice.
- DeepSeek-compatible JSON calls now disable thinking and retry invalid provider output, while event
  forecasts support zero-metric queries. A production LLM probe returned `connected`; live Guiyang
  event run `eventrun_b198ef7e30674aaf` completed two branches and passed replay verification.
- Deployments `6a919ca3db37f2e6ddbc0bb0` (API) and `6a919ca2db37f2e6ddbc0baf` (Web)
  are running in the isolated `swm-guizhou` Zeabur project. Public desktop acceptance passed for the
  AMap Guiyang city view, 2.5D venue drilldown, interior pages, floor switching and persona controls.
- Current quality gates: Ruff and formatting passed; strict mypy passed for 90 source files; 57
  backend tests passed with 87.96% total branch-aware coverage; frontend ESLint, strict TypeScript
  and production build passed.
- Production acceptance job `job_f1961a9052ee4c51` completed 3 independent decision rounds and
  15,000 decisions. Its result is available only from the Guizhou API; the legacy Suzhou API returns
  `404` for the same job ID.

## 2026-08-25

- Human Digital Twin contracts expanded from loose dictionaries to typed Big Five, Schwartz,
  Moral Foundations, risk, cognitive-style, goal, belief, emotion, memory, relationship and mental
  state structures.
- The stable research population now carries complete correlated personality/value/moral/risk/
  cognition/goal/belief vectors with field origins and immutable profile hashes.
- Added a unified, map-provider-independent Social World backend with a hierarchical city/campus
  location tree, capacity-aware mobility, six relationship types, six propagation channels,
  multi-event exposure and the fixed causal sequence `exposure -> belief -> emotion -> goal ->
  intention/action -> memory -> relationship`.
- Historical Suzhou baseline ran 5,000 weighted prototypes representing 13,047,700 synthetic
  residents; all 50 key, 450 representative and 4,500 background Agents executed every stage.
- Added population heatmap, emotion and belief distributions, diffusion curves, segment differences,
  location activity, Agent traces, final action distributions, profile search, Agent detail and
  location drilldown APIs without adding any frontend or AMap dependency.
- Each run persists population/relationship Parquet, locations, trajectory, Agent traces, NPZ
  snapshots, chained replay, result and manifest. Replay verifies tick continuity, immutable
  personality signatures, snapshot state hashes and every artifact hash.
- Added JSON Schemas, ADR 0005, implementation documentation, unit coverage and FastAPI integration
  coverage for the new path.
- Historical pre-Suzhou Social World acceptance run `worldrun_d54963e0d01c4dbd`: 5,000 weighted
  prototypes, 13,500,000 represented people, 3 paths × 72 ticks, 71.25% mean reach at tick 72 with a
  65.50%—75.86% p10—p90 path band, 876 Agent trace rows and 236 heatmap cells.
- All 219 replay records passed count, path-count, hash-chain, tick-sequence, immutable-personality,
  snapshot and artifact-hash checks. Discrete first-touch, untouched-belief, baseline-stress and
  awareness-gated-action invariants are covered by tests.
- Current backend quality gates: Ruff passed, strict mypy passed for 79 source files, 44 tests
  passed, and total branch-aware coverage is 86.96%.

## 2026-08-24

- Primary product rebuilt as a questionnaire-driven general event predictor with a five-step UI;
  city, policy, market, and governance surfaces are no longer in the main navigation.
- Stable generic personality population: 5,000 default agents with exact 50 key / 450
  representative / 4,500 background tiers, complete source/origin, trait/value/goal/channel/memory
  fields, and 25,000 family/acquaintance/coworker/community/online relationships.
- Every tier now participates in every `observe -> decide -> act -> remember` tick. The runtime
  propagates exposure and actions through relationship strength/trust, updates state, memory, and
  relationship trust, and supports baseline, described-event, and alternative scenarios.
- Questionnaire runtime supports single choice, multiple choice, scale, ranking, numeric, and open
  responses; it persists per-agent baseline/post-event probabilities and reports weighted totals,
  three group dimensions, uncertainty bands, structured themes, receipts, and OOD warnings.
- P0 research API, outcome backfill, JSON/CSV export, deterministic signatures, chained replay,
  CLI demo, JSON Schemas, and detailed technical/product documentation completed.
- Optional LLM semantics compiler is ready for an OpenAI-compatible API; offline lexical fallback
  remains executable and visibly reports confidence/missing evidence.
- M6 data-grounding path implemented: authorized aggregate population margins are versioned and
  raked with convergence/ESS/design-effect diagnostics; the derived weights now drive questionnaire,
  group, timeline, action, theme, and driver aggregation without mutating the base population.
- Historical questionnaire shares and resolved event outcomes now support versioned, leakage-safe
  temporal calibration. Exact target, construct, and target-type fallbacks are evaluated on a final
  time block; candidates that do not improve both Brier and log loss are retained but not applied.
- The five-step UI accepts both datasets as optional JSON inputs and reports population-grounding,
  calibration, represented-population, and effective-sample status in plain language.

- Architecture and four ADRs created before implementation.
- M0 foundation: package, configuration, contracts, deterministic utilities, synthetic generator, manifests, tests/tooling, CLI and docs.
- Executable vertical slice: weighted training, calibration, held-out evaluation, event-conditioned prediction, graph diffusion, three branches, tier selection, snapshots/replay, reports and FastAPI.
- Optional OpenAI-compatible provider configured only through environment variables.
- Cross-domain event forecasting runtime: timestamped evidence, candidate base hazards, state
  thresholds, parent-event lag windows, impact feedback, daily probability curves, conditional
  event times, severities, event chains, common-random-number interventions, immutable path
  artifacts, replay verification, and resolved-outcome backtesting.
- Suzhou coupled city profile: official city/district anchors, 15,000 weighted synthetic
  prototypes, households, organizations, OD, multiplex relations, ScopeQuery, organizational and
  resident joint evolution, common-random-number counterfactuals, K-path bands, API/CLI, report,
  SHA-256 checkpoints, and replay verification.
- Remaining work is tracked in `docs/IMPLEMENTATION_BACKLOG.md` and is not claimed complete.

### Verified result

- Questionnaire prediction formal run: `prediction_f8fbad4f6f114da0`, 5,000 agents, 10 mixed
  questions, 3 scenarios × 8 paths × 30 ticks; all 720 replay records, four stage counts, tier
  counts, state chains, and six output artifact hashes verified.
- The formal run persisted 100,000 per-agent baseline/post-event question records and 31 timeline
  states per path.
- Frontend: ESLint passed, strict TypeScript passed, Vinext production build passed; live smoke test
  returned HTTP 200 for `/`, `/predict`, `/api/echo/health`, and recent-project proxy requests.
- Current quality gates: Ruff passed, strict mypy passed for 72 source files, 41 tests passed, total
  branch-aware coverage 86.28%. Frontend ESLint, strict TypeScript, and production build passed.

- Formal demo: 10,000 synthetic participants, seed 2026, latest run `run_dcb20d3de8c84bf9`.
- Respondent holdout mean: log loss 0.5603, Brier 0.1894, ECE 0.0222.
- Purchase probability (prediction / transparent synthetic ground truth): control 0.7925 / 0.7946; price +30% 0.4990 / 0.5036; price +30% with student discount 0.5489 / 0.5464.
- Suzhou formal run: 15,000 prototypes representing 13,047,700 residents, 3 branches × 8 paths ×
  31 states; latest run `cityrun_ce65eba482ba49ac`.
- City replay: all 744 tick records unique and complete; all 15 full-state checkpoints verified.
- Event formal run: 2,048 paths per branch, 45 days, 4 linked candidates; latest run
  `eventrun_7cdf07d9d32d4aa8`, with all 90 daily replay records and the full path artifact verified.
- Previous quality baseline before the questionnaire runtime: 35 tests and 84.57% coverage.
- Replay: 45 persisted snapshots verified. Live HTTP smoke test returned 200 for `/health` and `/openapi.json`; 18 routes were exposed.
