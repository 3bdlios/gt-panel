"""Local, reversible 2.4 GHz workaround. No credentials leave the receiver."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

CONFIG = Path('/etc/wpa_supplicant.wlan0.conf')
STATE = Path('/var/lib/gt-wifi24')
FREQUENCIES = ' '.join(str(n) for n in range(2412, 2473, 5))
BLOCK = re.compile(r'(?m)^\s*network\s*=\s*\{[^\S\n]*\n.*?^\s*\}', re.S)
FIELD = re.compile(r'(?m)^[ \t]*(bssid|scan_freq|freq_list)[ \t]*=.*(?:\n|$)')


def rewrite(text, originals, restore=False):
    """Change only band/BSSID directives; preserve credentials and other options."""
    seen = {}
    count = 0

    def block_replace(match):
        nonlocal count
        block = match.group()
        ssid = re.search(r'(?m)^[ \t]*ssid[ \t]*=(.*)$', block)
        if not ssid:
            return block
        digest = hashlib.sha256(ssid.group(1).strip().encode()).hexdigest()
        index = seen.get(digest, 0)
        seen[digest] = index + 1
        key = digest + ':' + str(index)
        fields = [m.group().strip() for m in FIELD.finditer(block)]
        if restore:
            if key not in originals:
                return block
            # Do not overwrite later user edits to these same directives.
            expected = ['freq_list=' + FREQUENCIES, 'scan_freq=' + FREQUENCIES]
            if fields != expected:
                raise ValueError('Wi-Fi band settings changed since repair; restore skipped safely.')
            replacement = originals[key]
        else:
            originals.setdefault(key, fields)
            replacement = ['freq_list=' + FREQUENCIES, 'scan_freq=' + FREQUENCIES]
        cleaned = FIELD.sub('', block)
        end = cleaned.rfind('}')
        count += 1
        return cleaned[:end] + ''.join('\t' + line + '\n' for line in replacement) + cleaned[end:]

    return BLOCK.sub(block_replace, text), count


def atomic(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.gtwifi24-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def supported():
    try:
        return Path('/proc/device-tree/model').read_text().strip('\x00 \t\r\n') == 'GTMedia GT Combo'
    except OSError:
        return False


def perform(restore=False, automatic=False):
    if not supported():
        raise ValueError('This repair is for GTMedia GT Combo only.')
    if CONFIG.is_symlink() or STATE.is_symlink():
        raise ValueError('Unexpected symlink; no changes made.')
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = STATE / 'operation.lock'
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        statefile = STATE / 'state.json'
        state = json.loads(statefile.read_text()) if statefile.exists() else {'enabled': True, 'originals': {}}
        if automatic and not state.get('enabled', True):
            return '2.4 GHz mode is disabled.'
        if not CONFIG.is_file():
            if restore:
                state['enabled'] = False
                atomic(statefile, json.dumps(state, indent=2))
            return 'No saved wlan0 network yet. Connect to a saved network, then enable this repair.'
        text = CONFIG.read_text()
        originals = dict(state.get('originals', {}))
        new, count = rewrite(text, originals, restore)
        if not count:
            if restore:
                atomic(statefile, json.dumps({'enabled': False, 'originals': originals}, indent=2))
            return 'No matching saved networks; configuration unchanged.'
        changed = new != text
        if changed:
            backup = STATE / 'original.conf'
            if not backup.exists():
                atomic(backup, text)
            # Persist the rollback fields before modifying the live configuration.
            atomic(statefile, json.dumps({'enabled': not restore, 'originals': originals}, indent=2))
            atomic(CONFIG, new)
        else:
            atomic(statefile, json.dumps({'enabled': not restore, 'originals': originals}, indent=2))
        # Apply saved restrictions to the current supplicant too. This does not
        # restart Enigma2, change Ethernet, touch DHCP or unload kernel modules.
        mode = 'Previous Wi-Fi band settings restored.' if restore else '2.4 GHz mode enabled for saved wlan0 networks.'
        if not changed:
            return mode + ' Configuration already matches; connection left running.'
        result = subprocess.run(['/usr/sbin/wpa_cli', '-i', 'wlan0', 'reconfigure'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=6)
        live = result.returncode == 0 and result.stdout.strip().endswith('OK')
        return mode + (' Live settings reloaded.' if live else ' Settings saved; reconnect Wi-Fi to apply.')
    finally:
        lock.unlink()
