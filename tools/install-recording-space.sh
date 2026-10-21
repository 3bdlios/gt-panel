#!/bin/sh
set -eu
case "${1-}" in ""|--auto) ;; *) echo 'Use no arguments (install only) or --auto (prepare and reboot if needed)'; exit 1 ;; esac
[ "$#" -le 1 ] || exit 1
[ "$(id -u)" = 0 ] || { echo 'Run as root'; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Python3 is required'; exit 1; }
task_dir=$(mktemp -d /tmp/xc-recording-install.XXXXXX)
trap 'rm -rf "$task_dir"' EXIT HUP INT TERM
url=https://raw.githubusercontent.com/3bdlios/gt-panel/main/tools/prepare-recording-space.py
if command -v curl >/dev/null 2>&1; then
 curl -fL "$url" -o "$task_dir/prepare-recording-space.py"
else
 wget -O "$task_dir/prepare-recording-space.py" "$url"
fi
python3 - "$task_dir/prepare-recording-space.py" <<'VERIFY'
import hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);data=p.read_bytes()
if hashlib.sha256(data).hexdigest() != 'ae163e339d53f30d1fbe903dcb3bfb16681670283def884d297cc0d1e639d152':raise SystemExit('STOP: checksum mismatch')
compile(data,str(p),'exec')
VERIFY
# Preflight is read-only and must pass before installation.
python3 "$task_dir/prepare-recording-space.py"
python3 - "$task_dir/prepare-recording-space.py" <<'INSTALL'
from pathlib import Path
import os,sys,tempfile
source=Path(sys.argv[1]);folder=Path('/usr/local/sbin')
folder.mkdir(parents=True,exist_ok=True)
if folder.is_symlink():raise SystemExit('STOP: unexpected install-directory symlink')
fd,tmp=tempfile.mkstemp(prefix='.xc-recording-',dir=str(folder))
try:
 with os.fdopen(fd,'wb') as f:f.write(source.read_bytes());f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o755);os.replace(tmp,folder/'xc-recording-space')
finally:
 if os.path.exists(tmp):os.unlink(tmp)
INSTALL
printf '%s\n' 'Installed: xc-recording-space'
if [ "${1-}" = --auto ]; then
 exec python3 /usr/local/sbin/xc-recording-space --auto
fi
printf '%s\n' 'No partition changes or formatting performed.' 'For automatic preparation including reboot/resume: python3 /usr/local/sbin/xc-recording-space --auto'
