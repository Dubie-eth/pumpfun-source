# Quote-control report publication

`scripts/pump_quote_control_fresh_differential.py` wrote its gzip report straight
onto `--output` and returned 0, with no check that the path was also an input.
At base `5889e795eba64e85e613b4409921323bfecec414`, running it with `--output`
equal to `--candidate` on a private copy of the captured Pump ELF completed all
507 real LiteSVM cases, printed `507 cases, 0 mismatches`, exited 0, and left a
248,476-byte gzip file where the ELF had been (`1f8b0808` instead of `7f454c46`).
A symlinked or hardlinked output path reached the same bytes through the link.

`results.json` records the before and after runs. The normal control with a fresh
`report.json.gz` still reports 507 cases and zero mismatches in 7.9s.

The fix constructs the shared `PumpReport` publisher
(`scripts/pump_differential_output.py`, introduced for
`research/fees-aggregate-output-20261031/`) after the bound inputs are known and
before the first case executes. It refuses an output that aliases the candidate,
the script, or any bound input by path, symlink or hardlink, and publishes the
complete `gzip.compress(..., mtime=0)` payload through an owned staging file.
Normal replacement of an existing, non-input report is unchanged.

`tests/test_quote_control_output_publication.py` drives the real CLI three times
(direct alias, symlink, hardlink). On the base script all three fail with exit 0
and a replaced candidate; on the proposed script all three are rejected before
any case runs and finish in 0.2s. The suite is discovered by
`python -B -m unittest discover -s tests -v`.

Required checks on the proposed tree: `python3 -E -X utf8 scripts/test_tooling.py`
(217 pass) and `python3 -E -X utf8 scripts/verify_evidence.py` (nine captures
verified). macOS arm64, Python 3.14.3. No capture, fixture, suite case or
comparison key changes; no program-equivalence claim is made.
