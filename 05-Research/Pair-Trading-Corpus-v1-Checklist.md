# Pair Trading Corpus v1 Checklist

Use this checklist before expanding beyond the initial proof-of-work corpus.

## Corpus Rules

- Keep exactly three live pairs active for the first validation pass.
- Keep exactly one negative-control pair to test rejection logic.
- Do not add portfolio construction, basket ranking, or sector-wide scanning yet.
- Use one rolling lookback window per run.
- Use one cointegration test path and one Z-score signal path.

## Recommended Starting Pair

- Live pair 1: `SPY` / `IWM`
- Live pair 2: `KO` / `PEP`
- Live pair 3: `XOM` / `CVX`

## Optional Follow-On Pairs

- `KO` / `PEP`
- `XOM` / `CVX`

## Negative Control

- Select one unrelated cross-sector pair that should usually fail or weaken cointegration.
- Keep this pair out of the live-trading allowlist.

## Inclusion Filters

- Liquid, widely traded instruments only.
- Strong economic linkage between legs.
- Stable historical data quality.
- No obvious event-driven distortion.

## Exclusion Filters

- Thin liquidity.
- High event risk.
- Ambiguous relationship.
- Correlation without cointegration.

## Exit Criteria for v2

- Ingestion works without manual intervention.
- Cointegration results are reproducible.
- Spread and Z-score outputs are stable.
- Negative-control rejection is reliable.
- Rolling revalidation does not break the workflow.
