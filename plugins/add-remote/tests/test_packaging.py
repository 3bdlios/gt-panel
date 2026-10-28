import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_ipk',ROOT/'tools/build_ipk.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class PackagingTests(unittest.TestCase):
 def test_optional_bluetooth_does_not_trigger_feed_download(self):
  fields=dict(line.split(': ',1) for line in builder.CONTROL.strip().splitlines())
  self.assertNotIn('Recommends',fields)
  self.assertNotIn('python3-evdev',fields['Depends'])
  self.assertIn('enigma2',fields['Depends'])
  self.assertIn('python3-core',fields['Depends'])
  self.assertIn('python3-json',fields['Depends'])

if __name__=='__main__':unittest.main()
