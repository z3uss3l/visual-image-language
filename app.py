import base64,json,os,time,uuid
from pathlib import Path
from fastapi import FastAPI,File,Form,HTTPException,UploadFile
from fastapi.responses import FileResponse
import requests
from vlr_core import *

STATIC=ROOT/'static'; HOST=os.getenv('HOST','127.0.0.1'); PORT=int(os.getenv('PORT','8765'))
app=FastAPI(title='Infinity Reconstruction Lab',version='3.2.0')

def event(name:str,**fields):
 payload={'event':name,'at':time.time(),**fields}
 print('[VLR] '+json.dumps(payload,ensure_ascii=True),flush=True)

@app.get('/')
def index():return FileResponse(STATIC/'index_v3.html')
@app.get('/api/health')
def health():
 r=runtime_status(); m=runtime_probe(model=OLLAMA_MODEL); return {'ok':True,'version':app.version,'runtime':r,'probe':m,'ollama':bool(models()),'ollama_model':OLLAMA_MODEL,'ollama_models':[x.get('name') for x in models()],'ollama_running':running(),'comfyui':comfy(),'memory':mem(),'archive':str(ARCHIVE)}
@app.get('/api/resources')
def resources():return {'memory':mem(),'runtime':runtime_status(),'probe':runtime_probe(model=OLLAMA_MODEL),'ollama_running':running(),'comfyui':comfy()}
@app.get('/api/ollama/models')
def model_list():
 ms=models(); active=resolve_model(OLLAMA_MODEL); return {'ok':bool(ms),'url':ollama_url(),'configured':OLLAMA_MODEL,'active_model':active,'sota_recommendations':SOTA_MODEL_PRIORITY,'models':ms,'probe':runtime_probe(model=OLLAMA_MODEL)}

@app.post('/api/ollama/chat')
def ollama_api(request:dict):
 if not request.get('messages'):raise HTTPException(400,'Ollama messages fehlen.')
 phase_start('ollama')
 try:
  text,result=chat(request['messages'],request.get('model'),request.get('keep_alive'),request.get('options'))
  return {'model':request.get('model') or OLLAMA_MODEL,'text':text,'load_duration':result.get('load_duration'),'eval_duration':result.get('eval_duration')}
 finally:
  if runtime_cfg().mode in ('podman','auto'): phase_stop('ollama')
@app.post('/api/ollama/analyze')
async def analyze(file:UploadFile=File(...),instruction:str='',model:str=''):
 data=await file.read();selected=model or OLLAMA_MODEL;b64=base64.b64encode(data).decode('ascii');phase_start('ollama')
 try:
  text,result=chat([{'role':'user','content':instruction or 'Describe this image factually for faithful reconstruction.','images':[b64]}],selected,'5m',{'temperature':.05,'num_ctx':4096,'num_predict':1800});return {'model':selected,'text':text,'load_duration':result.get('load_duration')}
 finally:
  if runtime_cfg().mode in ('podman','auto'): phase_stop('ollama')
@app.post('/api/ollama/unload')
def unload(request:dict|None=None):
 m=(request or {}).get('model') or OLLAMA_MODEL;return {'ok':unload_ollama(m),'model':m,'running_after':running()}
@app.post('/api/comfyui/unload')
def unload_comfy():
 if runtime_cfg().mode in ('podman','auto'): return phase_stop('comfyui')
 return {'ok':free_comfy(),'stats_after':comfy()}
@app.post('/api/generate')
async def generate(request:dict):
 # Hard phase boundary: no Qwen/Ollama container may remain while ComfyUI runs.
 if runtime_cfg().mode in ('podman','auto'):
  phase_stop('ollama')
 request_id=uuid.uuid4().hex[:12];started=time.monotonic()
 event('generation_start',request_id=request_id,generation=request.get('generation'),candidate=request.get('candidate'))
 phase_start('comfyui')
 try:
  path=Path(COMFYUI_WORKFLOW)
  if not path.is_file():
   raise HTTPException(503,'ComfyUI-Workflow fehlt.')
  try:
   workflow=json.loads(path.read_text(encoding='utf-8'))
  except Exception as e:
   raise HTTPException(500,f'Workflow ungültig: {e}')
  for node in workflow.values():
   if isinstance(node,dict) and node.get('class_type')=='CLIPTextEncode':
    node.setdefault('inputs',{})['text']=request.get('prompt','')
  try:
   q=requests.post(f'{comfyui_url()}/prompt',json={'prompt':workflow},timeout=10)
   q.raise_for_status(); pid=q.json()['prompt_id']; deadline=time.time()+OLLAMA_TIMEOUT
   while time.time()<deadline:
    h=requests.get(f'{comfyui_url()}/history/{pid}',timeout=10); h.raise_for_status()
    for out in h.json().get(pid,{}).get('outputs',{}).values():
     for im in out.get('images',[]):
      r=requests.get(f'{comfyui_url()}/view',params={'filename':im['filename'],'subfolder':im.get('subfolder',''),'type':im.get('type','output')},timeout=30)
      r.raise_for_status()
      elapsed=round(time.monotonic()-started,3)
      event('generation_complete',request_id=request_id,generation=request.get('generation'),candidate=request.get('candidate'),seconds=elapsed)
      return {'content_type':r.headers.get('content-type','image/png'),'image':base64.b64encode(r.content).decode('ascii'),'request_id':request_id,'seconds':elapsed}
    time.sleep(.5)
   raise HTTPException(504,'ComfyUI Zeitlimit überschritten.')
  except requests.RequestException as e:
   raise HTTPException(502,f'ComfyUI fehlgeschlagen: {e}')
 except Exception as exc:
  event('generation_failed',request_id=request_id,generation=request.get('generation'),candidate=request.get('candidate'),error=str(exc))
  raise
 finally:
  if runtime_cfg().mode in ('podman','auto') and not request.get('keep_runtime', False):
   phase_stop('comfyui')
@app.get('/api/runtime')
def runtime(): return {'status':runtime_status(),'probe':runtime_probe(model=OLLAMA_MODEL)}

@app.post('/api/runtime/select')
def runtime_select(request:dict):
 mode=str(request.get('mode','')).lower()
 if mode not in {'native','podman','auto'}: raise HTTPException(400,'Runtime muss native, podman oder auto sein.')
 old=runtime_cfg().mode
 if old != mode and old in {'podman','auto'}:
  phase_stop('comfyui'); phase_stop('ollama')
 set_runtime_mode(mode)
 return {'ok':True,'previous':old,'selected':mode,'status':runtime_status(),'probe':runtime_probe(mode=mode,model=OLLAMA_MODEL)}

@app.post('/api/runtime/probe')
def runtime_probe_api(request:dict|None=None):
 r=request or {}; return runtime_probe(mode=r.get('mode') or runtime_cfg().mode,model=r.get('model') or OLLAMA_MODEL)

@app.post('/api/runtime/prepare')
def runtime_prepare(request:dict|None=None):
 r=request or {}; mode=r.get('mode') or runtime_cfg().mode
 if mode == 'native': return runtime_probe(mode='native',model=r.get('model') or OLLAMA_MODEL)
 try:
  phase_start('ollama')
 except HTTPException:
  raise
 return runtime_probe(mode=mode,model=r.get('model') or OLLAMA_MODEL)

@app.post('/api/runtime/start')
def runtime_start(request:dict): return phase_start(request.get('phase','ollama'))
@app.post('/api/runtime/stop')
def runtime_stop(request:dict): return phase_stop(request.get('phase','ollama'))
@app.post('/api/compare')
async def compare_api(reference:UploadFile=File(...),candidate:UploadFile=File(...)):return cmp(await reference.read(),await candidate.read())
@app.post('/api/archive/original')
async def archive_reference(file:UploadFile=File(...)):
 data=await file.read();return {'ok':True,'path':archive_original(data)}
@app.post('/api/archive/original-description')
def original_description(payload:dict):
 p=ARCHIVE/'original-description.md';content=str(payload.get('content',''))
 if not content.strip():raise HTTPException(400,'Originalbeschreibung fehlt.')
 if not p.exists():p.write_text(content,encoding='utf-8')
 return {'ok':True,'immutable':True}
@app.post('/api/archive')
async def archive(image:UploadFile=File(...),metadata:str=Form('')):
 try:m=json.loads(metadata) if metadata else {}
 except json.JSONDecodeError:m={}
 return {'ok':True,'run_id':archive_exp(m,await image.read())}
@app.get('/api/history')
def history(limit:int=100):
 with db() as c:r=c.execute('SELECT id,created_at,generation,label,parent_id,prompt,human_selected,original_match,previous_match,metrics_json,human_rating,mutation_type,mutation_feedback,seed,image_path,image_retained,is_winner,is_best FROM experiments ORDER BY created_at DESC LIMIT ?',(max(1,min(limit,1000)),)).fetchall()
 return [dict(x) for x in r]
@app.post('/api/retention')
def retention_api(request:dict):
 if request.get('full_history'):return {'ok':True,'mode':'full','deleted':0}
 return {'ok':True,'mode':'retained',**retention(int(request.get('current_generation',0)),int(request.get('keep_last',RETENTION_LAST)),bool(request.get('keep_improvements',RETENTION_KEEP_IMPROVEMENTS)),float(request.get('min_improvement',RETENTION_MIN_IMPROVEMENT)))}
@app.post('/api/archive/meta')
def meta(metadata:str=Form('')):
 try:m=json.loads(metadata)
 except json.JSONDecodeError:m={}
 mid=os.urandom(8).hex();content=m.get('content','')
 with db() as c:c.execute('INSERT INTO meta_prompts VALUES(?,?,?,?)',(mid,time.time(),int(m.get('source_count',0)),content))
 (ARCHIVE/f'metamaster_{mid}.md').write_text(content,encoding='utf-8');return {'ok':True,'id':mid}
@app.get('/api/meta-history')
def meta_history(limit:int=20):
 with db() as c:r=c.execute('SELECT * FROM meta_prompts ORDER BY created_at DESC LIMIT ?',(max(1,min(limit,100)),)).fetchall()
 return [dict(x) for x in r]
if __name__=='__main__':
 import uvicorn;uvicorn.run(app,host=HOST,port=PORT)
