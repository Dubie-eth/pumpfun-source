# Hold the revalidator to its own packet admission rules

Problem: `run_verify()` never inspected the packet directory itself, so a
packet whose root was a symlink revalidated as a pass and its out-of-tree
`verify.py` was executed. Separately, `main()` decided whether a verifier
existed with `Path.exists()`, which is false for a dangling link, so a manifest
alone carried such a packet to pass even though `run_verify()` already rejects
that shape as `verify.py is not a regular file`.

Fix: reject a linked or missing packet root at the top of `run_verify()`, and
gate on `os.path.lexists()` so a dangling verifier entry reaches the existing
admission rule.

Reproduction at base `8cf3c5f8a7912b36ced352e49ac8538ff864a4c2`:

```
mkdir research/linked; ln -s /tmp/external research/linked
python -B scripts/revalidate_all.py --output /tmp/audit
# results.json: {"linked": {"overall": "pass", ...}} and the external verify.py ran
```

After the change the same packet is `fail` with
`packet root is not a real directory`, and the external script is not executed.

Limits: the full research/ corpus is not re-executed here; synthetic packets
and the existing revalidate tests cover the same path. macOS arm64, Python 3.14.3.

## Review qualification

The actual batch CLI controls use marker files to prove linked verifiers do not
execute, a nonempty valid manifest for the dangling-verifier counterexample,
and FIFO/directory verifier entries. A regular verifier still runs. The active
manifest-admission and revalidation-qualification wrappers pin the reviewed
updated source; their source-replacement, retention and admission tests remain
in place. This does not change or regenerate historical packets.
