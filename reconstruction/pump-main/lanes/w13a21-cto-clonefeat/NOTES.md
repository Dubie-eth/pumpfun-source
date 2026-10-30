# Lane w13a21-cto-clonefeat (wave 13): clone-run register allocation in admin_cto::execute

Target: `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Continues w13a09-cto-cpiclone (#2904) and w13a12-cto-regalloc (#2911): clone-run register allocation
(`clonefeat.py` spill/reg; the original is 6/2) as the search objective, with llc oracles on captured post-opt IR.

## Landed change (this PR): key read after both Rc clones for two sharing-CPI accounts

```rust
// before (inside AdminCtoSharingConfig{..})
event_authority:a.pump_fees_event_authority.to_account_info(),program:a.pump_fees.to_account_info()
// after
event_authority:{let x=&*a.pump_fees_event_authority;AccountInfo{lamports:x.lamports.clone(),data:x.data.clone(),key:x.key,owner:x.owner,
  rent_epoch:x.rent_epoch,is_signer:x.is_signer,is_writable:x.is_writable,executable:x.executable}},program:{let x=&*a.pump_fees;AccountInfo{..same..}}
```

Same clones in the same order (all Rc increments unchanged); only the `key` load moves from the clone's first block to the
block after the `data` Rc increment. The `let x=&*a.X` binding is needed: plain `a.X.lamports` field access re-derefs the
accounts struct after every Rc store (no noalias scope), which is +16 B and lower (0.54178 on the valslot base).

| metric | main 6ac6f9b67 | this change |
| --- | ---: | ---: |
| admin_cto ratio | 0.56291 | **0.56741** |
| admin_cto slots_diff | 3,315 | 3,312 |
| bytes | 27,400 | 27,400 |
| normalized / raw | 1034 / 1034 | 1034 / 1034 (0 losses, 0 gains) |
| runtime differential | | 363 cases, 0 mismatches |
| unstripped sha256 | | `8350fddd3b2e0e45e9b8cdfe9a228ed3e4d93e9d750729f6be44d76c54e2e772` |

The pair held on every main measured: 6080344 0.55872 -> 0.56022 (27,400), 6ac6f9b 0.56291 -> 0.56741.

## Oracles and tools (`scripts/`)

| script | what it does |
| --- | --- |
| `keyscan.py <mod.ll> <out>` | llc oracle: for each inlined `AccountInfo::clone` of the sharing CPI, move the key load after both Rc increments (= the hand-written literal above). |
| `keycombo.py <mod.ll> <out>` | every subset of those moves (64 llc runs, ~10 s). |
| `movescan2.py` | w13a12 `movescan.py` plus `clonefeat` spill/reg per edit. |
| `edit_move.py` | `MOVE='v@x@before:w;...'` ctoracle edit: move a def before another value. |
| `multisink.py` | several sinks at once (edit_sink1 semantics) with clonefeat. |
| `var.py`, `trial.sh`, `batch.sh`, `rec.py` | named source genes on crate copies, capture build (IR kept as trimmed `mod.ll`), ctoracle + clonefeat, ledger rows. |
| `irdiff.py` | diff of two execute IR bodies with names/labels/metadata masked (shows exactly what a source spelling changed in IR). |
| others | copies of w13a12's capture/trim/ctoracle/clonefeat/edit_sink1. |

keyscan on main 6ac6f9b (sharing-CPI slot: k12 authority, k13 global, k14 mint, k15 sharing_config, k16 event_authority, k17 program):
best at 27,400 B is k16+k17 (0.56741); k16 alone 0.56646 at 27,376; k12+k14+k16 0.5671 at 27,344.
On the valslot base (6af878b) k14 (mint) alone was 0.54314 at 27,400 and k16 alone 0.54284.

## Findings

1. **w13a12's sink-one-mint-load oracle no longer pays on current mains.** On 2f268ad it is -8 B / 0.51715 (main 0.51857);
   the 864-edit movescan on 1043a51 finds no single move with a gain at 27,400 B. Only 9-25 of 861 edits change clonefeat
   at all; the best clonefeat is 5/3 (late global or mint field loads), never 6/2, and clonefeat does not track ratio.
2. **Cashback `and` at the curve store** (movescan oracle on 2f268ad: +0.0024 at 27,400). The faithful spelling is
   `let cashback=(st.cashback,!holder);` ... `curve.is_cashback_coin=cashback.0&&cashback.1;` (the `!holder` xor must stay
   early; `cashback=st.cashback` + late `&&!holder` is -128 B, re-reading `st.cashback` is -232 B). It measured
   0.51857 -> 0.52097, 0 losses, 363/0 on 2f268ad, but main moved first: 1043a51 27,368 / 0.53177, valslot 27,392 / 0.53154.
   No +32 B knob found to pair it with (scalar bump, tf/sharing program let, if-let, pool holder local, clock local, reset local).
3. **Late mint-field patch through `let mut cpi=..;cpi.accounts.mint.f=a.mint.f;`** reproduces the late load but moves the
   CpiContext header stores and adds 5-byte padding copies: 27,432-27,456 B, lower. Through `let mut accs` with a program let:
   27,328-27,384 B, lower.
4. The hand-written `AccountInfo{..}` clone is a general tool for moving any clone's plain-field loads relative to its Rc
   increments without changing clone order; other field orders (owner/flags after the next account's clone) need the value
   read after a later statement and have no clean spelling yet.

## Ledger

Approach `regalloc-clonefeat`, keys `0x22a10-w13-<main7>-clonefeat-*`.
