# Add Remote 0.3.1 publication validation

- 22 Add Remote tests passed.
- 3 new GT Panel integration tests passed: exact SHA256/size and file inventory, engine preparation with exact artifact bytes, rejected incompatible device before download.
- Plugin Python payload in the panel variant matches the published source byte for byte; only /usr/share/doc files are omitted from this variant to respect the engine allowlist.
- Full existing GT Panel suite: 35 tests, 32 passed; 3 failures/errors already reproduce on unmodified commit 6709a4f (legacy repair checks/bundle hash and VLC catalog fixture). No changes to that functionality or engine policy were made.
- Installer shell syntax passed; it downloads the pinned standard IPK via HTTPS, checks SHA256, and invokes opkg. No automatic GUI restart.
- Receiver validation: standard 0.3.1 installed on two local receivers; IR waveform and NEC hold events observed, active remote operated within plugin; native menu verified About without Arabic branding. Device profiles and credentials are not part of the release.
