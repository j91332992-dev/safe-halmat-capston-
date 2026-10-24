"""Analyze orientation-only trial recordings without changing runtime settings."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics as stats


def quantile(values, q):
    if not values:
        return None
    a=sorted(values); p=(len(a)-1)*q; lo=math.floor(p); hi=math.ceil(p)
    return a[lo]+(a[hi]-a[lo])*(p-lo)


def gravity(row):
    pitch,roll=map(math.radians,(row['pitch_deg'],row['roll_deg']))
    return (-math.sin(pitch),math.sin(roll)*math.cos(pitch),math.cos(roll)*math.cos(pitch))


def mean_gravity(rows):
    v=[stats.mean(g[i] for g in map(gravity,rows)) for i in range(3)]
    norm=math.sqrt(sum(x*x for x in v))
    return [x/norm for x in v]


def sustained(rows, threshold):
    # Supported intervals only: do not infer posture across >250ms gaps.
    longest=run=total=0.
    for a,b in zip(rows,rows[1:]):
        delta=b['elapsed_s']-a['elapsed_s']
        if 0<delta<=.25 and a['relative_tilt_deg']>=threshold and b['relative_tilt_deg']>=threshold:
            run+=delta; total+=delta; longest=max(longest,run)
        else:
            run=0.
    return total,longest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('session',type=Path)
    args=parser.parse_args(); folder=args.session.resolve()
    rows=[json.loads(line) for line in (folder/'samples.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    trials=json.loads((folder/'trials.json').read_text(encoding='utf-8-sig'))
    results=[]; all_gaps=[]; all_source_gaps=[]; gap_mismatch=[]; receive_delays=[]
    for trial in trials:
        samples=[r for r in rows if r['trial']==trial['number']]
        if not samples: continue
        gaps=[b['elapsed_s']-a['elapsed_s'] for a,b in zip(samples,samples[1:])]
        all_gaps.extend(gaps)
        for a,b in zip(samples,samples[1:]):
            source=(datetime.fromisoformat(b['server_received_at'].replace('Z','+00:00'))-
                    datetime.fromisoformat(a['server_received_at'].replace('Z','+00:00'))).total_seconds()
            all_source_gaps.append(source)
            gap_mismatch.append(abs(source-(b['elapsed_s']-a['elapsed_s']))*1000)
        for row in samples:
            receive_delays.append((datetime.fromisoformat(row['received_at'])-
                datetime.fromisoformat(row['server_received_at'].replace('Z','+00:00'))).total_seconds()*1000)
        first=[r for r in samples if r['elapsed_s']<=samples[0]['elapsed_s']+1]
        last=[r for r in samples if r['elapsed_s']>=samples[-1]['elapsed_s']-1]
        g1,g2=mean_gravity(first),mean_gravity(last)
        return_difference=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(g1,g2))))))
        peak=max(r['relative_tilt_deg'] for r in samples)
        span=samples[-1]['elapsed_s']-samples[0]['elapsed_s']
        yaw_unwrapped=[samples[0]['yaw_deg']]
        for a,b in zip(samples,samples[1:]):
            yaw_unwrapped.append(yaw_unwrapped[-1]+(b['yaw_deg']-a['yaw_deg']+180)%360-180)
        r=dict(number=trial['number'],label=trial['label'],samples=len(samples),
            nominal_hz=len(samples)/trial['duration_s'],observed_span_s=span,
            first_at=samples[0]['received_at'],last_at=samples[-1]['received_at'],
            first_median_tilt_deg=stats.median(x['relative_tilt_deg'] for x in first),
            last_median_tilt_deg=stats.median(x['relative_tilt_deg'] for x in last),
            return_pose_difference_deg=return_difference,peak_tilt_deg=peak,
            yaw_unwrapped_span_deg=max(yaw_unwrapped)-min(yaw_unwrapped),
            pitch_min_deg=min(x['pitch_deg'] for x in samples),pitch_max_deg=max(x['pitch_deg'] for x in samples),
            roll_min_deg=min(x['roll_deg'] for x in samples),roll_max_deg=max(x['roll_deg'] for x in samples),
            gap_median_ms=quantile(gaps,.5)*1000,gap_p95_ms=quantile(gaps,.95)*1000,
            gap_max_ms=max(gaps)*1000,gaps_over_250ms=sum(g>.25 for g in gaps),
            gaps_over_500ms=sum(g>.5 for g in gaps),gaps_over_1000ms=sum(g>1 for g in gaps),
            unsupported_gap_time_s=sum(g for g in gaps if g>.25),
            count_matches_trial_record=len(samples)==trial['samples'])
        for angle in (45,60,70,80,90):
            total,longest=sustained(samples,angle)
            r[f'above_{angle}_supported_s']=total
            r[f'above_{angle}_longest_supported_s']=longest
        results.append(r)
    groups=[]
    for label in dict.fromkeys(r['label'] for r in results):
        g=[r for r in results if r['label']==label]
        groups.append(dict(label=label,trials=len(g),samples=sum(r['samples'] for r in g),
            nominal_hz=sum(r['samples'] for r in g)/(10*len(g)),
            peak_min_deg=min(r['peak_tilt_deg'] for r in g),peak_median_deg=stats.median(r['peak_tilt_deg'] for r in g),
            peak_max_deg=max(r['peak_tilt_deg'] for r in g),
            return_difference_median_deg=stats.median(r['return_pose_difference_deg'] for r in g),
            return_difference_max_deg=max(r['return_pose_difference_deg'] for r in g),
            max_gap_ms=max(r['gap_max_ms'] for r in g),gaps_over_250ms=sum(r['gaps_over_250ms'] for r in g)))
    summary=dict(session=str(folder),trials=len(results),label_counts=dict(Counter(r['label'] for r in results)),
        saved_rows=len(rows),trial_rows=sum(r['samples'] for r in results),between_trial_rows=sum(r['trial']==0 for r in rows),
        all_trial_counts_match=all(r['count_matches_trial_record'] for r in results),
        nominal_trial_seconds=sum(t['duration_s'] for t in trials),
        gap_intervals=len(all_gaps),gap_median_ms=quantile(all_gaps,.5)*1000,
        gap_p95_ms=quantile(all_gaps,.95)*1000,gap_p99_ms=quantile(all_gaps,.99)*1000,
        max_gap_ms=max(all_gaps)*1000,gaps_over_250ms=sum(g>.25 for g in all_gaps),
        gaps_over_500ms=sum(g>.5 for g in all_gaps),gaps_over_1000ms=sum(g>1 for g in all_gaps),
        unsupported_gap_time_s=sum(g for g in all_gaps if g>.25),
        source_gap_p95_ms=quantile(all_source_gaps,.95)*1000,
        pc_source_gap_difference_p95_ms=quantile(gap_mismatch,.95),
        server_to_collector_delay_median_ms=quantile(receive_delays,.5),
        server_to_collector_delay_p95_ms=quantile(receive_delays,.95),groups=groups,per_trial=results,
        limitations=['Orientation only; no measured acceleration/gyro/impact, no fall ground truth.',
            'Four repetitions per labeled movement from one session; no held-out validation.',
            'Dashboard coalescing and accepted-server time are not sensor sequence/timestamp evidence.',
            'Durations require both endpoints above threshold and gap <=250ms; larger gaps are unknown.',
            'Return difference compares first/last 1s in fixed 10s windows, not externally marked motion start/end.'])
    normal=[r for r in results if '매트' not in r['label']]
    posture=[r for r in results if '매트' in r['label']]
    summary['descriptive_threshold_counts']={str(t):dict(normal_trials_with_peak_ge=sum(r['peak_tilt_deg']>=t for r in normal),
        normal_trials=len(normal),mat_posture_trials_with_peak_ge=sum(r['peak_tilt_deg']>=t for r in posture),
        mat_posture_trials=len(posture)) for t in (45,60,70,80,90)}
    (folder/'analysis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    with (folder/'trial_metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    english=['Head bend','Side tilt','Sit / stand','Mat posture','Walk / stop']
    colors=['#db8824','#5686be','#4b9b7b','#9560ae','#597565']
    color_map=dict(zip((g['label'] for g in groups),colors))
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    numbers=[r['number'] for r in results]
    axes[0].bar(numbers,[r['peak_tilt_deg'] for r in results],color=[color_map[r['label']] for r in results])
    axes[0].axhline(45,color='#ae3d38',linestyle='--',label='45 degrees (reference only)')
    axes[0].axhline(60,color='#333',linestyle=':',label='60 degrees (reference only)')
    axes[0].set(ylabel='Peak relative tilt (degrees)',title='HANMIR: 20 orientation-only trials (not fall detection accuracy)');axes[0].legend(loc='upper left',fontsize=8)
    axes[1].bar(numbers,[r['gap_max_ms'] for r in results],color=[color_map[r['label']] for r in results])
    axes[1].axhline(250,color='#ae3d38',linestyle='--',label='250 ms evidence-gap reference')
    axes[1].set(ylabel='Maximum within-trial receipt gap (ms)',xlabel='Trial number',xticks=numbers);axes[1].legend(fontsize=8)
    fig.savefig(folder/'trial_summary.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(5,1,figsize=(11,11),sharex=True,layout='constrained')
    for ax,g,title,color in zip(axes,groups,english,colors):
        for r in results:
            if r['label']!=g['label']:continue
            samples=[s for s in rows if s['trial']==r['number']]
            # Break lines over long unobserved gaps instead of interpolating.
            xs=[];ys=[];last=None
            for sample in samples:
                if last is not None and sample['elapsed_s']-last>.25:xs.append(float('nan'));ys.append(float('nan'))
                xs.append(sample['elapsed_s']-samples[0]['elapsed_s']);ys.append(sample['relative_tilt_deg']);last=sample['elapsed_s']
            ax.plot(xs,ys,label=f"trial {r['number']}",alpha=.8)
        ax.set(ylabel='Tilt (degrees)',title=title);ax.legend(ncol=4,fontsize=8);ax.grid(alpha=.2)
    axes[-1].set_xlabel('Seconds from first received sample in trial')
    fig.savefig(folder/'tilt_traces.png',dpi=150);plt.close(fig)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('per_trial','limitations')},ensure_ascii=True,indent=2))


if __name__=='__main__':main()
