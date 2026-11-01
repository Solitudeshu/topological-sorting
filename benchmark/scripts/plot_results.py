from pathlib import Path
import argparse
import os
from build import ROOT
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'benchmark/_cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import ScalarFormatter
import numpy as np
from summarize import read_csv

NAMES={'kahn_fifo':'Kahn FIFO','dfs_iterative':'DFS lặp','kahn_recompute':'Kahn tính lại','kahn_guarded':'Kahn kiểm tra trước','incremental_rpo':'Cập nhật cục bộ'}
COLORS={'kahn_fifo':'#536A7B','dfs_iterative':'#B77C54','kahn_recompute':'#536A7B','kahn_guarded':'#A4ACB3','incremental_rpo':'#B77C54'}
CASES=['forward','local_small','local_large','cycle','window_only','mixed']
LABELS=['Cạnh xuôi','Vùng nhỏ','Vùng lớn','Chu trình','W lớn, F nhỏ','Hỗn hợp']

def prepare():
    font=Path('C:/Windows/Fonts/segoeui.ttf')
    if font.exists():font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({'font.family':'Segoe UI' if font.exists() else 'DejaVu Sans','font.size':11,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#888888',
                         'axes.labelcolor':'#303030','text.color':'#303030','xtick.color':'#505050',
                         'ytick.color':'#505050','svg.fonttype':'none','savefig.facecolor':'white',
                         'axes.titleweight':'normal','legend.frameon':False})

def save(fig,dest,name):
    fig.savefig(dest/(name+'.png'),dpi=300,bbox_inches='tight')
    fig.savefig(dest/(name+'.svg'),bbox_inches='tight');plt.close(fig)

def numeric(rows):
    for row in rows:
        for k in row:
            if k not in ['benchmark','family','algorithm','baseline']:
                row[k]=float(row[k])
    return rows

def one(rows,**kwargs):
    found=[r for r in rows if all(r[k]==v for k,v in kwargs.items())]
    if len(found)!=1:raise ValueError((kwargs,len(found)))
    return found[0]

def line_iqr(ax,items,algorithm,xfield,scale=1):
    items=sorted(items,key=lambda r:r[xfield]);x=[r[xfield] for r in items]
    med=np.array([r['median_ns']/scale for r in items]);lo=np.array([r['q25_seed_ns']/scale for r in items]);hi=np.array([r['q75_seed_ns']/scale for r in items])
    ax.plot(x,med,marker='o',color=COLORS[algorithm],label=NAMES[algorithm],linewidth=1.8,markersize=5)
    ax.fill_between(x,lo,hi,color=COLORS[algorithm],alpha=.14,linewidth=0)
    ax.grid(axis='y',color='#E7E7E7',linewidth=.7);ax.set_axisbelow(True)

def plot(profile):
    prepare();base=ROOT/'benchmark/results'/profile;dest=base/'figures';dest.mkdir(parents=True,exist_ok=True)
    rows=numeric(read_csv(base/'summary/summary.csv'));speed=numeric(read_csv(base/'summary/speedups.csv'))
    n=max(r['n'] for r in rows if r['benchmark']=='dynamic');m=5*n
    fig,axs=plt.subplots(1,2,figsize=(11.6,4.2),layout='constrained')
    for alg in ['kahn_fifo','dfs_iterative']:
        items=[r for r in rows if r['family']=='sparse5' and r['algorithm']==alg]
        line_iqr(axs[0],items,alg,'n',1e6)
        dense=[r for r in rows if r['family']=='dense' and r['n']==1000 and r['algorithm']==alg]
        if not dense:dense=[r for r in rows if r['family']=='dense' and r['algorithm']==alg]
        for r in dense:r['density_percent']=100*2*r['m0']/(r['n']*(r['n']-1))
        line_iqr(axs[1],dense,alg,'density_percent',1e6)
    axs[0].set(xlabel='Số đỉnh n (m = 5n)',ylabel='Thời gian mỗi lần (ms)',title='(a) Tăng quy mô DAG thưa',xscale='log',yscale='log')
    axs[1].set(xlabel='Mật độ DAG (%)',ylabel='Thời gian mỗi lần (ms)',title='(b) Thay đổi mật độ, n cố định')
    for ax in axs:ax.legend()
    save(fig,dest,'Hinh_7_1_Topo_tinh')
    algorithms=['kahn_recompute','kahn_guarded','incremental_rpo']
    chosen={(family,alg):one(rows,benchmark='dynamic',family=family,n=n,m0=0 if family=='window_only' else m,algorithm=alg) for family in CASES for alg in algorithms}
    fig,ax=plt.subplots(figsize=(11.8,4.8),layout='constrained');x=np.arange(len(CASES));width=.24
    for j,alg in enumerate(algorithms):
        rr=[chosen[(family,alg)] for family in CASES];med=np.array([r['median_ns']/1000 for r in rr])
        err=np.array([[r['median_ns']/1000-r['q25_seed_ns']/1000 for r in rr],[r['q75_seed_ns']/1000-r['median_ns']/1000 for r in rr]])
        ax.bar(x+(j-1)*width,med,width,label=NAMES[alg],color=COLORS[alg],yerr=err,capsize=2,error_kw={'linewidth':.8})
    ax.set(xticks=x,xticklabels=LABELS,ylabel='Thời gian trung bình mỗi yêu cầu (µs, trục log)',yscale='log',title=f'n = {int(n):,}; m₀ = 5n, riêng W lớn F nhỏ có m₀ = 0')
    ax.grid(axis='y',color='#E7E7E7',linewidth=.7);ax.set_axisbelow(True);ax.legend(ncol=3,loc='upper left')
    save(fig,dest,'Hinh_7_2_Thoi_gian_cap_nhat')
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for j,alg in enumerate(algorithms):
        values=[chosen[(family,alg)]['edge_checks'] for family in CASES[:5]]
        axs[0].bar(np.arange(5)+(j-1)*width,values,width,color=COLORS[alg],label=NAMES[alg])
    axs[0].set(xticks=np.arange(5),xticklabels=LABELS[:5],ylabel='Số phần tử danh sách kề được xét / yêu cầu',title='(a) Công việc duyệt cạnh')
    small=['local_small','local_large','window_only']
    for j,(metric,label,color) in enumerate([('vertices','Đỉnh tìm kiếm','#536A7B'),('order_writes','Vị trí được ghi','#B77C54')]):
        values=[chosen[(f,'incremental_rpo')][metric] for f in small]
        bars=axs[1].bar(np.arange(3)+(j-.5)*.3,values,.3,label=label,color=color)
        axs[1].bar_label(bars,labels=[f'{v:,.0f}' for v in values],padding=3,fontsize=9)
    axs[1].set(xticks=np.arange(3),xticklabels=['Vùng nhỏ','Vùng lớn','W lớn, F nhỏ'],ylabel='Số lượng trung bình / yêu cầu',title='(b) Tìm kiếm và ghi cửa sổ của cập nhật cục bộ')
    for ax in axs:ax.grid(axis='y',color='#E7E7E7',linewidth=.7);ax.set_axisbelow(True);ax.legend(fontsize=9)
    save(fig,dest,'Hinh_7_3_Luong_cong_viec')
    if profile=='full':
        fig,axs=plt.subplots(1,2,figsize=(11.6,4.2),layout='constrained')
        for family,color,label in [('local_small','#536A7B','Vùng nhỏ'),('local_large','#B77C54','Vùng lớn'),('window_only','#727A60','W lớn, F nhỏ')]:
            items=sorted([r for r in speed if r['family']==family and r['baseline']=='kahn_recompute' and r['m0']==(0 if family=='window_only' else 5*r['n'])],key=lambda r:r['n'])
            axs[0].plot([r['n'] for r in items],[r['median_speedup'] for r in items],marker='o',color=color,label=label)
        items=sorted([r for r in speed if r['family']=='local_large' and r['baseline']=='kahn_recompute' and r['n']==1000],key=lambda r:r['m0'])
        axs[1].plot([100*2*r['m0']/(1000*999) for r in items],[r['median_speedup'] for r in items],marker='o',color='#B77C54')
        axs[0].set(xlabel='Số đỉnh n (m₀ = 5n, trừ trường hợp ghi chú)',ylabel='Hệ số tăng tốc so với Kahn tính lại',title='(a) Ảnh hưởng của quy mô',yscale='log')
        axs[1].set(xlabel='Mật độ ban đầu (%)',ylabel='Hệ số tăng tốc so với Kahn tính lại',title='(b) Sửa vùng lớn, n = 1.000')
        for ax in axs:ax.axhline(1,color='#888888',linestyle='--',linewidth=1);ax.grid(axis='y',color='#E7E7E7',linewidth=.7);ax.set_axisbelow(True)
        axs[0].legend();save(fig,dest,'Hinh_7_4_Quy_mo_va_mat_do')
    print(f'Figures: {dest}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],default='full');plot(p.parse_args().profile)
