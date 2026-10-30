# Admit selected programs once in the disassembly inventory

The selected Donation Relay capture is stored under `evidence/dependencies`,
so the dependency sweep used to offer its same path a second time. The output
name guard then rejected the whole inventory before disassembly.

The fix preserves every selected contract in selector order and omits only
dependency entries whose resolved path is already selected. Distinct files,
even with identical bytes, remain distinct inputs. Same output names from
different files still fail preflight, including case-insensitive collisions.
Explicitly selected aliases remain selected.

The reviewed composition retains #3104's UTF-8/LF manifest writer and updates
the section-name admission wrapper to the composed script's exact hash.
`sections()` and the wrapper's duplicate-section rejection are unchanged.

Validation: five dedupe/selection tests, six section-admission tests in normal
and optimized Python, two publication tests and ten input-admission tests.
The CLI fixture uses a real minimal ELF and a deterministic stub disassembler;
all nine retained ELF section tables also pass the existing admission tests.
This validates selection and publication, not the external Blueshift tool.
No Blueshift checkout was rebuilt and no full captured inventory was generated.
