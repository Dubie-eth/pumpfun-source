# w13a13-cto-region1of3: admin_cto::execute (0x22a10), region 1 of 3

Target: `0x22a10` `admin_cto::execute` (`programs/pump/src/creator/admin_cto.rs`), pinned at 27,400 B.
Angle: split the ORIGINAL window into 3 equal byte ranges and own range 1 (orig offsets `0x0000..0x23ad`:
prologue, holder_key/shared/quote_locked, CtoState, the whole validate block, prepare_bonding_curve, the 410
`require!`, and the first sweep blocks up to the 648/719 error blocks).
Bases: main cb298d5 (0.49101), main 9eb6c00 (0.49131 / 3,280 slots). Ledger keys `0x22a10-w13-<sha7>-region1-*-v1`.

## Oracle: `tools/regcon.py` (region split of the real metric)

`regcon.py <unstripped.so>...` recomputes target_metric's difflib ratio on admin_cto (same normalized tokens) and
splits the matched tokens by the ORIGINAL instruction's region. The three shares sum to the ratio, so any trial's
gain or loss can be attributed to a region. `--frame` masks r10 offsets (and the `add64 rX,-imm` frame addresses),
`--regs` masks registers, `--jumps` masks jump offsets (all three: a placement-free structure score).

```
python3 reconstruction/pump-main/lanes/w13a13-cto-region1of3/tools/regcon.py <so>... [--frame] [--regs] [--jumps]
```

| build | bytes | ratio | R1 matched /1085 | R2 /1137 | R3 /1117 | R1 frame-masked | R1 fully masked |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| main 9eb6c00 | 27,400 | 0.49131 | 532 | 377 | 731 | 609 | 697 |
| r1 (w13a03 entry copy) on 9eb6c00 | 27,424 | 0.50337 | 537 | 451 | 693 | 541 | 697 |
| P2m (w13a10 best P+hk_after_shared+p_ev_both_curve, + #2906) | 27,400 | 0.50899 | 512 | 493 | 694 | 519 | |
| P2m + `args` before CtoState (r1 order) | 27,384 | 0.51214 | 518 | 505 | 686 | | |
| HM+TAKE306 (w13a04/w13a06 per-site holder tests) | 27,024 | 0.44729 | 420 | 393 | 670 | | **720** |

Findings:
- Every recent gain (r1 entry copy, pfclimb's P2m) is in **region 2**; region 1 is flat or worse.
- `hk_after_shared` (holder_key after `shared`) costs region-1 *structure*: the find_program_address chunk drops
  1.00 -> 0.65 and memcmp#1 0.98 -> 0.55 (chunks2), R1 532 -> 512. The original computes holder_key first
  (its first call at orig +0x0f8), so hk_after_shared is a frame effect paid for with wrong code order.
- The per-site holder-test form (HM) is the most faithful region-1 structure (fully masked R1 697 -> 720) but loses
  112 exact R1 tokens to frame/registers and 376 B of size.

## Region-1 map (original order of the error blocks in region 1, by `line!()` immediate)

| | order |
| --- | --- |
| original | 289 298 306 296 326 312 307 330 338 334 410 719 648 |
| main 9eb6c00 | 298 289 296 326 306 312 307 330 338 410 334 719 648 |

Region-1 statements and what the original does there (orig offsets):

| orig | statement | original | ours |
| --- | --- | --- | --- |
| 0x000-0x0f8 | arg spills, `mint`, holder_key PDA | spills r4 -0x928, r3 -0x918, r1 -0x8f0, r2 -0x938; mint at -0x6c0; FPA is the first call | r1-order entry copy gives r4 -0x928 / r2 -0x938 only when holder_key is computed first |
| 0x100-0x278 | `shared` (creator==sharing key, owner, !empty) | sharing key copied into the FPA result temp slot -0x2d0 (stack-colored) | same code; hk_after_shared moves this block before the FPA |
| 0x280-0x2b8 | curve bools | cashback 0xa3, holder_reward 0xa5, mayhem 0xa2 loaded **before** global_quote | loaded after global_quote (literal-order genes reproduce the load order but lose ratio: ledger `*literal*`) |
| 0x2b8-0x438 | global_quote | quote_mint copy descending, memcmps | same |
| 0x440-0x4d0 | CtoState stores | creator copied **ascending** from `data+8` after the global loads | creator copied descending first |
| 0x4d8-0x538 | entry copy of `new` | tag, [1,8), [8,16), [16,24), [24,33) pieces | lazy (w13a03/w13a07) |
| 0x540-0x5d0 | sharing key temp, holder_key copy to -0x518 | holder_key by-value copy before the mayhem test | none (validate takes &holder_key; by-value forms are in the ledger, all worse) |
| 0x5d8-0x750 | 284/289/298 tests | one `holder&1` i1 (r8), then `new` tag `&1` from the copy | `(h&0xfd)==0` |
| 0xd78-0xe58 | after 312: cashback, shared override | `target=st.creator` copied **inside** the non-holder arm before the fee checks (orig chunk 0x0f20) | override after validate (OVMK collapses / costs) |
| 0x1858-0x1a48 | sharing payload / tuple phi copies | 7/9 B payload pieces from the copy, target + payload into the block result slots | |
| 0x1a50-0x1c58 | prepare_bonding_curve, 410 require | | |
