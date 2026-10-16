"""Temporarily run an app-only P4 experiment, then restore a supplied known-good app.

Requires both apps at 0x10000 and unchanged existing bootloader/partition table.
Never overwrites NVS/model partitions. Restore runs even after a benchmark error.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import serial
from esptool.reset import HardReset

p=argparse.ArgumentParser()
p.add_argument('--port',required=True)
p.add_argument('--experiment',type=Path,required=True)
p.add_argument('--restore',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
if a.output.exists():raise SystemExit('Use a new evidence directory')
for f in (a.experiment,a.restore):
    if not f.is_file() or not 0<f.stat().st_size<=4*1024*1024:raise SystemExit('Invalid application image')
a.output.mkdir(parents=True)
backup=a.output/'known-good-app.bin'
shutil.copyfile(a.restore,backup)
report={'port':a.port,'offset':'0x10000','restore_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
        'experiment_sha256':hashlib.sha256(a.experiment.read_bytes()).hexdigest(),'restored':False}
def flash(path,log):
    with (a.output/log).open('w',encoding='utf-8') as out:
        subprocess.run([sys.executable,'-m','esptool','--chip','esp32p4','--port',a.port,'--baud','460800',
            '--before','default_reset','--after','hard_reset','write_flash','0x10000',str(path)],
            stdout=out,stderr=subprocess.STDOUT,check=True,timeout=120)
try:
    flash(a.experiment,'flash-experiment.log')
    with serial.Serial(a.port,115200,timeout=.2) as port:
        port.dtr=False
        HardReset(port,uses_usb=True)()
        deadline=time.monotonic()+15
        with (a.output/'uart.log').open('wb') as log:
            while time.monotonic()<deadline:
                log.write(port.read(8192))
                log.flush()
finally:
    try:
        flash(backup,'flash-restore.log')
        report['restored']=True
    finally:
        (a.output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
