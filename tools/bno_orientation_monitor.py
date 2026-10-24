"""Local, USB-free observation of existing dashboard orientation messages.

No firmware commands, calibration writes, fall decisions, or per-sample DB polls.
Run with the repository venv; HANMIR_MONITOR_PASSWORD is read from the environment.
"""
import argparse
import asyncio
from collections import deque
import csv
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import queue
import statistics
import threading
import time
from urllib.parse import urlencode

import requests
import websockets

TRIAL_LABELS = ('천천히 고개 숙였다 복귀', '천천히 좌우로 기울였다 복귀',
                '앉았다 일어나기', '매트에서 보조자와 천천히 자세 변경', '천천히 걷고 정지')

def utc():
    return datetime.now(timezone.utc).isoformat()


def wrap(value):
    return (value + 180) % 360 - 180


def gravity(pitch, roll):
    p, r = math.radians(pitch), math.radians(roll)
    return (-math.sin(p), math.sin(r) * math.cos(p), math.cos(r) * math.cos(p))


class Monitor:
    def __init__(self, args):
        self.args = args
        self.folder = Path(args.output).resolve() / datetime.now().strftime('%Y%m%d-%H%M%S')
        self.folder.mkdir(parents=True, exist_ok=False)
        self.lock = threading.Lock()
        self.records = queue.Queue(maxsize=4096)
        self.history = deque(maxlen=600)
        self.intervals = deque(maxlen=600)
        self.latest = None
        self.baseline = None
        self.count = self.gaps = self.log_dropped = self.log_errors = self.written = 0
        self.last_mono = self.source_last = None
        self.previous = None
        self.connected = False
        self.connections = 0
        self.error = None
        self.active = None
        self.trials = []
        self.recording = True
        self.started = time.monotonic()
        self.camera_previous = None
        self.health = {}
        (self.folder / 'metadata.json').write_text(json.dumps({
            'started_at': utc(), 'device_id': args.device, 'source': 'existing /ws/dashboard orientation',
            'firmware_changed': False, 'server_changed': False,
            'limitations': ['Orientation only; no acceleration, angular velocity or impact measurement',
                'Dashboard may coalesce samples; gaps are not proven sensor loss',
                'Tilt is relative to locally saved pose; map heading calibration is unchanged',
                'Device sample timestamps/sequences are unavailable; server/PC receipt times only',
                'This session does not measure fall detection accuracy'],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        threading.Thread(target=self.writer, daemon=True, name='bno-log-writer').start()

    def log(self, kind, data):
        try:
            self.records.put_nowait((kind, data))
        except queue.Full:
            self.log_dropped += 1

    def writer(self):
        fields = ['received_at', 'server_received_at', 'elapsed_s', 'trial', 'label',
                  'yaw_deg', 'pitch_deg', 'roll_deg', 'relative_tilt_deg', 'pc_gap_ms', 'server_gap_ms']
        with (self.folder / 'samples.jsonl').open('w', encoding='utf-8') as raw, \
             (self.folder / 'samples.csv').open('w', newline='', encoding='utf-8-sig') as table, \
             (self.folder / 'events.jsonl').open('w', encoding='utf-8') as events:
            csv_writer = csv.DictWriter(table, fieldnames=fields, extrasaction='ignore')
            csv_writer.writeheader()
            last_flush = time.monotonic()
            while True:
                try:
                    kind, data = self.records.get(timeout=.5)
                except queue.Empty:
                    raw.flush(); table.flush(); events.flush()
                    continue
                try:
                    if kind == 'sample':
                        raw.write(json.dumps(data, ensure_ascii=False) + '\n')
                        csv_writer.writerow(data)
                        self.written += 1
                    else:
                        events.write(json.dumps(data, ensure_ascii=False) + '\n')
                    if time.monotonic() - last_flush >= 1:
                        raw.flush(); table.flush(); events.flush()
                        last_flush = time.monotonic()
                except OSError:
                    self.log_errors += 1
                finally:
                    self.records.task_done()

    def finish_trial(self, now):
        if self.active and now >= self.active['end_mono']:
            item = dict(self.active)
            item.pop('end_mono')
            item['finished_at'] = utc()
            self.trials.append(item)
            if len(self.trials) >= 20:
                self.recording = False
            self.log('event', {'type': 'trial_end', **item})
            self.active = None
            (self.folder / 'trials.json').write_text(json.dumps(self.trials, ensure_ascii=False, indent=2), encoding='utf-8')

    def sample(self, data):
        if data.get('device_id') != self.args.device:
            return
        values = [data.get('imu_' + k + '_deg') for k in ('yaw', 'pitch', 'roll')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            return
        now = time.monotonic()
        with self.lock:
            self.finish_trial(now)
            if now - self.started >= 3600:
                self.recording = False
            gap = None if self.last_mono is None else (now - self.last_mono) * 1000
            self.last_mono = now
            if gap is not None:
                self.intervals.append(gap)
                self.gaps += gap > 250
            source = data.get('heading_at')
            source_gap = None
            try:
                stamp = datetime.fromisoformat(source.replace('Z', '+00:00')).timestamp()
                if self.source_last is not None:
                    source_gap = (stamp - self.source_last) * 1000
                self.source_last = stamp
            except (ValueError, AttributeError):
                pass
            yaw, pitch, roll = values
            tilt = None
            if self.baseline:
                g = gravity(pitch, roll)
                tilt = math.degrees(math.acos(max(-1, min(1, sum(a*b for a,b in zip(g, self.baseline))))))
            row = dict(received_at=utc(), server_received_at=source,
                elapsed_s=round(now-self.started, 4), trial=self.active['number'] if self.active else 0,
                label=self.active['label'] if self.active else 'between_trials',
                yaw_deg=yaw, pitch_deg=pitch, roll_deg=roll, relative_tilt_deg=tilt,
                pc_gap_ms=gap, server_gap_ms=source_gap)
            if self.active:
                trial = self.active
                trial['samples'] += 1
                trial['max_gap_ms'] = max(trial['max_gap_ms'], gap or 0)
                if tilt is not None:
                    trial['peak_relative_tilt_deg'] = max(trial['peak_relative_tilt_deg'], tilt)
                for name, value in [('pitch', pitch), ('roll', roll)]:
                    trial[name+'_min_deg'] = min(trial.get(name+'_min_deg', value), value)
                    trial[name+'_max_deg'] = max(trial.get(name+'_max_deg', value), value)
            if self.previous:
                row['angle_step_deg'] = [wrap(v-p) for v,p in zip(values, self.previous)]
            self.previous = values
            self.count += 1
            self.latest = row
            self.history.append(row)
            if self.recording:
                self.log('sample', row)

    def state(self):
        with self.lock:
            now = time.monotonic()
            self.finish_trial(now)
            gaps = sorted(self.intervals)
            recent = [r for r in self.history if r['elapsed_s'] >= now-self.started-5]
            hz = ((len(recent)-1)/(recent[-1]['elapsed_s']-recent[0]['elapsed_s'])
                  if len(recent)>1 and recent[-1]['elapsed_s']>recent[0]['elapsed_s'] else 0)
            return dict(connected=self.connected, recording=self.recording, sample_count=self.count,
                age_ms=None if self.last_mono is None else round((now-self.last_mono)*1000),
                hz=round(hz,2), gap_median_ms=round(statistics.median(gaps),1) if gaps else None,
                gap_p95_ms=round(gaps[min(len(gaps)-1, math.ceil(len(gaps)*.95)-1)],1) if gaps else None,
                gap_max_ms=round(max(gaps),1) if gaps else None, gaps_over_250ms=self.gaps,
                connections=self.connections, last_error=self.error, log_written=self.written,
                log_dropped=self.log_dropped, log_errors=self.log_errors, log_queue=self.records.qsize(),
                latest=self.latest, history=list(self.history)[-200:], output=str(self.folder),
                baseline_set=self.baseline is not None, trials=self.trials,
                label_counts={label:sum(t['label']==label for t in self.trials) for label in TRIAL_LABELS},
                active=None if self.active is None else dict(number=self.active['number'],
                    label=self.active['label'], remaining_s=round(max(0,self.active['end_mono']-now),1)),
                health=self.health)

    def action(self, action, label):
        with self.lock:
            self.finish_trial(time.monotonic())
            if action in ('baseline','trial') and (self.last_mono is None or time.monotonic()-self.last_mono>1):
                return {'error':'BNO 실시간 수신을 먼저 확인하세요.'}
            if action == 'baseline':
                if self.active or self.trials:
                    return {'error':'비교 기준을 유지하기 위해 회차 시작 후 기준 자세를 바꾸지 않습니다.'}
                self.baseline = gravity(self.latest['pitch_deg'], self.latest['roll_deg'])
            elif action == 'trial':
                if self.baseline is None:
                    return {'error':'편한 기준 자세에서 기준 자세 저장을 먼저 누르세요.'}
                if self.active or len(self.trials)>=20 or not self.recording:
                    return {'error':'진행 중이거나 20회 기록이 끝났습니다.'}
                if label not in TRIAL_LABELS:
                    return {'error':'2~6번 동작 중 하나를 선택하세요.'}
                if sum(t['label']==label for t in self.trials) >= 4:
                    return {'error':'이 동작은 4회 완료했습니다. 다른 동작을 선택하세요.'}
                self.active = dict(number=len(self.trials)+1, label=label[:80],
                    started_at=utc(), end_mono=time.monotonic()+10, duration_s=10,
                    samples=0, max_gap_ms=0, peak_relative_tilt_deg=0)
            elif action == 'finish':
                if self.active:
                    self.active['end_mono']=time.monotonic()
                    self.finish_trial(time.monotonic())
                self.recording=False
            else:
                return {'error':'알 수 없는 동작'}
            self.log('event', dict(type=action, at=utc(), label=label[:80],
                                  trial=self.active['number'] if self.active else 0))
        state=self.state()
        (self.folder/'summary.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'ok':True}

    async def collect(self):
        password = os.environ.pop('HANMIR_MONITOR_PASSWORD', '')
        if not password:
            self.error='HANMIR_MONITOR_PASSWORD is required'; return
        while True:
            try:
                def login():
                    r=requests.post(self.args.server+'/api/auth/login',json={
                        'username':self.args.username,'password':password},timeout=10)
                    r.raise_for_status(); return r.json()['token']
                token=await asyncio.to_thread(login)
                url=self.args.server.replace('http://','ws://').replace('https://','wss://')+'/ws/dashboard?'+urlencode({'token':token})
                async with websockets.connect(url,max_size=2**21,ping_interval=20) as ws:
                    self.connected=True; self.connections+=1; self.error=None
                    self.log('event',dict(type='connected',at=utc(),connection=self.connections))
                    async for text in ws:
                        message=json.loads(text)
                        if message.get('type')=='orientation': self.sample(message.get('data',{}))
            except Exception as exc:
                self.error=type(exc).__name__  # Never log an authenticated URL.
                self.log('event',dict(type='connection_error',at=utc(),error=self.error))
            finally:
                self.connected=False
            await asyncio.sleep(2)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--server',default='http://127.0.0.1:8000')
    parser.add_argument('--username',default='TUTUS')
    parser.add_argument('--device',default='helmet-001-av')
    parser.add_argument('--port',type=int,default=8093)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    monitor=Monitor(args)
    html=Path(__file__).with_suffix('.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,code,content,kind='application/json; charset=utf-8'):
            self.send_response(code); self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(content)
        def do_GET(self):
            if self.path=='/': self.send(200,html,'text/html; charset=utf-8')
            elif self.path=='/state': self.send(200,json.dumps(monitor.state(),ensure_ascii=False).encode())
            else: self.send(404,b'{}')
        def do_POST(self):
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'):
                self.send(403,b'{}'); return
            if self.path!='/action': self.send(404,b'{}'); return
            length=int(self.headers.get('Content-Length','0'))
            if length>1024: self.send(413,b'{}'); return
            try:
                data=json.loads(self.rfile.read(length))
                result=monitor.action(data.get('action'),str(data.get('label','')))
                self.send(200,json.dumps(result,ensure_ascii=False).encode())
            except (ValueError,TypeError): self.send(400,b'{}')
    threading.Thread(target=lambda:asyncio.run(monitor.collect()),daemon=True).start()
    print(json.dumps({'url':f'http://127.0.0.1:{args.port}','output':str(monitor.folder)},ensure_ascii=True),flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__': main()
