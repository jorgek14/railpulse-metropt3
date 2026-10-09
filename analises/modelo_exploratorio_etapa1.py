"""Baseline exploratorio, nao se confunde com resultado final do artigo.
Python 3, pandas, numpy, scikit-learn. Executar com CSV original em /mnt/data.
"""
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument('--csv',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
import pandas as pd, numpy as np
from sklearn.ensemble import IsolationForest
P=a.csv
O=a.out
df=pd.read_csv(P,parse_dates=['timestamp'])
df=df.set_index('timestamp').sort_index()
events=[('F1','2020-04-18 00:00','2020-04-18 23:59'),('F2','2020-05-29 23:30','2020-05-30 06:00'),('F3','2020-06-05 10:00','2020-06-07 14:30'),('F4','2020-07-15 14:30','2020-07-15 19:00')]
analog=['TP2','TP3','H1','DV_pressure','Oil_temperature','Motor_current']
digital=['COMP','DV_eletric','Towers','MPG','LPS','Pressure_switch','Oil_level','Caudal_impulses']
df['motor_on']=(df.Motor_current>1).astype('float32')
# features calculadas apenas dos 10 minutos anteriores ao final da janela.
fns={x:['mean','std'] for x in analog}
fns.update({x:['mean'] for x in digital+['motor_on']})
fns['TP3']=['mean','std','min']
fns['Motor_current']=['mean','std','max']
g=df.resample('10min',label='right',closed='left').agg(fns)
g.columns=['_'.join(z) for z in g.columns]
g['n']=df['motor_on'].resample('10min',label='right',closed='left').count()
# disponibilidade por janela: ao menos 45/60 leituras e sem intervalo interno >60s.
step=df.index.to_series().diff().dt.total_seconds()
# descartar salto que atravessa o inicio de uma janela
bucket=df.index.floor('10min') + pd.Timedelta(minutes=10)
same_window=(bucket==pd.Series(bucket,index=df.index).shift(1))
step=step.where(same_window)
max_gap=step.groupby(bucket).max();g['maxgap']=max_gap
valid=(g.n>=45)&(g.maxgap<=60)
g=g.loc[valid].copy()
feats=[c for c in g.columns if c not in ['n','maxgap']]
g[feats]=g[feats].fillna(0.0)
train=g.index<pd.Timestamp('2020-02-20')
cal=(g.index>=pd.Timestamp('2020-02-20'))&(g.index<pd.Timestamp('2020-03-01'))
test=g.index>=pd.Timestamp('2020-03-01')
print('valid',len(g),'train',int(train.sum()),'cal',int(cal.sum()),'test',int(test.sum()), 'features',len(feats))
m=IsolationForest(n_estimators=120,max_samples=256,random_state=42,n_jobs=-1)
m.fit(g.loc[train,feats].to_numpy())
g['score']=-m.score_samples(g[feats].to_numpy())
threshold=g.loc[cal,'score'].quantile(.99)
g['anomaly']=g.score>threshold
print('threshold (99th cal)',float(threshold),'anomaly rate in test',g.loc[test,'anomaly'].mean())
# persistence 3 x 10-minute bins; with interval continuity.
episode_break = (g.anomaly != g.anomaly.shift(fill_value=False)) | (g.index.to_series().diff().dt.total_seconds()!=600)
g['episode_id']=episode_break.cumsum()
g['streak']=g.groupby('episode_id').cumcount()+1
g['alert']=g.anomaly & (g.streak>=3)
episodes=g.loc[g.anomaly].groupby('episode_id').agg(start=('score',lambda x:x.index.min()),end=('score',lambda x:x.index.max()),count=('score','size'),max_score=('score','max'))
episodes=episodes.loc[episodes['count']>=3].copy()
episodes['alert_time']=episodes.start+pd.Timedelta(minutes=20)
episodes=episodes.loc[episodes.alert_time>=pd.Timestamp('2020-03-01')]
print('episodes test',len(episodes))
for n,s,e in events:
    s,e=pd.Timestamp(s),pd.Timestamp(e)
    pre=g[(g.index>=s-pd.Timedelta(hours=2)) & (g.index<s)]
    during=g[(g.index>=s) & (g.index<=e)]
    hits=episodes[(episodes.alert_time>=s-pd.Timedelta(hours=2))&(episodes.alert_time<s)]
    print(n,'pre_windows',len(pre),'pre_anomal',int(pre.anomaly.sum()),'pre_alert',len(hits),'pre_first_alert',str(hits.alert_time.min()) if len(hits) else 'none','during_anomal',int(during.anomaly.sum()),'during_frac',round(float(during.anomaly.mean()),3) if len(during) else np.nan)
# alerts outside all (2h preceding .. 24h after) failures
mask_no_event=pd.Series(True,index=episodes.index)
for n,s,e in events:
 s,e=pd.Timestamp(s),pd.Timestamp(e)
 mask_no_event &= ~episodes.alert_time.between(s-pd.Timedelta(hours=2),e+pd.Timedelta(hours=24))
non=episodes.loc[mask_no_event]
# exposure counted days with any test available
ndays=g.loc[test].index.normalize().nunique()
print('episodes non-event',len(non),'valid observed days',ndays,'episodes/day',len(non)/ndays)
print('score q by subset',g.groupby(pd.cut(g.index, bins=[pd.Timestamp('2020-02-01'),pd.Timestamp('2020-03-01'),pd.Timestamp('2020-05-01'),pd.Timestamp('2020-07-01'),pd.Timestamp('2020-09-02')]),observed=True)['score'].agg(['median','mean']).round(3).to_string())
g.to_csv(O/'janelas_10min_baseline_exploratorio.csv',index_label='fim_janela')
episodes.to_csv(O/'alertas_baseline_exploratorio.csv',index_label='id_episodio')
with open(O/'resumo_baseline.txt','w') as f:
 f.write(f'janelas validas={len(g)}; treinamento={sum(train)}; calibracao={sum(cal)}; teste={sum(test)}\nlimiar={threshold}\nalertas fora dos eventos +/- janela={len(non)}; dias observados={ndays}\n')
