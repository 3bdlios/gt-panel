# Diagnostic 1.2.0 validation

- Ten local tests passed: event parsing, foreign lock protection, restoration after startup failure, phase completion, HTTP download and file traversal protection, symlinked /tmp recovery, temporary native mapping and restoration with action-delivery evidence, existing mapping preservation, LIRC record parsing, and cleanup publish-error containment.
- Installed on SF8008 at 192.168.8.13, OpenBH. /tmp resolves to /var/volatile/tmp.
- Reproduced old failure: publishing the saved report raised ValueError due to comparing a resolved report parent against unresolved /tmp. Crash log confirmed this escaped from Screen.cleanup.
- GUI test on 1.2.0: REPORT_PUBLISH_OK=True, CLOSE_OK, FRESH_SCREEN_READY. No new crash log appeared.
- Existing 5307-byte report listed in HTTP API and downloaded byte-for-byte, SHA256 6c56ec2356b5508a7f92f9291c0c37f39fe98cf123ac4917a8bafe6481a7b399.
- Requested explanatory text and footer absent from served page.
- Expanded physical key rounds, LIRC modes and temporary mapping test await the user's new run. No claim of universal hardware/protocol support or a completed persistence/reboot test.
