import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Run the actual pure TS helper without adding a frontend test dependency.
const source=readFileSync(new URL('../src/services/positionUpdates.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {mergeWorkerPosition,positionTimestamp}=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
const worker=(time,x)=>({worker_id:'worker-001',x,y:2,confidence:.9,current_zone:null,
  risk_score:0,updated_at:time,position_status:{server_received_at:time}});

test('late snapshot cannot move the marker back; metadata still updates',()=>{
  const live=worker('2026-10-24T06:00:02Z',3);
  const late={...worker('2026-10-24T06:00:01Z',1),risk_score:100};
  const r=mergeWorkerPosition(late,live);
  assert.equal(r.x,3);assert.equal(r.risk_score,100);assert.equal(r.position_status,live.position_status);
});
test('new positions and equal-timestamp layout resets can update',()=>{
  const old=worker('2026-10-24T06:00:01Z',1);
  assert.equal(mergeWorkerPosition(worker('2026-10-24T06:00:02Z',3),old).x,3);
  assert.equal(mergeWorkerPosition(worker('2026-10-24T06:00:01Z',2),old).x,2);
});
test('position timestamp takes priority over a newer generic worker update',()=>{
  const old={...worker('2026-10-24T06:00:01Z',1),updated_at:'2026-10-24T06:10:00Z'};
  assert.equal(mergeWorkerPosition(old,worker('2026-10-24T06:00:02Z',3)).x,3);
});
test('timestamps without UTC suffix match backend UTC convention',()=>{
  assert.equal(positionTimestamp(worker('2026-10-24T06:00:01',1)),Date.parse('2026-10-24T06:00:01Z'));
});
test('initial and different workers are not blocked',()=>{
  const incoming=worker('2026-10-24T06:00:01Z',1);
  assert.equal(mergeWorkerPosition(incoming),incoming);
  assert.equal(mergeWorkerPosition(incoming,{...incoming,worker_id:'other'}),incoming);
});
