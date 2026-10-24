import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/services/surveyEstimate.ts',import.meta.url),'utf8');
const {outputText}=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}});
const {surveyDisplaySize}=await import('data:text/javascript;base64,'+Buffer.from(outputText).toString('base64'));
const pair=(name,value,extra={})=>({pair:name,estimate_m:value,count:12,total:16,span_seconds:9,spread_m:.1,passed:false,...extra});
test('partial sides display reference values without promoting registration',()=>{
 const result={passed:false,pairs:[pair('1-2',5.193,{count:8}),pair('1-4',4.076,{passed:true}),pair('2-3',5.78,{count:5})]};
 const size=surveyDisplaySize(result);
 assert.equal(size.reference,true);assert.ok(Math.abs(size.width-5.193)<1e-9);assert.ok(Math.abs(size.height-4.076)<1e-9);
 assert.equal(result.passed,false);
});
test('does not fill an absent axis from an old room size or isolated sample',()=>{
 const size=surveyDisplaySize({passed:false,width:5.2,height:3.6,pairs:[pair('1-2',7,{count:1}),pair('1-4',4)]});
 assert.equal(size.width,null);assert.equal(size.height,4);
});
test('rejects short, multimodal, and highly scattered samples',()=>{
 for(const extra of [{span_seconds:2},{multimodal:true},{spread_m:2}])
  assert.equal(surveyDisplaySize({pairs:[pair('1-2',5,extra)]}).width,null);
});
test('keeps validated dimensions unchanged',()=>{
 assert.deepEqual(surveyDisplaySize({passed:true,width:5.1,height:3.5}),{width:5.1,height:3.5,reference:false,inferred:false});
});
test('can infer one side from an actual diagonal and the other side',()=>{
 const r=surveyDisplaySize({pairs:[pair('1-4',3),pair('1-3',5)]});
 assert.equal(r.width,4);assert.equal(r.height,3);assert.equal(r.inferred,true);
 assert.equal(surveyDisplaySize({pairs:[pair('1-3',5),pair('2-4',5)]}).width,null);
});
