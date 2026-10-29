#!/usr/bin/env python3
"""Build an architecture-independent opkg ar package using Python stdlib only."""
import io
import pathlib
import tarfile
import hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL = '''Package: enigma2-plugin-extensions-addremotediagnostic
Version: 1.2.0
Architecture: all
Maintainer: Fares3nzi
Section: extra
Priority: optional
Depends: enigma2, python3-core, python3-json, python3-netserver, python3-compression, python3-threading, python3-fcntl, python3-misc
Description: IR diagnostic with local browser report downloads on port 6060
'''

def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz', format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(entries.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()

def build():
    entries = {}
    for file in (ROOT / 'src').rglob('*'):
        if not file.is_file() or file.suffix not in ('.py', '.png', '.svg'):
            continue
        entries['./usr/lib/enigma2/python/' + str(file.relative_to(ROOT / 'src'))] = file.read_bytes()
    entries['./usr/share/doc/addremotediagnostic/README.md'] = (ROOT / 'README.md').read_bytes()
    entries['./usr/share/doc/addremotediagnostic/LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    members = {'debian-binary': b'2.0\n', 'control.tar.gz': archive({'./control': CONTROL.encode()}), 'data.tar.gz': archive(entries)}
    output = ROOT.parent / 'enigma2-plugin-extensions-addremotediagnostic_1.2.0_all.ipk'
    with output.open('wb') as f:
        f.write(b'!<arch>\n')
        for name, data in members.items():
            header = '%-16s%-12s%-6s%-6s%-8s%-10s`\n' % (name + '/', 0, 0, 0, '100644', len(data))
            f.write(header.encode('ascii'))
            f.write(data)
            if len(data) % 2:
                f.write(b'\n')
    print(output)
    print('SHA256', hashlib.sha256(output.read_bytes()).hexdigest())

if __name__ == '__main__':
    build()
