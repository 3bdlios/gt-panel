"""Automatic Linux rc-core scancode reception. No keymap or wakeup changes."""
import array
import fcntl
import glob
import hashlib
import json
import os
import struct
import tempfile
import time
from .inputs import identity

STATE = '/etc/enigma2/addremote/protocol-session.json'
PROTOCOL_NAMES = {2: 'RC5', 3: 'RC5X', 4: 'RC5-SZ', 5: 'JVC', 6: 'Sony12',
                  7: 'Sony15', 8: 'Sony20', 9: 'NEC', 10: 'NECX', 11: 'NEC32',
                  12: 'Sanyo', 15: 'RC6', 16: 'RC6', 17: 'RC6', 18: 'RC6',
                  19: 'RC6-MCE', 20: 'Sharp', 21: 'XMP', 23: 'iMON'}


def protocols(path):
    with open(path, encoding='ascii') as f:
        words = f.read().split()
    return {w.strip('[]') for w in words}, {w[1:-1] for w in words if w.startswith('[') and w.endswith(']')}


def write_state(data):
    directory = os.path.dirname(STATE)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.protocols-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def safe_protocol_path(path):
    # Never accept an arbitrary write destination from the recovery file.
    return path in glob.glob('/sys/class/rc/rc[0-9]*/protocols')


def recover_protocols():
    try:
        with open(STATE) as f:
            entries = json.load(f)
    except FileNotFoundError:
        return
    failed = []
    for item in entries:
        path, added = item['path'], item['added']
        if not safe_protocol_path(path):
            if os.path.exists(path):
                failed.append(item)
            continue
        try:
            supported, enabled = protocols(path)
            for name in added:
                if name not in supported or not name.replace('-', '').replace('_', '').isalnum():
                    continue
                if name in enabled:
                    with open(path, 'w') as f:
                        f.write('-' + name)
            _, after = protocols(path)
            if set(added) & after:
                failed.append(item)
        except OSError:
            failed.append(item)
    write_state(failed)
    if failed:
        raise OSError('Could not restore temporary IR protocols; see protocol-session.json')


def parse_scancodes(data, receiver):
    if len(data) % 24:
        raise ValueError('Incomplete LIRC scancode record')
    events, native, last_protocol = [], 0, None
    for timestamp, flags, proto, keycode, code in struct.iter_unpack('=QHHIQ', data):
        last_protocol = PROTOCOL_NAMES.get(proto, 'Protocol %d' % proto)
        # Native mapped buttons already reach Enigma2: do not inject them twice.
        if keycode:
            native += 1
            continue
        if proto:
            events.append(('ir:%s:%d:%x' % (receiver, proto, code), 2 if flags & 2 else 1))
    return events, native, last_protocol


def raw_token(receiver, durations):
    return 'raw:%s:%s' % (receiver, ','.join(str(round(v / 100) * 100) for v in durations))


def raw_match(first, second):
    if not first.startswith('raw:') or not second.startswith('raw:'):
        return first == second
    try:
        _, rid1, a = first.split(':', 2)
        _, rid2, b = second.split(':', 2)
        a, b = [int(x) for x in a.split(',')], [int(x) for x in b.split(',')]
        return (rid1 == rid2 and 12 <= len(a) == len(b) <= 512 and
                all(abs(x-y) <= max(150, min(x,y) * 0.25) for x,y in zip(a,b)))
    except (ValueError, TypeError):
        return False


class RawFrames:
    def __init__(self):
        self.repeats = 0
        self.frame = []
        self.last = 0

    def finish(self):
        frame, self.frame = self.frame, []
        # NEC short hold frame: leader pulse, repeat gap, trailing pulse.
        if len(frame) == 3 and 8000 <= frame[0] <= 10000 and 1800 <= frame[1] <= 2800 and 350 <= frame[2] <= 850:
            self.repeats += 1
        if 12 <= len(frame) <= 512:
            return [frame]
        return []

    def feed(self, data):
        frames = []
        if len(data) % 4:
            raise ValueError('Incomplete raw IR record')
        for (value,) in struct.iter_unpack('=I', data):
            kind, duration = value >> 24, value & 0xffffff
            if kind == 4:  # overflow: incomplete signal must never be learned
                self.frame = []
            elif kind == 3 or (kind == 0 and duration > 12000):
                frames.extend(self.finish())
            elif kind in (0, 1) and duration > 0:
                if kind == 1 or self.frame:
                    # Positive pulse / negative space retains polarity in the frame.
                    expected_pulse = len(self.frame) % 2 == 0
                    if (kind == 1) != expected_pulse:
                        self.frame = []
                        if kind == 0:
                            continue
                    self.frame.append(duration)
                    self.last = time.monotonic()
                    if len(self.frame) > 512:
                        self.frame = []
        return frames

    def flush_idle(self):
        return self.finish() if self.frame and time.monotonic() - self.last > 0.10 else []


class AutoReader:
    def __init__(self, source=None, mappings=None):
        self.devices = []
        self.notes = []
        self.native = 0
        self.last_protocol = None
        self.mappings = mappings or {}
        self.native_until = {}
        self.last_raw = {}
        recover_protocols()  # recover a previous diagnostic version, if necessary
        try:
            for rc in sorted(glob.glob('/sys/class/rc/rc[0-9]*')):
                lircs = glob.glob(rc + '/lirc[0-9]*')
                if len(lircs) != 1:
                    continue
                path = '/dev/' + os.path.basename(lircs[0])
                rid = hashlib.sha256(os.path.realpath(rc).encode()).hexdigest()[:16]
                opened = False
                # Independent per-fd raw reception requires no protocol changes.
                for kind, mode in (('native', 8), ('raw', 4)):
                    fd = None
                    try:
                        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                        fcntl.ioctl(fd, 0x40046912, array.array('I', [mode]))
                        self.devices.append((kind, fd, rid, RawFrames() if kind == 'raw' else None))
                        opened = opened or kind == 'raw'
                    except OSError as e:
                        if fd is not None:
                            os.close(fd)
                        self.notes.append('%s %s: %s' % (path, kind, e))
                if not opened:
                    self.notes.append(path + ': raw IR unsupported; decoded scancodes only')
            try:
                import evdev
                for path in evdev.list_devices():
                    d = evdev.InputDevice(path)
                    if d.info.bustype == 5 and 1 in d.capabilities():
                        stable = json.dumps(identity(d), sort_keys=True)
                        rid = hashlib.sha256(stable.encode()).hexdigest()[:16]
                        self.devices.append(('bt', d, rid, None))
                    else:
                        d.close()
            except ImportError:
                self.notes.append('Bluetooth HID unavailable')
            if not self.devices:
                raise OSError('No supported IR receiver. ' + '; '.join(self.notes))
        except Exception:
            self.close()
            raise

    def poll(self):
        events, frames, repeats = [], [], []
        now = time.monotonic()
        raw_receivers = {rid for kind, d, rid, parser in self.devices if kind == 'raw'}
        # Native records are checked before raw frames to avoid original IR duplicates.
        for kind, d, rid, parser in self.devices:
            try:
                if kind == 'native':
                    data = os.read(d, 24 * 128)
                    if not data:
                        raise OSError('IR receiver disconnected')
                    decoded, native, proto = parse_scancodes(data, rid)
                    self.native += native
                    if native:
                        self.native_until[rid] = now + 0.25
                    if rid not in raw_receivers:
                        events.extend(decoded)
                        self.last_protocol = proto or self.last_protocol
                elif kind == 'raw':
                    try:
                        data = os.read(d, 4096)
                        if not data:
                            raise OSError('IR receiver disconnected')
                        frames.extend((rid, frame) for frame in parser.feed(data))
                    except BlockingIOError:
                        pass
                    frames.extend((rid, frame) for frame in parser.flush_idle())
                    if parser.repeats:
                        repeats.append((rid, parser.repeats))
                        parser.repeats = 0
                else:
                    for e in d.read():
                        if e.type == 1 and e.value in (0, 1, 2):
                            events.append(('bt:%s:%d' % (rid, e.code), e.value))
            except BlockingIOError:
                pass
        for rid, frame in frames:
            if self.native_until.get(rid, 0) > now:
                continue
            token = raw_token(rid, frame)
            # Use the saved template when timings vary slightly on the next press.
            token = next((saved for saved in self.mappings if raw_match(saved, token)), token)
            previous = self.last_raw.get(rid)
            holding = previous and now - previous[1] <= 0.22 and raw_match(previous[0], token)
            if holding:
                token = previous[0]
            self.last_raw[rid] = (token, now)
            events.append((token, 2 if holding else 1))
            self.last_protocol = 'IR waveform'
        for rid, count in repeats:
            previous = self.last_raw.get(rid)
            if previous and now - previous[1] <= 0.28 and self.native_until.get(rid, 0) <= now:
                self.last_raw[rid] = (previous[0], now)
                events.append((previous[0], 2))
        return events

    def close(self):
        errors = []
        for kind, d, rid, parser in self.devices:
            try:
                d.close() if kind == 'bt' else os.close(d)
            except OSError as e:
                errors.append(str(e))
        self.devices = []
        if errors:
            raise OSError('; '.join(errors))
