import io
import pathlib
import sys
import tarfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from GTPanel import ipk

class IPKSecurityTests(unittest.TestCase):
    def test_reject_postinst(self):
        package = ROOT / "build/repair-ipk/gtcombo-android-fix_1.0.0_all.ipk"
        members = ipk.read_ar(package.read_bytes())

        with tarfile.open(fileobj=io.BytesIO(members["control.tar.gz"]), mode="r:gz") as tf:
            control = tf.extractfile(tf.getmembers()[0]).read()

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
            for name, data in (
                ("control", control),
                ("postinst", b"#!/bin/sh\nexit 0\n"),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))

        def member(name, data):
            header = (
                name.ljust(16) + "0".ljust(12) +
                "0".ljust(6) + "0".ljust(6) +
                "100644".ljust(8) +
                str(len(data)).ljust(10) + "`\n"
            ).encode("ascii")
            return header + data + (b"\n" if len(data) % 2 else b"")

        modified = b"!<arch>\n"
        for name in ("debian-binary", "control.tar.gz", "data.tar.gz"):
            data = buffer.getvalue() if name == "control.tar.gz" else members[name]
            modified += member(name, data)

        with self.assertRaises(ipk.IPKError):
            ipk.payload(modified, {
                "/etc/init.d/gtcombo-boot-menu",
                "/usr/lib/gtcombo/android-boot.py",
                "/usr/lib/gtcombo/android-once.py",
            })
