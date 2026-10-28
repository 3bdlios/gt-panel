import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from Plugins.Extensions.AddRemote.layout import build_skin,buttons,SYMBOLS
from Plugins.Extensions.AddRemote.core import ROWS,TARGETS

class LayoutTests(unittest.TestCase):
    def test_hd_and_fhd_have_no_clipped_widgets(self):
        for width,height in [(1920,1080),(1280,720)]:
            root=ET.fromstring(build_skin(width,height))
            names=[w.attrib['name'] for w in root.findall('widget')]
            self.assertEqual(len(names),len(set(names)))
            for w in root:
                if 'position' in w.attrib:
                    x,y=map(int,w.attrib['position'].split(','));a,b=map(int,w.attrib['size'].split(','))
                    self.assertLessEqual(x+a,width)
                    self.assertLessEqual(y+b,height)
            self.assertNotIn('فارس',ET.tostring(root,encoding='unicode'))
    def test_reference_navigation_and_color_order(self):
        self.assertEqual([k for _,k in ROWS[5]],['KEY_RED','KEY_GREEN','KEY_YELLOW','KEY_BLUE'])
        self.assertEqual([k for _,k in ROWS[6]],['KEY_MENU','KEY_UP','KEY_EXIT'])
        self.assertEqual([k for _,k in ROWS[7]],['KEY_LEFT','KEY_OK','KEY_RIGHT'])
        self.assertEqual([k for _,k in ROWS[8]],['KEY_INFO','KEY_DOWN','KEY_EPG'])
        self.assertNotIn('__PROFILES__',TARGETS)
    def test_all_symbol_assets_exist(self):
        folder=pathlib.Path(__file__).resolve().parents[1]/'src/Plugins/Extensions/AddRemote'
        for symbol in SYMBOLS.values():self.assertTrue((folder/'assets'/(symbol+'.png')).is_file())
        self.assertTrue((folder/'plugin.png').is_file())

if __name__=='__main__':unittest.main()
