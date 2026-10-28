# Copyright (c) 2026 فارس. See LICENSE.
import time
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from enigma import eTimer, eActionMap, getDesktop
from keyids import KEYIDS
from .keyflow import KeyFlow
from .layout import build_skin, buttons, COLORS, ACCENT, TEXT, SYMBOLS
from .core import Store, ROWS, bind, new_profile, activate_for_save
from .inputs import Reader, discover
from .autoir import AutoReader, recover_protocols, raw_match


def timer(callback):
    t = eTimer()
    if hasattr(t, 'callback'):
        t.callback.append(callback)
    else:
        t.connection = t.timeout.connect(callback)
    return t


class Runtime:
    def __init__(self):
        self.reader = None
        self.profile = None
        self.error = ''
        self.paused = False
        self.timer = timer(self.tick)
        self.flow = KeyFlow(lambda code, flag: eActionMap.getInstance().keyPressed('AddRemote', code, flag))
        self.resume_after = 0

    def stop(self):
        self.timer.stop()
        self.flow.release()
        if self.reader:
            try:
                self.reader.close()
            except Exception as e:
                self.error = str(e)
        self.reader = None

    def reload(self):
        self.stop()
        try:
            recover_protocols()
            data = Store().load()
            self.profile = next((p for p in data['profiles'] if p['id'] == data['active']), None)
            if self.profile:
                if not callable(getattr(eActionMap.getInstance(), 'keyPressed', None)):
                    raise RuntimeError('This image does not expose keyPressed')
                self.reader = AutoReader(mappings=self.profile['mappings']) if self.profile['source']['kind'] == 'auto' else Reader(self.profile['source'])
                self.timer.start(40, False)
            self.error = ''
        except Exception as e:
            self.error = str(e)
            self.stop()

    def pause_capture(self):
        self.paused = True
        self.stop()

    def resume_capture(self):
        self.paused = False
        self.resume_after = time.monotonic() + 0.4
        self.reload()

    def tick(self):
        try:
            events = self.reader.poll()
            now = time.monotonic()
            if self.paused or now < self.resume_after:
                self.flow.release()
                return
            self.flow.expire(now)
            for token, value in events:
                if self.paused or self.reader is None:
                    break
                target = self.profile['mappings'].get(token)
                code = KEYIDS.get(target)
                if code is not None:
                    self.flow.event(token, code, value, now)
        except Exception as e:
            self.error = str(e)
            self.stop()


runtime = None


class AddRemote(Screen):
    def __init__(self, session):
        desktop = getDesktop(0).size()
        self.skin = build_skin(desktop.width(), desktop.height())
        self.button_colors = {(b['r'],b['c']): b['color'] for b in buttons()}
        Screen.__init__(self, session)
        self['status'] = Label('')
        self['help'] = Label('Arrows: select    OK: capture    Menu: options / About    Exit: back')
        for r, row in enumerate(ROWS):
            for c, (label, key) in enumerate(row):
                if key in SYMBOLS:
                    self['i%d_%d' % (r,c)] = Pixmap()
                self['b%d_%d' % (r, c)] = Label(label)
                self['m%d_%d' % (r, c)] = Label('')
        self.r = self.c = 0
        self.reader = None
        self.deadline = 0
        self.arm = 0
        self.message = ''
        self.broken = False
        try:
            self.data = Store().load()
        except Exception as e:
            self.data = {'version': 1, 'active': None, 'profiles': []}
            self.message = 'Profile file error; writes disabled: ' + str(e)
            self.broken = True
        if not self.data['profiles']:
            self.data['profiles'].append(new_profile('Remote 1'))
        self.profile = next((p for p in self.data['profiles'] if p['id'] == self.data['active']), self.data['profiles'][0])
        self['actions'] = ActionMap(['OkCancelActions', 'DirectionActions', 'ColorActions', 'MenuActions'], {
            'up': lambda: self.move(-1, 0), 'down': lambda: self.move(1, 0),
            'left': lambda: self.move(0, -1), 'right': lambda: self.move(0, 1),
            'ok': self.capture, 'cancel': self.cancel, 'red': self.profiles,
            'green': self.save, 'yellow': self.sources, 'blue': self.restart,
            'menu': self.menu}, -2)
        self.poller = timer(self.poll)
        self.onClose.append(self.cleanup)
        self.onLayoutFinish.append(self.refresh)

    def refresh(self):
        for r, row in enumerate(ROWS):
            for c, (_, target) in enumerate(row):
                w = self['b%d_%d' % (r, c)].instance
                if w:
                    from skin import parseColor
                    focused = (r, c) == (self.r, self.c)
                    w.setBackgroundColor(parseColor('#266b7a' if focused else self.button_colors[(r, c)]))
                    w.setForegroundColor(parseColor('#ffffff' if focused else '#ff7a89' if target == 'KEY_POWER' else ACCENT if target == 'KEY_OK' else TEXT))
                    label = ROWS[r][c][0]
                    self['b%d_%d' % (r, c)].setText('' if target in SYMBOLS else label)
                    self['m%d_%d' % (r, c)].setText('✓' if target in self.profile['mappings'].values() else '•' if focused else '')
        s = self.profile.get('source')
        selected = ROWS[self.r][self.c][1]
        mapped = next((k for k, v in self.profile['mappings'].items() if v == selected), 'unassigned')
        if mapped.startswith('raw:'):
            mapped = 'IR waveform learned ✓'
        active_state = 'ACTIVE ✓' if self.data['active'] == self.profile['id'] else 'INACTIVE'
        selected_name = ROWS[self.r][self.c][0] or selected.replace('KEY_', '')
        toolbar = selected.startswith('__')
        self['status'].setText('%s\n%s\n\n%d buttons learned\n\n%s\n%s\n\n%s\n\n%s' % (self.profile['name'], active_state, len(self.profile['mappings']), selected_name, 'Toolbar action' if toolbar else mapped, self.message, ('Runtime: ' + runtime.error) if runtime and runtime.error else 'Choose a button, press OK,\nthen press the new remote\nbutton twice.'))


    def move(self, dr, dc):
        if self.reader:
            return
        self.r = (self.r + dr) % len(ROWS)
        self.c = (self.c + dc) % len(ROWS[self.r])
        self.refresh()

    def info(self, text):
        self.session.open(MessageBox, text, type=MessageBox.TYPE_INFO)

    def save(self, activate=True):
        if self.reader:
            return False
        if self.broken:
            self.info('Repair or restore the invalid profile file first; no data overwritten.')
            return False
        try:
            if activate:
                activate_for_save(self.data, self.profile)
            Store().save(self.data)
            if runtime:
                runtime.reload()
            self.message = 'تم الحفظ والتفعيل ✓' if self.data['active'] == self.profile['id'] else 'تم الحفظ — الملف غير مفعّل'
            self.refresh()
            return True
        except Exception as e:
            self.info('Save failed: ' + str(e))
            return False

    def sources(self):
        if self.reader:
            return
        self.info('الاستقبال تلقائي؛ لا تحتاج اختيار مصدر أو بروتوكول.\nحدد زرًا في الرسم واضغط OK، ثم اضغط زر الريموت الجديد.\nيتم استقبال بصمة نبضات IR تلقائيًا دون تغيير بروتوكولات الجهاز. اضغط الزر مرتين لتأكيد البصمة.\nأزرار الريموت الأصلي المعرفة بالنظام لا يعاد حقنها لتجنب التكرار.\nلا يمكن ضمان استقبال بروتوكول لا يدعمه العتاد أو التعريف.')

    def capture(self):
        if self.reader:
            return
        target = ROWS[self.r][self.c][1]
        if target.startswith('__'):
            if target == '__PROFILES__':
                self.profiles()
            elif target == '__RENAME__':
                self.rename_profile()
            else:
                self.sources()
            return
        if target not in KEYIDS:
            self.info('This Enigma2 image has no key ID for ' + target)
            return
        try:
            if runtime:
                runtime.pause_capture()
            self.reader = AutoReader(mappings=self.profile['mappings'])
            self.candidate = None
            self.candidate_time = 0
            self.profile['source'] = {'kind': 'auto', 'label': 'Automatic IR detection'}
            self.reader.poll()  # drain selection input
            self.arm = time.monotonic() + 0.8
            self.deadline = self.arm + 30
            self.message = 'حرر OK ثم اضغط زر الريموت الجديد مرتين\nجارٍ استقبال الإشارة تلقائيًا — 30 ثانية\nExit: إلغاء'
            self.poller.start(40, False)
        except Exception as e:
            self.message = 'Capture unavailable: ' + str(e)
            self.end_capture()
        self.refresh()

    def poll(self):
        try:
            events = self.reader.poll()
            now = time.monotonic()
            if now >= self.deadline:
                if self.reader.native:
                    self.message = 'تم استقبال ريموت يعرفه النظام بالفعل.\nلم نكرر ربطه للحفاظ على عمل الريموت الأصلي.'
                else:
                    self.message = 'لم يصل رمز IR قابل للفك خلال المهلة.\nقد يكون البروتوكول غير مدعوم. لم يُحفظ ربط.'
                self.end_capture()
            elif now >= self.arm:
                for token, value in events:
                    if value == 1:
                        if token.startswith('raw:'):
                            if self.candidate is None or not raw_match(self.candidate, token):
                                self.candidate = token
                                self.candidate_time = now
                                self.message = 'وصلت إشارة IR — اضغط نفس الزر مرة ثانية للتأكيد'
                                continue
                            if now - self.candidate_time < 0.18:
                                continue
                            token = self.candidate
                        target = ROWS[self.r][self.c][1]
                        if token in self.profile['mappings'] and self.profile['mappings'][token] != target:
                            self.message = 'Button already assigned. Choose another button.'
                        else:
                            bind(self.profile, token, target)
                            protocol = self.reader.last_protocol or 'Bluetooth HID'
                            self.message = '✓ تم استقبال الإشارة وربط الزر بنجاح\n%s | %s\nGreen: save profile' % (protocol, target)
                            self.session.open(MessageBox, '✓ تم استقبال الإشارة وربط الزر بنجاح\n%s\n%s\nاحفظ الملف بالزر الأخضر.' % (ROWS[self.r][self.c][0], 'IR waveform' if token.startswith('raw:') else token), type=MessageBox.TYPE_INFO, timeout=4)
                        self.end_capture()
                        break
        except Exception as e:
            self.message = 'Receiver disconnected/error: ' + str(e)
            self.end_capture()
        self.refresh()

    def end_capture(self):
        was_capturing = self.reader is not None or (runtime and runtime.paused)
        self.poller.stop()
        if self.reader:
            try:
                self.reader.close()
            except Exception as e:
                self.message += '\nProtocol restore error: ' + str(e)
        self.reader = None
        if was_capturing and runtime:
            runtime.resume_capture()

    def cancel(self):
        if self.reader:
            self.end_capture()
            self.message = 'Capture cancelled.'
            self.refresh()
        else:
            self.session.openWithCallback(lambda yes: self.close() if yes else None, MessageBox, 'Close? Unsaved changes will be discarded.', type=MessageBox.TYPE_YESNO, default=False)

    def profiles(self):
        if self.reader:
            return
        choices = [(p['name'], p) for p in self.data['profiles']] + [('New profile', None), ('Delete current profile', 'delete')]
        def chosen(choice):
            if not choice:
                return
            if choice[1] == 'delete':
                self.session.openWithCallback(self.delete, MessageBox, 'Delete this profile?', type=MessageBox.TYPE_YESNO, default=False)
            elif choice[1] is None:
                self.session.openWithCallback(self.create, VirtualKeyBoard, title='Profile name', text='')
            else:
                self.profile = choice[1]
                self.refresh()
        self.session.openWithCallback(chosen, ChoiceBox, title='Profiles', list=choices)

    def create(self, name):
        if name:
            try:
                self.profile = new_profile(name)
                self.data['profiles'].append(self.profile)
                self.refresh()
            except ValueError as e:
                self.info(str(e))

    def delete(self, yes):
        if yes:
            if self.data['active'] == self.profile['id']:
                self.data['active'] = None
            self.data['profiles'].remove(self.profile)
            if not self.data['profiles']:
                self.data['profiles'].append(new_profile('Remote 1'))
            self.profile = self.data['profiles'][0]
            self.save(activate=False)

    def menu(self):
        if self.reader:
            return
        def chosen(choice):
            if not choice:
                return
            action = choice[1]
            if action == 'about':
                self.info('Add Remote 0.3.1\n\nFares3nzi\nhttps://t.me/fares3nzi\n\nAutomatic IR waveform capture.\nFree software — MIT license.\nHardware compatibility varies.')
            elif action == 'disable':
                self.data['active'] = None
                self.save(activate=False)
            elif action == 'rename':
                self.rename_profile()
            else:
                if not self.profile['mappings'] or not self.profile['source']:
                    self.info('Capture at least one button first; receiver detection is automatic.')
                    return
                self.session.openWithCallback(self.activate, MessageBox, 'Activate this profile?\nIR waveform matching runs only while this profile is active; receiver protocols are not changed. Native IR buttons already handled by Enigma2 are ignored. Bluetooth HID may duplicate native actions; verify first.', type=MessageBox.TYPE_YESNO, default=False)
        self.session.openWithCallback(chosen, ChoiceBox, title='Add Remote', list=[('Activate current profile', 'activate'), ('Disable all mappings', 'disable'), ('Rename profile', 'rename'), ('About', 'about')])

    def rename_profile(self):
        def renamed(name):
            if name and name.strip() and len(name.strip()) <= 64:
                self.profile['name'] = name.strip()
                self.refresh()
        self.session.openWithCallback(renamed, VirtualKeyBoard, title='Rename profile', text=self.profile['name'])

    def activate(self, yes):
        if yes:
            self.data['active'] = self.profile['id']
            self.save()

    def restart(self):
        if self.reader:
            return
        def confirmed(yes):
            if yes and self.save():
                from Screens.Standby import TryQuitMainloop
                self.session.open(TryQuitMainloop, 3)
        self.session.openWithCallback(confirmed, MessageBox, 'Save profiles and restart the Enigma2 user interface? Playback will be interrupted.', type=MessageBox.TYPE_YESNO, default=False)

    def cleanup(self):
        self.end_capture()
        if runtime:
            runtime.paused = False
            runtime.reload()


def main(session, **kwargs):
    session.open(AddRemote)


def sessionstart(reason, session=None, **kwargs):
    global runtime
    if reason == 0 and session is not None:
        if runtime:
            runtime.stop()
        runtime = Runtime()
        runtime.reload()
    elif runtime:
        runtime.stop()


def Plugins(**kwargs):
    return [PluginDescriptor(name='Add Remote', description='Automatic IR remote profiles', icon='plugin.png', where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main), PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart)]
