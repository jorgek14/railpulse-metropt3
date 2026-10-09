#!/usr/bin/env python3
"""MetroPT-3, etapa 2: comparação pré-definida de Isolation Forest global versus
condicionado a regimes. Análise exploratória e temporal, não validação prospectiva.

A execução utiliza features de janelas de 10 minutos produzidas pelo script da
etapa 1 (modelo_exploratorio.py). Somente as features são reutilizadas; escores,
rótulos e alertas da etapa 1 são descartados e recalculados. Nenhuma informação
de falhas futuras é utilizada em treino, salvo exclusão da primeira falha do treino.
"""
from pathlib import Path
import argparse
p=argparse.ArgumentParser()
p.add_argument('--windows',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

INPUT = a.windows
OUT = a.out
OUT.mkdir(parents=True,exist_ok=True)
RANDOM_STATE=42
PER=0.99
STREAK=3
EVENTS={
    'F1 (desenvolvimento)': ('2020-04-18 00:00','2020-04-18 23:59'),
    'F2':('2020-05-29 23:30','2020-05-30 06:00'),
    'F3':('2020-06-05 10:00','2020-06-07 14:30'),
    'F4':('2020-07-15 14:30','2020-07-15 19:00'),
}

def episodes_from_scores(g, model_name):
    df=g.loc[g['split']=='test'].copy()
    flag=df[f'{model_name}_anomaly'].fillna(False).astype(bool)
    dt=df.index.to_series().diff().dt.total_seconds()
    brk=(flag!=flag.shift(fill_value=False))|(dt!=600)
    blocks=brk.cumsum()
    z=df.loc[flag].assign(block=blocks.loc[flag].to_numpy())
    ep=z.groupby('block', sort=False).agg(
        start=('regime',lambda x:x.index.min()),
        end=('regime',lambda x:x.index.max()),
        bins=('regime','size'),
        max_score=(f'{model_name}_score','max'),
        regime_start=('regime','first'))
    ep=ep[ep.bins>=STREAK].copy()
    ep['alert_time']=ep['start']+pd.Timedelta(minutes=10*(STREAK-1))
    ep['model']=model_name
    return ep

def metrics(g, eps, name):
    test=g.loc[g.split=='test']
    exclusion=pd.Series(False,index=test.index)
    for k,(ss,ee) in EVENTS.items():
        if k.startswith('F1'):continue
        ss=pd.Timestamp(ss);ee=pd.Timestamp(ee)
        exclusion |= (test.index >= ss-pd.Timedelta(hours=2))&(test.index <= ee+pd.Timedelta(hours=24))
    vday=test.index.normalize().nunique()
    day_no_event=test.index[~exclusion].normalize().nunique()
    ep_exclusion=pd.Series(False,index=eps.index)
    for k,(ss,ee) in EVENTS.items():
        if k.startswith('F1'):continue
        ss=pd.Timestamp(ss); ee=pd.Timestamp(ee)
        ep_exclusion |= eps['alert_time'].between(ss-pd.Timedelta(hours=2),ee+pd.Timedelta(hours=24))
    n_non=(~ep_exclusion).sum()
    res={'modelo':name,'janelas_teste':len(test),'anomalias_janelas':int(test[f'{name}_anomaly'].sum()),
         'taxa_anomalias_pct':float(100*test[f'{name}_anomaly'].mean()),
         'episodios_total':len(eps),'episodios_fora_eventos':int(n_non),
         'dias_observados':int(vday),'dias_fora_eventos':int(day_no_event),
         'alertas_dia_observado':float(n_non/day_no_event),
         'cal_anomalias_pct':float(100*g.loc[((g.index>=pd.Timestamp('2020-02-20'))&(g.index<pd.Timestamp('2020-03-01'))) if name=='global_fev' else (g.split=='cal'),f'{name}_anomaly'].mean())}
    return res

def event_details(eps, g, model, nm, ss,ee):
    s=pd.Timestamp(ss); e=pd.Timestamp(ee)
    pre_start=s-pd.Timedelta(hours=2)
    pre=eps[eps['alert_time'].between(pre_start,s, inclusive='left')]
    during=eps[eps['alert_time'].between(s,e)]
    ongoing=eps[(eps['alert_time']<s) & (eps['end']>=s)]
    # Janelas (não episódios) no intervalo; os horários de fim-de-janela correspondem à leitura disponível.
    in_event=g.loc[(g.split=='test') & (g.index >= s)&(g.index<=e)]
    return {'modelo':model,'evento':nm,'janelas_durante':len(in_event),
            'janelas_anomalas_durante':int(in_event[f'{model}_anomaly'].sum()),
            'novos_alertas_2h_antes':len(pre),
            'primeiro_novo_alerta_2h_antes':str(pre['alert_time'].min()) if len(pre) else '',
            'novo_alerta_durante':len(during),'primeiro_alerta_durante':str(during['alert_time'].min()) if len(during) else '',
            'alerta_ja_ativo_inicio':bool(len(ongoing)),
            'inicio_alerta_ja_ativo':str(ongoing['alert_time'].min()) if len(ongoing) else '',
           }

def main():
    g=pd.read_csv(INPUT,parse_dates=['fim_janela']).set_index('fim_janela').sort_index()
    on=g['motor_on_mean']; dv=g['DV_eletric_mean']
    # Limiar escolhido a priori com base na semântica de sensores; sem usar rótulos do teste.
    g['regime']=np.select([(on<=.1),(on>=.9)&(dv>=.8)], ['desligado','carga_continua'],default='misto_ou_sem_carga')
    g['split']='unused'
    train_dates=(g.index<pd.Timestamp('2020-05-01'))
    failure_exclusion=(g.index>=pd.Timestamp('2020-04-17'))&(g.index<=pd.Timestamp('2020-04-20'))
    g.loc[train_dates & ~failure_exclusion,'split']='train'
    g.loc[(g.index>=pd.Timestamp('2020-05-01'))&(g.index<pd.Timestamp('2020-05-23')),'split']='cal'
    g.loc[g.index>=pd.Timestamp('2020-05-23'),'split']='test'
    excluded=[c for c in ['n','maxgap','score','anomaly','episode_id','streak','alert', 'LPS_mean','Oil_level_mean','motor_on_mean'] if c in g]
    cols=[c for c in g.columns if c not in excluded+['regime','split']]
    print('FEATURES',len(cols), cols)
    train=g.split=='train'; cal=g.split=='cal';test=g.split=='test'
    print('SPLIT',int(train.sum()),int(cal.sum()),int(test.sum()), 'exclude', int((g.split=='unused').sum()))
    print(pd.crosstab(g.regime,g.split).to_string())
    settings={'dataset':'MetroPT3(AirCompressor).csv', 'features':cols,
        'state_definition':{'desligado':'motor_on_mean<=0.1','carga_continua':'motor_on_mean>=0.9 and DV_eletric_mean>=0.8','misto_ou_sem_carga':'restante'},
        'train':'Feb1 - Apr30, minus Apr17-Apr20 (F1 + surroundings)','cal':'May1-May22','test':'May23-Sep1',
        'cal_quantile':PER,'consecutive_anomaly_windows':STREAK,
        'random_state':RANDOM_STATE,'n_estimators':120,'max_samples':256,
        'excluded_from_model':['LPS_mean','Oil_level_mean','motor_on_mean']}
    (OUT/'configuracao.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2))
    # Referência controlada: modelo treinado apenas em fevereiro, mesma lista de features e mesmo período de teste.
    old_train=g.index<pd.Timestamp('2020-02-20')
    old_cal=(g.index>=pd.Timestamp('2020-02-20'))&(g.index<pd.Timestamp('2020-03-01'))
    feb=IsolationForest(n_estimators=120,max_samples=256,random_state=RANDOM_STATE,n_jobs=-1)
    feb.fit(g.loc[old_train,cols].to_numpy(dtype='float32'))
    g['global_fev_score']=-feb.score_samples(g[cols].to_numpy(dtype='float32'))
    tfeb=float(g.loc[old_cal,'global_fev_score'].quantile(PER))
    g['global_fev_anomaly']=g['global_fev_score']>tfeb
    print('FEB threshold', tfeb, 'cal pct',round(100*g.loc[old_cal,'global_fev_anomaly'].mean(),3))
    # O baseline global e o modelo condicional enxergam os mesmos dados, exceto para treino/calibracao por regime.
    global_if=IsolationForest(n_estimators=120,max_samples=256,random_state=RANDOM_STATE,n_jobs=-1)
    global_if.fit(g.loc[train,cols].to_numpy(dtype='float32'))
    g['global_score']=-global_if.score_samples(g[cols].to_numpy(dtype='float32'))
    tglobal=float(g.loc[cal,'global_score'].quantile(PER))
    g['global_anomaly']=g['global_score']>tglobal
    print('GLOBAL threshold',tglobal)
    g['regime_score']=np.nan
    g['regime_anomaly']=False
    tdict={}
    for rg in ['desligado','misto_ou_sem_carga','carga_continua']:
        t=train & (g.regime==rg)
        c=cal & (g.regime==rg)
        ix=(g.regime==rg)
        nt=int(t.sum());nc=int(c.sum())
        if nt<60 or nc<30:
            raise RuntimeError(f'Regime {rg} train/cal insufficent: {nt}/{nc}')
        model=IsolationForest(n_estimators=120,max_samples=256,random_state=RANDOM_STATE,n_jobs=-1)
        model.fit(g.loc[t,cols].to_numpy(dtype='float32'))
        score=-model.score_samples(g.loc[ix,cols].to_numpy(dtype='float32'))
        g.loc[ix,'regime_score']=score
        threshold=float(g.loc[c,'regime_score'].quantile(PER))
        g.loc[ix,'regime_anomaly']=g.loc[ix,'regime_score']>threshold
        tdict[rg]={'train':nt,'cal':nc,'test':int((test & ix).sum()),'threshold':threshold,
                   'cal_anomaly_pct':round(100*g.loc[c,'regime_anomaly'].mean(),3),
                   'test_anomaly_pct':round(100*g.loc[test & ix,'regime_anomaly'].mean(),3)}
    (OUT/'limiares_por_regime.json').write_text(json.dumps({'global_fev':tfeb,'global':tglobal,'por_regime':tdict},ensure_ascii=False,indent=2))
    print('STATE THRESHOLDS',tdict)
    metricrows=[];evrows=[]
    for name in ['global_fev','global','regime']:
        ep=episodes_from_scores(g,name)
        ep.to_csv(OUT/f'episodios_{name}.csv',index_label='bloco')
        met=metrics(g,ep,name);metricrows.append(met)
        print('METRICS',met)
        for enm,(s,e) in EVENTS.items():
            if enm.startswith('F1'):continue
            res=event_details(ep,g,name,enm,s,e)
            evrows.append(res)
            print('EVENT',res)
    pd.DataFrame(metricrows).to_csv(OUT/'comparacao_modelos.csv',index=False)
    pd.DataFrame(evrows).to_csv(OUT/'avaliacao_eventos.csv',index=False)
    # Excluir features detalhadas do output para manter pacote compacto; arquivo base+scripts permitem reproduzir.
    outcols=['regime','split','n','maxgap','Motor_current_mean','DV_eletric_mean','TP2_mean','TP3_mean','H1_mean','Oil_temperature_mean',
             'global_fev_score','global_fev_anomaly','global_score','global_anomaly','regime_score','regime_anomaly']
    g[outcols].to_csv(OUT/'janelas_avaliadas.csv',index_label='fim_janela')
    pd.crosstab(g.regime,g.split).to_csv(OUT/'contagem_regimes.csv')

if __name__=='__main__':main()
