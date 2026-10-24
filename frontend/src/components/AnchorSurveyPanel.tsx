import {useEffect,useState} from 'react';
import {api} from '../services/api';
import type {AnchorSurveyState} from '../services/api';
import type {LayoutDraft} from '../types';
import {surveyDisplaySize} from '../services/surveyEstimate';

export function AnchorSurveyPanel({dirty,onImported}:{dirty:boolean;onImported:(draft:LayoutDraft,issues:string[])=>void}) {
  const [state,setState]=useState<AnchorSurveyState|null>(null);
  const [elapsed,setElapsed]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [pollError,setPollError]=useState('');
  useEffect(()=>{
    let active=true;
    let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{
      try {const value=await api.anchorSurvey();if(active){setState(value);setPollError('');}}
      catch(e){if(active)setPollError(e instanceof Error?e.message:'측량 상태 확인 실패');}
      if(active)timer=setTimeout(()=>void poll(),1000);
    };
    void poll();return()=>{active=false;clearTimeout(timer);};
  },[]);
  const session=state?.session;
  const size=session?surveyDisplaySize(session.result):null;
  const hasSize=size&&(size.width!=null||size.height!=null);
  const problemPairs=session?.result.pairs?.filter(p=>!p.passed).map(p=>p.pair.replace('-','–'))??[];
  const active=session && ['requested','measuring'].includes(session.status);
  useEffect(()=>{
    if(session?.status!=='measuring'){setElapsed(0);return;}
    const base=session.elapsed_seconds;
    const started=performance.now();
    setElapsed(Math.min(10,base));
    const timer=setInterval(()=>setElapsed(Math.min(10,base+(performance.now()-started)/1000)),100);
    return()=>clearInterval(timer);
  },[session?.status,session?.elapsed_seconds]);
  const labels:Record<string,string>={requested:'측정 준비 중',ready:'측정 완료',
    rejected:hasSize?'측정값 확인':'수집값 대기',timed_out:'수집값 대기',
    cancelled:'측정 취소',imported:'설계안에 반영됨'};
  const execute=async(action:()=>Promise<void>)=>{
    setBusy(true);setError('');
    try{await action();setState(await api.anchorSurvey());}
    catch(e){setError(e instanceof Error?e.message:'측량 요청 실패');}
    finally{setBusy(false);}
  };
  return <section className="anchor-survey-panel" aria-label="앵커 간 10초 측정">
    <h3>작업장 크기 측정</h3>
    {dirty && <p>설계 저장 후 측정하세요.</p>}
    {state && !state.supported && <p role="status">앵커 연결 대기</p>}
    <div className="survey-actions">
      <button className="survey-button primary" disabled={!state?.supported||state?.coordinator_busy||!!active||busy||dirty} onClick={()=>void execute(async()=>{await api.startAnchorSurvey();})}>10초 측정</button>
      {active && <button className="survey-button secondary" disabled={busy} onClick={()=>void execute(async()=>{await api.cancelAnchorSurvey(session!.session_id);})}>측정 취소</button>}
    </div>
    {session?.status==='measuring' ? <div role="status">
      <strong className="survey-countdown">{elapsed.toFixed(1)} / 10초</strong>
      <progress value={elapsed} max={10} aria-label="측정 진행"/>
      {elapsed>=10 && <p>결과 확인 중</p>}
    </div> : session && <div>
      <p role="status">{labels[session.status]??'측정 대기'}</p>
      {hasSize && <p className="survey-dimensions">
        가로 <strong>{size.width?.toFixed(2)??'—'}m</strong> <span className="survey-size-divider">×</span> 세로 <strong>{size.height?.toFixed(2)??'—'}m</strong>
        {size.reference && <span className="survey-reference-badge">{size.inferred?'추정 참고값':'참고값'}</span>}
      </p>}
      {problemPairs.length>0&&session.status!=='cancelled'&&<small className="survey-issues">확인 필요 {problemPairs.join(' · ')}</small>}
      {session.status==='ready' && <div className="survey-actions">
        <button className="survey-button primary" disabled={busy||dirty} onClick={()=>void execute(async()=>{const r=await api.importAnchorSurvey(session.session_id);onImported(r.draft,r.issues);})}>설계안에 넣기</button>
      </div>}
    </div>}
    {error && <p role="alert" className="bad">{error}</p>}
    {pollError && <p role="status">{pollError}</p>}
  </section>;
}
