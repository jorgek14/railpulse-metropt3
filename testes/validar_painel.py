"""Integração real: sobe API em localhost, envia demo F3, verifica e captura painel."""
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PORT=8879
URL=f'http://127.0.0.1:{PORT}'
DB=ROOT/'resultados'/'screenshot_demo.sqlite'
for end in ('','-wal','-shm'):
    (Path(str(DB)+end)).unlink(missing_ok=True)
server=subprocess.Popen([sys.executable,'-m','iot_monitor.server','--port',str(PORT),'--db',str(DB)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
try:
    for _ in range(70):
        if server.poll() is not None:raise RuntimeError('Servidor encerrou: '+server.stdout.read())
        try:
            with urlopen(URL+'/api/status',timeout=1) as r:break
        except Exception:time.sleep(.1)
    else:raise RuntimeError('Servidor nao iniciou')
    result=subprocess.run([sys.executable,'-m','iot_monitor.replay','--demo','F3','--speed','0','--reset','--url',URL],cwd=ROOT,capture_output=True,text=True,timeout=70)
    if result.returncode:raise RuntimeError(result.stderr)
    print('REPLAY F3:',result.stdout.strip())
    with urlopen(URL+'/api/status') as resp:status=json.load(resp)
    with urlopen(URL+'/api/alerts?limit=30') as resp:alerts=json.load(resp)['items']
    assert status['counts']=={'readings':303,'alerts':3,'primary_alerts':1},status['counts']
    assert [x['timestamp'] for x in alerts if x['method']=='Pressao_nao_recuperada_q99']==['2020-06-05 09:51:38']
    # O navegador da infraestrutura de teste bloqueia navegacao localhost.
    # Para inspecao visual, renderizamos um snapshot com respostas REAIS da API
    # injetadas em fetch; o teste end-to-end HTTP acima continua real.
    with urlopen(URL+'/api/readings?limit=400') as resp:readings=json.load(resp)
    responses={'/api/status':status,'/api/alerts?limit=60':{'items':alerts},'/api/readings?limit=400':readings}
    html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    css=(ROOT/'web'/'style.css').read_text(encoding='utf-8')
    js=(ROOT/'web'/'app.js').read_text(encoding='utf-8')
    payload=json.dumps(responses,ensure_ascii=False)
    shim='<script>const __responses='+payload+';window.fetch=async function(url){return new Response(JSON.stringify(__responses[url]||{}),{status:200,headers:{"Content-Type":"application/json"}})}</script>'
    html=html.replace('<link rel="stylesheet" href="/style.css">','<style>'+css+'</style>')
    html=html.replace('<script src="/app.js"></script>',shim+'<script>'+js+'</script>')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1430,'height':1130},device_scale_factor=1)
        page.set_content(html,wait_until='load')
        page.wait_for_function('document.getElementById("primaryCount").textContent==="1"',timeout=15000)
        assert page.locator('h2').inner_text()=='Telemetria e diagnóstico operacional'
        assert '09:51:38' in page.locator('#alerts').inner_text()
        page.screenshot(path=str(ROOT/'resultados'/'painel_demonstracao_F3.png'),full_page=True)
        print('PAINEL: snapshot real da API renderizado e screenshot salvo')
        browser.close()
    (ROOT/'resultados'/'demo_F3_integracao.json').write_text(json.dumps({'status':status,'alerts':alerts},ensure_ascii=False,indent=2))
    print('INTEGRACAO: OK, 303 leituras, 3 alertas, 1 regra principal')
finally:
    server.terminate()
    try:server.wait(timeout=7)
    except subprocess.TimeoutExpired:server.kill()
