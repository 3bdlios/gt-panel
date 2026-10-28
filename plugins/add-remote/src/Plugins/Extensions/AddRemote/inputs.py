"""Read-only, non-exclusive decoded input adapters; never call grab or irrecord."""
import glob
import os
import socket
import stat

def identity(d):
    return {"name": d.name, "phys": d.phys, "uniq": d.uniq,
            "bus": d.info.bustype, "vendor": d.info.vendor, "product": d.info.product}

def discover():
    sources, notes = [], []
    try:
        import evdev
        for path in sorted(evdev.list_devices()):
            d = None
            try:
                d = evdev.InputDevice(path)
                if evdev.ecodes.EV_KEY in d.capabilities():
                    sources.append({"kind": "evdev", "path": path, "identity": identity(d),
                                    "label": "%s [%s%s]" % (d.name, path, ", Bluetooth HID" if d.info.bustype == 5 else "")})
            except OSError as e:
                notes.append("%s: %s" % (path, e))
            finally:
                if d is not None:
                    d.close()
    except ImportError:
        notes.append("python3-evdev unavailable; evdev capture disabled")
    for path in ("/run/lirc/lircd", "/var/run/lirc/lircd", "/dev/lircd"):
        if os.path.exists(path) and stat.S_ISSOCK(os.stat(path).st_mode):
            real = os.path.realpath(path)
            if not any(s["path"] == real for s in sources):
                sources.append({"kind": "lirc", "path": real, "label": "LIRC " + real})
    notes.append("Raw LIRC devices: " + (", ".join(glob.glob("/dev/lirc[0-9]*")) or "none"))
    notes.append("Decoded events only. Device listing is not proof of IR protocol compatibility.")
    return sources, notes

def parse_lirc(line):
    parts = line.split()
    if len(parts) != 4:
        return None
    try:
        int(parts[0], 16)
        repeat = int(parts[1], 16)
    except ValueError:
        return None
    return ("lirc:%s:%s" % (parts[3], parts[2]), 1) if repeat == 0 else None

class Reader:
    def __init__(self, source):
        self.kind = source["kind"]
        self.buffer = b""
        if self.kind == "evdev":
            import evdev
            matches = []
            for path in evdev.list_devices():
                d = evdev.InputDevice(path)
                if identity(d) == source["identity"]:
                    matches.append(d)
                else:
                    d.close()
            if len(matches) != 1:
                for d in matches:
                    d.close()
                raise OSError("Source identity missing or ambiguous; select receiver again")
            self.device = matches[0]
        elif self.kind == "lirc":
            self.device = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.device.settimeout(0.2)
            try:
                self.device.connect(source["path"])
                self.device.setblocking(False)
            except Exception:
                self.device.close()
                raise
        else:
            raise ValueError("Unknown source")
    def poll(self):
        events = []
        try:
            if self.kind == "evdev":
                for event in self.device.read():
                    if event.type == 1 and event.value in (0, 1, 2):
                        events.append(("evdev:%d" % event.code, event.value))
            else:
                chunk = self.device.recv(4096)
                if not chunk:
                    raise OSError("LIRC disconnected")
                self.buffer += chunk
                if len(self.buffer) > 65536:
                    raise OSError("Oversized LIRC data")
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    event = parse_lirc(line.decode("ascii", "replace"))
                    if event:
                        events.append(event)
        except BlockingIOError:
            pass
        return events
    def close(self):
        self.device.close()
