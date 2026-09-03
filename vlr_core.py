import base64, gc, hashlib, io, json, os, sqlite3, time, uuid
from pathlib import Path
import cv2, numpy as np, psutil, requests
from vlr_runtime import cfg as runtime_cfg, status as runtime_status, probe as runtime_probe, set_runtime_mode, start_ollama, stop_ollama, start_comfyui, stop_comfyui, RuntimeErrorState
from fastapi import File, Form, HTTPException, UploadFile
from PIL import Image
from skimage.metrics import structural_similarity as ssim

ROOT=Path(__file__).resolve().parent; ARCHIVE=ROOT/'archive'; CONFIG=ROOT/'config'; DB=ARCHIVE/'experiments.sqlite3'; ARCHIVE.mkdir(exist_ok=True); CONFIG.mkdir(exist_ok=True)
OLLAMA_URL=os.getenv('OLLAMA_URL','http://127.0.0.1:11434'); COMFYUI_URL=os.getenv('COMFYUI_URL','http://127.0.0.1:8188'); OLLAMA_MODEL=os.getenv('OLLAMA_MODEL','qwen3.8:27b'); OLLAMA_TIMEOUT=float(os.getenv('OLLAMA_TIMEOUT','600')); OLLAMA_PHASE_KEEP_ALIVE=os.getenv('OLLAMA_PHASE_KEEP_ALIVE','5m')
COMFYUI_WORKFLOW=os.getenv('COMFYUI_WORKFLOW',str(CONFIG/'comfyui-workflow.json')); RETENTION_LAST=int(os.getenv('RETENTION_LAST','5')); RETENTION_KEEP_IMPROVEMENTS=os.getenv('RETENTION_KEEP_IMPROVEMENTS','1')!='0'; RETENTION_MIN_IMPROVEMENT=float(os.getenv('RETENTION_MIN_IMPROVEMENT','0.005'))

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
 with db() as c:
  # Create the base tables first.  Do NOT create indexes on newly introduced
  # columns until legacy databases have been migrated.  V3.2 previously did
  # this in the opposite order, which made an existing V2/V3 database fail
  # during import with: no such column: image_retained.
  c.execute('''CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,created_at REAL NOT NULL,generation INTEGER,label TEXT,parent_id TEXT,prompt TEXT,description TEXT,metrics_json TEXT,human_selected INTEGER DEFAULT 0,original_match REAL,previous_match REAL,human_rating INTEGER)''')
  c.execute('''CREATE TABLE IF NOT EXISTS reference_images(id TEXT PRIMARY KEY,sha256 TEXT UNIQUE NOT NULL,created_at REAL NOT NULL,original_path TEXT NOT NULL)''')
  c.execute('''CREATE TABLE IF NOT EXISTS meta_prompts(id TEXT PRIMARY KEY,created_at REAL NOT NULL,source_count INTEGER,content TEXT NOT NULL)''')
  cols={r[1] for r in c.execute('PRAGMA table_info(experiments)')}
  migrations={'mutation_type':'TEXT','mutation_feedback':'TEXT','seed':'TEXT','image_path':'TEXT','image_retained':'INTEGER DEFAULT 1','is_winner':'INTEGER DEFAULT 0','is_best':'INTEGER DEFAULT 0'}
  for n,t in migrations.items():
   if n not in cols:
    c.execute(f'ALTER TABLE experiments ADD COLUMN {n} {t}')
  # Index creation is deliberately after migration.
  c.execute('CREATE INDEX IF NOT EXISTS idx_exp_generation ON experiments(generation)')
  c.execute('CREATE INDEX IF NOT EXISTS idx_exp_retained ON experiments(image_retained)')
init_db()

def req(url,method='get',timeout=30,**kw):return requests.request(method,url,timeout=timeout,**kw)
def ollama_url():
 r=runtime_cfg()
 if r.mode == 'podman': return f'http://127.0.0.1:{r.ollama_host_port}'
 if r.mode == 'auto':
  try:
   if runtime_status().get('ollama',{}).get('running'): return f'http://127.0.0.1:{r.ollama_host_port}'
  except Exception: pass
 return os.getenv('OLLAMA_URL','http://127.0.0.1:11434')

def comfyui_url():
 r=runtime_cfg()
 if r.mode == 'podman': return f'http://127.0.0.1:{r.comfy_host_port}'
 if r.mode == 'auto':
  try:
   if runtime_status().get('comfyui',{}).get('running'): return f'http://127.0.0.1:{r.comfy_host_port}'
  except Exception: pass
 return os.getenv('COMFYUI_URL','http://127.0.0.1:8188')

def models():
 try:r=req(f'{ollama_url()}/api/tags',timeout=3);r.raise_for_status();return r.json().get('models',[])
 except requests.RequestException:return []
def running():
 try:r=req(f'{ollama_url()}/api/ps',timeout=3);r.raise_for_status();return r.json().get('models',[])
 except requests.RequestException:return []
def mem():
 v=psutil.virtual_memory();return {'total':v.total,'available':v.available,'used':v.used,'percent':v.percent}
def img(data):
 a=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
 if a is None:raise ValueError('Ungültige Bilddatei')
 return a
def cos(a,b):
 d=float(np.linalg.norm(a)*np.linalg.norm(b));return float(np.dot(a,b)/d) if d else 1.0
def cmp(a,b):
 a=cv2.resize(img(a),(512,512),interpolation=cv2.INTER_AREA);b=cv2.resize(img(b),(512,512),interpolation=cv2.INTER_AREA);ag=cv2.cvtColor(a,cv2.COLOR_BGR2GRAY);bg=cv2.cvtColor(b,cv2.COLOR_BGR2GRAY)
 mse=float(np.mean((a.astype(np.float32)-b.astype(np.float32))**2)); s=float(ssim(ag,bg,data_range=255)); ea=cv2.Canny(ag,80,180);eb=cv2.Canny(bg,80,180);u=np.logical_or(ea>0,eb>0).sum();e=float(np.logical_and(ea>0,eb>0).sum()/u) if u else 1.0
 ah=cv2.cvtColor(a,cv2.COLOR_BGR2HSV);bh=cv2.cvtColor(b,cv2.COLOR_BGR2HSV);ha=cv2.calcHist([ah],[0,1],None,[32,32],[0,180,0,256]);hb=cv2.calcHist([bh],[0,1],None,[32,32],[0,180,0,256]);cv2.normalize(ha,ha);cv2.normalize(hb,hb);color=max(0,min(1,(float(cv2.compareHist(ha,hb,cv2.HISTCMP_CORREL))+1)/2))
 ga=cv2.Laplacian(ag,cv2.CV_32F);gb=cv2.Laplacian(bg,cv2.CV_32F);ga=(ga-ga.mean())/(ga.std()+1e-6);gb=(gb-gb.mean())/(gb.std()+1e-6);g=max(0,min(1,(cos(ga.ravel(),gb.ravel())+1)/2));ta=cv2.resize(a,(32,32),interpolation=cv2.INTER_AREA).astype(np.float32);tb=cv2.resize(b,(32,32),interpolation=cv2.INTER_AREA).astype(np.float32);t=max(0,min(1,(cos(ta.ravel(),tb.ravel())+1)/2));score=.28*s+.18*e+.18*color+.18*g+.18*t
 return {'mse':mse,'psnr_db':float(cv2.PSNR(a,b)) if mse else 99.0,'ssim':s,'edge_iou':e,'color_similarity':color,'gradient_similarity':g,'thumbnail_similarity':t,'composite':float(score),'threshold_98':score>=.98,'metric_version':'vlr-composite-v3'}
SOTA_MODEL_PRIORITY = [
    'qwen3.8:27b', 'gemma4:31b', 'glm-5.3-flash:18b', 'qwen3-vl:30b',
    'gemma4:12b', 'nemotron-3.5:30b', 'deepseek-v4:28b', 'qwen3-vl:8b',
    'qwen2.5-vl:7b', 'llama3.2-vision:11b', 'llava:13b', 'gemma4:e4b',
    'qwen3-vl:2b'
]


def resolve_model(requested_model=None):
    target = requested_model or OLLAMA_MODEL
    avail = [x.get('name') for x in models() if x.get('name')]
    if not avail or target in avail:
        return target
    for pref in SOTA_MODEL_PRIORITY:
        if pref in avail:
            return pref
    for m in avail:
        if any(v in m.lower() for v in ('vl', 'vision', 'llava', 'qwen', 'gemma', 'llama')):
            return m
    return avail[0]

def chat(messages,model=None,keep=None,options=None):
 m=resolve_model(model)
 p={'model':m,'messages':messages,'stream':False,'keep_alive':OLLAMA_PHASE_KEEP_ALIVE if keep is None else keep,'options':options or {'temperature':.1,'num_ctx':4096,'num_predict':1800}}
 try:r=req(f'{ollama_url()}/api/chat','post',OLLAMA_TIMEOUT,json=p);r.raise_for_status();j=r.json();return j.get('message',{}).get('content','').strip(),j
 except requests.RequestException as e:raise HTTPException(502,f'Ollama request failed: {e}')
def unload_ollama(model=None):
 m=resolve_model(model)
 try:r=req(f'{ollama_url()}/api/generate','post',30,json={'model':m,'prompt':'','stream':False,'keep_alive':0});return r.ok
 except requests.RequestException:return False

def free_comfy():
 try:r=req(f'{comfyui_url()}/free','post',10,json={'unload_models':True,'free_memory':True});return r.ok
 except requests.RequestException:return False
def comfy():
 try:r=req(f'{comfyui_url()}/system_stats',timeout=3);return {'ok':r.ok,'stats':r.json() if r.ok else {}}
 except requests.RequestException:return {'ok':False,'stats':{}}
def archive_original(data):
 h=hashlib.sha256(data).hexdigest();folder=ARCHIVE/'originals';folder.mkdir(exist_ok=True);p=folder/f'{h[:16]}.png'
 if not p.exists():Image.open(io.BytesIO(data)).convert('RGB').save(p,'PNG')
 with db() as c:c.execute('INSERT OR IGNORE INTO reference_images VALUES (?,?,?,?)',(uuid.uuid4().hex,h,time.time(),str(p.relative_to(ROOT))))
 return str(p.relative_to(ROOT))
def archive_exp(meta,data):
 rid=uuid.uuid4().hex;g=int(meta.get('generation',-1));folder=ARCHIVE/f'gen_{g}_{rid[:8]}';folder.mkdir(parents=True,exist_ok=True);p=folder/'image.png';p.write_bytes(data);m=dict(meta);m.update({'run_id':rid,'archived_at':time.time(),'image':str(p.relative_to(ROOT))});(folder/'metadata.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
 with db() as c:c.execute('''INSERT INTO experiments(id,created_at,generation,label,parent_id,prompt,description,metrics_json,human_selected,original_match,previous_match,human_rating,mutation_type,mutation_feedback,seed,image_path,image_retained,is_winner,is_best) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(rid,m['archived_at'],g,m.get('label'),m.get('parent_id'),m.get('prompt',''),m.get('description',''),json.dumps(m.get('metrics',{}),ensure_ascii=False),int(bool(m.get('human_selected'))),float(m.get('metrics',{}).get('composite',0)),float(m.get('previous_match',0)),int(m['human_rating']) if str(m.get('human_rating','')).isdigit() else None,m.get('mutation_type'),m.get('mutation_feedback',''),str(m.get('seed','')),str(p.relative_to(ROOT)),1,int(bool(m.get('is_winner'))),0))
 return rid
def retention(g,keep=RETENTION_LAST,improve=RETENTION_KEEP_IMPROVEMENTS,delta=RETENTION_MIN_IMPROVEMENT):
 cut=g-max(0,keep)+1
 with db() as c:
  rows=c.execute('SELECT * FROM experiments WHERE image_retained=1 ORDER BY generation,created_at').fetchall();best=c.execute('SELECT id FROM experiments ORDER BY original_match DESC,created_at DESC LIMIT 1').fetchone();protected={best['id']} if best else set()
  if improve:
   by={}
   for r in rows:by.setdefault(r['generation'],[]).append(r)
   bestso=-1
   for gen in sorted(by):
    score=max(float(r['original_match'] or 0) for r in by[gen])
    if score-bestso>=delta:bestso=score;protected.add(max(by[gen],key=lambda r:float(r['original_match'] or 0))['id'])
  for r in rows:
   if r['id'] in protected or r['generation']>=cut:continue
   p=ROOT/r['image_path'] if r['image_path'] else None
   if p and p.exists():
    try:p.unlink();(p.parent/'metadata.json').unlink(missing_ok=True);p.parent.rmdir()
    except OSError:pass
   c.execute('UPDATE experiments SET image_retained=0 WHERE id=?',(r['id'],))
 gc.collect();return {'cutoff_generation':cut,'kept_last':keep,'kept_improvements':improve,'min_improvement':delta}


def phase_start(kind: str) -> dict:
    runtime = runtime_cfg()
    if runtime.mode == "native":
        return {"mode": "native", "started": False, "kind": kind}
    if runtime.mode == "auto" and (not runtime.podman_bin or not runtime_status().get("podman_available")):
        return {"mode": "native-fallback", "started": False, "kind": kind}
    try:
        return {"mode": "podman", "kind": kind, **(start_ollama() if kind == "ollama" else start_comfyui())}
    except RuntimeErrorState as exc:
        if runtime.mode == "auto":
            return {"mode": "native-fallback", "started": False, "kind": kind, "error": str(exc)}
        raise HTTPException(503, str(exc))


def phase_stop(kind: str) -> dict:
    runtime = runtime_cfg()
    if runtime.mode == "native":
        return {"mode": "native", "stopped": False, "kind": kind}
    try:
        return {"mode": "podman", "kind": kind, **(stop_ollama() if kind == "ollama" else stop_comfyui())}
    except RuntimeErrorState as exc:
        if runtime.mode == "auto":
            return {"mode": "native-fallback", "stopped": False, "kind": kind, "error": str(exc)}
        raise HTTPException(503, str(exc))
