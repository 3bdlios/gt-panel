# GT Combo HEVC restart repair

A captured kernel panic on Linux 5.15.196 shows NULL destination `memcpy`
from `vh265_clear_mmu_config` in `amvdec_h265`. Static analysis of the actual
module confirms that the swap DMA buffer is freed but its old size remains.
The old allocation condition skips allocation when size is nonzero even if
the destination pointer is NULL.

The repair changes one AArch64 instruction at file offset `0x123d0`:
`68020035` (`cbnz w8`) to `600200b5` (`cbnz x0`), preserving its branch target.
A NULL destination now reaches the existing allocator and allocation-failure
handling before memcpy. No kernel panic policy is disabled.

Accepted original SHA256:
`c47fa7043757b2d8787f83e04c8db788ce30a75d5cee566d9f87b93123795379`

Patched SHA256:
`829cd7d8fea5baedc302f6560e414bb4df75fea2b8d503c32123d0986cff11f4`

The repair tool accepts only that complete module and the GT Combo / 5.15.196
host. It saves and verifies the original under `/var/lib/gt-hevc`, replaces the
file atomically and offers restore. Version 1.0.1 applies automatically on the first GUI startup after installation,
then displays a five-second notice and reboots the receiver fully once. A persistent
completion marker prevents a reboot loop and preserves a later manual restore.
Failure displays an error and does not reboot. The plugin menu retains manual
installation and restore. A GUI restart alone does not reload the kernel module. Never
unload this decoder live: the live-reload experiment lost connectivity and
the device rebooted; full boot loading is the supported path.

The discarded `enable_swap=0` experiment could not initialize HEVC because
the non-swap firmware was unavailable; it is not part of this repair.

Analysis evidence:
- Original: `ev_09c1136e9576f066279f74819a92e13339e32a5609717709aadfee70d920f058`
- Patched: `ev_ff1482c7398f31d8276e3cdc78e2e206c5c8338a525e6ff4bddbefd8523e9c07`
- [Corresponding CoreELEC source](https://github.com/CoreELEC/media_modules-aml/blob/5.15.196_20260225/drivers/frame_provider/decoder/h265/vh265.c)

Validation: seven automated tests cover backup, idempotence, restore, rejection
of unknown modules/corrupt backups, instruction operand and preserved target.
Receiver booted with the patched module. The previously crashing interlaced HEVC channel crossed the same MMU-clear path twice without a panic; video timestamps advanced across monitoring samples. Receiver owner confirmed picture/playback stable after the minute-long trial. Broader channel/build coverage remains untested.
