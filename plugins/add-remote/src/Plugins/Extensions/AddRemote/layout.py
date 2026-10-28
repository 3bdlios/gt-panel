"""Native Enigma2 layout matching the GT Remote reference page."""
from xml.sax.saxutils import escape
import os
from .core import ROWS

BACKGROUND = '#09121f'
BUTTON = '#192b41'
BORDER = '#31465e'
TEXT = '#e5edf8'
ACCENT = '#53d2c2'
COLORS = {'KEY_RED':'#df4055','KEY_GREEN':'#28a65a','KEY_YELLOW':'#d4ad22','KEY_BLUE':'#376fe1'}

SYMBOLS = {'KEY_POWER':'power', '__PROFILES__':'mail', '__HELP__':'expand',
           'KEY_REWIND':'rewind','KEY_FASTFORWARD':'forward','KEY_PREVIOUS':'previous',
           'KEY_NEXT':'next','KEY_LEFT':'left','KEY_RIGHT':'right','KEY_UP':'up',
           'KEY_DOWN':'down','KEY_PLAY':'play','KEY_PAUSE':'pause',
           'KEY_RECORD':'record','KEY_STOP':'stop'}

def buttons():
    y = 92
    result = []
    for r, row in enumerate(ROWS):
        height = 40 if r == 0 else 26 if r == 5 else 48 if 6 <= r <= 8 else 42 if r <= 10 else 36
        gap = 10
        width = (560 - gap * (len(row)-1)) // len(row)
        for c, (label, target) in enumerate(row):
            result.append(dict(r=r,c=c,x=680+c*(width+gap),y=y,w=width,h=height,
                               label=label,target=target,color=COLORS.get(target,'#173e4b' if target=='KEY_OK' else BUTTON)))
        y += height + (10 if r in (0,4,5,8,10,12) else 7)
    return result


def build_skin(width=1920, height=1080):
    scale = min(width/1920.0, height/1080.0)
    def box(x,y,w,h):
        return 'position="%d,%d" size="%d,%d"' % tuple(round(v*scale) for v in (x,y,w,h))
    def font(n): return max(12,round(n*scale))
    xml = ['<screen name="AddRemote" position="0,0" size="%d,%d" flags="wfNoBorder" title="Add Remote" backgroundColor="%s">' % (width,height,BACKGROUND)]
    def text(value,x,y,w,h,size,color=TEXT,align='left'):
        xml.append('<eLabel text="%s" %s font="Regular;%d" foregroundColor="%s" halign="%s" valign="center" transparent="1" zPosition="2" />' % (escape(value, {'"':'&quot;'}),box(x,y,w,h),font(size),color,align))
    text('ENIGMA2',680,18,560,22,16,ACCENT,'right')
    text('Add Remote',680,42,560,40,34,TEXT,'right')
    for b in buttons():
        r,c,x,y,w,h = (b[k] for k in ('r','c','x','y','w','h'))
        border = ACCENT if b['target']=='KEY_OK' else BORDER
        xml.append('<eLabel %s backgroundColor="%s" cornerRadius="%d" zPosition="1" />' % (box(x,y,w,h),border,max(4,font(11))))
        xml.append('<widget name="b%d_%d" %s font="Regular;%d" foregroundColor="%s" backgroundColor="%s" halign="center" valign="center" transparent="0" cornerRadius="%d" zPosition="3" />' % (r,c,box(x+1,y+1,w-2,h-2),font(23 if 1<=r<=4 else 21),TEXT,b['color'],max(4,font(10))))
        if b['target'] in SYMBOLS:
            icon_size = min(h-8,32)
            asset = os.path.join(os.path.dirname(__file__),'assets',SYMBOLS[b['target']]+'.png')
            xml.append('<widget name="i%d_%d" %s pixmap="%s" alphatest="blend" scale="1" zPosition="4" />' % (r,c,box(x+(w-icon_size)//2,y+(h-icon_size)//2,icon_size,icon_size),asset))
        xml.append('<widget name="m%d_%d" %s font="Regular;%d" foregroundColor="%s" halign="right" transparent="1" zPosition="5" />' % (r,c,box(x+w-29,y+2,23,22),font(17),ACCENT))
    text('REMOTE PROFILE',100,158,450,30,18,ACCENT)
    xml.append('<widget name="status" %s font="Regular;%d" foregroundColor="%s" transparent="1" zPosition="3" />' % (box(100,210,450,650),font(25),TEXT))
    for i,(name,color) in enumerate([('Profiles',COLORS['KEY_RED']),('Save + activate',COLORS['KEY_GREEN']),('Status',COLORS['KEY_YELLOW']),('Save / restart',COLORS['KEY_BLUE'])]):
        x=100+i*435
        xml.append('<eLabel %s backgroundColor="%s" cornerRadius="5" zPosition="2" />' % (box(x,1007,10,27),color))
        text(name,x+23,1002,390,36,22)
    xml.append('<widget name="help" %s font="Regular;%d" foregroundColor="#8ca1b8" transparent="1" zPosition="3" />' % (box(100,1040,1720,30),font(20)))
    xml.append('</screen>')
    return ''.join(xml)
