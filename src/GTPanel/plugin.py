from __future__ import absolute_import
import os, json
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.MenuList import MenuList
from Components.Label import Label
from Components.ActionMap import ActionMap
from Plugins.Plugin import PluginDescriptor
from twisted.internet.threads import deferToThread
from . import core

CONFIG = '/etc/gt-panel/repository.json'
class GTPanel(Screen):
    skin = '''<screen name="GTPanel" position="center,center" size="1000,600" title="GT Panel"><widget name="status" position="30,20" size="940,95" font="Regular;22" /><widget name="list" position="30,125" size="940,380" scrollbarMode="showOnDemand" /><widget name="help" position="30,530" size="940,50" font="Regular;20" /></screen>'''
    def __init__(self, session):
        Screen.__init__(self,session)
        self['status'] = Label('GT Panel | Loading GitHub catalog...')
        self['list'] = MenuList(list(core.CATEGORIES))
        self['help'] = Label('OK: Open / Review    RED: Back    BLUE: Backups')
        self['actions'] = ActionMap(['OkCancelActions','ColorActions'], {'ok':self.select,'cancel':self.back,'red':self.back,'blue':self.backups},-1)
        self.doc={'items':[]}; self.level='categories'; self.rows=[]; self.busy=True; self.alive=True
        self.onClose.append(self.closed)
        self.onFirstExecBegin.append(self.load)
    def closed(self): self.alive=False
    def error(self, failure):
        self.busy=False
        if self.alive:
            self['status'].setText('Operation stopped. No automatic retry.')
            self.session.open(MessageBox,str(getattr(failure,'value',failure)),MessageBox.TYPE_ERROR)
    def load(self):
        def work():
            with open(CONFIG if os.path.isfile(CONFIG) else os.path.join(os.path.dirname(__file__), 'repository.json')) as f: config=json.load(f)
            # Exactly one catalog request per opening. No timer, startup hook or refresh loop.
            doc=core.validate(json.loads(core.fetch(config['manifest_url'],config['repository'],512*1024,True).decode('utf-8')))
            return config,doc
        deferToThread(work).addCallbacks(self.loaded,self.error)
    def loaded(self,result):
        self.busy=False
        if self.alive:
            self.config,self.doc=result
            self['status'].setText('GT Panel | Select a category')
    def back(self):
        if self.busy: return
        if self.level=='categories': self.close()
        else:
            self.level='categories'; self['list'].setList(list(core.CATEGORIES))
            self['status'].setText('GT Panel | Select a category')
    def select(self):
        if self.busy: return
        if self.level=='categories':
            category=self['list'].getCurrent()
            self.rows=[i for i in self.doc['items'] if i['category']==category]
            self.level='items'; self['list'].setList([i.get('title',i['id'])+' | '+i.get('version','?') for i in self.rows])
            self['status'].setText(category + ' | ' + str(len(self.rows)) + ' items')
        elif self.level=='backups':
            if self.rows:
                folder=self.rows[self['list'].getSelectedIndex()]
                self.session.openWithCallback(lambda yes:self.rollback(folder,yes),MessageBox,'Restore files from this backup?\n'+folder+'\nLater changes to these files will be overwritten.',MessageBox.TYPE_YESNO,default=False)
        elif self.rows:
            item=self.rows[self['list'].getSelectedIndex()]
            try:
                device=core.facts()
                if not core.compatible(item,device): raise core.SafetyError('Incompatible item: exact model/image/version/Python match required')
                text='%s\n%s\nVersion: %s\nFiles:\n%s\nDownload and verify for review? No installation yet.' % (item.get('title',item['id']),item.get('description',''),item.get('version','?'),'\n'.join(item['files']))
                self.session.openWithCallback(lambda yes:self.download(item,device,yes),MessageBox,text,MessageBox.TYPE_YESNO,default=False)
            except Exception as e: self.error(e)
    def download(self,item,device,yes):
        if not yes: return
        self.busy=True; self['status'].setText('Downloading and verifying...')
        deferToThread(core.prepare,item,self.config['repository'],device).addCallbacks(lambda payload:self.review(item,payload),self.error)
    def review(self,item,payload):
        self.busy=False
        if self.alive:
            text='Verified SHA256 and file inventory.\nInstall %s?\n%s\nExisting files will be backed up. Plugin code may execute after a manual GUI restart.\nNo automatic reboot.' % (item.get('title',item['id']),'\n'.join(sorted(payload)))
            self.session.openWithCallback(lambda yes:self.apply(item,payload,yes),MessageBox,text,MessageBox.TYPE_YESNO,default=False)
    def apply(self,item,payload,yes):
        if yes is not True: return
        self.busy=True
        deferToThread(core.install,item,payload,True).addCallbacks(self.installed,self.error)
    def installed(self,path):
        self.busy=False
        if self.alive: self.session.open(MessageBox,'Installation completed. Backup:\n'+path+'\nRestart GUI manually when ready.',MessageBox.TYPE_INFO)
    def backups(self):
        if self.busy: return
        self.level='backups'
        self.rows=sorted([os.path.join(core.STATE,n) for n in os.listdir(core.STATE) if os.path.isfile(os.path.join(core.STATE,n,'journal.json'))],reverse=True) if os.path.isdir(core.STATE) else []
        self['list'].setList([os.path.basename(p) for p in self.rows])
        self['status'].setText('Backups | OK to review restore')
    def rollback(self,folder,yes):
        if yes is not True: return
        self.busy=True
        deferToThread(core.restore,folder).addCallbacks(lambda unused:self.restored(),self.error)
    def restored(self):
        self.busy=False
        if self.alive: self.session.open(MessageBox,'Backup restored. Restart GUI manually when ready.',MessageBox.TYPE_INFO)

def main(session,**kwargs): session.open(GTPanel)
def Plugins(**kwargs):
    return [PluginDescriptor(name='GT Panel',description='GT Enigma2 fixes, plugins, skins and updates',where=PluginDescriptor.WHERE_PLUGINMENU,fnc=main)]
