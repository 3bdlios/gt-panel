import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from Plugins.Extensions.AddRemote import autoir

class AutoTests(unittest.TestCase):
    def test_unknown_keycode_captured_without_kernel_keymap(self):
        data = struct.pack('=QHHIQ', 100, 0, 9, 0, 0x123456)
        events, native, proto = autoir.parse_scancodes(data, 'receiver')
        self.assertEqual(events, [('ir:receiver:9:123456', 1)])
        self.assertEqual(native, 0)
        self.assertEqual(proto, 'NEC')
    def test_native_remote_and_repeats_do_not_inject(self):
        data = struct.pack('=QHHIQ', 100, 0, 9, 352, 0x304)
        data += struct.pack('=QHHIQ', 200, 2, 9, 0, 0x1234)
        self.assertEqual(autoir.parse_scancodes(data, 'r')[:2], ([('ir:r:9:1234', 2)], 1))
    def test_protocol_is_part_of_identity(self):
        data = struct.pack('=QHHIQ', 100, 0, 2, 0, 1)
        data += struct.pack('=QHHIQ', 200, 0, 9, 0, 1)
        events, _, _ = autoir.parse_scancodes(data, 'r')
        self.assertNotEqual(events[0][0], events[1][0])
    def test_partial_record_rejected(self):
        with self.assertRaises(ValueError):
            autoir.parse_scancodes(b'x', 'r')
    def test_raw_jitter_matches_but_different_button_does_not(self):
        a = autoir.raw_token('r', [9000,4500]+[560,560]*16+[560])
        b = autoir.raw_token('r', [9100,4400]+[580,530]*16+[570])
        c = autoir.raw_token('r', [9000,4500]+[560,1690]*16+[560])
        self.assertTrue(autoir.raw_match(a,b))
        self.assertFalse(autoir.raw_match(a,c))
    def test_raw_frame_and_repeat_filter(self):
        frame = [9000,4500]+[560,560]*16+[560]
        data = b''.join(struct.pack('=I', v | (0x1000000 if i%2==0 else 0)) for i,v in enumerate(frame))
        data += struct.pack('=I', 0x3000000 | 15000)
        self.assertEqual(autoir.RawFrames().feed(data), [frame])
        short = struct.pack('=IIII', 0x1002328, 2250, 0x1000230, 0x3003a98)
        self.assertEqual(autoir.RawFrames().feed(short), [])

if __name__ == '__main__': unittest.main()
