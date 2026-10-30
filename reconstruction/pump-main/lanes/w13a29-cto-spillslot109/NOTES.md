# w13a29-cto-spillslot109: the 109th spill slot, and the clone-run evaluation order

Target `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Scratch: `~/.cache/pumpfun-reconstruction/lanes/w13a29-cto-spillslot109/` (not in git).
Ledger keys: `0x22a10-w13-k1-spillslot109-*`, `0x22a10-w13-d81d0f5-spillslot109-*`, `0x22a10-w13-dfc3693-spillslot109-*`.

## Result (landable)

| main | before | after | bytes | normalized / raw | losses |
| --- | ---: | ---: | ---: | --- | --- |
| dfc3693 | 0.59916 / 3,313 | **0.61833** / 3,306 | 27,400 | 1034 / 1034 | none |

Runtime differential: 363 cases, 0 mismatches. Unstripped sha16 `2bc480ebebb23f98`.

Source change (two lines, line count unchanged):
1. `transfer_creator_fees_to_pump_v2`: the `TransferCreatorFeesToPumpV2` literal in the original's clone order
   `payer, quote_mint, token_program, system_program, associated_token_program, ...` with every field a plain
   `.to_account_info()`, except the two `pump_amm` clones (the `CpiContext::new` program and the `program` field), which
   are hand-written `AccountInfo{key,owner,lamports.clone(),data.clone(),..}` (owner read before the Rc increments).
2. The event's `is_holder_reward` read back from the curve (`a.bonding_curve.is_holder_reward`, w13a10's `m_ev_hr_curve`),
   the -8 B size companion.

How it was found: payer-first all-plain base `P0` (27,416 B, 0.5879 on 06e6bb8+) captured as raw IR, then w13a21's
`fieldscan.py --pairs 6` llc oracle over it: `O1878+O2404` (owner early in both pump_amm clones) = 0.61114 at 27,400,
and the source build matched the oracle exactly (s2 = 0.61114). Main's hill-climbed literal (system_program first with
key-late copies) does not compose with payer-first (q0 0.56578 at 27,440); the faithful order wants its own copy forms.

## Spill-slot map (k1 = #3011, 0.56291)

`tools/smap.py <cand> 0x8d8 0xc38 o` lists, for each original 8 B slot, every access and the candidate slot that
the masked whole-function alignment pairs it with (`-` = no aligned counterpart). `c` gives the candidate view.
`tools/dsum.py <cand> lo hi` compresses that into runs of (orig - cand) deltas. `tools/remap.py <cand> 'lo:hi:d,..'`
rewrites candidate frame offsets and rescores (an upper bound for a pure slot-numbering fix).

- StackSlotColoring gives colors in weight order (stable sort, heaviest first), so the spill area is ordered by
  spill weight, not by creation order. `llc -debug-only=stack-slot-coloring` on the k1 IR: 108 colors (fi#178..#285).
- Most of 0x998..0xc38 is the 13-account `TransferCreatorFeesToPumpV2` AccountInfo clone run (orig 0x2690..0x3a18):
  each account's key / lamports-Rc / data-Rc / owner / rent / 3 flag bytes are spilled one by one and reloaded in
  reverse when the account_infos array is built. A second run (orig 0x3e00..0x49d0) shares the colors.
- Upper bound of a perfect renumbering of the -8 ranges on k1: 0xa08..0xa40 alone +0.008, plus 0xb40..0xc30 +0.026.

## Finding 1: the clone run's evaluation order is payer-first (`tcf_order`)

`tools/vtrack.py` names every spilled value of the run by (account offset, field). The original clones
`pump_amm, [_212+0], quote_mint, token_program, [_212+48 via the &a.system_program pointer], associated_token_program, ...`;
ours (since #2524) clones `system_program` second and `payer` (admin_set_creator_authority, `_212+0`) fifth. So the
original struct literal is

```rust
TransferCreatorFeesToPumpV2{payer:..,quote_mint:..,token_program:..,system_program:..,associated_token_program:..,..}
```

(the pre-#2524 order, also w12's `tcf_field_order` gene from y1-cto-diffwin). On the current mains it is a big win in
ratio but +24 B:

| base | form | bytes | ratio |
| --- | --- | ---: | ---: |
| k1 (6ac6f9b) | main | 27,400 | 0.56291 |
| k1 | payer first (p1) | 27,424 | 0.58063 |
| k1 | p1 + `z_sh_flat_owner_first` + `s7_rentlocal` (v1) | **27,400** | **0.57909** (3,214 slots, 1034/1034, 0 losses) |
| d81d0f5 (0.57100) | payer first (m1) | 27,424 | 0.58811 |
| d81d0f5 | m1 + `z_sh_flat_owner_first` + `s7_rentlocal` | 27,416 | 0.57323 |

With payer first the spill area 0x9c8..0xb30 becomes exact (dsum 0); 0xb40..0xc38 stays -8.

## Finding 2: the value we keep in a register is `&a.holder_creator_vault`

The run is +24 B in ours because the clone run has fewer free callee-saved registers. Ours keeps two long-lived
values in r8/r9 across the whole run that the original spills before it:
- `%326 = gep _212, 264` (`&a.holder_creator_vault`, an inline AccountInfo, defined inside the inlined `sweep`):
  original `mov r1,r8; add r1,0x108; stxdw [r10-0x8e0],r1` at orig 0x1f38 (spilled at its def); ours
  `mov r8,r6; add r8,0x108` and spills it only at ~0x31a0 inside the run.
- a bool call result (orig r9, spilled to [r10-0x918] at orig 0x1f68 and reloaded at 0x2090); ours keeps it in r9.
With r8/r9 busy, ours spills each account key at its load; the original keeps keys in r6/r7/r9/r0 and spills them
later in batches (orig 0xb38 = `A28.key` spilled late from r9 via `mov r9,r6`, the extra 109th slot).

IR oracles on the payer-first IR (`llcx.py`, `cfg.py` for the dominated blocks): a fake use of `%326` at the sweep
exit (-> 27,464 B, 0.48474) or hoisting it to the entry with a use before `ret` (27,304 B, 0.51771) both overshoot:
the remedy must free r8/r9 only through the run, not lengthen `%326` over the post-sweep code.
