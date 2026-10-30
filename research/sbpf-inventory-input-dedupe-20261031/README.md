# Admit each captured program once in the disassembly inventory

Problem: `scripts/sbpf_disassembly_inventory.py` could not run against this
repository's own evidence. `analyze.capture_directory('donation_relay')`
routes that program to `evidence/dependencies/donation_relay`, so
`program_inputs()` already listed it; `main()` then appended every
`evidence/dependencies/*/deployed.so` as well. The preflight refused the whole
run.

Reproduction at base `9b9440fe5`:

    python3 -B scripts/sbpf_disassembly_inventory.py \
      --tool-source /tmp/sbpftool --output /tmp/sbpf-out
    # ValueError: duplicate program output name: 'donation_relay'
    # (no output directory created)

Fix: `capture_inputs(root)` keeps selector order first, then adds dependency
binaries that are not already selected, deduplicated by resolved path.
Deduplicating by path rather than by name leaves real output-name collisions
to `validate_program_names()`, which still refuses them.

After: the preflight passes and the run reaches the pinned tool
(`FileNotFoundError` for `<tool-source>/target/release/sbpf`, expected here
because no sbpf checkout was built).

`research/sbpf-section-name-admission` pins the exact bytes of this script.
The dedupe changes only input enumeration, not `sections()` or any admission
rule, so its successor keeps the rule and advances the pin — the same rebind
pattern as `lalalune/pumpfun-source#2992` and `lalalune/pumpfun-source#2510` (before `f2341040…`, after `783c9cbd…`).

Tests: `tests/test_sbpf_inventory_input_dedupe.py` (2 tests) fails on base and
passes after; the section-name packet's 6 tests, the publication suite's 2,
`tests/test_sbpf_admitted_inputs.py`'s 10, `scripts/test_tooling.py`'s 228 and
`scripts/verify_evidence.py`'s 9 captures all pass. macOS arm64, Python 3.14.3.

Limits: no inventory packet is regenerated — no pinned sbpf checkout was built
or run — so instruction coverage, tool identity and manifest contents are not
re-proved. Peer PR `lalalune/pumpfun-source#3104` edits this file's manifest
write and will move the pinned bytes again; its diff does not overlap
`capture_inputs()`.
