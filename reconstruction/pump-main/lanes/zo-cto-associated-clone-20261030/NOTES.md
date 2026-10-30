# Admin CTO: associated-token program copy in the transfer CPI

Base: fresh main `4a7d4c8bf0495f5f906363b1efd6f029b74d00bc`, including #3039.

The `TransferCreatorFeesToPumpV2` associated-token program account is copied
explicitly. Pure metadata reads precede the lamports/data `Rc` clones and the
key read follows them. All field values and the order of both reference-count
increments are preserved. The same accounts, CPI arguments, signer seeds and
state transitions are used. The system-program spelling merged in #3039 stays
intact. Source line count and error macro sites are preserved.

| Identity build measurement | Fresh main | Candidate |
| --- | ---: | ---: |
| `admin_cto::execute` bytes | 27,400 | 27,400 |
| Target sequence similarity | 0.57669 | 0.58238 |
| Aligned normalized instruction tokens | 1,925 | 1,944 |
| Positional differing 8-byte slots | 3,312 | 3,312 |
| Raw exact windows | 1,034 | 1,034 |
| Normalized exact windows | 1,034 | 1,034 |
| Raw / normalized losses | 0 / 0 | 0 / 0 |
| Internal / syscall calls in handler | 154 / 3 | 154 / 3 |

This is partial handler similarity progress, not a new complete exact match.

## Validation

- Ordinary single-module identity build against the fresh main above; complete
  scoring retains all raw and normalized windows. Gain and loss lists are empty.
- Independent source build reproduces both candidate image hashes below. The
  multi-copy search binaries are not used as publication evidence.
- 363 signed synthetic `pump_admin_cto_differential.py` runtime cases against the
  captured original and genuine dependency CPIs, zero mismatches. This corpus
  does not prove full program equivalence.
- No stack warnings; runtime-valid build receipt; no build-input changes.

SHA-256:

- Fresh-main unstripped:
  `d87d0c699cf39396e5d0190fafe65245ad6b5db9a24a757859dde5f932d2982b`
- Candidate unstripped, two ordinary builds:
  `79572535ad547d7f197f14435d5a53ef88f38eccbdf4817c90e4a3008e2214eb`
- Candidate runtime image, two ordinary builds:
  `b1a2f87b845f95f56446bcaf3504df3d95a9b56258d915c87efc29eeb792cf9e`
- Captured original:
  `7a19affaa2c6187e04a5fe0ea298cee81fa5eb8c24cfcc30d85f615e89f7b02d`

Use the pinned SDK and dependency cache documented by the harness:

```sh
python3 reconstruction/harness/fastbuild.py --src programs/pump --work <work> --out <candidate> --recipe identity
python3 reconstruction/harness/target_metric.py <candidate>/unstripped.so 0x22a10 --sym 'admin_cto::execute$'
python3 reconstruction/harness/score.py <candidate>/unstripped.so --baseline <fresh-main-score.json> --json <candidate>/score.json
python3 scripts/pump_admin_cto_differential.py --candidate <candidate>/candidate.so --output <runtime-report.json>
```

## Coordination

- [#3045](https://github.com/lalalune/pumpfun-source/pull/3045) changes explicit
  copies of system_program and coin_creator_vault_ata in the same transfer CPI
  and source line. This change retains the landed #3039 system-program copy and
  changes associated_token_program instead. Shared file and closely related
  scope; its alternate system-program spelling has not been composed here.
- [#3049](https://github.com/lalalune/pumpfun-source/pull/3049) changes the cashback
  Result tuple and sweep bump lifetime in the same source file. Shared file,
  distinct edits; integration has not been tested.
- Merged [#3039](https://github.com/lalalune/pumpfun-source/pull/3039),
  [#3019](https://github.com/lalalune/pumpfun-source/pull/3019) and
  [#3020](https://github.com/lalalune/pumpfun-source/pull/3020) are preserved.
  Related payer-first clone-run research is in
  [#3028](https://github.com/lalalune/pumpfun-source/pull/3028); initializer order
  remains unchanged here.
