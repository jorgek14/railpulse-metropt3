#!/usr/bin/env python3
"""MetroPT-3 etapa 3: indicadores fisicos causais e avaliacao temporal honesta.

Uso: python etapa3_indicadores_fisicos.py --csv 'MetroPT3(AirCompressor).csv' --out etapa3_dir
Requer numpy, pandas, scikit-learn. Nao usa rotulos de teste para treinamento ou calibracao.
Nota: os indicadores sao PROXIES, nao medicoes diretas de vazamento, fluxo ou eficiencia.
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

EVENTS={'F1':('2020-04-18 00:00','2020-04-18 23:59'),
        'F2':('2020-05-29 23:30','2020-05-30 06:00'),
        'F3':('2020-06-05 10:00','2020-06-07 14:30'),
        'F4':('2020-07-15 14:30','2020-07-15 19:00')}
RNG=42

def compute_physical_features(raw):
    raw=raw.sort_index()
    idx=raw.index
    seconds=idx.to_series().diff().dt.total_seconds()
    good=seconds.between(5,25)
    motor_on=raw.Motor_current>2.0
    loaded=motor_on & (raw.DV_eletric>0.5)
    stopped=~motor_on
    pairs_load=good & loaded & loaded.shift(fill_value=False)
    pairs_off=good & stopped & stopped.shift(fill_value=False)
    slopes=(raw.TP3.diff()/seconds*60).replace([np.inf,-np.inf],np.nan)
    # Somente diferencas sucessivas durante estado consistente; nao preencher NaN com zero.
    features=pd.DataFrame({
        'motor_on':motor_on.astype('float32'),
        'loaded':loaded.astype('float32'),
        'motor_current':raw.Motor_current,
        'oil':raw.Oil_temperature,
        'TP3':raw.TP3,
        'TP2':raw.TP2,
        'reservoirs':raw.Reservoirs,
        'pressure_rate_load':slopes.where(pairs_load),
        'pressure_rate_off':slopes.where(pairs_off),
        'frac_low_gain_loaded':(slopes<=0.05).where(pairs_load).astype('float32'),
        'frac_loaded_low_p':(raw.TP3<8.2).where(loaded).astype('float32'),
        'I_loaded':raw.Motor_current.where(loaded),
    },index=idx)
    agg={'motor_on':['mean'],'loaded':['mean'],'motor_current':['mean'],
         'oil':['mean'],'TP3':['mean','min','std'],'TP2':['mean'],
         'reservoirs':['mean'],'pressure_rate_load':['mean','median','count'],
         'pressure_rate_off':['mean','count'],'frac_low_gain_loaded':['mean'],
         'frac_loaded_low_p':['mean'],'I_loaded':['mean']}
    b=features.resample('10min',label='right',closed='left').agg(agg)
    b.columns=['_'.join(x) for x in b.columns]
    b['n']=features.TP3.resample('10min',label='right',closed='left').count()
    # calcular gap apenas intra-janela (sem salto entre janelas)
    buck=idx.floor('10min')+pd.Timedelta(minutes=10)
    intra_gap=seconds.where(pd.Series(buck,index=idx).eq(pd.Series(buck,index=idx).shift()))
    b['maxgap']=intra_gap.groupby(buck).max()
    valid=(b.n>=45)&(b.maxgap<=60)
    b=b.loc[valid].copy()
    # segmentos de cobertura continua; rejeitar janelas de 60min que atravessem falhas de telemetria
    b['segmento']=(b.index.to_series().diff().dt.total_seconds().ne(600)).cumsum()
    by=b.groupby('segmento',sort=False)
    def roll(col,fun='mean',minp=6):
        return by[col].transform(lambda x:getattr(x.rolling(6,min_periods=minp),fun)())
    b['duty_60min']=roll('motor_on_mean')
    b['load_60min']=roll('loaded_mean')
    b['pressao_60min']=roll('TP3_mean')
    b['pressao_min_60min']=roll('TP3_min','min')
    b['temperatura_60min']=roll('oil_mean')
    b['corrente_60min']=roll('motor_current_mean')
    b['tp2_60min']=roll('TP2_mean')
    # Periodos sem pares sob carga contribuem com peso ZERO, nao invalidam toda
    # a hora. Sem fillna(0), rolling(..., min_periods=6) exigiria 6 bins COM carga,
    # introduzindo viés de selecao contra funcionamento intermitente normal.
    b['pressao_ganho_carreg_60min']=by.apply(
        lambda x: (x.pressure_rate_load_mean.mul(x.pressure_rate_load_count).fillna(0).rolling(6,min_periods=6).sum()
                   /x.pressure_rate_load_count.rolling(6,min_periods=6).sum()),
        include_groups=False).droplevel(0).reindex(b.index)
    b['n_pares_carga_60min']=roll('pressure_rate_load_count','sum')
    b.loc[b.n_pares_carga_60min<30,'pressao_ganho_carreg_60min']=np.nan
    b['fracao_baixo_ganho_60min']=by.apply(
        lambda x: (x.frac_low_gain_loaded_mean.mul(x.pressure_rate_load_count).fillna(0).rolling(6,min_periods=6).sum()
                   /x.pressure_rate_load_count.rolling(6,min_periods=6).sum()),
        include_groups=False).droplevel(0).reindex(b.index)
    b.loc[b.n_pares_carga_60min<30,'fracao_baixo_ganho_60min']=np.nan
    b['delta_pressao_50min']=b.TP3_mean - by.TP3_mean.shift(5)
    b['delta_temp_50min']=b.oil_mean - by.oil_mean.shift(5)
    b['proxy_ganho_por_ampere']=b['pressao_ganho_carreg_60min']/b['I_loaded_mean'].replace(0,np.nan)
    # amostra fisica em carga, gerando atributo de interesse, nao rotulo de falha
    b['valid_phys']=b['duty_60min'].notna() & b['pressao_ganho_carreg_60min'].notna()
    b['split']='unused'
    b.loc[(b.index<pd.Timestamp('2020-05-01')) & ~b.index.to_series().between(pd.Timestamp('2020-04-17'),pd.Timestamp('2020-04-20')),'split']='train'
    b.loc[b.index.to_series().between(pd.Timestamp('2020-05-01'),pd.Timestamp('2020-05-22 23:59')),'split']='cal'
    b.loc[b.index>=pd.Timestamp('2020-05-23'),'split']='test'
    return b

def make_episodes(g,flag,model,min_streak=3):
    t=g.loc[g.split.eq('test')].copy()
    t['flag']=flag.loc[t.index].fillna(False).astype(bool)
    isbreak=t.flag.ne(t.flag.shift(fill_value=False)) | t.index.to_series().diff().dt.total_seconds().ne(600)
    t['block']=isbreak.cumsum()
    rows=[]
    for id,group in t.loc[t.flag].groupby('block'):
        if len(group)<min_streak:continue
        start,end=group.index[0],group.index[-1]
        rows.append({'modelo':model,'inicio_primeira_janela':start,'fim_ultima_janela':end,
                     'horario_primeiro_alerta':start+pd.Timedelta(minutes=10*(min_streak-1)),
                     'janelas_consecutivas':len(group)})
    return pd.DataFrame(rows,columns=['modelo','inicio_primeira_janela','fim_ultima_janela','horario_primeiro_alerta','janelas_consecutivas'])

def test_results(g,episodes,flag,model):
    ev=[];exclude=pd.Series(False,index=g.loc[g.split.eq('test')].index)
    for event,(s,e) in EVENTS.items():
        if event=='F1':continue
        s,e=pd.Timestamp(s),pd.Timestamp(e)
        # O bin rotulado t contem EXCLUSIVAMENTE leituras em [t-10min,t),
        # logo t == inicio registrado da falha pertence ao horizonte PRE.
        win=g.loc[g.split.eq('test') & g.index.to_series().between(s-pd.Timedelta(hours=2),e)]
        justpre=win.loc[(win.index>s-pd.Timedelta(hours=2))&(win.index<=s)]
        during=win.loc[win.index>s]
        episodeon=episodes.copy()
        if len(episodes):
            starts=episodes.horario_primeiro_alerta
            ends=episodes.fim_ultima_janela
            new=episodeon.loc[starts.between(s-pd.Timedelta(hours=2),s,inclusive='right')]
            ongoing=episodeon.loc[(starts<s)&(ends>=s-pd.Timedelta(hours=2))&(ends>=s)]
            duringalerts=episodeon.loc[(starts>s)&(starts<=e)]
        else:new=ongoing=duringalerts=episodeon
        ev.append({'modelo':model,'falha':event,'janelas_disponiveis_2h_antes':len(justpre),
                   'janelas_alerta_2h_antes':int(flag.reindex(justpre.index).fillna(False).sum()),
                   'janelas_disponiveis_durante':len(during),
                   'janelas_alerta_durante':int(flag.reindex(during.index).fillna(False).sum()),
                   'novos_alertas_persistentes_2h_antes':len(new),
                   'horario_primeiro_novo_alerta':str(new.horario_primeiro_alerta.min()) if len(new) else '',
                   'alerta_iniciado_antes_e_ativo_na_falha':int(len(ongoing)>0),
                   'novos_alertas_durante':len(duringalerts)})
        exclude |= (exclude.index>=s-pd.Timedelta(hours=2))&(exclude.index<=e+pd.Timedelta(hours=24))
    if len(episodes):
        keep=pd.Series(True,index=episodes.index)
        for event,(s,e) in EVENTS.items():
            if event=='F1':continue
            s,e=pd.Timestamp(s),pd.Timestamp(e)
            # Conta como fora somente se o episodio NAO se sobrepoe a nenhum
            # horizonte relacionado aos eventos, inclusive na cauda.
            keep &= ~((episodes.fim_ultima_janela>=s-pd.Timedelta(hours=2)) &
                     (episodes.horario_primeiro_alerta<=e+pd.Timedelta(hours=24)))
        out_ev=int(keep.sum())
    else: out_ev=0
    nday=int(exclude.loc[~exclude].index.normalize().nunique())
    ts=g[g.split.eq('test')]
    eligible=ts.valid_phys if model in {'Fisico_IsolationForest','Regra_alta_carga_baixo_ganho','Apenas_alta_carga'} else pd.Series(True,index=ts.index)
    n_valid=int(eligible.sum())
    stats={'modelo':model,'janelas_teste':len(ts),
        'janelas_elegiveis':n_valid,'cobertura_pct':round(100*n_valid/len(ts),3),
        'janelas_sinalizadas':int(flag.reindex(ts.index).fillna(False).sum()),
        'pct_janelas_sinalizadas':round(100*flag.reindex(ts.index).fillna(False).mean(),3),
        'pct_elegiveis_sinalizadas':round(100*flag.reindex(ts.index).fillna(False).sum()/n_valid,3) if n_valid else np.nan,
        'episodios_teste':len(episodes),'episodios_fora_janelas_de_evento':out_ev,
        'dias_teste_sem_janelas_de_evento':nday,
        'episodios_fora_por_dia':round(out_ev/nday,3) if nday else np.nan,
        'eventos_com_novo_alerta_pre_2h':sum(x['novos_alertas_persistentes_2h_antes']>0 for x in ev)}
    return stats,ev

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--csv',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    cols=['timestamp','TP2','TP3','Reservoirs','Oil_temperature','Motor_current','DV_eletric']
    raw=pd.read_csv(args.csv,parse_dates=['timestamp'],usecols=cols).set_index('timestamp')
    g=compute_physical_features(raw)
    print('RECORDS',len(raw),'BIN_TOTAL',len(g),'WITH_60MIN',int(g.duty_60min.notna().sum()), 'VALID_PHYS',int(g.valid_phys.sum()),flush=True)
    print('SPLIT',g.groupby('split').size().to_dict(),flush=True)
    print('PHYS_PER_SPLIT',g.loc[g.valid_phys].groupby('split').size().to_dict(),flush=True)
    # Nao treinar com F1 ou dados posteriores a 22/Mai. Critério de calibracao 99o percentil.
    # Modelo fisico de regime: janelas de alta carga apenas para condicao pressurizacao (nao faz inferencia para parado)
    train=(g.split=='train') & g.valid_phys
    cal=(g.split=='cal') & g.valid_phys
    test=(g.split=='test') & g.valid_phys
    feat=['duty_60min','load_60min','pressao_60min','pressao_min_60min',
          'corrente_60min','temperatura_60min','delta_temp_50min',
          'pressao_ganho_carreg_60min','fracao_baixo_ganho_60min']
    finite=g[feat].replace([np.inf,-np.inf],np.nan).notna().all(axis=1)
    train &=finite;cal &=finite;test &=finite
    print('MODEL_TRAIN_CAL_TEST',train.sum(),cal.sum(),test.sum(),flush=True)
    if min(train.sum(),cal.sum(),test.sum())<100: raise RuntimeError('insufficient valid loaded examples')
    model=IsolationForest(n_estimators=160,max_samples=256,random_state=RNG,n_jobs=-1)
    model.fit(g.loc[train,feat].to_numpy('float32'))
    g['phys_if_score']=np.nan
    ix=train|cal|test
    g.loc[ix,'phys_if_score']=-model.score_samples(g.loc[ix,feat].to_numpy('float32'))
    th=float(g.loc[cal,'phys_if_score'].quantile(.99))
    g['phys_if_flag']=g.phys_if_score.gt(th).fillna(False)
    # Indicador fisico simples: carga alta e ganho de pressao baixo.
    # Percentis/calibracao fixados PRE teste; janelas sem carregamento elegivel nao sao anomalias fisicas avaliaveis.
    qd=float(g.loc[cal,'load_60min'].quantile(.90))
    qg=float(g.loc[cal & g.load_60min.ge(qd),'pressao_ganho_carreg_60min'].quantile(.10))
    if not np.isfinite(qg):raise RuntimeError('threshold low gain missing')
    g['high_duty_low_gain_flag']=g.valid_phys & g.load_60min.ge(qd) & g.pressao_ganho_carreg_60min.le(qg)
    # Ablação diagnostica: carga ao menos 90% nos ultimos 60 minutos sem analise
    # da pressao. Limiar operacional definido explicitamente, nao ajustado ao teste.
    qsimple=0.90
    g['high_duty_only_flag']=g.valid_phys & g.load_60min.ge(qsimple)
    # Baseline da etapa 2, alinhado aos mesmos timestamps de teste (limiar anterior ja congelado).
    prev_path=out/'baseline_etapa2_compact.csv'
    if not prev_path.exists():
        prev_path=out.parent/'metropt3_etapa2'/'janelas_avaliadas.csv'
    if prev_path.exists():
        previous=pd.read_csv(prev_path,parse_dates=['fim_janela']).set_index('fim_janela')
        g['prev_global_flag']=previous['global_anomaly'].reindex(g.index).fillna(False).astype(bool)
        g['prev_regime_flag']=previous['regime_anomaly'].reindex(g.index).fillna(False).astype(bool)
    methods={'Fisico_IsolationForest':'phys_if_flag',
             'Regra_alta_carga_baixo_ganho':'high_duty_low_gain_flag',
             'Apenas_alta_carga':'high_duty_only_flag'}
    if 'prev_global_flag' in g:methods.update({'Baseline_global_E2':'prev_global_flag','Baseline_regime_E2':'prev_regime_flag'})
    metric=[];evrows=[];episodes=[]
    for name,flag in methods.items():
        ep=make_episodes(g,g[flag],name)
        s,ev=test_results(g,ep,g[flag],name)
        metric.append(s);evrows+=ev;episodes.append(ep)
        print('METRIC',s,flush=True)
        print('EVENTS',[(x['falha'],x['novos_alertas_persistentes_2h_antes'],x['janelas_alerta_durante']) for x in ev],flush=True)
    pd.DataFrame(metric).to_csv(out/'comparacao_modelos.csv',index=False)
    pd.DataFrame(evrows).to_csv(out/'avaliacao_por_falha.csv',index=False)
    pd.concat(episodes,ignore_index=True).to_csv(out/'episodios_alertas.csv',index=False)
    count=g.groupby('split').agg(janelas=('n','size'),elegiveis_60min=('valid_phys','sum'),carga_60min_mediana=('load_60min','median'),
                                 pressao_ganho_carreg_mediana=('pressao_ganho_carreg_60min','median'),
                                 duty_mediana=('duty_60min','median'))
    count.to_csv(out/'estatisticas_periodos.csv')
    # Investigacao da evolucao fisica: janelas observadas nos 24h precedentes, duas horas e durante cada falha.
    sliced=[]
    for event,(ss,ee) in EVENTS.items():
        s=pd.Timestamp(ss);e=pd.Timestamp(ee)
        for period,a,z in [('antes_24h',s-pd.Timedelta(hours=24),s),('antes_2h',s-pd.Timedelta(hours=2),s),('durante_ate_24h',s,min(e,s+pd.Timedelta(hours=24)))]:
            df=g.loc[(g.index>a)&(g.index<=z)] if period=='durante_ate_24h' else g.loc[(g.index>a)&(g.index<s)]
            sliced.append({'falha':event,'periodo':period,'janelas':len(df),'janelas_elegiveis_fisica':int(df.valid_phys.sum()),
                           'motor_ligado_mediana':df.motor_on_mean.median(),
                           'carga_60min_mediana':df.load_60min.median(),
                           'pressao_60min_mediana':df.pressao_60min.median(),
                           'temperatura_60min_mediana':df.temperatura_60min.median(),
                           'ganho_pressao_carga_mediana':df.pressao_ganho_carreg_60min.median(),
                           'fracao_baixo_ganho_60min_mediana':df.fracao_baixo_ganho_60min.median()})
    pd.DataFrame(sliced).to_csv(out/'perfil_eventos_fisicos.csv',index=False)
    # g com todas as variaveis necessarias para reproduzir visualizacoes; elimina 1.5M linhas sensiveis? dataset publico.
    save=['split','segmento','n','maxgap','valid_phys','motor_on_mean','loaded_mean','TP3_mean','TP3_min','oil_mean','motor_current_mean',
          'pressure_rate_load_mean','pressure_rate_load_count','duty_60min','load_60min','pressao_60min',
          'pressao_min_60min','temperatura_60min','corrente_60min','delta_temp_50min',
          'pressao_ganho_carreg_60min','fracao_baixo_ganho_60min','phys_if_score', 'phys_if_flag','high_duty_low_gain_flag','high_duty_only_flag']
    save += [x for x in ['prev_global_flag','prev_regime_flag'] if x in g]
    g[save].to_csv(out/'janelas_fisicas.csv',index_label='fim_janela')
    conf={'original_filename':args.csv.name,'original_rows':len(raw),'valid_bins':len(g),
          'notes':'Sinais de pressao/corrente/temperatura e proxies derivados; nao mede diretamente fuga ou eficiencia.',
          'time_resolution':'~10 s nominal; janelas [t-10min,t) rotuladas por t; acumulados de 60min exigem 6 bins validos consecutivos.',
          'pair_slope':'TP3(t)-TP3(t-1) / dt(min) somente se 5<=dt<=25 segundos e motor em carga nos dois pontos',
          'train':'antes de 2020-05-01, excluindo 2020-04-17 ate 2020-04-20 (F1)',
          'cal':'2020-05-01 ate 2020-05-22', 'test':'a partir de 2020-05-23',
        'q_duty_high':qd,'q_gain_low_given_high_duty':qg,'limiar_controle_carga':qsimple,'if_threshold_99':th,
          'persistence_bins':3,'min_bin_obs':45,'max_bin_gap_sec':60,'rolling_bins':6,
          'features_model':feat,'events':EVENTS,'random_state':RNG,'n_estimators':160,'max_samples':256,
          'prealert_horizon_h':2,'limitation':'Sem ground truth exaustivo; nao equivale a previsao validada; eventos restantes F2-F4 sao holdout descritivo.'}
    (out/'configuracao_e_limites.json').write_text(json.dumps(conf,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
