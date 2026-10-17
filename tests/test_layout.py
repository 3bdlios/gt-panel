import unittest,ast,pathlib,os,xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load_layout():
    src=ast.parse((ROOT/'src/GTPanel/plugin.py').read_text())
    node=next(n for n in src.body if isinstance(n,ast.FunctionDef) and n.name=='layout')
    scope={'os':os,'escape':escape,'HERE':str(ROOT/'src/GTPanel')}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'layout','exec'),scope)
    return scope['layout']
class LayoutTests(unittest.TestCase):
    def test_widgets_fit_fhd_hd_and_sd(self):
        layout=load_layout()
        for desktop in (1920,1280,1024,720):
            xml,_=layout(desktop);screen=ET.fromstring(xml);w,h=map(int,screen.attrib['size'].split(','))
            self.assertLess(w,desktop)
            for e in screen:
                x,y=map(int,e.attrib['position'].split(','));a,b=map(int,e.attrib['size'].split(','))
                self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0);self.assertLessEqual(x+a,w);self.assertLessEqual(y+b,h)
            names={e.attrib['name'] for e in screen if 'name' in e.attrib}
            self.assertIn('icon',names);self.assertIn('detail',names);self.assertIn('list',names)
    def test_assets_exist(self):
        for name in ('icon.png','icon-large.png'):
            self.assertTrue((ROOT/'src/GTPanel'/name).exists())
    def test_text_and_icon_above_backgrounds(self):
        xml,_=load_layout()(1920)
        screen=ET.fromstring(xml)
        backgrounds=[int(e.get('zPosition','0')) for e in screen if e.tag=='eLabel']
        for widget in screen.findall('widget'):
            self.assertGreater(int(widget.get('zPosition','0')),max(backgrounds))
    def test_list_rendering_after_enigma_applies_tuple_scale(self):
        src=ast.parse((ROOT/'src/GTPanel/plugin.py').read_text())
        cls=next(n for n in src.body if isinstance(n,ast.ClassDef) and n.name=='GTPanel')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='entries')
        scope={'MultiContentEntryText':lambda **values:values,'RT_VALIGN_CENTER':0}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'entries','exec'),scope)
        class List:
            def setList(self,rows):self.rows=rows
        class Panel:
            scale=((1920,1920),(1080,1080))
            panel_scale=1.0
            def __getitem__(self,key):return self.list
        panel=Panel();panel.list=List()
        scope['entries'](panel,[('Fixes','Repair receiver')])
        self.assertIsInstance(panel.list.rows[0],list)
        self.assertEqual(panel.list.rows[0][1]['text'],'Fixes')
if __name__=='__main__':unittest.main()
