"""Open a local helmet test call; discard received audio and retain counters only."""
import asyncio
import getpass
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
import websockets


async def main():
    password = os.environ.pop('HANMIR_MONITOR_PASSWORD','') or getpass.getpass('관리자 비밀번호: ')
    session = requests.Session()
    base = 'http://127.0.0.1:8000'
    r = session.post(base+'/api/auth/login',json=dict(username='TUTUS',password=password),timeout=10)
    r.raise_for_status()
    session.headers['Authorization'] = 'Bearer '+r.json()['token']
    r = session.get(base+'/api/calls/helmet-001-av/status',timeout=5);r.raise_for_status()
    if r.json()['operator_connected']: raise RuntimeError('An existing call is active; leaving it untouched')
    r = session.post(base+'/api/calls/helmet-001-av/ticket',timeout=5);r.raise_for_status()
    ticket = r.json()['ticket']
    rows = []
    received = 0
    started = time.monotonic()
    async with websockets.connect('ws://127.0.0.1:8000/ws/call/operator/helmet-001-av?ticket='+ticket) as socket:
        while time.monotonic()-started < 45:
            try:
                payload = await asyncio.wait_for(socket.recv(),timeout=1)
                if isinstance(payload,bytes): received += len(payload)
                else: rows.append(dict(at=datetime.now(timezone.utc).isoformat(),control=json.loads(payload)))
            except asyncio.TimeoutError: pass
        await socket.send('{"type":"call_stop"}')
    result = dict(started_elapsed_s=time.monotonic()-started,received_audio_bytes=received,controls=rows,
        note='Received PCM discarded. This verifies control flow, not bidirectional acoustic quality.')
    path = Path('C:/dev/hanmir-runtime/zone-warning-call-check-20261024.json')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__ == '__main__': asyncio.run(main())
