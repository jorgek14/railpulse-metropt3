#!/usr/bin/env python3
"""Audita a versão exata do MetroPT-3 usada no artigo."""
import argparse, hashlib, json
from pathlib import Path
import pandas as pd
EXPECTED='db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24'
p=argparse.ArgumentParser();p.add_argument('--csv',required=True,type=Path);a=p.parse_args()
dig=hashlib.sha256()
with a.csv.open('rb') as inp:
    for chunk in iter(lambda:inp.read(2*1024*1024),b''):dig.update(chunk)
df=pd.read_csv(a.csv,parse_dates=['timestamp'])
delta=df['timestamp'].diff().dt.total_seconds()
result={'arquivo':str(a.csv),'sha256':dig.hexdigest(),'sha256_esperado':EXPECTED,
  'hash_igual':dig.hexdigest()==EXPECTED,'registros':len(df),
  'total_colunas_csv':len(df.columns),'sensores':len(df.columns)-2,
  'ausentes':int(df.isna().sum().sum()),
  'timestamps_duplicados':int(df.timestamp.duplicated().sum()),
  'inicio':str(df.timestamp.min()),'fim':str(df.timestamp.max()),
  'intervalo_modal_s':float(delta.mode().iloc[0]),
  'lacunas_maiores_60s':int((delta>60).sum()),
  'lacunas_maiores_3600s':int((delta>3600).sum())}
print(json.dumps(result,ensure_ascii=False,indent=2))
if not result['hash_igual']:print('ATENÇÃO: arquivo diferente da versão do artigo; contagens podem mudar.')
