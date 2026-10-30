# w13a29-cto-spillslot109: the 109th spill slot, and the clone-run evaluation order

Target `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Scratch: `~/.cache/pumpfun-reconstruction/lanes/w13a29-cto-spillslot109/` (not in git).
Ledger keys: `0x22a10-w13-k1-spillslot109-*`, `0x22a10-w13-d81d0f5-spillslot109-*`.

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
