import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from Plugins.Extensions.AddRemote.keyflow import KeyFlow
from Plugins.Extensions.AddRemote.autoir import RawFrames
import struct

class HoldTests(unittest.TestCase):
    def test_short_press_balanced_release(self):
        out=[]; f=KeyFlow(lambda c,v:out.append((c,v)))
        f.event('raw:r:1',103,1,0);f.expire(.29)
        self.assertEqual(out,[(103,0),(103,1)])
    def test_hold_emits_repeat_long_once_and_break(self):
        out=[];f=KeyFlow(lambda c,v:out.append((c,v)))
        f.event('raw:r:1',103,1,0)
        for i in range(1,16):
            f.expire(i/10);f.event('raw:r:1',103,2,i/10)
        f.expire(1.8)
        self.assertEqual(out[0],(103,0));self.assertEqual(out[-1],(103,1))
        self.assertGreater(len([x for x in out if x[1]==2]),3)
        self.assertEqual(len([x for x in out if x[1]==3]),1)
    def test_key_switch_and_stop_release(self):
        out=[];f=KeyFlow(lambda c,v:out.append((c,v)))
        f.event('a',1,1,0);f.event('b',2,1,.1);f.release()
        self.assertEqual(out,[(1,0),(1,1),(2,0),(2,1)])
    def test_bluetooth_release(self):
        out=[];f=KeyFlow(lambda c,v:out.append((c,v)))
        f.event('bt:r:1',1,1,0);f.expire(.3)
        self.assertEqual(len(out),1)
        f.event('bt:r:1',1,0,.4)
        self.assertEqual(out[-1],(1,1))
    def test_nec_repeat_is_not_learned_as_new_button(self):
        parser=RawFrames()
        data=struct.pack('=IIII',0x1000000|9000,2250,0x1000000|560,0x3000000|15000)
        self.assertEqual(parser.feed(data),[])
        self.assertEqual(parser.repeats,1)

if __name__=='__main__':unittest.main()
