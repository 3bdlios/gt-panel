#!/bin/sh
# Add Remote 0.3.2 — Fares3nzi
set -eu
command -v opkg >/dev/null 2>&1 || { echo 'opkg is required'; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required'; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' || { echo 'Python 3.8+ is required'; exit 1; }
[ -d /usr/lib/enigma2/python ] || { echo 'Enigma2 is required'; exit 1; }
command -v sha256sum >/dev/null 2>&1 || { echo 'sha256sum is required'; exit 1; }
addremote_tmp=$(mktemp -d /tmp/addremote-install.XXXXXX)
trap 'rm -rf "$addremote_tmp"' EXIT
trap 'exit 1' HUP INT TERM
addremote_ipk="$addremote_tmp/enigma2-plugin-extensions-addremote_0.3.2_all.ipk"
addremote_url='https://github.com/3bdlios/gt-panel/releases/download/add-remote-v0.3.2/enigma2-plugin-extensions-addremote_0.3.2_all.ipk'
if command -v wget >/dev/null 2>&1; then
    wget -O "$addremote_ipk" "$addremote_url"
elif command -v curl >/dev/null 2>&1; then
    curl --fail --location --proto '=https' --proto-redir '=https' -o "$addremote_ipk" "$addremote_url"
else
    echo 'wget or curl is required'; exit 1
fi
printf '%s  %s\n' '39bfbc12f32701137f0d4ce53b64ee4c40d161181a90853c80469d281d3b2572' "$addremote_ipk" | sha256sum -c -
opkg install "$addremote_ipk"
echo 'Add Remote 0.3.2 installed. Restart the Enigma2 GUI manually when ready.'
echo 'Existing remote profiles are preserved. IR hardware compatibility varies.'
