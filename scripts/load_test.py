"""Solo contra su entorno de prueba. Credencial por variable, nunca por argumento."""
import argparse,os,time,json,statistics,concurrent.futures,urllib.request,urllib.error
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--requests',type=int,default=100);p.add_argument('--concurrency',type=int,default=5);p.add_argument('--output',default='evidencias/load.json');a=p.parse_args()
if not a.url.startswith('https://'):p.error('Usar HTTPS con certificado valido')
if not 1<=a.concurrency<=100 or not 1<=a.requests<=10000:p.error('Limites de la practica: 1-100 hilos y 1-10000 requests')
token=os.environ['RECO_API_TOKEN'];start=time.perf_counter()
def one(_):
 s=time.perf_counter();status=0
 try:
  req=urllib.request.Request(a.url.rstrip('/')+'/recomendaciones?user_id='+os.environ.get('TEST_USER_ID','999999999999'),headers={'Authorization':'Bearer '+token})
  with urllib.request.urlopen(req,timeout=10) as r:status=r.status;r.read()
 except urllib.error.HTTPError as e:status=e.code
 except Exception:status=0
 return (time.perf_counter()-s)*1000,status
with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as ex:rows=list(ex.map(one,range(a.requests)))
elapsed=time.perf_counter()-start;times=sorted(t for t,s in rows if s==200)
def percentile(q):return times[max(0,int(len(times)*q+.999999)-1)] if times else None
from collections import Counter
result={'requests':len(rows),'concurrency':a.concurrency,'duration_s':elapsed,'throughput_rps':len(rows)/elapsed,'errors':sum(s!=200 for _,s in rows),'http_status_counts':dict(Counter(str(s) for _,s in rows)),'p50_ms':percentile(.5),'p95_ms':percentile(.95),'p99_ms':percentile(.99),'note':'Percentiles de respuestas 200, latencia desde cliente. Estado 0 identifica error de transporte. No valida 10000 usuarios concurrentes.'}
from pathlib import Path
Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
