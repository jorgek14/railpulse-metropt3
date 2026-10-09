#!/usr/bin/env python3
"""Etapa 4 - ciclos de pressurizacao e alertas causais (exploratorio).
Uso: python etapa4_ciclos.py --csv '/caminho/MetroPT3(AirCompressor).csv' --out pasta
Requer numpy e pandas; NAO pretende identificar o instante fisico verdadeiro de falha.
"""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
import pandas as pd

EVENTS={'F1':('2020-04-18 00:00','2020-04-18 23:59'),
        'F2':('2020-05-29 23:30','2020-05-30 06:00'),
        'F3':('2020-06-05 10:00','2020-06-07 14:30'),
        'F4':('2020-07-15 14:30','2020-07-15 19:00')}
TARGET=9.7 # bar, meta operacional exploratoria; nao e norma de fabricante
GAP_MAX=30.0
NOMINAL_START=(7.7,8.5)
CAL_START=pd.Timestamp('2020-05-01')
CAL_END=pd.Timestamp('2020-05-23')
TEST_START=pd.Timestamp('2020-05-23')


def build_cycles(raw):
    raw=raw.sort_values('timestamp',kind='stable').reset_index(drop=True)
    times=raw.timestamp.to_numpy(dtype='datetime64[ns]')
    dt=raw.timestamp.diff().dt.total_seconds().to_numpy()
    current=raw.Motor_current.to_numpy()
    pressure=raw.TP3.to_numpy()
    loaded=(current>2.0)&(raw.DV_eletric.to_numpy()>0.5)
    breaks=np.r_[True,(loaded[1:]!=loaded[:-1])|(dt[1:]>GAP_MAX)|(~np.isfinite(dt[1:]))|(dt[1:]<=0)]
    starts_all=np.flatnonzero(breaks)
    ends_all=np.r_[starts_all[1:]-1,len(raw)-1]
    mask=loaded[starts_all]
    starts=starts_all[mask]
    ends=ends_all[mask]
    n=len(raw)
    prev_idx=np.maximum(starts-1,0)
    next_idx=np.minimum(ends+1,n-1)
    # completas = observacoes anterior e posterior pertencem a outra fase, sem gap
    complete=(starts>0)&(ends<n-1)&(dt[starts].__ge__(0))&(dt[starts]<=GAP_MAX) & (dt[next_idx]>0)&(dt[next_idx]<=GAP_MAX) & (~loaded[prev_idx]) & (~loaded[next_idx])
    sec=(times[ends]-times[starts])/np.timedelta64(1,'s')
    start_p=pressure[starts];end_p=pressure[ends]
    segments=np.cumsum(breaks)
    hits=np.flatnonzero(loaded & (pressure>=TARGET))
    first=pd.DataFrame({'sid':segments[hits],'pos':hits}).groupby('sid',sort=False).pos.min()
    first_pos=first.reindex(segments[starts]).to_numpy(dtype=float)
    recovered=np.isfinite(first_pos)
    time_to=np.full(len(starts),np.nan)
    time_to[recovered]=(times[first_pos[recovered].astype(int)]-times[starts[recovered]])/np.timedelta64(1,'s')
    df=pd.DataFrame({'start':times[starts],'end':times[ends], 'duration_s':sec,
             'observations':ends-starts+1,'complete':complete,
             'pressure_start':start_p,'pressure_end':end_p,'pressure_gain':end_p-start_p,
             'current_mean': np.add.reduceat(current,starts_all)[mask]/(ends-starts+1),
             'oil_mean':np.add.reduceat(raw.Oil_temperature.to_numpy(),starts_all)[mask]/(ends-starts+1),
             'first_target_s':time_to,'target_observed':recovered})
    df['nominal_start']=df.pressure_start.between(*NOMINAL_START)
    df['eligible']=df.complete & df.nominal_start & (df.duration_s>=35)
    # Nunca usar duracao final para definir tempo de alerta! Ela pode terminar depois da falha.
    df['split']='other'
    df.loc[(df.start<'2020-05-01') & ~df.start.between('2020-04-16','2020-04-21'),'split']='train'
    df.loc[(df.start>=CAL_START)&(df.end<CAL_END),'split']='cal'
    df.loc[df.start>=TEST_START,'split']='test'
    return df,raw,starts,ends,loaded,times,pressure


def thresholds(cyc):
    cal=cyc[(cyc.split=='cal') &cyc.eligible]
    cal_hit=cal[cal.target_observed]
    assert len(cal)>=100 and len(cal_hit)>=100
    q_recovery=float(cal_hit.first_target_s.quantile(.99))
    q_duration=float(cal.duration_s.quantile(.99))
    return {'q99_tempo_ate_9_7_s':q_recovery,
            'q99_duracao_carga_s':q_duration,
            'n_ciclos_calibracao':len(cal),
            'n_calibracao_alcancaram_meta':len(cal_hit),
            'pct_sem_meta_na_calibracao':100*(1-len(cal_hit)/len(cal))}


def build_alerts(cyc,times,pressure,loaded,starts,ends,parameters):
    # Para cada episodio testado, gerar alerta apenas usando leituras ate aquele instante.
    # Comparadores: (1) tempo em carga >P99 duracao, (2) tempo em carga >P99 de recuperacao
    # e meta 9.7 bar ainda nao alcançada, (3) mesmissimo corte de recuperacao, carga apenas.
    specs=[('Carga_longa_q99',parameters['q99_duracao_carga_s'],False),
           ('Pressao_nao_recuperada_q99',parameters['q99_tempo_ate_9_7_s'],True),
           ('Somente_carga_mesmo_limiar',parameters['q99_tempo_ate_9_7_s'],False)]
    rows=[]
    for method,threshold,require_pressure in specs:
        for i,r in enumerate(cyc.itertuples()):
            if r.split!='test' or not r.nominal_start: continue
            # Em tempo real, basta observar inicio da carga, e nao conhecer seu fim.
            if r.duration_s<threshold:continue
            first_sample_idx=np.searchsorted(times, np.datetime64(r.start)+np.timedelta64(int(np.ceil(threshold*1000)),'ms'),'left')
            first_sample_idx=max(int(first_sample_idx),int(starts[i]))
            if first_sample_idx>int(ends[i]):continue
            # verificar tempo efetivo, evitar off-by-one
            if (times[first_sample_idx]-times[starts[i]])/np.timedelta64(1,'s')<threshold:continue
            if require_pressure and np.isfinite(r.first_target_s) and r.first_target_s <= (times[first_sample_idx]-times[starts[i]])/np.timedelta64(1,'s'):
                continue
            rows.append({'metodo':method,'inicio_carga':r.start,'alerta':pd.Timestamp(times[first_sample_idx]),
                    'pressao_no_alerta':float(pressure[first_sample_idx]),
                    'pressao_inicial':float(r.pressure_start),
                    'duracao_observada_ate_alerta_s':(times[first_sample_idx]-times[starts[i]])/np.timedelta64(1,'s'),
                    'termino_carga':r.end,'duracao_total_posteriormente_observada_s':r.duration_s,
                    'meta_9_7_alcancada_ate_alerta':bool(np.isfinite(r.first_target_s) and r.first_target_s<=(times[first_sample_idx]-times[starts[i]])/np.timedelta64(1,'s')),
                    'ciclo_completo_posteriormente':bool(r.complete)})
    return pd.DataFrame(rows)


def categorize(cycles,alerts):
    rows=[]
    for name,(ss,ee) in EVENTS.items():
        if name=='F1':continue
        start=pd.Timestamp(ss);end=pd.Timestamp(ee)
        for method,g in alerts.groupby('metodo'):
            pre=g[(g.alerta>=start-pd.Timedelta('2h'))&(g.alerta<start)]
            onset=g[(g.alerta>=start)&(g.alerta<=end)]
            first_pre=pre.alerta.min() if len(pre) else pd.NaT
            rows.append({'falha':name,'metodo':method,'inicio_documentado':start,
                         'primeiro_alerta_pre2h':first_pre,
                         'antecedencia_min':round((start-first_pre).total_seconds()/60,2) if pd.notna(first_pre) else np.nan,
                         'alertas_pre2h':len(pre),'alertas_durante':len(onset),
                         'inicio_carga_primeiro_pre2h':pre.sort_values('alerta').inicio_carga.iloc[0] if len(pre) else pd.NaT})
    evaluation=pd.DataFrame(rows)
    outside=[]
    for method,g in alerts.groupby('metodo'):
        near=np.zeros(len(g),dtype=bool)
        pre=np.zeros(len(g),dtype=bool)
        during=np.zeros(len(g),dtype=bool)
        for name,(ss,ee) in EVENTS.items():
            if name=='F1':continue
            start,end=pd.Timestamp(ss),pd.Timestamp(ee)
            near|=((g.alerta>=start-pd.Timedelta('2h'))&(g.alerta<=end+pd.Timedelta('24h'))).to_numpy()
            pre|=((g.alerta>=start-pd.Timedelta('2h'))&(g.alerta<start)).to_numpy()
            during|=((g.alerta>=start)&(g.alerta<=end)).to_numpy()
        # Em carga por dias, um alerta no início representa um episodio, nao alertas repetidos.
        outside.append({'metodo':method,'total_alertas_teste':len(g),
                'alertas_pre2h_falhas':int(pre.sum()),'alertas_durante_falhas':int(during.sum()),
                'alertas_fora_proximidades':int((~near).sum()),
                'eventos_com_alerta_pre2h':int((evaluation[(evaluation.metodo==method)].alertas_pre2h>0).sum()),
                'alertas_fora_por_30_dias':round(int((~near).sum())/(pd.Timestamp('2020-09-01')-TEST_START).days*30,2)})
    return evaluation,pd.DataFrame(outside)


def describe_cycles(cyc):
    """Atributos retrospectivos nao devem usar o termino futuro no PRE."""
    rows=[]
    for nm,(ss,ee) in EVENTS.items():
        start,end=pd.Timestamp(ss),pd.Timestamp(ee)
        for phase,a,b in [('pre2h',start-pd.Timedelta('2h'),start),('pre24h',start-pd.Timedelta('24h'),start),('durante',start,end)]:
            subset=cyc[cyc.nominal_start & (cyc.start>=a)&(cyc.start<b)]
            completed=subset[subset.complete&(subset.end<b)&(subset.duration_s>=35)]
            active=subset[(subset.start<b)&(subset.end>=b)]
            rows.append({'falha':nm,'periodo':phase,'n_inicio_carga':len(subset),
              'n_completos_ate_limite':len(completed),
              'duracao_mediana_concluidos_s':completed.duration_s.median(),
              'recuperacao_9_7_mediana_concluidos_s':completed.first_target_s.median(),
              'n_em_andamento_no_limite':len(active),
              'idade_carga_ativa_no_limite_min':((b-active.start).dt.total_seconds()/60).max() if len(active) else np.nan,
              'pressao_partida_mediana_bar':completed.pressure_start.median(),
              'temperatura_mediana_C':completed.oil_mean.median()})
    return pd.DataFrame(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    raw=pd.read_csv(a.csv,parse_dates=['timestamp'],usecols=['timestamp','TP3','Reservoirs','TP2','Oil_temperature','Motor_current','DV_eletric'])
    cyc,raw,st,en,load,times,pressure=build_cycles(raw)
    parms=thresholds(cyc)
    al=build_alerts(cyc,times,pressure,load,st,en,parms)
    ev,comparison=categorize(cyc,al)
    desc=describe_cycles(cyc)
    cyc.to_csv(a.out/'ciclos_carga.csv',index=False)
    al.to_csv(a.out/'alertas_ciclos.csv',index=False)
    ev.to_csv(a.out/'avaliacao_falhas.csv',index=False)
    comparison.to_csv(a.out/'comparacao_regras.csv',index=False)
    desc.to_csv(a.out/'perfis_antes_falhas.csv',index=False)
    sha=hashlib.sha256();
    with a.csv.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): sha.update(block)
    parms.update({'original_n':len(raw),'n_fases_carga':len(cyc),'n_ciclos_inicio_nominal_validos':int(cyc.eligible.sum()),
      'pressao_referencia_bar':TARGET,'estado_carga':'Motor_current>2A e DV_eletric>0.5',
      'max_intervalo_telemetria_s':GAP_MAX,'cal_periodo':'2020-05-01 ate 2020-05-22',
      'test_periodo':'2020-05-23 ate 2020-09-01', 'sha256_csv':sha.hexdigest(),
      'limite': 'Avaliação retrospectiva informada pelos eventos; meta e percentis não foram estabelecidos em um protocolo preregistrado. Falhas não rotuladas fora dos intervalos podem existir.'})
    (a.out/'parametros.json').write_text(json.dumps(parms,indent=2,ensure_ascii=False))
    print('DATASET',len(raw),'LOAD_RUNS',len(cyc),'VALID_CYCLES',int(cyc.eligible.sum()))
    print('CAL PARAMS',parms['q99_tempo_ate_9_7_s'],parms['q99_duracao_carga_s'],'CYCLES',parms['n_ciclos_calibracao'])
    print('COMPARISON\n',comparison.to_string(index=False))
    print('EVALUATION\n',ev.to_string(index=False))
    print('PREV 2h\n',desc[desc.periodo=='pre2h'].to_string(index=False))

if __name__=='__main__': main()
