# w13a08-cto-sweepphi (wave 13)

## Landable on main 4394685 (0.49071): curve stores in the original's order (hr2)

| build | bytes | ratio | slots_diff | normalized / raw | losses |
| --- | ---: | ---: | ---: | --- | --- |
| main 4394685 | 27,400 | 0.49071 | 3,313 | 1034 / 1034 | - |
| hr2 | 27,400 | **0.49131** | 3,314 | 1034 / 1034 | 0 / 0 |

`let old_fee=curve.creator_fee_bps;curve.is_holder_reward=holder;` then `curve.is_cashback_coin=cashback;`:
the original reads the old fee right after the creator store, then stores `is_holder_reward` (from the holder
phi slot -0x950) and then `is_cashback_coin` (orig 0x4b48-0x4b78). Unstripped sha256 prefix `da4cd7d523a29a5b`;
differential 363/0. Holder before the old-fee read (`hr_first`) gives the same ratio (other bytes); cashback last
after the fee read (`hr3`) 0.49101. With old-before-bump on top: 27,432 B / 0.49222 (needs -32 B);
+ `if let Some(val)=sharing_update` + early `reset` 27,424 B / 0.49229.

Target: `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Angle: the sweep gate and the pool-CPI holder as phis (S5/S10 of w12a09-cto-cleanroom).
Base: main 3912c47ac (0.48772, 3,273 slots, 27,400 B, 1034/1034).

## Result on 3912c47ac: skip flag + vsigner + bump before old (skp3_vsig_bo)

Superseded on main by #2885 (w13a11-cto-stitch, 085e5dffb): the same skip tree + vsigner + bump-first composite with
`reset` bound early as the size companion, also 0.48922 at 27,400 B. This branch now carries notes only.

| build | bytes | ratio | slots_diff | normalized / raw | losses |
| --- | ---: | ---: | ---: | --- | --- |
| main 3912c47ac | 27,400 | 0.48772 | 3,273 | 1034 / 1034 | - |
| skp3_vsig_bo | 27,400 | **0.48922** | 3,302 | 1034 / 1034 | 0 / 0 |

Unstripped sha256 prefix `dd82adee23d07217`. Runtime differential: 363 cases, 0 mismatches.

Three source changes, each keeps every line:
1. The sharing tree also yields the sweep **skip flag** as a phi of constants, in the original's
   order (skip, collect_old, sharing_update): `(false,false,Some(None))` shared+holder,
   `(true,false,Some(new))` shared+!holder, `(true,collect_old,None)` !shared. The sweep is gated with
   `(!skip).then(||sweep(..)).transpose()?.unwrap_or(0)`. The original's gate is one test of a spilled
   phi-of-constants flag (orig 0x1d38 `ldxdw r1,[r10-0x8e0]; jne r1,0`); main tested `shared&&holder` with two compares.
2. **vsigner hoist**: `let vsigner:&[&[&[u8]];1]=&[vaultseeds];` bound once and passed to both sweep transfers
   (the original stores the `{ptr,3}` signer element at seeds time).
3. `let bump=[..];let old=..;` (bump before old) in the sweep seeds: the size companion that brings 1+2
   (+32 B) back to 27,400 B.

The skip tree alone collapses the layout (post-sweep chain moves to the end, w12a07); with vsigner it holds.

## Trials on main 3912c47ac (measure.sh)

| variant | bytes | ratio | note |
| --- | ---: | ---: | --- |
| skip_vsig (tuple order sharing,collect,skip) | 27,440 | 0.49065 | best ratio, +40 B |
| skip_vsig_rl (+ Rent local) | 27,424 | 0.49049 | |
| skp3_vsig (order skip,collect,sharing) | 27,432 | 0.49042 | |
| skp3_vsig_rl | 27,416 | 0.49027 | |
| skip_vsig_bo | 27,408 | 0.48944 | |
| **skp3_vsig_bo** | **27,400** | **0.48922** | landable |
| skip_vsig_rl_bo | 27,392 | 0.48929 | |
| skip_vsig_mv / skp3_vsig_mv (Rent local inside saturating_sub) | 27,424 / 27,416 | 0.48780 / 0.48757 | |
| skiph_vsig (tree also rebinds holder; !shared arm passes holder) | 27,440 | 0.49065 | byte-identical to skip_vsig |
| dotree_vsig (positive sweep_on flag) | 27,440 | 0.49065 | byte-identical to skip_vsig |
| svb_ik (+ split 312 check) | 27,400 | 0.47438 | 157 calls |
| svb_shn / svb_stql | 27,408 | 0.48944 | byte-neutral knobs |
| svrb_vnm / svrb_fu | 27,392 | 0.48869 / 0.48809 | |
| sv_ff (frozen first) | 27,488 | 0.40556 | layout collapse |

Ledger approach `sweepphi`, keys `0x22a10-w13-3912c47-*`. Tools: w12a07-cto-sweepthread's capir/extract/orc oracle,
re-pathed to this lane's out dir (scratch only).

## Trials on main 085e5dffb (#2885, 0.48922)

| variant | bytes | ratio |
| --- | ---: | ---: |
| old before bump (ob) | 27,432 | 0.49102 |
| ob + Rent local | 27,416 | 0.49087 |
| ob + p3 order + Rent local | 27,408 | 0.49064 |
| ob + p3 | 27,424 | 0.49079 |
| Rent local | 27,384 | 0.48996 |
| p3 order | 27,392 | 0.48899 |
| ob + reset late | 27,440 | 0.49065 |
| `holder=match holder{Some(true)=>true,_=>false}` / `if let Some(true)` | 27,096 | 0.42212 |

## Trials on main 4394685 (#2892, 0.49071)

| variant | bytes | ratio | note |
| --- | ---: | ---: | --- |
| **ob: `let old=..;let bump=..;` (old before bump)** | 27,432 | **0.49162** | +0.0009 for +32 B: needs a -32 B companion |
| ob + `Rent::get()?.minimum_balance(0)` inline | 27,448 | 0.49147 | |
| ob + p3 tuple order | 27,432 | 0.49102 | |
| p3 tuple order | 27,400 | 0.49011 | worse |
| Rent inline | 27,416 | 0.49027 | |
| ob + shared-key borrow / dest-key borrow | 27,352 | 0.48936 / 0.48996 | -80 B knobs overshoot |
| gate `if skip{Ok(0)}else{..}?`, `match skip{..}?`, `let rent=Rent::get()?` | 27,400 | 0.49071 | byte-identical to main |

The holder-phi forms (S10) fold back: rebinding holder in the sharing tree is byte-identical, a 4-arm tree
that splits the !shared arm on holder costs +200 B and one call, and `match`/`if let` holder forms shrink the
function by 304 B.
