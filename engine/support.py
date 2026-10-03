"""Local evidence utilities; no acquisition or external service code."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
UNIT=Path(__file__).resolve().parent
ROOT=UNIT.parent.parent
def now():return datetime.now(timezone.utc).isoformat()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def safe(base,name):
    if not name or name.startswith('/') or ':' in name or '\\' in name or '..' in name.split('/'):raise ValueError('UNSAFE_PATH')
    p=base/name
    if not p.resolve().is_relative_to(base.resolve()) or p.is_symlink():raise ValueError('PATH_ESCAPE')
    return p
def pin(p,base):
    h=hashlib.sha256();n=0
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b);n+=len(b)
    return {'path':p.relative_to(base).as_posix(),'bytes':n,'sha256':h.hexdigest()}
def verify(r,base):
    if pin(safe(base,r['path']),base)!={k:r[k] for k in ('path','bytes','sha256')}:raise ValueError('PIN_MISMATCH')
def write(p,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
    with Path(p).open('xb') as f:f.write(raw)
    return {'path':Path(p).name,'bytes':len(raw),'sha256':sha(raw)}
def strict_rpc(raw):
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('DUPLICATE_JSON_KEY')
            d[k]=v
        return d
    def no(_):raise ValueError('NONINTEGER_RPC_NUMBER')
    return json.loads(raw,object_pairs_hook=pairs,parse_float=no,parse_constant=no)
def lines(p,max_line=1048576):
    with p.open('rb') as f:
        while True:
            b=f.readline(max_line+1)
            if not b:break
            if len(b)>max_line:raise ValueError('LINE_LIMIT')
            yield json.loads(b)
