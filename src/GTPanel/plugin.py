from __future__ import absolute_import
import os, json
from xml.sax.saxutils import escape
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ActionMap import ActionMap
from Components.MultiContent import MultiContentEntryText
from Plugins.Plugin import PluginDescriptor
from enigma import getDesktop, eListboxPythonMultiContent, gFont, RT_VALIGN_CENTER
from twisted.internet.threads import deferToThread
from . import core

HERE=os.path.dirname(__file__)
CONFIG='/etc/gt-panel/repository.json'
CAPTIONS={'Fixes':'Repair your receiver', 'Plugins':'Add new features', 'Skins':'Make it your own', 'Updates':'Reviewed improvements'}


def layout(width):
    scale=min(1.0, max(0.3, (width-60)/1640.0))
    def n(value):return max(0,int(value*scale))
    def pos(x,y):return '%d,%d'%(n(x),n(y))
    def size(w,h):return pos(w,h)
    parts=['<screen name="GTPanel" position="center,center" size="%s" title="GT Panel" backgroundColor="#0b1220" flags="wfNoBorder">'%size(1640,880)]
    def rect(x,y,w,h,color):parts.append('<eLabel zPosition="0" position="%s" size="%s" backgroundColor="%s" />'%(pos(x,y),size(w,h),color))
    def text(name,x,y,w,h,font=24,color='#e6efff',bg='#0b1220'):
        parts.append('<widget zPosition="2" name="%s" position="%s" size="%s" font="Regular;%d" foregroundColor="%s" backgroundColor="%s" transparent="1" />'%(name,pos(x,y),size(w,h),n(font),color,bg))
    rect(0,0,1640,152,'#101d31'); rect(0,152,1640,2,'#24415a')
    parts.append('<widget zPosition="2" name="icon" position="%s" size="%s" pixmap="%s" alphatest="blend" scale="1" />'%(pos(28,24),size(104,104),escape(os.path.join(HERE,'icon-large.png'))))
    text('brand',156,29,650,54,43);text('subtitle',158,91,850,34,23,'#8da6bf')
    text('badge',1320,42,280,40,24,'#4ae3cf');text('connection',1160,94,440,32,20,'#8da6bf')
    rect(0,154,280,650,'#0e192a');text('rail_title',30,194,220,36,22,'#4ae3cf')
    text('rail_copy',30,252,215,210,26);text('device',30,540,220,210,20,'#8da6bf')
    text('section',320,190,760,48,33);text('status',320,246,760,54,21,'#8da6bf')
    parts.append('<widget zPosition="2" name="list" position="%s" size="%s" scrollbarMode="showOnDemand" backgroundColor="#101d31" foregroundColor="#e6efff" backgroundColorSelected="#154c70" foregroundColorSelected="#ffffff" transparent="0" />'%(pos(320,316),size(770,448)))
    rect(1120,190,480,574,'#101d31');rect(1120,190,4,574,'#28cbbb')
    text('detail_tag',1152,222,416,35,20,'#4ae3cf');text('detail_title',1152,278,416,108,31)
    text('detail',1152,405,416,244,23,'#afc2d7');text('detail_hint',1152,691,416,44,20,'#4ae3cf')
    rect(0,804,1640,76,'#101d31');rect(30,835,6,16,'#ef6574');rect(430,835,6,16,'#56d7bd');rect(920,835,6,16,'#639ffa')
    text('key_red',50,828,350,34,22);text('key_green',450,828,440,34,22);text('key_blue',940,828,600,34,22)
    parts.append('</screen>')
    return ''.join(parts),scale

class GTPanel(Screen):
    def __init__(self,session):
        self.skin,self.panel_scale=layout(getDesktop(0).size().width())
        Screen.__init__(self,session)
        labels={'brand':'GT PANEL','subtitle':'Your receiver. Repaired, expanded, personalised.', 'badge':'REPAIR HUB  /  2.1.1',
                'connection':'GitHub catalog', 'rail_title':'GT ENIGMA2', 'rail_copy':'DOWNLOADS\n& REPAIRS\n\nOne place for\nyour receiver.',
                'device':'Checking device…','section':'Explore your panel','status':'Loading the GitHub catalog…',
                'detail_tag':'BUILT FOR YOUR RECEIVER','detail_title':'Choose a category','detail':'Review compatibility and changes before installing.\n\nBackups are created before files are replaced.',
                'detail_hint':'OK to explore', 'key_red':'Back / Close', 'key_green':'OK / Green: Install', 'key_blue':'Blue: Backups & restore'}
        for key,value in labels.items():self[key]=Label(value)
        self['icon']=Pixmap()
        self['list']=MenuList([],content=eListboxPythonMultiContent)
        self['list'].l.setFont(0,gFont('Regular',int(29*self.panel_scale)))
        self['list'].l.setFont(1,gFont('Regular',int(21*self.panel_scale)))
        self['list'].l.setItemHeight(int(112*self.panel_scale))
        self['list'].onSelectionChanged.append(self.details)
        self['actions']=ActionMap(['OkCancelActions','ColorActions'],{'ok':self.select,'green':self.select,'cancel':self.back,'red':self.back,'blue':self.backups},-1)
        self.doc={'items':[]};self.level='categories';self.rows=[];self.busy=True;self.alive=True;self.config={}
        try:
            self.device=core.facts()
            self['device'].setText('%s\n\n%s\n%s\nPython %s'%(self.device['model'],self.device['image'],self.device['version'],self.device['python']))
        except Exception:self.device={};self['device'].setText('Unknown device\n\nCompatibility checks\nwill block installs.')
        self.show_categories()
        self.onClose.append(self.closed)
        self.onFirstExecBegin.append(self.load)
    def closed(self):self.alive=False
    def entries(self,values):
        def n(v):return int(v*self.panel_scale)
        entries=[]
        for title,sub in values:
            entries.append([title,MultiContentEntryText(pos=(n(24),n(16)),size=(n(710),n(42)),font=0,flags=RT_VALIGN_CENTER,text=title,color=0xe6efff,color_sel=0xffffff),MultiContentEntryText(pos=(n(24),n(65)),size=(n(710),n(30)),font=1,text=sub,color=0x8da6bf,color_sel=0xb7e9ef)])
        self['list'].setList(entries)
    def show_categories(self):
        self.level='categories';self.rows=list(core.CATEGORIES)
        self.entries([(c,CAPTIONS[c]) for c in self.rows]);self['section'].setText('Explore your panel');self.details()
    def error(self,failure):
        self.busy=False
        if self.alive:
            self['status'].setText('Stopped safely. Review the message to continue.')
            self.session.open(MessageBox,str(getattr(failure,'value',failure)),MessageBox.TYPE_ERROR)
    def load(self):
        def work():
            with open(CONFIG if os.path.isfile(CONFIG) else os.path.join(HERE,'repository.json')) as f:config=json.load(f)
            doc=core.validate(json.loads(core.fetch(config['manifest_url'],config['repository'],512*1024,True).decode('utf-8')))
            return config,doc
        deferToThread(work).addCallbacks(self.loaded,self.error)
    def loaded(self,result):
        self.busy=False
        if self.alive:
            self.config,self.doc=result
            self['connection'].setText(self.config['repository'])
            self['status'].setText('%d catalog items  •  Checked when you opened the panel'%len(self.doc['items']))
            self.details()
    def details(self):
        if not self.alive:return
        index=self['list'].getSelectedIndex()
        if not self.rows or index<0 or index>=len(self.rows):return
        if self.level=='categories':
            c=self.rows[index];count=sum(1 for i in self.doc['items'] if i['category']==c)
            self['detail_tag'].setText('EXPLORE  /  '+c.upper());self['detail_title'].setText(CAPTIONS[c])
            self['detail'].setText('%d available items\n\nOpen this collection to review versions, compatibility and installation details.'%count)
            self['detail_hint'].setText('OK to open '+c)
        elif self.level=='items':
            i=self.rows[index];ok=bool(self.device) and core.compatible(i,self.device)
            self['detail_tag'].setText('COMPATIBLE' if ok else 'CHECK COMPATIBILITY')
            self['detail_title'].setText(i.get('title',i['id']))
            self['detail'].setText('Version %s\n\n%s'%(i.get('version','?'),i.get('description','')[:350]))
            self['detail_hint'].setText('OK: Download and install')
        else:
            self['detail_tag'].setText('RECOVERY');self['detail_title'].setText('Restore previous files')
            self['detail'].setText('The selected backup restores the files from that installation. Later changes to those files will be overwritten.')
            self['detail_hint'].setText('OK to review restore')
    def back(self):
        if self.busy:return
        if self.level=='categories':self.close()
        else:self.show_categories();self['status'].setText('Choose a collection to continue.')
    def select(self):
        if self.busy or not self.rows:return
        index=self['list'].getSelectedIndex()
        if index<0 or index>=len(self.rows):return
        if self.level=='categories':
            c=self.rows[index];self.rows=[i for i in self.doc['items'] if i['category']==c];self.level='items'
            self.entries([(i.get('title',i['id']), 'Version '+i.get('version','?')+'  •  '+('Repair package' if i.get('action')=='repair' else 'File package')) for i in self.rows])
            self['section'].setText(c);self['status'].setText('%d items  •  Select one to review'%len(self.rows));self.details()
            if not self.rows:self['detail_title'].setText('Nothing here yet');self['detail'].setText('New packages appear from GitHub the next time you open GT Panel.')
        elif self.level=='backups':
            folder=self.rows[index]
            self.session.openWithCallback(lambda yes:self.rollback(folder,yes),MessageBox,'Restore this backup?\n'+folder+'\nLater changes to these files will be overwritten.',MessageBox.TYPE_YESNO,default=False)
        else:
            i=self.rows[index]
            try:
                device=core.facts()
                if not core.compatible(i,device):raise core.SafetyError('Incompatible item: exact model/image/version/Python match required')
                self.download(i,device,True)
            except Exception as e:self.error(e)
    def download(self,item,device,yes):
        if yes is not True:return
        self.busy=True;self['status'].setText('Downloading and checking package hashes…')
        deferToThread(core.prepare,item,self.config['repository'],device).addCallbacks(lambda p:self.review(item,p),self.error)
    def review(self,item,payload):
        self.busy=False
        if self.alive:
            self.apply(item,payload,True)
    def apply(self,item,payload,yes):
        if yes is not True:return
        self.busy=True;self['status'].setText('Creating backup and installing verified files…')
        deferToThread(core.install,item,payload,True).addCallbacks(self.installed,self.error)
    def installed(self,path):
        self.busy=False
        if self.alive:
            self['status'].setText('Installed successfully  •  Backup saved')
            self.session.open(MessageBox,'Installation completed. Backup:\n'+path+'\nRestart the GUI manually when ready.',MessageBox.TYPE_INFO)
    def backups(self):
        if self.busy:return
        self.level='backups';self.rows=sorted([os.path.join(core.STATE,n) for n in os.listdir(core.STATE) if os.path.isfile(os.path.join(core.STATE,n,'journal.json'))],reverse=True) if os.path.isdir(core.STATE) else []
        self.entries([(os.path.basename(p),'Local file backup  •  Review before restore') for p in self.rows])
        self['section'].setText('Backups & recovery');self['status'].setText('%d saved backups'%len(self.rows));self.details()
    def rollback(self,folder,yes):
        if yes is not True:return
        self.busy=True
        deferToThread(core.restore,folder).addCallbacks(lambda unused:self.restored(),self.error)
    def restored(self):
        self.busy=False
        if self.alive:self['status'].setText('Backup restored');self.session.open(MessageBox,'Files restored. Restart the GUI manually when ready.',MessageBox.TYPE_INFO)

def main(session,**kwargs):session.open(GTPanel)
def Plugins(**kwargs):return [PluginDescriptor(name='GT Panel',description='Downloads, repairs and recovery for GT Enigma2',where=PluginDescriptor.WHERE_PLUGINMENU,icon='icon.png',fnc=main)]
