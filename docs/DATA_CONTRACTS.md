# Data contracts

All external data enters through Pydantic v2 models in `echo_swm.contracts`. Models reject unknown fields. `PersonProfile` separates static profile from `DynamicAgentState` and carries value origins and explicit missingness. `EventSpec` separates occurrence from availability. Scenario, graph, question, forecast, population, and source contracts enforce ranges and time ordering.

The Human Digital Twin contract adds typed Big Five, Schwartz, Moral Foundations, risk, cognitive-style, goal, belief, emotion, memory, relationship and mental-state models. The social-world API separately validates hierarchical locations, multi-channel event injections, simulation limits and all visualization-neutral result objects. Exported schemas are `social-world-simulation-request.schema.json` and `social-world-simulation-result.schema.json`.

The interactive persona profile is separately exported as `persona-profile.schema.json`. It exposes nine named frameworks, dimension definitions, scale endpoints, localized interpretations, definition/model/data versions, per-section origins and a completeness score. Compatibility fields such as the ranked Big Five and Schwartz lists remain available, but the framework array is the complete machine-readable definition.

Analytical tables use canonical columns and Parquet metadata. The demo labels every table `SYNTHETIC DATA — NOT REAL HUMAN DATA`. Outcome and `gt_` columns are evaluation-only and are rejected by the leakage scanner if selected as model inputs.
