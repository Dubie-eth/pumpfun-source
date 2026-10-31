# Two achieved pre-fee phases, two rejected native builds

S1 moved creator Result success projection before direct caller fee checks.
S2 additionally moved shared nonholder creator selection before those checks,
and the selected key reached real curve and pool consumers. Both intended
phases survived native compilation. Both sources still failed to recover the
private fee-Some shared gate, retained an outlined sweep, and were rejected.
This packet preserves that failed causal prediction; it claims no source gain.

These are historical ECEA measurements, separate from
[PR3436's C1 Option-carrier negative](https://github.com/lalalune/pumpfun-source/pull/3436).
S1 and S2 are each direct children of ECEA. `S1-to-S2.patch` is a content
comparison, not a parent relationship or a proposed latest-main patch.

| | ECEA control | S1 | S2 |
|---|---:|---:|---:|
| source revision | `ecea7021` | `66caa3e2` | `5cfe37b1` |
| raw native ZIP members | 43 | 45 | 45 |
| native build seconds | 122.7 | 103.7 | 98.4 |
| execute bytes | 27,400 | 17,992 | 18,088 |
| outlined sweep bytes | inline | 9,096 | 9,096 |
| normalized / raw matches | 1034 / 1034 | 1034 / 347 | 1034 / 347 |
| raw losses against ECEA | — | 687 | 687 |

The builds succeeded without stack warnings. Each subsequent no-loss guard
correctly failed. Both untouched native ZIPs retain their original
`FAILURE.json`, saved full score and rejecting comparison; neither contains a
replacement success receipt. Root independently checked the saved 1,035-row
outcomes. This replay recomputes their arithmetic, not the official scorer.

## What was actually learned

Offsets here are relative to execute VA `0x22a10`; they belong to these exact
historical ELFs. Logical decoding treats LDDW as 16 bytes.

- **S1 moved projection before fees.** Creator success joins at
  `+a78`; its overlapping 7/9-byte fragment copies complete before the fee
  tag read/test `+ad0/+ad8`. Valid fee-Some's retained byte read `+1268`
  reaches the same `+1270` head as fee-None. That head has only three native
  instructions: store, shared load, branch. Payload-copy removal alone did
  not produce the private shared gate. The direct call `+1e28` reaches the
  separate 9,096-byte sweep at `0x27058`.
- **S2 realized the additional target-value phase.** Branch `+b00` selects
  creator block `+e50`, which rejoins `+b08` before fee read/test `+b28/+b30`.
  The prefix seven bytes reload through the curve pointer; middle/tail pieces
  come from the owned snapshot. This is not an all-32-bytes-from-one-frame
  claim. Selected fragments reach target32 at FP `[-1216,-1184)`, assembled
  at `+1518..+1560`. Its six direct stores are the only direct writes to that
  range in execute. The key is read into curve stores `+1fe0..+2010` and passed
  in r3 at `+2dd8` to the pool helper, whose four word reads serialize it.
  The portable checker adds narrow r1/r3 register bridges to those recorded
  consumer pairs. Fee-None and successful fee-Some still share `+1330`'s
  three-instruction head. There is one bounded validation fee-tag read;
  sweep remains outlined at `0x270b8`, called at `+1ea0`.

The exact source bindings retain creator `Result<Pubkey>` and its unused fee
parameter, creator checks, both existing volatile reads at lines 334/338, fee
error order/coordinates 326/330/334/338, 772 source lines, and the downstream
flags/CPI/event source. S2 substitutes the already owned creator snapshot
before fees, after creator validation. On the successful source path there
is no intervening curve write or CPI; supplied-new errors still occur before
selection. These constraints do not prove original Rust helper/type identity.

## Prior credit and limits

The broad boundary family is not new. Exact retained
[#3384 f1/f2](https://github.com/lalalune/pumpfun-source/pull/3384) already
project creator Result in execute before a private fee helper; f3 uses an
`and_then` closure. Their notes/results report 9,080 bytes and sweep no longer
inlined on `2e1379d`, using an IR/oracle measurement. Those scripts omit the
current volatile reads and S2 pre-fee shared-C selection. The exact placement
is now known, superseding the earlier UNKNOWN; no historical build was rerun.
[#3197](https://github.com/lalalune/pumpfun-source/pull/3197) also retains a
per-arm private fee helper negative. Old OV negatives remain relevant. This
packet supplies actual native phase/consumer evidence, not novelty credit,
an inliner-threshold explanation, or grounds for another helper combination.

`captures.tar.xz` seals all three provider ZIPs, source/build/score receipts,
selected prior text and unchanged analysis records. Each ZIP includes full
141 source files, 142 staged files and 236 CORE inputs. Common frozen CORE text
is archived; 28 pinned binary CORE inputs and original 7a are read from the
repository. The earlier incomplete shared-slot reader and corrected supplement
are both preserved. Empty/failed S1 ABI analysis is explicitly unqualified;
the separate Error284 receipt is optional evidence, not a blanket ABI claim.

Run `PYTHONDONTWRITEBYTECODE=1 python3 -B verify.py --repo /path/to/repo`.
`verification.json` records a real replay. The stdlib checker authenticates
inputs and source deltas, saved rejection arithmetic, selected raw/CFG joins,
direct frame-store census and register/consumer bridges. Calls are assumed to
return normally on the selected success paths; R6–R9 follow the SBF ABI.
Direct-store absence assumes external resource/callee pointers do not alias
the private target buffers. Context ancestry and allocation-role attribution
remain bounded source/ABI assumptions. Frame occupancy is not a Rust lifetime.

No compiler/IR/VM/scorer rerun, S1/S2 runtime differential, exterior-address-only
theorem, latest-main executable qualification, source gain, size repayment or
followup source authorization follows. The last CTO window remains open.
