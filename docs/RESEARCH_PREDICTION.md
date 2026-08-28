# Questionnaire-driven general event prediction

This document describes the executable product runtime implemented in `src/echo_swm/research/`.
The product contract and acceptance priority remain defined by
[`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md).

## 1. Scope and claims

The runtime estimates conditional distributions of questionnaire responses and social reactions
under a supplied event description. It is a synthetic social simulation, not a clone of real
people and not a guarantee about the future.

The current implementation provides:

- 5,000 stable personality agents per default formal run, expandable to 20,000;
- a persistent multiplex relationship graph;
- baseline, described-event, and optional alternative scenarios;
- at least 30 observe/decide/act/remember ticks;
- multiple reproducible paths and p10/p50/p90 bands;
- six questionnaire response types and per-agent probabilities;
- aggregate and subgroup forecasts, receipts, replay, export, and outcome backfill;
- optional OpenAI-compatible semantic compilation with a deterministic offline fallback.

The current implementation does not claim that a synthetic 5,000-agent population is a
representative sample of a real jurisdiction or community. Such a claim requires authorized
population margins, observed survey panels, event outcomes, temporal validation, and calibration.

## 2. End-to-end data flow

```text
PredictionRequest
  ├─ PopulationSpec or population_id
  ├─ optional population_margin_id
  ├─ Questionnaire or questionnaire_id
  ├─ optional calibration_id
  ├─ EventScenario
  ├─ EvaluationProtocol (locked metric, direction, threshold, forecast_as_of)
  ├─ horizon_ticks >= 30
  └─ paths >= 3
          │
          ▼
Event interpretation
  ├─ explicit value signals
  ├─ constrained LLM compilation when configured
  └─ lexical fallback with confidence/missing-input flags
          │
          ▼
Stable ResearchPopulation
  ├─ agents.parquet
  ├─ relationships.parquet
  └─ profile and artifact hashes
          │
          ├─ optional authorized aggregate margins
          └─ IPF/raking + ESS/design-effect diagnostics
          │
          ▼
Vectorized multiplex simulation
  ├─ baseline_no_event
  ├─ event_as_described
  ├─ zero or more alternatives
  └─ common random numbers for the same path index across every branch
          │
          ▼
Paired counterfactual assessment
  ├─ p10 / p50 / p90 branch-minus-baseline deltas
  ├─ direction consistency and COD
  ├─ locked-metric scenario ranking
  └─ future-information exclusion receipt
          │
          ▼
Questionnaire projection
  ├─ baseline per-agent probabilities
  ├─ post-event per-path per-agent probabilities
  ├─ weighted total
  └─ age / role / channel differences
          │
          ├─ optional validated historical calibration
          └─ question / construct / target-type fallback
          │
          ▼
PredictionResult + immutable artifacts + outcome feedback
```

## 3. Population and stable personality

### 3.1 Stable identity

An agent ID is a SHA-256-derived function of:

```text
population model version + population_id + root seed + row index
```

The generator does not use a run UUID in identity construction. Rebuilding a population with the
same specification and version therefore produces the same agent IDs and stable traits. Each row
also receives a `profile_hash`; the population manifest stores a signature over the ordered list
of profile hashes.

### 3.2 Profile state

The persisted profile contains:

| Layer | Executable fields |
| --- | --- |
| Identity and source | `agent_id`, `source_id`, `profile_origin`, per-section `field_origins` |
| Demography | age, age group, gender, education, household and region type |
| Social position | social role, household ID, segment |
| Personality | five Big Five dimensions and a versioned interpretation definition |
| Values and morals | ten Schwartz values and six Moral Foundation sensitivities |
| Motivation | seven goal priorities, primary goal and primary interest |
| Decision tendencies | five risk scores, four bipolar cognitive axes, six beliefs, trust, skepticism, expression and action tendency |
| Media habits | social media, news, interpersonal, community and search channel shares |
| Memory | working/event counters and a stable long-term memory reference |
| Runtime role | influence score and key/representative/background tier |

All built-in profile sections are marked `synthetic`. The schema can also describe observed and
inferred fields when authorized inputs are added, but origin must never be silently omitted.
The interactive profile endpoint exposes all nine frameworks and 54 dimensions with scale bounds,
pole labels, definition text, model/data/definition versions and a completeness score. See
`docs/PERSONA_DEFINITION.md` and `data_contracts/persona-profile.schema.json`.

### 3.3 Three runtime tiers

For a 5,000-agent population:

- **Key: 50** — highest influence score, lower decision noise, slower and more deliberative state
  updates, and stronger propagation when sharing or participating.
- **Representative: 450** — intermediate policy depth and propagation.
- **Background: 4,500** — vectorized statistical policy preserving population scale and tails.

For populations above 5,000, key and representative counts remain 50 and 450 while the additional
agents enter the background tier. The tier does not decide whether an agent participates. Every
agent executes all four stages at every tick in every scenario and path.

## 4. Multiplex relationship graph

Each agent creates one outgoing edge in each layer:

1. family;
2. acquaintance;
3. coworker;
4. community;
5. online.

Targets are sampled from compatible pools using household, age, social-role, region, and media
channel homophily. Every edge stores a relationship type, strength, and trust value. A default
5,000-person graph therefore has 25,000 directed edges.

Neighbor aggregation for target agent `j` is:

```text
neighbor(j) = Σ_i strength(i,j) × trust(i,j) × source_value(i)
              -------------------------------------------------
                  Σ_i strength(i,j) × trust(i,j)
```

After interaction, trust moves slightly upward when source and target stances are compatible and
downward when they diverge. It is bounded to avoid disappearing or explosive links.

## 5. Event interpretation

`EventScenario` is domain independent. It contains title, description, actors, audience, channels,
evidence, intensity, credibility, direct valence, expected outcomes, and alternatives.

The numerical runtime uses six value signals: care, fairness, security, tradition, autonomy, and
community. These signals are resolved in this order:

1. explicit structured signals supplied by the caller;
2. constrained JSON compilation by an OpenAI-compatible model when configured;
3. auditable bilingual lexical fallback.

The LLM prompt explicitly asks for semantics rather than results. Its response is validated by
Pydantic, bounded to `[-1, 1]`, cached by content hash, and subject to call/token budgets. A failed
provider call falls back to local interpretation rather than inventing an answer. Confidence and
missing evidence are carried into the result.

## 6. Per-tick agent runtime

Each scenario and stochastic path starts from a copy of the same initial state. The same path index
uses the same exogenous random stream in every scenario (common random numbers). Scenario-specific
event intensity changes exposure thresholds and subsequent endogenous behavior, so paired branch
differences are less contaminated by unrelated Monte Carlo noise.

### 6.1 Observe

- Direct exposure is sampled per agent from event intensity, credibility, time decay, and that
  agent's channel preferences.
- Relationship exposure is aggregated from neighbors whose previous action was share, discuss, or
  participate.
- An unexposed agent receives no event-alignment, belief, emotion, trust, or risk update. A node
  without an incoming active edge receives zero social signal rather than a population-average
  fallback.
- Key and representative agents have explicit propagation multipliers, but background agents can
  also initiate and relay exposure.
- Awareness increases monotonically with bounded remaining capacity.

### 6.2 Decide

- Event-to-person alignment combines the six value dimensions, direct valence, personal relevance,
  information skepticism, credibility, and neighbor stance.
- Support moves toward a bounded target at a tier-specific deliberation rate.
- Belief confidence, emotion, trust, and perceived risk update from awareness and consistency.
- Seven action logits are calculated for every agent: support, oppose, share, discuss, silence,
  participate, and exit.
- A seeded Gumbel draw selects an action. Key agents use lower decision noise; no tier uses hidden
  unseeded randomness.

### 6.3 Act

The selected action becomes an observable network signal. Share, discuss, and participate actions
carry exposure; active stances affect social feedback. Aggregated action shares form the public
timeline, while individual action arrays are retained for receipts and replay hashes.

### 6.4 Remember

Reached agents update bounded working memory and cumulative event memory. Every agent is still
processed by the four-stage loop. Each tick separately records operational stage counts and
`directly_exposed`, `socially_exposed`, `newly_exposed`, `cumulative_exposed`, and `unexposed`.
This prevents a processing receipt from being misread as universal information exposure.

## 7. Questionnaire projection

### 7.1 Supported response types

| Type | Per-agent output | Aggregate output |
| --- | --- | --- |
| Single choice | normalized option probability vector | option share bands |
| Multiple choice | independent option selection probabilities | selection-rate bands |
| Scale | probability over integer scale values | scale distribution bands |
| Ranking | option utility distribution | predicted rank and share bands |
| Numeric | bounded numeric expectation | numeric p10/p50/p90 |
| Open text | structured theme membership | theme shares and simulated representative answers |

Each question declares a generic latent construct such as awareness, support, trust, risk, emotion,
participation, sharing, confidence, fairness, or personal impact. The runtime projects the current
agent state onto the construct and then onto the response space. Explicit option positions are
recommended; missing positions or unsupported constructs set the question's out-of-distribution
flag.

### 7.2 Baseline and post-event

The baseline questionnaire uses the common initial state. The post-event questionnaire is computed
for every path of `event_as_described`. The stored individual table includes one baseline and one
representative post-event probability record per agent and question; the displayed interval uses
all post-event paths.

### 7.3 Group differences

The default group dimensions are age group, gender, social role, organization type, education and
primary information channel. Every category is retained in the cross-tab with prototype count,
represented weight, weighted share and the complete response distribution or numeric mean. The
largest signed deviations remain available as a compact insight list.

### 7.4 Open responses

Open responses are not claimed as verbatim human statements. The implementation clusters state
into support, concern/opposition, and observation themes, then produces explicitly labeled
"simulated answers" from structured drivers. Every question can additionally expose up to three
synthetic representative responses grounded in role, organization type, goal, value and channel;
the API and interface permanently mark them as synthetic.

## 8. Uncertainty and downstream reactions

Every scenario is run on `K` seeded paths. Timelines expose p10, p50, and p90 for awareness,
support, opposition, sharing, discussion, silence, participation, exit, polarization, and trust.

The first downstream layer is intentionally generic:

- broad awareness;
- discussion surge;
- polarization risk;
- visible collective participation.

Each item includes a probability band and likely crossing tick. Domain-specific downstream events
can be added through a future typed outcome compiler, but the system does not invent arbitrary
event names from random text.

### 8.1 Constrained-L2 decision protocol

Before a run, `EvaluationProtocol` locks a primary metric, optional auxiliary metrics, desired
direction, minimum meaningful effect, no-event baseline, horizon, and `forecast_as_of`. Evidence
whose `available_at` is later than that cutoff is excluded before semantic compilation.

For each non-baseline branch and metric, the engine calculates the pathwise final-state difference
against the matching baseline path. COD is transparent and bounded rather than a hidden model
score:

```text
direction_consistency = fraction of paired paths moving in the desired direction
magnitude_score = min(1, positive median oriented delta / minimum meaningful effect)
metric_COD = direction_consistency × magnitude_score
```

Scenario COD is the weighted mean across locked metrics. The report also ranks all branches by
weighted metric utility. If two non-baseline interventions differ by less than the locked threshold
on every metric, the result explicitly marks them as currently indistinguishable.

## 9. Persistence and replay

Each formal run writes:

- the normalized request;
- the user-facing result JSON;
- questionnaire CSV;
- per-agent probability Parquet;
- per-path timeline CSV;
- replay JSONL;
- a run manifest.

Every replay record contains scenario, path, tick, previous record hash, full-state hash, four stage
counts, five visibility counts, three tier counts, and its own hash. Verification checks:

1. every artifact hash in the manifest;
2. every replay chain link;
3. every record hash;
4. all four participation counts;
5. tier totals;
6. exact expected record count (`scenarios × paths × ticks`).

The deterministic signature binds normalized request, population signature, questionnaire, and
final state hashes. Run IDs and creation timestamps do not enter this signature.

### 9.1 Report assurance

Every new result includes `report_metadata` and `report_quality`. Metadata records model/data
versions, seed, path and tick counts, scenarios, requested/successful/failed agents, represented
population, effective sample size, source, weighting method, interval definition, calibration and
profile signature. The quality gate checks interval ordering, probability/action mass, full Agent
completion, interval collapse, cross-tab and representative-response coverage, calibration,
population grounding, future-information isolation and semantic coverage. Uncalibrated or
ungrounded runs remain valid simulations but receive visible warnings rather than implied accuracy.

## 10. Population grounding, outcome backfill, and calibration

`POST /v1/population-margins` accepts authorized de-identified aggregate margins. Supported
dimensions are age group, education, gender, primary channel, region type, and social role. The
runtime rakes the synthetic prototypes to the supplied totals with IPF, rejects unsupported cells,
and reports convergence, maximum relative error, effective sample size, design effect, and extreme
weight warnings. Grounded weights are scoped to the prediction and do not mutate the registered
base population. Questionnaire totals, groups, reaction timelines, action shares, open-theme
intervals, and driver correlations use the same weights.

`POST /v1/calibration-datasets` accepts aggregate historical records for question-option shares and
resolved event outcomes. Every record carries both `forecast_as_of` and `outcome_available_at`.
Fitting sorts by forecast time, reserves the final temporal block as holdout, and only trains on
outcomes that were available by the holdout cutoff. This prevents future-outcome leakage.

`POST /v1/calibrations` fits temperature/bias calibration at exact question-option or event-outcome
level when support is sufficient, then falls back through questionnaire construct or target type.
The profile is marked `validated` only when both weighted holdout Brier score and log loss do not
worsen. Candidate profiles that fail the gate remain inspectable but are never applied by the
runtime. Validated profiles calibrate both questionnaire option distributions and generic
downstream-event probabilities.

`POST /v1/predictions/{run_id}/outcomes` stores actual questionnaire shares, numeric means, event
outcomes, per-scenario final metrics, sample size, timestamp, and notes. Comparable values receive
an immediate squared-error report. Scenario metrics additionally produce direction accuracy,
Top-1, Spearman, Kendall, 80% interval coverage, interval width, and WIS. Valid question-option and
event-outcome observations are also appended to the calibration backfill log for construction of
the next immutable dataset version.

The result always exposes grounding and calibration status. Without supplied data it explicitly
states `synthetic_unanchored` and `uncalibrated_prior`; importing a dataset alone does not create an
accuracy claim.

## 11. Scaling and LLM integration

The runtime uses NumPy arrays and PyArrow tables rather than an operating-system process per agent.
For 5,000 agents, 30 ticks, three scenarios, and eight paths, the core workload is a bounded set of
vector operations over agents and 25,000 edges.

An LLM provider can be added without changing the numerical contract. Current integration is used
for event semantic compilation. Future key-agent response generation may use the same adapter, but
must remain JSON constrained, budgeted, cached, replayable, and summarized as decision factors
rather than hidden chain-of-thought.

## 12. Acceptance evidence

The automated suite verifies:

- stable IDs and profile signatures across regeneration;
- exact 50/450/4,500 tiers;
- five relationship types and 25,000 edges;
- all six question types in one 10-question page;
- 5,000 participants in all four stages;
- 30 ticks and baseline/event/alternative scenarios;
- per-agent baseline and post-event records;
- three group dimensions;
- deterministic signatures;
- identical intervention branches produce identical paired paths under common random numbers;
- forecast-time evidence isolation, COD, paired deltas, and locked-metric ranking;
- replay visibility counts distinguish actual exposure from four-stage processing;
- replay record counts and artifact hashes;
- JSON/CSV export and actual-outcome feedback;
- authorized aggregate raking and effective-sample diagnostics;
- leakage-safe temporal calibration for questionnaire and event outcomes;
- calibration non-regression gates and result-level data-status reporting;
- full P0 HTTP round trip;
- frontend lint, strict TypeScript check, and production build.
