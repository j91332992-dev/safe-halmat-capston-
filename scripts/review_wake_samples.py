"""Loopback-only recording review. Labels are saved locally, never inferred."""
import argparse
import json
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

HTML = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>투투스 녹음 분류</title>
<style>body{font:18px system-ui;max-width:850px;margin:40px auto;background:#101827;color:#eef4ff}button{font:inherit;padding:14px;margin:6px;border:0;border-radius:8px;cursor:pointer}audio{width:100%;margin:25px 0}small{color:#bac5d6}#status{color:#78e3ad}</style>
<h1>투투스 녹음 분류</h1><p>녹음을 듣고 실제 내용으로 분류해 주세요. 불확실하거나 여러 번 부른 파일은 제외합니다.</p>
<p id="count"></p><small id="filename"></small><audio id="player" controls></audio>
<div><button onclick="save('positive')">투투스 정확히 1회</button><button onclick="save('negative')">투투스 없음</button><button onclick="save('discard')">불확실·반복·잘림</button></div>
<div><button onclick="move(-1)">이전</button><button onclick="move(1)">다음</button><button onclick="nextUnreviewed()">미분류로 이동</button></div>
<p id="status"></p><p>분류 결과는 이 PC에 자동 저장됩니다. 비슷한 소리라도 정확한 호출어가 아니면 ‘없음’, 판단이 어려우면 ‘제외’로 표시하세요.</p>
<script>
let items=[],labels={},index=0;
async function init(){let d=await (await fetch('/api/samples')).json();items=d.items;labels=d.labels;nextUnreviewed()}
function show(){let n=items[index];document.getElementById('count').textContent=`${index+1} / ${items.length} · 분류 완료 ${Object.keys(labels).length}`;document.getElementById('filename').textContent=n;let a=document.getElementById('player');a.src='/audio/'+encodeURIComponent(n);document.getElementById('status').textContent=labels[n]||'미분류';}
function move(n){index=Math.max(0,Math.min(items.length-1,index+n));show()}
function nextUnreviewed(){let n=items.findIndex(x=>!labels[x]);index=n<0?0:n;show()}
async function save(label){let n=items[index];let r=await fetch('/api/label',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:n,label})});if(!r.ok){alert('저장 실패');return}labels[n]=label;move(1)}
init();</script></html>"""


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--port',type=int,default=8091);a=p.parse_args()
    data=a.data.resolve();items=sorted(x.name for x in data.glob('*.wav'));label_file=data/'human_labels.json'
    labels=json.loads(label_file.read_text(encoding='utf-8')) if label_file.exists() else {}
    class Handler(BaseHTTPRequestHandler):
        def send(self,body,kind='application/json',status=200):
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/':return self.send(HTML.encode(),'text/html; charset=utf-8')
            if self.path=='/api/samples':return self.send(json.dumps(dict(items=items,labels=labels)).encode())
            if self.path.startswith('/audio/'):
                name=unquote(self.path[7:])
                if name in items:return self.send((data/name).read_bytes(),'audio/wav')
            self.send(b'not found','text/plain',404)
        def do_POST(self):
            origin=self.headers.get('Origin','')
            if origin not in ('',f'http://127.0.0.1:{a.port}',f'http://localhost:{a.port}'):
                return self.send(b'forbidden','text/plain',403)
            if self.path!='/api/label':return self.send(b'not found','text/plain',404)
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<4096:raise ValueError()
                r=json.loads(self.rfile.read(size));name=r['file'];label=r['label']
                if name not in items or label not in ('positive','negative','discard'):raise ValueError()
                labels[name]=label;tmp=label_file.with_suffix('.tmp');tmp.write_text(json.dumps(labels,indent=2),encoding='utf-8');tmp.replace(label_file)
                self.send(b'{"ok":true}')
            except (ValueError,KeyError):self.send(b'invalid','text/plain',400)
        def log_message(self,*args):pass
    print(f'Review http://127.0.0.1:{a.port}',flush=True);HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()

if __name__=='__main__':main()
