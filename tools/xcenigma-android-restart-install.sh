#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run as root'; exit 1; }
command -v python3 >/dev/null || { echo 'Python3 required'; exit 1; }
task_dir=$(mktemp -d /tmp/xc-android-install.XXXXXX)
trap 'rm -rf "$task_dir"' EXIT HUP INT TERM
url=https://raw.githubusercontent.com/3bdlios/gt-panel/main/tools/xcenigma-android-restart-bundle.tar.gz
if command -v curl >/dev/null 2>&1; then
 curl -fL "$url" -o "$task_dir/bundle.tar.gz"
else
 wget -O "$task_dir/bundle.tar.gz" "$url"
fi
python3 - "$task_dir/bundle.tar.gz" <<'CHECK'
import hashlib,sys
assert hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest() == '41bb96381296d500fb30f361a1f22952ad0a81daea7a75bb1c252f4c0a950a95', 'Download checksum mismatch'
CHECK
tar -xzf "$task_dir/bundle.tar.gz" -C "$task_dir"
sh "$task_dir/install.sh"
