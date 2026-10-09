"""Testes locais da regra e transporte sem bibliotecas externas."""
import csv
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from iot_monitor.detector import Detector,validate_reading
from iot_monitor.server import Context,Handler

CONFIG=json.loads((ROOT/'parametros_etapa4.json').read_text())

class TestDetector(unittest.TestCase):
    def test_limite_causal(self):
        d=Detector(CONFIG)
        base='2020-06-05 09:48:'
        from datetime import datetime,timedelta
        start=datetime.fromisoformat('2020-06-05 09:48:30')
        generated=[]
        for s in list(range(0,210,10)):
            t=start+timedelta(seconds=s)
            generated += d.process({'timestamp':t.isoformat(sep=' '),'TP3':8.2,'Motor_current':7.2,'DV_eletric':1,'Oil_temperature':61.2})
        pri=[a for a in generated if a['method']=='Pressao_nao_recuperada_q99']
        self.assertEqual(len(pri),1)
        self.assertEqual(pri[0]['elapsed_s'],190)
        self.assertEqual(pri[0]['timestamp'],'2020-06-05 09:51:40')

    def test_meta_atingida_antes_bloqueia_alerta(self):
        from datetime import datetime,timedelta
        d=Detector(CONFIG)
        start=datetime.fromisoformat('2020-06-05 09:48:30')
        generated=[]
        for s in range(0,220,10):
            t=start+timedelta(seconds=s)
            generated+=d.process({'timestamp':t.isoformat(sep=' '),'TP3':9.8 if s>=120 else 8.2,'Motor_current':7,'DV_eletric':1,'Oil_temperature':60})
        self.assertFalse(any(a['method']=='Pressao_nao_recuperada_q99' for a in generated))

    def test_gap_reinicia_ciclo(self):
        d=Detector(CONFIG)
        for ts in ['2020-06-05 09:48:30','2020-06-05 09:49:00','2020-06-05 09:50:00']:
            d.process({'timestamp':ts,'TP3':8.2,'Motor_current':7,'DV_eletric':1,'Oil_temperature':60})
        self.assertEqual(d.gaps,1)
        self.assertEqual(d.cycle_count,2)

    def test_validador_rejeita_nan(self):
        data={'timestamp':'2020-06-05 09:48:30','TP3':float('nan'),'Motor_current':7,'DV_eletric':1,'Oil_temperature':60}
        with self.assertRaises(ValueError):validate_reading(data)

    def test_recortes_reais_coincidem_com_referencia(self):
        expected={'f2':(818,2,'2020-05-29 22:51:38'),
                  'f3':(303,1,'2020-06-05 09:51:38'),
                  'f4':(817,10,'2020-07-15 12:48:25'),
                  'normal':(364,0,None)}
        for name,(n,k,first) in expected.items():
            with self.subTest(cenario=name):
                detector=Detector(CONFIG)
                out=[]
                with (ROOT/'dados_demo'/('demo_'+name+'.csv')).open(newline='',encoding='utf-8-sig') as f:
                    for row in csv.DictReader(f):out.extend(detector.process(row))
                primary=[a for a in out if a['method']=='Pressao_nao_recuperada_q99']
                self.assertEqual(detector.processed,n)
                self.assertEqual(len(primary),k)
                self.assertEqual(primary[0]['timestamp'] if primary else None,first)

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.server.ctx=Context(CONFIG,Path(cls.tmp.name)/'test.sqlite')
        cls.host='http://127.0.0.1:'+str(cls.server.server_address[1])
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        cls.server.ctx.store.db.close()
        cls.tmp.cleanup()

    def post(self,url,obj):
        req=Request(self.host+url,data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req) as r:return json.load(r)

    def get(self,url):
        with urlopen(self.host+url) as r:return json.load(r)

    def test_demo_F3_http_sqlite_alerts_and_reset(self):
        self.post('/api/reset',{})
        path=ROOT/'dados_demo'/'demo_f3.csv'
        with path.open(newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                self.post('/api/reading',r)
        st=self.get('/api/status')
        self.assertEqual(st['counts']['readings'],303)
        alerts=self.get('/api/alerts?limit=100')['items']
        p=[a for a in alerts if a['method']=='Pressao_nao_recuperada_q99']
        self.assertEqual(len(p),1)
        self.assertEqual(p[0]['timestamp'],'2020-06-05 09:51:38')
        self.assertEqual(p[0]['cycle_start'],'2020-06-05 09:48:30')
        self.assertEqual(st['counts']['alerts'],3)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/reading',{'timestamp':'2020-06-05 09:51:38','TP3':8,'Motor_current':7,'Oil_temperature':70,'DV_eletric':1})
        self.assertEqual(ctx.exception.code,400)
        self.post('/api/reset',{})
        self.assertEqual(self.get('/api/status')['counts']['readings'],0)

if __name__=='__main__':unittest.main(verbosity=2)
