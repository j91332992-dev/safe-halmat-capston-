"""Prepare a small, human-labeled PILOT, never a production accuracy claim."""
import argparse
import hashlib
import json
import random
import wave
from pathlib import Path
import numpy as np
import yaml
from mmap_ninja.ragged import RaggedMmap
from microwakeword.audio.audio_utils import generate_features_for_clip


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--holdout-session', help='Validation/test originals only from this new session; no augmented copies cross splits.')
    a=p.parse_args()
    labels=json.loads((a.data/'human_labels.json').read_text(encoding='utf-8'))
    groups={k:sorted(n for n,v in labels.items() if v==k) for k in ('positive','negative')}
    if len(groups['positive'])<6 or len(groups['negative'])<12:
        raise SystemExit('Pilot requires >=6 human-confirmed positives and >=12 negatives; do not replace with STT labels.')
    if a.output.exists():raise SystemExit('Use a new output directory to preserve earlier splits/models.')
    provenance={r['file']:r['source_session'] for r in json.loads((a.data/'provenance.json').read_text())} if a.holdout_session else {}
    a.output.mkdir(parents=True);manifest=[];seen=set()
    for label,names in groups.items():
        random.Random(20261016).shuffle(names)
        eligible=[n for n in names if provenance.get(n)==a.holdout_session] if a.holdout_session else names
        if len(eligible)<3:raise ValueError('Need at least 3 new labeled originals per class for holdout')
        test=max(1,min(len(names)//5,len(eligible)//3));valid=test
        heldout=eligible[:test+valid]
        splits={'testing':eligible[:test],'validation':eligible[test:test+valid],'training':[n for n in names if n not in heldout]}
        for split, files in splits.items():
            features=[]
            for name in files:
                if Path(name).name!=name:raise ValueError('Invalid filename')
                src=a.data/name;digest=hashlib.sha256(src.read_bytes()).hexdigest()
                if digest in seen:raise ValueError('Duplicate audio across dataset')
                seen.add(digest)
                with wave.open(str(src),'rb') as w:
                    if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('Audio format')
                    pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
                # Fresh frontend state for each original recording. No augmented
                # copies cross split boundaries. Held-out SPEAKERS still required.
                x=np.concatenate([np.zeros(8000,dtype=np.int16),pcm,np.zeros(1600,dtype=np.int16)])
                f=generate_features_for_clip(x, step_ms=10).astype(np.float32)
                features.append(f)
                manifest.append(dict(file=name,label=label,split=split,sha256=digest,feature_frames=len(f),source_session=provenance.get(name)))
            dst=a.output/label/split/'clips_mmap';dst.parent.mkdir(parents=True)
            RaggedMmap.from_generator(out_dir=str(dst),sample_generator=iter(features),batch_size=100,verbose=False)
    config=dict(window_step_ms=10,train_dir=str((a.output/'model').resolve()),features=[
        dict(features_dir=str((a.output/k).resolve()),sampling_weight=1.0,penalty_weight=1.0,truth=k=='positive',truncation_strategy='truncate_start',type='mmap') for k in groups],
        training_steps=[300],positive_class_weight=[1],negative_class_weight=[5],learning_rates=[.001],batch_size=16,
        time_mask_max_size=[0],time_mask_count=[0],freq_mask_max_size=[0],freq_mask_count=[0],
        eval_step_interval=50,clip_duration_ms=1500,target_minimization=.9,minimization_metric=None,maximization_metric='recall')
    (a.output/'training_parameters.yaml').write_text(yaml.safe_dump(config),encoding='utf-8')
    (a.output/'split_manifest.json').write_text(json.dumps(dict(status='PILOT_SINGLE_SESSION_NOT_DEPLOYABLE',files=manifest),indent=2),encoding='utf-8')
    print(json.dumps({k:len(v) for k,v in groups.items()}))

if __name__=='__main__':main()
