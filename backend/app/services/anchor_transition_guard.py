"""Debounce large position changes caused by transient anchor-set changes."""
import math
import time
from threading import Lock


class AnchorTransitionGuard:
    def __init__(self):
        self.states = {}
        self.lock = Lock()

    def check(self, key, session, anchors, x, y, now=None):
        now = time.monotonic() if now is None else now
        anchors = tuple(sorted(anchors))
        with self.lock:
            self.states = {k:v for k,v in self.states.items() if now-v['touched'] < 60}
            s = self.states.get(key)
            if s is None or s['session'] != session:
                if len(self.states) >= 1000:
                    self.states.pop(min(self.states, key=lambda k:self.states[k]['touched']))
                self.states[key] = dict(session=session, anchors=anchors, x=x, y=y, touched=now)
                return dict(accepted=True, reason='anchor_set_initialized')
            s['touched'] = now
            jump = math.hypot(x-s['x'], y-s['y'])
            result = dict(previous_anchors=list(s['anchors']), current_anchors=list(anchors), displacement_m=jump)
            if anchors == s['anchors'] or jump <= .4:
                s.update(anchors=anchors, x=x, y=y)
                s.pop('pending', None)
                return dict(result, accepted=True, reason='anchor_set_stable_or_small_change')
            p = s.get('pending')
            if p is None or p['anchors'] != anchors:
                p = dict(anchors=anchors, started=now, count=0)
            p['count'] += 1
            s['pending'] = p
            span = now-p['started']
            ready = p['count'] >= 3 and span+1e-9 >= .6
            if ready:
                s.update(anchors=anchors, x=x, y=y)
                s.pop('pending', None)
            return dict(result, accepted=ready, reason='anchor_set_confirmed' if ready else 'anchor_set_change_pending',
                        confirmation_samples=p['count'], confirmation_seconds=span)


anchor_transition_guard = AnchorTransitionGuard()
