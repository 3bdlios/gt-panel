import io
import json
import pathlib
import sys
import tarfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from GTPanel import ipk


class IPKTests(unittest.TestCase):

    def test_real_repair_packages(self):
        packages = [
            ("gtcombo-android-fix", "gtcombo-android-v1", 3),
            ("gtcombo-frontpanel-fix", "gtcombo-frontpanel-v1", 4),
        ]

        for name, source, count in packages:
            with self.subTest(package=name):
                metadata = ROOT / "repository" / (
                    source + ".tar.gz.item.json"
                )
                item = json.loads(metadata.read_text())

                package = ROOT / "build/repair-ipk" / (
                    name + "_1.0.0_all.ipk"
                )
                files = ipk.payload(
                    package.read_bytes(),
                    set(item["files"])
                )
                self.assertEqual(len(files), count)

    def test_invalid_archive_rejected(self):
        with self.assertRaises(ipk.IPKError):
            ipk.payload(b"invalid", set())

    def test_truncated_archive_rejected(self):
        with self.assertRaises(ipk.IPKError):
            ipk.read_ar(b"!<arch>\n" + b"bad")

    def test_undeclared_file_rejected(self):
        package = ROOT / "build/repair-ipk" / (
            "gtcombo-android-fix_1.0.0_all.ipk"
        )
        with self.assertRaises(ipk.IPKError):
            ipk.payload(package.read_bytes(), {"/tmp/wrong"})

    def test_duplicate_archive_member_rejected(self):
        package = ROOT / "build/repair-ipk" / (
            "gtcombo-android-fix_1.0.0_all.ipk"
        )
        data = package.read_bytes()
        members = ipk.read_ar(data)
        self.assertEqual(
            set(members),
            {"debian-binary", "control.tar.gz", "data.tar.gz"}
        )


if __name__ == "__main__":
    unittest.main()
