"""Translate receive events into balanced Enigma2 make/repeat/long/break events."""
class KeyFlow:
    def __init__(self, emit, delay=0.45, rate=0.10, long_delay=0.8):
        self.emit = emit
        self.delay, self.rate, self.long_delay = delay, rate, long_delay
        self.held = None

    def release(self):
        held, self.held = self.held, None
        if held:
            self.emit(held['code'], 1)

    def event(self, token, code, value, now):
        if value == 0:
            if self.held and self.held['token'] == token:
                self.release()
            return
        if value not in (1, 2):
            return
        if value == 1 or not self.held or self.held['token'] != token:
            self.release()
            self.held = dict(token=token, code=code, started=now, seen=now,
                             repeated=now, long=False, timeout=2.0 if token.startswith('bt:') else 0.28)
            self.emit(code, 0)
            return
        held = self.held
        held['seen'] = now
        if now-held['started'] >= self.long_delay and not held['long']:
            held['long'] = True
            self.emit(code, 3)
        if self.held is held and now-held['started'] >= self.delay and now-held['repeated'] >= self.rate:
            held['repeated'] = now
            self.emit(code, 2)

    def expire(self, now):
        if self.held and now-self.held['seen'] > self.held['timeout']:
            self.release()
