# Revalidation invocation status

`scripts/revalidate_all.py` classified any non-zero exit as a failed
verification. 161 of the 209 packets at base `5889e795eba64e85e613b4409921323bfecec414`
carry a `verify.py`, and 48 of them declare a required option
(`--images` in 46, `--repo-root` in 2) that the audit never supplies. Those
verifiers exit 2 with an argparse usage error before running a single check, and
the audit reported them as evidence failures.

`results.json` records both audit runs. Only `scripts/revalidate_all.py` differs
between them; the checkout, Python and packet set are identical.

| Run | Pass | Fail | Not invoked | Skip | Total |
|-----|-----:|-----:|------------:|-----:|------:|
| base | 112 | 49 | — | 48 | 209 |
| proposed | 112 | 1 | 48 | 48 | 209 |

The 48 reclassified packets are exactly the 48 that exited 2 with
`the following arguments are required:`. Their required options are recorded
per packet. The pass and skip sets are unchanged, and the one remaining failure
is a real assertion: `tooling-source-manifest-symlinks-20261029` reports
`AssertionError: scripts/build_source_manifest.py`, which this change does not
touch.

The transition keeps `run_verify`'s decision local to the observed output: an
exit code of 2 whose stderr names missing required arguments becomes
`not_invoked`, carrying `required`; every other non-zero exit stays `fail`, so
a verifier that disagrees with its evidence is still a failure, and a verifier
that fails *and* happens to print that phrase on exit 2 is not silently excused.
The audit summary, `not-invoked.json`, and the README table report the new
category separately instead of folding it into failures or skips. The alternative
of guessing packet arguments from `--help` was rejected: supplying an argument
the packet does not document would make the audit run an invocation the packet
never sanctioned.

Reproduce on a private worktree (the second run above `after` applying
`proposed-asset-transition.json`):

```sh
git worktree add --detach /tmp/reval-base 5889e795eba64e85e613b4409921323bfecec414
cd /tmp/reval-base
python3 -B scripts/revalidate_all.py --output /tmp/audit-before
python3 -B scripts/revalidate_all.py --output /tmp/audit-after
```

The focused regression is `python3 -B tests/test_revalidate_all_invocation.py -v`
(six tests: usage-error parsing, a real failure and a pass staying distinct, and
the report partition). Required checks on the proposed tree:
`python3 -E -X utf8 scripts/test_tooling.py` (223 pass, which now imports the six
tests) and `python3 -E -X utf8 scripts/verify_evidence.py` (nine captures
verified). macOS arm64, Python 3.14.3; no Linux or Windows run, and no packet
evidence, capture or historical receipt is rewritten.

`proposed-asset-transition.json` records the two maintained scripts' old and new
hashes, the new test file, and that the direct `scripts/*.py` name set, program
source and capture bytes are unchanged.
