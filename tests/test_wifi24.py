import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wifi_repair', ROOT/'src/GTWiFi24/repair.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
CONFIG = 'ctrl_interface=/run/wpa_supplicant\nnetwork={\n\tssid="Example"\n\tpsk="local-secret"\n\tbssid=00:11:22:33:44:55\n\tpriority=3\n}\n'


class BandRepairTests(unittest.TestCase):
    def test_apply_preserves_credentials_and_unrelated_options(self):
        saved = {}
        new, count = repair.rewrite(CONFIG, saved)
        self.assertEqual(count, 1)
        self.assertIn('psk="local-secret"', new)
        self.assertIn('priority=3', new)
        self.assertNotIn('bssid=', new)
        self.assertIn('freq_list=2412 2417', new)
        self.assertNotIn('local-secret', json.dumps(saved))
        self.assertNotIn('Example', json.dumps(saved))

    def test_round_trip_and_duplicate_ssids(self):
        text = CONFIG + CONFIG[CONFIG.index('network='):].replace('priority=3', 'priority=7')
        saved = {}
        new, count = repair.rewrite(text, saved)
        self.assertEqual(count, 2)
        self.assertEqual(len(saved), 2)
        restored, count = repair.rewrite(new, saved, restore=True)
        self.assertCountEqual(restored.splitlines(), text.splitlines())

    def test_idempotent_and_does_not_lose_original_fields(self):
        saved = {}
        once, _ = repair.rewrite(CONFIG, saved)
        original = json.dumps(saved)
        twice, _ = repair.rewrite(once, saved)
        self.assertEqual(once, twice)
        self.assertEqual(json.dumps(saved), original)

    def test_restore_preserves_changed_password(self):
        saved = {}
        new, _ = repair.rewrite(CONFIG, saved)
        result, _ = repair.rewrite(new.replace('local-secret', 'new-password'), saved, restore=True)
        self.assertIn('new-password', result)
        self.assertIn('bssid=00:11:22:33:44:55', result)

    def test_restore_rejects_later_band_edits(self):
        saved = {}
        new, _ = repair.rewrite(CONFIG, saved)
        with self.assertRaisesRegex(ValueError, 'changed'):
            repair.rewrite(new.replace('freq_list='+repair.FREQUENCIES, 'freq_list=5180'), saved, restore=True)

    def test_no_network_is_not_modified(self):
        text = 'ctrl_interface=/run/wpa_supplicant\n'
        self.assertEqual(repair.rewrite(text, {}), (text, 0))

    def test_file_apply_restore_and_disabled_autostart(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'wifi.conf'
            config.write_text(CONFIG)
            state = Path(folder)/'state'
            with patch.object(repair, 'CONFIG', config), patch.object(repair, 'STATE', state), \
                 patch.object(repair, 'supported', return_value=True), \
                 patch.object(repair.subprocess, 'run', return_value=subprocess.CompletedProcess([],0,'OK\n','')) as run:
                repair.perform()
                self.assertEqual((state/'original.conf').read_text(), CONFIG)
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                self.assertFalse((state/'operation.lock').exists())
                repair.perform(automatic=True)
                self.assertEqual(run.call_count, 1, 'GUI restart must not reconnect an unchanged network')
                repair.perform(restore=True)
                restored = config.read_text()
                self.assertCountEqual(restored.splitlines(), CONFIG.splitlines())
                repair.perform(automatic=True)
                self.assertEqual(config.read_text(), restored)
                self.assertEqual(run.call_count, 2)

    def test_wrong_device_is_not_modified(self):
        with patch.object(repair, 'supported', return_value=False):
            with self.assertRaisesRegex(ValueError, 'GTMedia'):
                repair.perform()

    def test_restore_without_saved_network_disables_future_autostart(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'missing.conf'
            state = Path(folder)/'state'
            with patch.object(repair, 'CONFIG', config), patch.object(repair, 'STATE', state), \
                 patch.object(repair, 'supported', return_value=True):
                repair.perform(restore=True)
                config.write_text(CONFIG)
                repair.perform(automatic=True)
                self.assertEqual(config.read_text(), CONFIG)


if __name__ == '__main__':
    unittest.main()
