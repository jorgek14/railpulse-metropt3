"""Publica telemetria histórica via HTTP POST com tempo acelerado (simulação IoT)."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent.parent
SENSOR_FIELDS=['timestamp','TP3','Motor_current','Oil_temperature','DV_eletric']

def post_json(url,data,timeout=20):
    req=Request(url,data=json.dumps(data).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=timeout) as response:
            return json.load(response)
    except HTTPError as e:
        raise RuntimeError(f'Servidor respondeu {e.code}: {e.read().decode()}') from e

def samples(csv_path,start=None,end=None):
    with open(csv_path,newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        for r in reader:
            ts=r['timestamp']
            if start and ts<start:continue
            if end and ts>end:break
            yield {k: r[k] for k in SENSOR_FIELDS}

def main():
    p=argparse.ArgumentParser(description='Reprodução de registros históricos simulando telemetria IoT')
    p.add_argument('--csv',type=Path,help='CSV completo ou recorte demonstrativo')
    p.add_argument('--demo',choices=['F2','F3','F4','NORMAL'],default=None)
    p.add_argument('--url',default='http://127.0.0.1:8765')
    p.add_argument('--from',dest='start',default=None)
    p.add_argument('--to',dest='end',default=None)
    p.add_argument('--speed',type=float,default=150.0,help='Aceleracao da escala temporal; use 0 para sem espera')
    p.add_argument('--reset',action='store_true',help='Zerar a sessao anterior do servidor')
    args=p.parse_args()
    if args.speed<0: p.error('--speed nao pode ser negativo')
    if not args.csv and not args.demo:p.error('Informe --csv ou --demo')
    path=args.csv if args.csv else ROOT/'dados_demo'/('demo_'+args.demo.lower()+'.csv')
    if not path.exists():p.error('CSV nao encontrado: '+str(path))
    if args.reset: post_json(args.url+'/api/reset',{})
    previous=None;count=0;alert_count=0
    try:
        for row in samples(path,args.start,args.end):
            timestamp=datetime.fromisoformat(row['timestamp'])
            if previous is not None and args.speed>0:
                delay=max(0,(timestamp-previous).total_seconds()/args.speed)
                if delay>0:time.sleep(min(delay,1.0))
            result=post_json(args.url+'/api/reading',row)
            previous=timestamp;count+=1
            for alert in result.get('alerts',[]):
                alert_count+=1
                print(f"[ALERTA] {alert['timestamp']} | {alert['method']} | TP3={alert['pressure_bar']:.3f} bar")
            if count%500==0:print(f'Publicados: {count} registros, {alert_count} alertas',flush=True)
    except KeyboardInterrupt:
        print('Replay interrompido pelo usuario')
    print(f'Replay concluido: {count} leituras transmitidas, {alert_count} alertas. Painel: {args.url}',flush=True)

if __name__=='__main__':main()
