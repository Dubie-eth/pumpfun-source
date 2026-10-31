# Captured legacy SPL destination-credit boundary

At base `ed47ac72a632e54a4d5ca9a192912c8d5b40faf2`, the native liquidity
model returns token error 14 when a legacy SPL destination credit exceeds
`u64::MAX`. The retained AMM and SPL binaries succeed and wrap that credit.
The equivalent Token-2022 call returns error 14 and rolls accounts back.

This follows the bounded observation recorded by the maintainer in
[`06cd679de`](https://github.com/lalalune/pumpfun-source/commit/06cd679de6efdfeec44bd8f62d7be5f26384fab6).
These inputs deliberately have inconsistent token totals. They do not
establish a reachable on-chain state. The earlier delegate evidence and its
historical qualification are preserved.

The correction uses wrapping destination credit only for legacy SPL in
`programs/pump-amm/recovered/liquidity.rs`; Token-2022 retains checked credit.
This is the native reconstruction model, not the production AMM source.
No SBF build, source byte-identity score or complete liquidity parity is claimed.

## Measured result

The same 29 local cases were run against separately compiled base and fixed
hosts and the retained AMM/SPL/Token-2022 binaries. Six discrepancies become
zero. The cases include base and quote transfers during deposit and withdrawal,
credits immediately below/at/above the maximum, the maintainer's max/max
example, and later failures that must roll back the prior wrapped credit.
Full successful account bytes, event bytes and CPI data are compared by the
existing capture checker; failed cases check error, no committed event and
account rollback.

The new regression method contains those same 29 subcases. The full affected
suite passes seven test methods, including the existing 124 fixed, 40 seeded
and 24 delegate subcases and identity/tamper checks. Mandatory checks pass
250 tooling tests and all nine captured-image verifications. Exact hashes,
outcomes and timings are in `results.json`.

## Reproduce

Use the repository requirements and `rustc` (measured with 1.99.1). Run from
the checkout being compared. Keep `reproduce.py` from this packet available
when running against the base checkout.

```sh
rustc --edition=2021 -O -D warnings \
  programs/pump-amm/recovered/liquidity_host.rs -o /tmp/liquidity-host
python research/runtime-legacy-transfer-wrap-20261031/reproduce.py \
  --repo "$PWD" --host /tmp/liquidity-host --output /tmp/liquidity-result.json
python -B tests/test_pump_amm_liquidity_captured.py
python scripts/verify_evidence.py
python scripts/test_tooling.py
```

The base probe reports `mismatches: 6`; the corrected host reports zero.
The affected test is also invoked by the existing `host-fragments` CI job.
The capture hashes are checked before execution. All transactions use only
synthetic local LiteSVM accounts; no RPC or live action is involved.
