#!/bin/sh
# Add Remote Diagnostic 1.2.0 — Fares3nzi
set -eu
command -v opkg >/dev/null 2>&1 || { echo 'opkg is required'; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required'; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' || { echo 'Python 3.9+ is required'; exit 1; }
[ -d /usr/lib/enigma2/python ] || { echo 'Enigma2 is required'; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo 'sha256sum is required'; exit 1; }
addremote_tmp=$(mktemp -d /tmp/addremote-install.XXXXXX)
trap 'rm -rf "$addremote_tmp"' EXIT
trap 'exit 1' HUP INT TERM
addremote_ipk="$addremote_tmp/enigma2-plugin-extensions-addremotediagnostic_1.2.0_all.ipk"
addremote_url='https://github.com/3bdlios/gt-panel/releases/download/add-remote-diagnostic-v1.2.0/enigma2-plugin-extensions-addremotediagnostic_1.2.0_all.ipk'
if command -v wget >/dev/null 2>&1; then
    wget -O "$addremote_ipk" "$addremote_url"
elif command -v curl >/dev/null 2>&1; then
    curl --fail --location --proto '=https' --proto-redir '=https' -o "$addremote_ipk" "$addremote_url"
else
    echo 'wget or curl is required'; exit 1
fi
printf '%s  %s\n' '46a4812dec18099fcc968917f9860243091d1649797d2e5cc02ee14aaf7d9143' "$addremote_ipk" | sha256sum -c -
opkg install "$addremote_ipk"
echo 'Add Remote Diagnostic 1.2.0 installed. Restart the Enigma2 GUI manually when ready.'
echo 'Open Add Remote Diagnostic, run the test, then download reports at http://RECEIVER-IP:6060/'
echo 'Standalone diagnostic only. GT Panel and Add Remote are not upgraded by this installer.'
