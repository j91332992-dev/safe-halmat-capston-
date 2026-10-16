"""Timestamp UART lines on the host, without resetting P4 or claiming audio latency."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import serial

p=argparse.ArgumentParser()
p.add_argument('--port',default='COM25')
p.add_argument('--seconds',type=int,default=120)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if not 1<=a.seconds<=600:p.error('duration must be 1..600 seconds')
if a.output.exists():p.error('Use a new output file')
a.output.parent.mkdir(parents=True,exist_ok=True)
s=serial.Serial();s.port=a.port;s.baudrate=115200;s.timeout=.2;s.dtr=False;s.rts=False
s.open()
deadline=time.monotonic()+a.seconds
pending=b''; lines=0
with s,a.output.open('w',encoding='utf-8') as out:
    while time.monotonic()<deadline:
        pending+=s.read(8192)
        while b'\n' in pending:
            line,pending=pending.split(b'\n',1)
            out.write(json.dumps(dict(host_received_at=datetime.now(timezone.utc).isoformat(),
                line=line.decode('utf-8',errors='replace').rstrip('\r')),ensure_ascii=False)+'\n')
            out.flush();lines+=1
        if len(pending)>65536:pending=pending[-65536:]
print(json.dumps(dict(lines=lines,path=str(a.output))))
