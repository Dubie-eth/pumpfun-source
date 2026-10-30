# Lane w13a11-cto-stitch (wave 13)

Target: `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Angle: integrator/stitcher. Collect unlanded admin_cto source genes from w12/w13 lanes, combine compatible
edits on latest main at exactly 27,400 B, and land zero-loss composites through `land.py`.
Base: main 3912c47ac (programs/ identical on origin/main 5d597ce7a): 27,400 B, ratio 0.48772, slots 3,273.

Tooling (not in git, `~/.cache/.../lanes/w13a11-cto-stitch/tools`): w12a04-cto-k4size's `genes.py`/`run.py`
(queue runner, fastbuild + target_metric, two builds max) with `genes13.py` adding w12a07-cto-sweepthread's
source genes. Every gene keeps the newline count, so every error/require site keeps its `line!()`.

## Composite 1 (#2885, landed 085e5dffb): skip flag + vsigner + bump-first + reset early

| metric | main 3912c47ac | this lane | original |
| --- | ---: | ---: | ---: |
| admin_cto bytes | 27,400 | **27,400** | 27,400 |
| ratio | 0.48772 | **0.48922** | 1 |
| slots_diff (positional) | 3,273 | 3,303 | 0 |
| calls | 154+3 | 154+3 | 154+3 |
| normalized / raw | 1034 / 1034 | 1034 / 1034 | 1035 |
| losses (norm / raw) | | 0 / 0 | |
| runtime differential | | 363/363 | |

Unstripped sha256 `4fc952ce8efbf4aa8d30036222f6d7c0a94363a6cb1739a09ccfdc50b975354a`.

Genes (source of each):
- `st_skip` (w12a07-cto-sweepthread `skiptree`): the sharing tree yields a `skip` flag as a phi of constants
  (`false` only in the shared+holder arm) and the sweep gate is `(!skip).then(..)`; the original gates the sweep
  on such a flag.
- `st_vsig` (w12a07 `vsig`): `let vsigner:&[&[&[u8]];1]=&[vaultseeds];` once, shared by both sweep transfers.
  These two alone: 27,440 / 0.49065 (+40 B).
- `st_bo` (w12a07 `bumpold`): `let bump=..;let old=..;` order: -32 B (27,408 / 0.48944).
- `h_reset_early` (w12a04-cto-k4size step 4): `let reset=sharing_update.is_some();` before the pool signer
  seeds, used by the event: alone on main 27,392 / 0.48869; here it takes the composite to 27,400.

## Compose / conflict table (measured on main 3912c47ac; bytes / ratio)

| variant | bytes | ratio | note |
| --- | ---: | ---: | --- |
| main | 27,400 | 0.48772 | |
| h_reset_early | 27,392 | 0.48869 | |
| h_ev_cb_global (event `is_cashback_coin` from the curve) | 27,384 | 0.48906 | |
| w_cp_inline (wallet `coin_present` bound inside `do_coin`) | 27,416 | 0.48997 | calls 155+3 |
| st_skip + st_vsig | 27,440 | 0.49065 | |
| + st_bo | 27,408 | 0.48944 | |
| + st_bo + h_reset_early | **27,400** | **0.48922** | composes: landed candidate |
| + st_rl + st_bo | 27,392 | 0.48929 | |
| + st_rl + st_bo + h_reset_early + h_fee_iflet | 27,400 | 0.48742 | fee_iflet conflicts with reset here |
| h_ev_cb_global + w_cp_inline | **27,400** | **0.49041** | composes (155+3 calls), but not with the skip family (A8 27,432 / 0.48892) |
| skip+vsig + h_ev_cb_global | 27,456 | 0.49140 | |
| skip+vsig + h_ev_cb_global + reset | 27,448 | 0.49147 | best ratio seen, 48 B over |
| A4 = skip+vsig+bo + evcb + reset | 27,416 | 0.49027 | |
| A1 = A4 + st_rref (`let rent=&Rent::get()?`) | 27,400 | 0.49011 | st_rl gives the same bytes |
| skip+vsig + st_rref | 27,424 | 0.49049 | |
| skip+vsig+bo + reset + st_rref | 27,384 | 0.48996 | |
| A5/A7 (skip family + w_cp_inline) | 27,416-27,440 | 0.489 | w_cp_inline conflicts with the skip family |

## Composite 2 (#2892, merged 4394685): + Result gate + event cashback from the curve + Rent ref, minus reset

w13a10-cto-pfclimb (#2888) found the same skip/vsigner/bump-first family independently with the Result-valued
gate `swept=if !skip{sweep(..)}else{Ok(0)}?;` (-8 B) as the size companion instead of `reset`.

| variant (on main 3912c47ac; S = skip+vsig+bo) | bytes | ratio | note |
| --- | ---: | ---: | --- |
| S + gate_res (= #2888) | 27,400 | 0.48951 | |
| S + gate_res + evcb + reset | 27,408 | 0.49034 | |
| **C1 = S + gate_res + evcb + st_rref** | **27,400** | **0.49071** | this PR, 0 losses, 363/363 |
| S + gate_res + evcb + reset + rref + fee_iflet | 27,392 | 0.48899 | |
| S + gate_res + reset + fee_iflet | 27,408 | 0.48705 | fee_iflet hurts with the skip family |

Composite 2 versus main 085e5dffb: drop `reset` (event reads `sharing_update.is_some()` again), add the Result
gate, `is_cashback_coin:a.bonding_curve.is_cashback_coin` in the event (`h_ev_cb_global`, w12a04 H-table:
27,384 / 0.48906 alone on H2) and `let rent=&Rent::get()?;` in the sweep native arm (`rent_ref`,
w12a14-cto-hillclimb). 27,400 B / **0.49071** / slots 3,313, 1034/1034, zero losses, unstripped sha256
`48d5a9c99d2fd34f...`, differential 363/363.

## Composite 3 (this PR, on main cb298d5c8 = #2907): entry copy of `new` + event flags from the curve + reset

Main moved to cb298d5c8 (#2907 w13a10-cto-pfclimb-2: event `is_holder_reward` from the curve, `st.cashback&&!holder`;
0.49101). The new gene is w13a03-cto-entrycopy's `g8`: `let args=&(new,);` bound after the `CtoState` literal
and `Some(args.0)` in the shared non-holder arm. The borrowed tuple keeps an entry copy of `new` in the frame
(the original copies all of `new`'s SROA pieces at entry, orig 0x4d8-0x538). Alone it is +16 B
(C1 + g8 27,416 / 0.49296; 085e5df + g8 27,432 / 0.50569); the size companions are the two event/reset genes:

| variant (bytes / ratio) | bytes | ratio |
| --- | ---: | ---: |
| C1 (main 4394685) + g8 | 27,416 | 0.49296 |
| + `is_holder_reward` from the curve (#2907's gene) | 27,408 | 0.49334 |
| **+ that + `reset` before the pool seeds (P1, this PR)** | **27,400** | **0.49431** |
| C1 + g8 + `reset` + `if let` sharing CPI | 27,408 | 0.49334 |
| C1 + g8 + event cashback local | 27,432 | 0.50150 |
| 085e5df + g8 | 27,432 | 0.50569 |
| 085e5df + g8 + `is_holder_reward` from the curve | 27,432 | 0.50599 |
| 085e5df + g8 + Result gate | 27,440 | 0.50262 |

P1: 27,400 B / **0.49431** / slots 3,306, 1034/1034 normalized and raw, zero losses against cb298d5c8, differential
363/363, unstripped sha256 `46ba0c60c7b4dd11...`. P1 keeps `!holder&&st.cashback` (main's `st.cashback&&!holder` is
measured separately as P1c).

The 085e5df + g8 family (0.505-0.506 at 27,432 B) is the next target: it needs -32 B.
