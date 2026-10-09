"""Receptor HTTP, detector online, SQLite e painel web de replay local.

Uso: python -m iot_monitor.server --port 8765
O servidor limita-se por padrao a 127.0.0.1. Nao disponibilize na Internet.
"""
import argparse
import csv
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse,parse_qs

from .detector import Detector,validate_reading
from .storage import Store

ROOT=Path(__file__).resolve().parent.parent
DEFAULT_CONFIG=ROOT/'parametros_etapa4.json'

class Context:
    def __init__(self,config,db):
        self.config=config
        self.store=Store(db)
        self.detector=Detector(config)
        self.lock=Lock()
        # Reconstrói o estado causal caso o servidor tenha sido reiniciado:
        # a máquina de estados é reexecutada somente com telemetria já persistida.
        if self.store.counts()['readings']:
            expected = self.store.counts()['alerts']
            actual = 0
            for timestamp,tp3,current,oil,dv in self.store.db.execute(
                    'SELECT timestamp,tp3,motor_current,oil_temperature,dv_eletric FROM readings ORDER BY id'):
                actual += len(self.detector.process({'timestamp':timestamp,'TP3':tp3,
                    'Motor_current':current,'Oil_temperature':oil,'DV_eletric':dv}))
            if actual != expected:
                raise RuntimeError('Banco inconsistente: alertas salvos nao conferem com replay do detector')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'web'),**kwargs)

    def log_message(self,*args):
        return  # evita poluir o terminal durante o replay

    def json_response(self, code, obj):
        body=json.dumps(obj,ensure_ascii=False,default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url=urlparse(self.path)
        ctx=self.server.ctx
        q=parse_qs(url.query)
        if url.path=='/api/status':
            with ctx.lock:
                latest=ctx.store.recent('readings',1)
                self.json_response(200,{'status':'executando','mode':'replay_historico_http',
                  'counts':ctx.store.counts(),'last':latest[-1] if latest else None,
                  'gaps':ctx.detector.gaps,'cycles':ctx.detector.cycle_count,
                  'parameters':{'pressure_target_bar':ctx.detector.target,
                    'recovery_limit_s':ctx.detector.recovery_cutoff,
                    'duration_limit_s':ctx.detector.duration_cutoff,
                    'max_gap_s':ctx.detector.max_gap}})
            return
        if url.path in ('/api/readings','/api/alerts'):
            with ctx.lock:
                data=ctx.store.recent('readings' if url.path.endswith('readings') else 'alerts',q.get('limit',['250'])[0])
            self.json_response(200,{'items':data})
            return
        if url.path=='/api/export_alerts.csv':
            with ctx.lock:
                alerts=ctx.store.all_alerts()
            f=io.StringIO()
            columns=('method','timestamp','cycle_start','elapsed_s','pressure_bar','start_pressure_bar','motor_current_a','severity','message')
            writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
            writer.writeheader(); writer.writerows(alerts)
            data=f.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="alertas_iot.csv"')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
            return
        if url.path=='/': self.path='/index.html'
        elif url.path not in ('/index.html','/app.js','/style.css'):
            self.json_response(404,{'error':'Rota desconhecida'});return
        super().do_GET()

    def do_POST(self):
        path=urlparse(self.path).path
        if path not in ('/api/reading','/api/reset'):
            self.json_response(404,{'error':'Rota desconhecida'});return
        try:
            n=int(self.headers.get('Content-Length','0'))
        except ValueError:
            self.json_response(400,{'error':'Content-Length invalido'});return
        if n>32768 or n<=0:
            self.json_response(413,{'error':'Corpo JSON deve ter de 1 a 32768 bytes'});return
        try:
            obj=json.loads(self.rfile.read(n).decode('utf-8'))
            ctx=self.server.ctx
            with ctx.lock:
                if path=='/api/reset':
                    ctx.store.clear()
                    ctx.detector=Detector(ctx.config)
                    res={'ok':True,'message':'Sessao reiniciada'}
                else:
                    reading=validate_reading(obj)
                    # Invalid input is rejected before either the detector or database are changed.
                    if ctx.detector.prev_time and datetime.fromisoformat(reading['timestamp'])<=ctx.detector.prev_time:
                        raise ValueError('Timestamp repetido ou fora de ordem; execute reset antes de novo replay')
                    alerts=ctx.detector.process(reading)
                    ctx.store.insert(reading,alerts)
                    res={'ok':True,'alerts':alerts}
            self.json_response(200,res)
        except (ValueError,TypeError) as ex:
            self.json_response(400,{'ok':False,'error':str(ex)})


def main():
    p=argparse.ArgumentParser(description='Servidor local MetroPT-3 etapa 5')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--db',default=str(ROOT/'execucao_iot.sqlite'))
    args=p.parse_args()
    config=json.loads(DEFAULT_CONFIG.read_text(encoding='utf-8'))
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.ctx=Context(config,args.db)
    print(f'Painel: http://{args.host}:{args.port} | Banco: {args.db}',flush=True)
    print('Publicador: python -m iot_monitor.replay --demo F3 --reset',flush=True)
    server.serve_forever()

if __name__=='__main__': main()
