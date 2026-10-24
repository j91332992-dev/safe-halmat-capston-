import type {SurveySession} from './api';
type Pair=NonNullable<SurveySession['result']['pairs']>[number];

// Display-only partial estimate. Never promotes the server's registration gate
// or fills missing ranges with the old layout / a known room dimension.
export function surveyDisplaySize(result:SurveySession['result']) {
  if(result.passed&&Number.isFinite(result.width)&&Number.isFinite(result.height))
    return {width:result.width!,height:result.height!,reference:false,inferred:false};
  const eligible=(p:Pair)=>p.estimate_m!=null&&Number.isFinite(p.estimate_m)&&p.estimate_m>=.5&&p.estimate_m<=100
    &&p.count>=8&&(p.span_seconds??0)>=6&&!p.multimodal&&p.spread_m!=null
    &&p.spread_m<=Math.max(.3,.08*p.estimate_m);
  const axis=(names:string[])=>{
    const pairs=(result.pairs??[]).filter(p=>names.includes(p.pair)&&eligible(p));
    if(!pairs.length)return null;
    const weight=(p:Pair)=>p.count/Math.pow(Math.max(.03,p.spread_m!),2);
    pairs.sort((a,b)=>Number(b.passed)-Number(a.passed)||weight(b)-weight(a));
    const best=pairs[0];
    const coherent=pairs.filter(p=>Math.abs(p.estimate_m!-best.estimate_m!)<=Math.max(.3,.08*best.estimate_m!));
    return coherent.reduce((sum,p)=>sum+p.estimate_m!*weight(p),0)/coherent.reduce((sum,p)=>sum+weight(p),0);
  };
  let width=axis(['1-2','3-4']),height=axis(['1-4','2-3']);
  let inferred=false;
  // A measured diagonal plus one measured side identifies the other side.
  // Diagonals alone cannot identify X and Y separately.
  if((width==null)!==(height==null)){
    const known=(width??height)!;
    const diagonal=(result.pairs??[]).filter(p=>['1-3','2-4'].includes(p.pair)&&eligible(p)&&p.estimate_m!>known)
      .sort((a,b)=>Number(b.passed)-Number(a.passed)||a.spread_m!-b.spread_m!)[0];
    if(diagonal){
      const other=Math.sqrt(diagonal.estimate_m!**2-known**2);
      if(Number.isFinite(other)&&other>=.5&&other<=100){
        if(width==null)width=other;else height=other;
        inferred=true;
      }
    }
  }
  return {width,height,reference:true,inferred};
}
