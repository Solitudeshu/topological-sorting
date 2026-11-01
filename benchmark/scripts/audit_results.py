"""Verify that archived inputs, repetitions and the measured C++ sources match the manifest."""
import argparse
import gzip
import hashlib
import json
import math
from build import ROOT
from summarize import read_csv

def audit(profile):
    folder=ROOT/'benchmark/results'/profile
    manifest=json.loads((folder/'manifest.json').read_text())
    env=json.loads((folder/'environment.json').read_text(encoding='utf-8'))
    for r in manifest:
        data=(ROOT/'benchmark/data'/profile/r['input']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==r['compressed_sha256'],r['workload']
        raw=gzip.decompress(data)
        assert hashlib.sha256(raw).hexdigest()==r['sha256'],r['workload']
        assert raw.splitlines()[1].decode()==f"{r['n']} {r['m0']} {r['q']}"
        timing=read_csv(folder/'raw'/r['workload']/'timing.csv')
        assert all(int(t['elapsed_ns'])>0 and int(t['batch'])>=1 for t in timing)
    for path,digest in env['source_sha256'].items():
        if path.endswith(('.cpp','.hpp')):
            assert hashlib.sha256((ROOT/path.replace('\\','/')).read_bytes()).hexdigest()==digest,path
    for row in read_csv(folder/'summary/summary.csv'):
        med=float(row['median_ns']);lo=float(row['q25_seed_ns']);hi=float(row['q75_seed_ns'])
        assert math.isfinite(med) and 0<lo<=med<=hi
    result=dict(passed=True,archived_inputs_verified=len(manifest),cpp_source_matches_measured_version=True,
                positive_timings=True,summary_quantiles_valid=True)
    (folder/'summary/audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],default='full');audit(p.parse_args().profile)
