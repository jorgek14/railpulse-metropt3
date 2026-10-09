#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd,numpy as np
from etapa4_ciclos import build_cycles,thresholds,build_alerts,EVENTS

def verify(csv,out):
    calpar=pd.read_json(out/'parametros.json',typ='series')
    cyc=pd.read_csv(out/'ciclos_carga.csv',parse_dates=['start','end'])
    alarms=pd.read_csv(out/'alertas_ciclos.csv',parse_dates=['inicio_carga','alerta'])
    assert len(cyc)==15769 and len(alarms)>0
    assert ((alarms.alerta>=alarms.inicio_carga)&(alarms.alerta>=pd.Timestamp('2020-05-23'))).all()
    assert not alarms.meta_9_7_alcancada_ate_alerta.loc[alarms.metodo=='Pressao_nao_recuperada_q99'].any()
    assert cyc.loc[cyc.split=='cal','start'].lt('2020-05-23').all()
    assert cyc.loc[cyc.split=='test','start'].ge('2020-05-23').all()
    # Prefix invariance tests: recomputar o mesmo algoritmo em bases truncadas sem futuro.
    raw=pd.read_csv(csv,parse_dates=['timestamp'],usecols=['timestamp','TP3','Reservoirs','TP2','Oil_temperature','Motor_current','DV_eletric'])
    for event, cutoff in [('F2','2020-05-29 23:25:00'),('F3','2020-06-05 09:56:00'),('F4','2020-07-15 14:29:00')]:
        dt=pd.Timestamp(cutoff)
        prefix=raw[raw.timestamp<=dt].copy()
        pc,_,st,en,lo,ts,pr=build_cycles(prefix)
        pth=thresholds(pc)
        assert np.isclose(pth['q99_tempo_ate_9_7_s'],calpar['q99_tempo_ate_9_7_s'])
        assert np.isclose(pth['q99_duracao_carga_s'],calpar['q99_duracao_carga_s'])
        pa=build_alerts(pc,ts,pr,lo,st,en,pth)
        # Compare apenas timestamps de alertas, nao duracao retrospectiva de ciclos.
        ori=alarms.loc[alarms.alerta<=dt,['metodo','alerta']].sort_values(['metodo','alerta']).reset_index(drop=True)
        act=pa.loc[pa.alerta<=dt,['metodo','alerta']].sort_values(['metodo','alerta']).reset_index(drop=True)
        pd.testing.assert_frame_equal(ori,act,check_dtype=False)
        print('PASS causal_prefix',event,cutoff,'n_alerts',len(act))
    print('PASS temporal_split_and_pressure')
    print('PASS dataset_integrity',len(raw),'records',len(cyc),'loaded episodes')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();verify(a.csv,a.out)
