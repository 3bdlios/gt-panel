# GT Combo Wi-Fi: 2.4 GHz mode

This is a reversible **workaround**, not a kernel-driver repair. On the reviewed
GT Combo, the Wi-Fi firmware/SDIO transport could hang while wpa_supplicant and
DHCP kept running. A GUI restart did not reset the failed radio. A direct 2.4 GHz
association and three HTTPS requests through wlan0 succeeded during diagnosis.
Long-term stability is not yet established.

Install **Wi-Fi stability: 2.4 GHz mode** from GT Panel > Fixes. Restart the GUI
manually once. At the next GUI start, the extension restricts saved wlan0
networks to 2.4 GHz channels 1–13 and reloads wpa_supplicant only when settings
actually change. Unchanged GUI starts leave the connection running. Regulatory
restrictions still apply. Networks offered only on 5 GHz will be unavailable.

To restore, open Plugins > **GT Wi-Fi: 2.4 GHz mode** > **Restore previous band
settings**. This also disables automatic application on later GUI starts.
Restore this setting before uninstalling the extension or rolling back its
files through GT Panel; file rollback alone cannot undo Wi-Fi configuration.

The extension backs up the initial configuration under `/var/lib/gt-wifi24/`
with root-only permissions. Rollback changes only band/BSSID directives for
matching saved networks, preserving subsequent password changes and other
settings. Conflicting later edits to band settings cause rollback to stop
without overwriting them. New saved networks are handled on the next application.
Saving settings in Enigma2's network editor may remove the frequency restrictions;
reapply from this extension's menu if needed.

The bundle contains no SSIDs, Wi-Fi credentials, private keys, or receiver logs.
It does not modify Ethernet, DHCP, boot files, kernel modules or firmware and
does not reboot the receiver. If the radio is already stuck and cannot scan,
changing its band will not reset it; recover the radio first and keep Ethernet
available for diagnosis.

Validated on the exact catalog compatibility target: GTMedia GT Combo,
OpenATV 8.0.1.20261007, Python 3.14. Tested: configuration round-trip,
duplicate SSIDs, password preservation, idempotence, conflicting edits,
disabled autostart and the hardware guard. Generic package acceptance on the
receiver is recorded separately; longer-term stability remains a user trial.
