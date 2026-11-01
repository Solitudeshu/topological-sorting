"""Replay archived inputs without regenerating or overwriting the published results."""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
from build import ROOT
from run_benchmarks import environment

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workload',default='dynamic_local_small_n10000_m50000_q200_s11',help='manifest workload name, or all')
    parser.add_argument('--repeats',type=int,default=10)
    parser.add_argument('--warmups',type=int,default=3)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'benchmark/results/full/manifest.json').read_text())
    selected=[r for r in manifest if args.workload in ['all',r['workload']]]
    if not selected:raise SystemExit('Workload not found in full/manifest.json')
    exe=ROOT/'benchmark/build'/('topo_bench.exe' if os.name=='nt' else 'topo_bench')
    out=ROOT/'benchmark/results/replay';out.mkdir(parents=True,exist_ok=True)
    (out/'environment.json').write_text(json.dumps(environment(exe,'replay',args.repeats,args.warmups),indent=2,ensure_ascii=False),encoding='utf-8')
    cache=ROOT/'benchmark/_cache/replay';cache.mkdir(parents=True,exist_ok=True)
    for r in selected:
        raw=gzip.decompress((ROOT/'benchmark/data/full'/r['input']).read_bytes())
        assert hashlib.sha256(raw).hexdigest()==r['sha256']
        path=cache/(r['workload']+'.dag');path.write_bytes(raw)
        subprocess.run([str(exe),'--input',str(path),'--out',str(out/r['workload']),
                        '--repeats',str(args.repeats),'--warmups',str(args.warmups)],check=True,cwd=ROOT)
    print(f'Published results unchanged. New measurements: {out}')

if __name__=='__main__':main()
