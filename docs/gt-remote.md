# GT Remote 1.0.1

Standalone, touch-friendly OpenWebif remote for iPhone and Android browsers.
Install **GT Remote - Mobile web remote** from **GT Panel → Plugins**.
After the GUI restarts, open **GT Remote** in the receiver's plugin menu.
It displays the local URL (port **8088**) without a pairing code.
Open that URL on a phone on the same LAN to use the remote directly.

All buttons use the installed OpenWebif remote key codes. Hold a button for
550 ms to send a long press. The text, message and standby/wakeup controls
also use OpenWebif. OpenWebif must be enabled on port 80. Its authentication,
if enabled, remains in effect. The independent web process starts with Enigma2
and exits when Enigma2 exits. It does not change network configuration.

Optional screenshots capture menus/OSD, not channel video. There is no periodic
screenshot polling. The page is for
local-network use, not direct Internet exposure.

Build with `python3 tools/build_remote.py`. Validate with
`python3 -m unittest discover -s tests -p test_remote.py`.

Tested installation and service startup on GT Combo / OpenATV
8.0.1.20261007 / Python 3.14, followed by receiver-owner browser acceptance.
