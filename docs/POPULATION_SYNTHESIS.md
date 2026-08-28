# Population synthesis

The population plane supports survey weights, effective sample size, weighted distributions, and multi-margin iterative proportional fitting. IPF refuses negative targets, unsupported categories, zero-support positive cells, and silent category removal. The public demo uses 5,000–20,000 reproducible synthetic prototypes with normalized log-normal survey weights.

The production path is survey microdata plus licensed census margins. It should store prototype plus weight rather than materializing millions of duplicate people.
