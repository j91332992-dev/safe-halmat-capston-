"""Conservative per-person PPE evidence. No extra model or helmet commands."""
from collections import deque
from uuid import uuid4

ITEMS = ('helmet', 'vest', 'glove')


def coords(box):
    return [float(box[k]) for k in ('x1', 'y1', 'x2', 'y2')] if isinstance(box, dict) else list(box)


def iou(a, b):
    ax, ay, bx, by = coords(a)
    cx, cy, dx, dy = coords(b)
    intersection = max(0, min(bx, dx)-max(ax, cx))*max(0, min(by, dy)-max(ay, cy))
    return intersection/max(1, (bx-ax)*(by-ay)+(dx-cx)*(dy-cy)-intersection)


def owner(box, people, item):
    x1, y1, x2, y2 = coords(box)
    cx, cy = (x1+x2)/2, (y1+y2)/2
    owners = []
    for index, person in enumerate(people):
        px, py, qx, qy = coords(person['box'])
        w, h = qx-px, qy-py
        lo, hi = {'helmet': (-.12, .42), 'vest': (.16, .85), 'glove': (.15, 1.05)}[item]
        pad = .25 if item == 'glove' else .08
        if px-w*pad <= cx <= qx+w*pad and py+h*lo <= cy <= py+h*hi:
            owners.append(index)
    return owners[0] if len(owners) == 1 else None


def build_observations(detections, candidates, image, person_threshold):
    """Require an explicit part detection, not inferred proportions, for absence.

    Part visibility remains a conservative model proxy, not a certified occlusion
    detector. Ambiguous ownership/overlapping people cannot produce absence.
    """
    import cv2
    people = [d for d in detections if d.get('category') == 'person'
              and d.get('positive', True) and d.get('confidence', 0) >= person_threshold][:32]
    h, w = image.shape[:2]
    evidence = [{k: {'positive': [], 'parts': [], 'negative': []} for k in ITEMS} for _ in people]
    for d in detections:
        item = d.get('category')
        if item not in ITEMS or not d.get('box'):
            continue
        index = owner(d['box'], people, item)
        if index is not None:
            evidence[index][item]['positive' if d.get('positive', True) else 'negative'].append(d)
    parts = {'head': 'helmet', 'body': 'vest', 'torso': 'vest', 'hand': 'glove',
             'bare hand': 'glove', 'barehand': 'glove'}
    for c in candidates:
        name = c.get('class', '').lower().replace('_', ' ').replace('-', ' ')
        item = parts.get(name)
        if item is None or c.get('confidence', 0) < .5:
            continue
        # Only full-frame part proposals: crop duplicates are not new evidence.
        if c.get('pass') != 'full':
            continue
        index = owner(c['box'], people, item)
        if index is not None:
            evidence[index][item]['parts'].append(c)
    result = []
    for index, person in enumerate(people):
        overlapping = any(iou(person['box'], other['box']) > .15
                          for j, other in enumerate(people) if j != index)
        items = {}
        for item, ev in evidence[index].items():
            positives = ev['positive']
            proposals = ev['negative'] + ev['parts']
            positive = bool(positives)
            if item == 'glove' and proposals:
                # A second visible unprotected hand must not inherit the first
                # hand's glove. Generic hand detections do not prove bare skin.
                positive = positive and all(any(iou(part['box'], p['box']) >= .25
                    for p in positives) for part in proposals)
            valid = False
            reason = 'body_part_not_visible'
            quality = None
            for part in sorted(proposals, key=lambda d: d.get('confidence', 0), reverse=True)[:2]:
                x1, y1, x2, y2 = coords(part['box'])
                if x1 <= 2 or y1 <= 2 or x2 >= w-2 or y2 >= h-2:
                    reason = 'part_clipped'
                    continue
                if min(x2-x1, y2-y1) < (40 if item == 'vest' else 20):
                    reason = 'part_too_small'
                    continue
                roi = image[int(y1):int(y2), int(x1):int(x2)]
                if not roi.size:
                    continue
                gray = cv2.cvtColor(cv2.resize(roi, (64, 64)), cv2.COLOR_BGR2GRAY)
                quality = round(float(cv2.Laplacian(gray, cv2.CV_32F).var()), 2)
                if quality < 15:
                    reason = 'part_blurred'
                    continue
                valid, reason = True, 'visible_part_without_ppe'
                break
            if overlapping:
                valid, positive, reason = False, False, 'person_overlap'
            # A positive hand/glove does not prove that BOTH hands are equipped.
            items[item] = dict(value=True if positive else False if valid else None,
                               visible=positive or valid,
                               reason='ppe_detected' if positive else reason,
                               confidence=max((d.get('confidence', 0) for d in positives), default=None),
                               quality=quality,
                               scope='visible_hands_only' if item == 'glove' else 'visible_part')
        result.append(dict(box=person['box'], items=items))
    return result


class PPETracker:
    WINDOW = 2.0
    GAP = 1.5

    def __init__(self):
        self.tracks = {}
        self.counter = 0
        self.session = uuid4().hex[:8]

    def update(self, device, observations, now):
        notifications = self.expire(now, device)
        old = {key: t for key, t in self.tracks.items() if t['device'] == device}
        candidates = {i: [key for key, t in old.items() if iou(obs['box'], t['box']) >= .35]
                      for i, obs in enumerate(observations)}
        used = set()
        output = []
        for index, obs in enumerate(observations):
            matches = candidates[index]
            unique = len(matches) == 1 and sum(matches[0] in m for m in candidates.values()) == 1
            key = matches[0] if unique else None
            if key is None:
                self.counter += 1
                key = f'{self.session}-{self.counter}'
                self.tracks[key] = dict(device=device, box=obs['box'], seen=now,
                    history={k: deque(maxlen=64) for k in ITEMS}, alerts={})
            track = self.tracks[key]
            used.add(key)
            track['box'], track['seen'] = obs['box'], now
            states = {}
            for item in ITEMS:
                evidence = obs['items'][item]
                history = track['history'][item]
                while history and now-history[0][0] > self.WINDOW:
                    history.popleft()
                if evidence['value'] is None:
                    history.clear()  # do not bridge occlusion with old evidence
                    status = 'unknown'
                else:
                    history.append((now, evidence['value']))
                    count = len(history)
                    span = now-history[0][0]
                    missing = sum(value is False for _, value in history)
                    status = 'observed' if evidence['value'] else 'pending'
                    if count >= 6 and span >= 1.5 and missing/count >= .8:
                        status = 'check_required' if item == 'glove' else 'missing_suspected'
                    # Recovery requires a continuous positive run, not one hit.
                    positive_run = []
                    for sample in reversed(history):
                        if not sample[1]:
                            break
                        positive_run.append(sample)
                    recovered = len(positive_run) >= 3 and now-positive_run[-1][0] >= 1.0
                    if recovered:
                        status = 'worn'
                    alert = track['alerts'].get(item)
                    if recovered and alert:
                        notifications.append(dict(track_id=key, item=item, kind='resolved', device=device))
                        del track['alerts'][item]
                    elif status in {'check_required', 'missing_suspected'}:
                        if not alert:
                            track['alerts'][item] = dict(at=now, reminded=False)
                            notifications.append(dict(track_id=key, item=item, kind='opened', device=device))
                        elif not alert['reminded'] and now-alert['at'] >= 15:
                            alert['reminded'] = True
                            notifications.append(dict(track_id=key, item=item, kind='reminder', device=device))
                    elif alert:
                        status = 'recovering' if evidence['value'] else 'pending'
                count = len(history)
                missing = sum(value is False for _, value in history)
                states[item] = dict(evidence, status=status, valid_samples=count,
                                    missing_samples=missing,
                                    missing_ratio=round(missing/count, 3) if count else None,
                                    span_seconds=round(now-history[0][0], 3) if count else 0)
            output.append(dict(track_id=key, box=obs['box'], items=states))
        # Lost/ambiguous identities end observation, never claim successful PPE recovery.
        for key in old.keys()-used:
            notifications.extend(self._remove(key))
        for note in notifications:
            note['person'] = next((p for p in output if p['track_id'] == note['track_id']), None)
        return output, notifications

    def _remove(self, key):
        track = self.tracks.pop(key, None)
        return [dict(track_id=key, item=item, kind='observation_ended', device=track['device'])
                for item in track['alerts']] if track else []

    def expire(self, now, device=None):
        result = []
        for key, t in list(self.tracks.items()):
            if (device is None or t['device'] == device) and now-t['seen'] > self.GAP:
                result.extend(self._remove(key))
        return result


ppe_tracker = PPETracker()
