from pathlib import Path
import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime,timezone,timedelta
from build import ROOT,build
from workloads import specifications,save

def command_output(command):
    return subprocess.run(command,cwd=ROOT,text=True,capture_output=True,check=False).stdout.strip()

def environment(exe,profile,repeats,warmups):
    cpu=platform.processor();ram=None
    if os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as k:
            cpu=winreg.QueryValueEx(k,'ProcessorNameString')[0].strip()
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ['physical','available','page','available_page','virtual','available_virtual','extended']]
        info=Memory();info.length=ctypes.sizeof(info)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):ram=info.physical
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
             for folder in ['benchmark/include','benchmark/src','benchmark/tests','benchmark/scripts']
             for p in sorted((ROOT/folder).glob('*')) if p.suffix in ['.hpp','.cpp','.py']}
    return dict(timestamp=datetime.now(timezone(timedelta(hours=7))).isoformat(),timezone='Asia/Ho_Chi_Minh',
                cpu=cpu,logical_cpus=os.cpu_count(),ram_bytes=ram,platform=platform.platform(),
                python=sys.version,compiler=command_output([shutil.which('g++') or 'clang++','--version']),
                build_flags=['-std=c++17','-O3','-DNDEBUG','-Wall','-Wextra','-Wpedantic'],
                git_source_commit=command_output(['git','rev-parse','HEAD']),
                executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),source_sha256=sources,
                packages={p:importlib.metadata.version(p) for p in ['numpy','matplotlib','networkx']},
                profile=profile,repeats=repeats,warmups=warmups,threads=1,
                timer='std::chrono::steady_clock',static_target_batch_ns=3000000,
                algorithm_order='seeded shuffle (7301) each repetition',
                memory='capacity-based vector payload, instrumented separately; not process peak RAM',
                power_scheme=command_output(['powercfg','/getactivescheme']) if os.name=='nt' else None)

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],default='quick')
    p.add_argument('--skip-build',action='store_true');p.add_argument('--limit',type=int)
    args=p.parse_args()
    if not args.skip_build:build()
    exe=ROOT/'benchmark/build'/('topo_bench.exe' if os.name=='nt' else 'topo_bench')
    dest=ROOT/'benchmark/results'/args.profile;dest.mkdir(parents=True,exist_ok=True)
    inputs=ROOT/'benchmark/data'/args.profile;cache=ROOT/'benchmark/_cache'/args.profile;cache.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'benchmark/configs'/f'{args.profile}.json').read_text())
    repeats,warmups=cfg['repeats'],cfg['warmups']
    (dest/'environment.json').write_text(json.dumps(environment(exe,args.profile,repeats,warmups),indent=2,ensure_ascii=False),encoding='utf-8')
    specs=specifications(args.profile)
    if args.limit:specs=specs[:args.limit]
    manifest=[]
    for i,spec in enumerate(specs):
        record,data=save(spec,inputs);manifest.append(record)
        (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        raw=cache/(record['workload']+'.dag');raw.write_bytes(data)
        output=dest/'raw'/record['workload']
        subprocess.run([str(exe),'--input',str(raw),'--out',str(output),'--repeats',str(repeats),'--warmups',str(warmups)],check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
        print(f"[{i+1}/{len(specs)}] {record['workload']}",flush=True)
    print(f'Completed {len(manifest)} workloads: {dest}',flush=True)

if __name__=='__main__':main()
