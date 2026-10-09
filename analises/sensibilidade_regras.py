"""Análise complementar exploratória do limiar temporal, SEM otimização sobre eventos de teste.
Reutiliza o extrator da Etapa 4, preservando 9,7 bar e faixa 7,7–8,5 bar.
"""
from pathlib import Path
import argparse
import numpy as np, pandas as pd
import etapa4_ciclos as e
parser=argparse.ArgumentParser(description='Sensibilidade pós-hoc para R1 (P95/P97.5/P99)')
parser.add_argument('--csv',type=Path,required=True,help='MetroPT3(AirCompressor).csv original')
parser.add_argument('--out',type=Path,required=True,help='Diretório de saída')
a=parser.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
raw=pd.read_csv(a.csv,parse_dates=['timestamp'],usecols=['timestamp','TP3','Reservoirs','TP2','Oil_temperature','Motor_current','DV_eletric'])
cyc,raw,st,en,load,times,pressure=e.build_cycles(raw)
cal=cyc[(cyc.split=='cal') &cyc.eligible &cyc.target_observed]
rows=[]; alerts_out=[]
for q in [0.95,0.975,0.99]:
    threshold=float(cal.first_target_s.quantile(q))
    aa=e.build_alerts(cyc,times,pressure,load,st,en,{'q99_duracao_carga_s':337.12,'q99_tempo_ate_9_7_s':threshold})
    aa=aa[aa.metodo=='Pressao_nao_recuperada_q99'].copy()
    events=e.EVENTS
    near=np.zeros(len(aa),dtype=bool)
    pre=np.zeros(len(aa),dtype=bool)
    hits={}
    for key in ['F2','F3','F4']:
        t0,t1=map(pd.Timestamp,events[key])
        window=(aa.alerta>=t0-pd.Timedelta('2h'))&(aa.alerta<t0)
        hits[key]=int(window.sum())
        pre|=window.to_numpy()
        near|=((aa.alerta>=t0-pd.Timedelta('2h'))&(aa.alerta<=t1+pd.Timedelta('24h'))).to_numpy()
    rows.append({'percentil_calibracao':q,'limiar_segundos':threshold,'alertas_total':len(aa),'alertas_pre2h':int(pre.sum()),'alertas_fora_proximidades':int((~near).sum()),'eventos_pre2h':sum(1 for v in hits.values() if v>0),**{f'alertas_pre_{k}':v for k,v in hits.items()}})
    alerts_out.append(aa.assign(percentil_calibracao=q,limiar_segundos=threshold))
out=a.out
pd.DataFrame(rows).to_csv(out/'sensibilidade_temporal_exploratoria.csv',index=False)
pd.concat(alerts_out).to_csv(out/'alertas_sensibilidade_temporal.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))
print('Checagem P99 esperada: total=33, pre2h=13, fora=20')
