import io
import pathlib
import sys
import tarfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from GTPanel import ipk

PACKAGE = ROOT / "build/repair-ipk/gtcombo-android-fix_1.0.0_all.ipk"

def ar_member(name, data):
    h = (
        name.ljust(16) + "0".ljust(12) +
        "0".ljust(6) + "0".ljust(6) +
        "100644".ljust(8) +
        str(len(data)).ljust(10) + "`\n"
    ).encode("ascii")
    return h + data + (b"\n" if len(data) % 2 else b"")

def repack(files):
    original = ipk.read_ar(PACKAGE.read_bytes())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path, content in files:
            info = tarfile.TarInfo(path)
            info.size = len(content)
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(content))
    original["data.tar.gz"] = buf.getvalue()
    return b"!<arch>\n" + b"".join(
        ar_member(name, original[name])
        for name in ("debian-binary", "control.tar.gz", "data.tar.gz")
    )

class MalformedIPKTests(unittest.TestCase):
    def test_duplicate_paths(self):
        data = repack([
            ("usr/lib/gtcombo/android-boot.py", b"A"),
            ("usr/lib/gtcombo/android-boot.py", b"B"),
        ])
        with self.assertRaises(ipk.IPKError):
            ipk.payload(data, {"/usr/lib/gtcombo/android-boot.py"})

    def test_path_traversal(self):
        data = repack([
            ("../../etc/passwd", b"bad"),
        ])
        with self.assertRaises(ipk.IPKError):
            ipk.payload(data, {"/etc/passwd"})

if __name__ == "__main__":
    unittest.main()
