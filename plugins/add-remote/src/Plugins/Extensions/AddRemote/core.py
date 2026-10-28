"""Add Remote 0.1 — Copyright فارس. No receiver configuration changes."""
import json
import os
import tempfile
import uuid

ROWS = [
 [('⏻','KEY_POWER'), ('✉','__PROFILES__'), ('T','__RENAME__'), ('⛶','__HELP__')],
 [('1','KEY_1'),('2','KEY_2'),('3','KEY_3')],
 [('4','KEY_4'),('5','KEY_5'),('6','KEY_6')],
 [('7','KEY_7'),('8','KEY_8'),('9','KEY_9')],
 [('<','KEY_PREVIOUSSONG'),('0','KEY_0'),('>','KEY_NEXTSONG')],
 [('', 'KEY_RED'),('', 'KEY_GREEN'),('', 'KEY_YELLOW'),('', 'KEY_BLUE')],
 [('Menu','KEY_MENU'),('▲','KEY_UP'),('Exit','KEY_EXIT')],
 [('◀','KEY_LEFT'),('OK','KEY_OK'),('▶','KEY_RIGHT')],
 [('Info','KEY_INFO'),('▼','KEY_DOWN'),('EPG','KEY_EPG')],
 [('Vol+','KEY_VOLUMEUP'),('Mute','KEY_MUTE'),('CH+','KEY_CHANNELUP')],
 [('Vol−','KEY_VOLUMEDOWN'),('History','KEY_LIST'),('CH−','KEY_CHANNELDOWN')],
 [('⏪','KEY_REWIND'),('▶','KEY_PLAY'),('Ⅱ','KEY_PAUSE'),('⏩','KEY_FASTFORWARD')],
 [('⏮','KEY_PREVIOUS'),('●','KEY_RECORD'),('■','KEY_STOP'),('⏭','KEY_NEXT')],
 [('Text','KEY_TEXT'),('Audio','KEY_AUDIO'),('Sub','KEY_SUBTITLE'),('Video','KEY_VIDEO')],
 [('PVR','KEY_PVR'),('TV','KEY_TV'),('Radio','KEY_RADIO'),('Help','KEY_HELP')],
 [('Setup','KEY_SETUP'),('Portal','KEY_WWW'),('Sleep','KEY_SLEEP'),('Timer','KEY_TIME')],
 [('F1','KEY_F1'),('F2','KEY_F2'),('Fav','KEY_FAVORITES'),('PIP','KEY_SCREEN')],
 [('Back','KEY_BACK'),('Opt','KEY_OPTION'),('Context','KEY_CONTEXT_MENU'),('Aspect','KEY_ZOOM')]]
TARGETS = {key for row in ROWS for _, key in row if not key.startswith('__')}
# Preserve values used by previously saved profiles.
TARGETS.update({'KEY_PREVIOUS', 'KEY_NEXT'})

def bind(profile, token, target):
    if target not in TARGETS or not isinstance(token, str) or not token:
        raise ValueError("Invalid mapping")
    profile["mappings"] = {k: v for k, v in profile["mappings"].items() if v != target}
    profile["mappings"][token] = target

def new_profile(name):
    name = name.strip()
    if not name or len(name) > 64:
        raise ValueError("Name must contain 1–64 characters")
    return {"id": uuid.uuid4().hex, "name": name, "source": None, "mappings": {}}

class Store:
    def __init__(self, path="/etc/enigma2/addremote/profiles.json"):
        self.path = path
    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"version": 1, "active": None, "profiles": []}
        if data.get("version") != 1 or not isinstance(data.get("profiles"), list):
            raise ValueError("Unsupported profile file")
        ids = set()
        for p in data["profiles"]:
            if not isinstance(p.get("id"), str) or p["id"] in ids:
                raise ValueError("Invalid profile ID")
            ids.add(p["id"])
            if not isinstance(p.get("name"), str) or not isinstance(p.get("mappings"), dict):
                raise ValueError("Invalid profile")
            if any(not isinstance(k, str) or v not in TARGETS for k, v in p["mappings"].items()):
                raise ValueError("Invalid mappings")
            s = p.get("source")
            if s is not None and (not isinstance(s, dict) or s.get("kind") not in ("evdev", "lirc", "auto")):
                raise ValueError("Invalid source")
        if data.get("active") is not None and data["active"] not in ids:
            raise ValueError("Unknown active profile")
        return data
    def save(self, data):
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".profiles-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def activate_for_save(data, profile):
    """Saving a learned profile also makes it the one used on session startup."""
    if profile not in data['profiles']:
        raise ValueError('Profile does not belong to this store')
    if profile.get('source') and profile.get('mappings'):
        data['active'] = profile['id']
        return True
    return False
