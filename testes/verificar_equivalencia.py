"""Executa detector online em ordem cronologica no CSV original e compara a Etapa 4."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from iot_monitor.detector import Detector

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--csv',required=True,type=Path)
    p.add_argument('--reference',default=str(ROOT/'resultados_referencia'/'alertas_referencia_etapa4.csv'))
    p.add_argument('--out',type=Path,default=ROOT/'resultados'/'equivalencia.json')
    args=p.parse_args()
    detector=Detector(json.loads((ROOT/'parametros_etapa4.json').read_text()))
    online=[]
    with args.csv.open(newline='',encoding='utf-8-sig') as f:
        for sample in csv.DictReader(f):
            online.extend(detector.process(sample))
    with Path(args.reference).open(newline='',encoding='utf-8-sig') as f:
        reference=list(csv.DictReader(f))
    ref=Counter((r['metodo'],r['alerta']) for r in reference)
    actual=Counter((r['method'],r['timestamp']) for r in online)
    extra=actual-ref;miss=ref-actual
    res={'original_registros':detector.processed,'ciclos_identificados':detector.cycle_count,
         'alertas_esperados':sum(ref.values()),'alertas_stream':sum(actual.values()),
         'metodos':dict(Counter(r['method'] for r in online)),
         'ausentes':list(miss.elements())[:15], 'extras':list(extra.elements())[:15],
         'todos_iguais':actual==ref}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(res,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(res,indent=2,ensure_ascii=False))
    if actual!=ref:raise SystemExit(1)

if __name__=='__main__':main()
