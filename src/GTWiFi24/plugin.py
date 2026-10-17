"""Enigma2 entry points for a reversible GT Combo Wi-Fi band workaround."""
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from twisted.internet.threads import deferToThread
from . import repair


def sessionstart(reason, session=None, **kwargs):
    if reason == 0 and session is not None:
        deferToThread(repair.perform, automatic=True).addCallbacks(
            lambda text: print('[GTWiFi24] ' + text),
            lambda failure: print('[GTWiFi24] ' + str(failure.value)))


def main(session, **kwargs):
    def selected(choice):
        if choice is None:
            return
        restore = choice[1] == 'restore'
        prompt = ('Restore the previous Wi-Fi band settings?' if restore else
                  'Limit saved wlan0 networks to 2.4 GHz?\n'
                  'Wi-Fi may reconnect. Networks available only on 5 GHz will not connect.\n'
                  'This is a workaround; it does not repair the kernel driver.')

        def confirmed(yes):
            if yes is not True:
                return
            def done(text):
                session.open(MessageBox, text, MessageBox.TYPE_INFO)
            def failed(failure):
                session.open(MessageBox, str(failure.value), MessageBox.TYPE_ERROR)
            deferToThread(repair.perform, restore=restore).addCallbacks(done, failed)
        session.openWithCallback(confirmed, MessageBox, prompt, MessageBox.TYPE_YESNO, default=False)

    session.openWithCallback(selected, ChoiceBox, title='GT Wi-Fi: 2.4 GHz mode',
        list=[('Enable 2.4 GHz mode', 'enable'), ('Restore previous band settings', 'restore')])


def Plugins(**kwargs):
    return [PluginDescriptor(name='GT Wi-Fi: 2.4 GHz mode',
                description='Enable or restore the GT Combo Wi-Fi band workaround',
                where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main),
            PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart)]
