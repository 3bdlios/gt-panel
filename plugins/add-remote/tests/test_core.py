import importlib.util
import pathlib
import tempfile
import unittest

BASE = pathlib.Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, BASE / 'src/Plugins/Extensions/AddRemote' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
core, inputs = module('core'), module('inputs')

class Tests(unittest.TestCase):
    def test_roundtrip_unicode_and_no_path_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = core.Store(tmp + '/nested/profiles.json')
            d = s.load()
            p = core.new_profile('../../فارس')
            core.bind(p, 'evdev:123', 'KEY_OK')
            d['profiles'].append(p)
            d['active'] = p['id']
            s.save(d)
            self.assertEqual(s.load(), d)
            self.assertEqual(len(list(pathlib.Path(tmp).rglob('*.json'))), 1)
    def test_reassignment_and_invalid_target(self):
        p = core.new_profile('Test')
        core.bind(p, 'evdev:1', 'KEY_OK')
        core.bind(p, 'evdev:2', 'KEY_OK')
        self.assertEqual(p['mappings'], {'evdev:2': 'KEY_OK'})
        with self.assertRaises(ValueError):
            core.bind(p, 'x', 'arbitrary_command')
    def test_invalid_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'profiles.json'
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                core.Store(str(path)).load()
            self.assertEqual(path.read_text(), '{broken')
    def test_unknown_active_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = core.Store(tmp + '/profiles.json')
            s.save({'version': 1, 'profiles': [], 'active': 'missing'})
            with self.assertRaises(ValueError):
                s.load()
    def test_lirc_repeat_and_invalid(self):
        self.assertEqual(inputs.parse_lirc('000001fe 00 KEY_OK remote'), ('lirc:remote:KEY_OK', 1))
        for line in ['000001fe 01 KEY_OK remote', 'garbage', 'zz 00 KEY_OK r']:
            self.assertIsNone(inputs.parse_lirc(line))
    def test_save_activates_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = core.Store(tmp + '/profiles.json')
            data = store.load()
            profile = core.new_profile('Remote 1')
            profile['source'] = {'kind': 'auto'}
            core.bind(profile, 'ir:r:9:1', 'KEY_UP')
            data['profiles'].append(profile)
            self.assertTrue(core.activate_for_save(data, profile))
            store.save(data)
            self.assertEqual(store.load()['active'], profile['id'])
            data['active'] = None
            store.save(data)
            self.assertIsNone(store.load()['active'])

    def test_empty_profile_does_not_activate(self):
        p = core.new_profile('empty')
        data = {'profiles': [p], 'active': None}
        self.assertFalse(core.activate_for_save(data, p))
        self.assertIsNone(data['active'])

    def test_grid_and_names(self):
        self.assertGreaterEqual(len(core.TARGETS), 45)
        for name in ['', ' ' , 'x' * 65]:
            with self.assertRaises(ValueError):
                core.new_profile(name)

if __name__ == '__main__':
    unittest.main()
