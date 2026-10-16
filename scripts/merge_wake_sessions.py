"""Merge only completed human labels, preserving provenance and source files."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--data', type=Path, nargs='+', required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if len({r.name for r in a.data}) != len(a.data):
    raise SystemExit('Session directory names must be unique')
if a.output.exists():
    raise SystemExit('Output exists; preserve previous datasets.')
rows, labels, hashes = [], {}, set()
for root in a.data:
    human = json.loads((root/'human_labels.json').read_text(encoding='utf-8'))
    files = sorted(root.glob('*.wav'))
    if any(f.name not in human for f in files):
        raise SystemExit(f'Unreviewed files remain: {root.name}')
    for f in files:
        label = human[f.name]
        if label not in ('positive', 'negative', 'discard'):
            raise ValueError('Unknown label')
        if label == 'discard': continue
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        if digest in hashes: raise ValueError('Duplicate recording')
        hashes.add(digest)
        name = root.name + '__' + f.name
        rows.append(dict(source_session=root.name, source_file=f.name,
                         file=name, sha256=digest, label=label))
        labels[name] = label
a.output.mkdir(parents=True)
for root in a.data:
    for row in rows:
        if row['source_session'] == root.name:
            shutil.copyfile(root/row['source_file'], a.output/row['file'])
(a.output/'human_labels.json').write_text(json.dumps(labels, indent=2), encoding='utf-8')
(a.output/'provenance.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps({k: sum(v == k for v in labels.values()) for k in ('positive','negative')}))
