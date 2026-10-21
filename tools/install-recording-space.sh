#!/bin/sh
set -eu
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
if hashlib.sha256(data).hexdigest() != '23e86eebe40971c20e531a1bcc307d2e3c5c7be0b3f6c7b1f00612f44f09d229':raise SystemExit('STOP: checksum mismatch')
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
printf '%s
' 'Installed: xc-recording-space' 'No partition changes or formatting performed.' 'To create the extra partition: python3 /usr/local/sbin/xc-recording-space --apply' 'Reboot the receiver when requested, then run the same --apply command again to format and mount the NEW partition.'
