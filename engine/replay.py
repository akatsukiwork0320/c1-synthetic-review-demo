"""Offline, provider-relative CORE/TICKS replay under an explicit model assumption."""
import argparse,hashlib,json,os,re,sqlite3,sys,time
from pathlib import Path
from support import UNIT,ROOT,load,write,pin,verify,sha,canonical,safe,lines,now,strict_rpc
from event_decoder import decode_event,EventOrder,DecodeError
from replay_store import ReplayStore,ReplayError
from process_guard import ProcessGuard
import ref_invariants as inv

class Stop(RuntimeError):
    def __init__(self,code,status='Unknown'):self.code=code;self.status=status;super().__init__(code)
def integer_text(v):
    if type(v)is int:return v
    if type(v)is str and (v=='0' or v.lstrip('-').isdigit()) and str(int(v))==v:return int(v)
    raise Stop('NONCANONICAL_ANCHOR_INTEGER','Invalid')
def verified_pin(row,base):
    try:verify(row,base)
    except ValueError as e:raise Stop('INPUT_PIN_MISMATCH','Invalid') from e
def hash32(value):
    if type(value)is not str or re.fullmatch(r'0x[0-9a-fA-F]{64}',value)is None:raise Stop('HEADER_HASH_SCHEMA','Invalid')
    return value.lower()
def ticks_from_p4(path):
    for r in lines(path):
        yield (integer_text(r['tick']),integer_text(r['values']['liquidityGross']),integer_text(r['values']['liquidityNet']))
def write_final(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode()
    if path.exists():
        if path.read_bytes()!=raw:raise Stop('FINAL_ARTIFACT_CONFLICT','Invalid')
    else:
        tmp=path.with_name(path.name+'.partial')
        with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
def write_final_ticks(path,rows):
    if path.exists():
        with path.open('rb') as f:
            for t,g,n in rows:
                if f.readline()!=canonical({'tick':t,'gross':str(g),'net':str(n)})+b'\n':raise Stop('FINAL_ARTIFACT_CONFLICT','Invalid')
            if f.read(1):raise Stop('FINAL_ARTIFACT_CONFLICT','Invalid')
    else:
        tmp=path.with_name(path.name+'.partial')
        with tmp.open('wb') as f:
            for t,g,n in rows:f.write(canonical({'tick':t,'gross':str(g),'net':str(n)})+b'\n')
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
def final_bitmap(rows,spacing):
    lo,hi=inv.usable_tick_bounds(spacing);lo=(lo//spacing)>>8;hi=(hi//spacing)>>8
    current=lo;bits=0
    for tick,gross,net in rows:
        word=(tick//spacing)>>8;bit=(tick//spacing)&255
        while current<word:yield current,bits;current+=1;bits=0
        bits|=1<<bit
    while current<=hi:yield current,bits;current+=1;bits=0
def run(output,resume=False):
    plan=load(UNIT/'RUN_PLAN.json');seal=load(UNIT/'RUN_PLAN.SEAL.json')
    if sha((UNIT/'RUN_PLAN.json').read_bytes())!=seal['raw_sha256']:raise Stop('PLAN_SEAL','Invalid')
    for r in plan['code_pins']+plan['unit_pins']:verify(r,UNIT)
    binding=load(UNIT/'INPUT_BINDINGS.json');scope=binding['scope']
    if plan['scope_id']!=binding['scope_id']:raise Stop('SCOPE_BINDING','Invalid')
    acceptance=load(UNIT/'P4_ACCEPTANCE.json')
    if acceptance.get('anchor_verified') is not True:raise Stop('P4_NOT_READY')
    if plan['model']!='ASSUMED_MODEL' or plan['verification_scope']!='MATHEMATICAL_INTEGRITY' or plan['source_identity']!='UNKNOWN':raise Stop('MODEL_CONTRACT','Invalid')
    out=Path(output).resolve()
    if 'output' in plan and out!=safe(ROOT,plan['output']).resolve():raise Stop('OUTPUT_BINDING','Invalid')
    sources=[];nextblock=scope['from_block']
    for source in lines(UNIT/'SOURCE_ROWS.jsonl'):
        if len(sources)>=plan['limits'].get('source_metadata_rows',4096):raise Stop('SOURCE_METADATA_LIMIT')
        if (type(source['ordinal'])is not int or source['ordinal']!=len(sources)+1 or
            type(source['from_block'])is not int or type(source['to_block'])is not int or
            source['from_block']!=nextblock or source['to_block']<nextblock):raise Stop('SOURCE_RANGE_ORDER','Invalid')
        nextblock=source['to_block']+1;sources.append(source)
    if nextblock!=scope['to_block']+1 or len(sources)!=binding['response_count']:raise Stop('SOURCE_RANGE_INCOMPLETE')
    if out.exists() and not resume:raise Stop('OUTPUT_EXISTS','Invalid')
    if not out.exists():out.mkdir(parents=True)
    if (out/'RESULT.json').exists():raise Stop('FINAL_RESULT_EXISTS','Invalid')
    allowed=[ROOT/r['path'] for r in binding['artifacts']]+[ROOT/r['body_path'] for r in sources]
    guard=ProcessGuard(UNIT,out,allowed);sys.addaudithook(guard.hook)
    start=time.monotonic();progress_at=start;counts={'headers':0,'responses_verified':0,'log_occurrences':0,'events_applied':0,'resume_skipped_responses':0}
    result={'schema':'p5-replay-result/1','sharing':'LOCAL_RESTRICTED','source_class':plan['source_class'],
       'started_utc':now(),'status':'RUNNING','model':'ASSUMED_MODEL','source_identity':'UNKNOWN',
       'scope_id':plan['scope_id'],'run_plan_sha256':sha((UNIT/'RUN_PLAN.json').read_bytes()),
       'queries':['CORE','TICKS'],'actual_balance':'OMIT','proof_scope':'Conditional event-projection replay; not full EVM validation',
       'counts':counts,'resumed':resume}
    headers=None;store=None;last_snapshot=None
    def check():
        if time.monotonic()-start>plan['limits']['seconds']:raise Stop('TIME_LIMIT')
    def progress(phase,force=False):
        nonlocal progress_at
        check()
        if force or time.monotonic()-progress_at>=20:
            progress_at=time.monotonic()
            size=sum(p.stat().st_size for p in out.iterdir() if p.is_file())
            if size>plan['limits']['output_bytes']:raise Stop('OUTPUT_LIMIT')
            message={'phase':phase,'counts':dict(counts),'elapsed_seconds':round(progress_at-start,3)}
            with (out/'PROGRESS.jsonl').open('ab') as f:f.write(canonical(message)+b'\n')
            print(json.dumps(message),flush=True)
    try:
        for r in binding['artifacts']:verified_pin(r,ROOT)
        headers=sqlite3.connect(out/'HEADERS.sqlite');headers.execute('PRAGMA journal_mode=DELETE');headers.execute('PRAGMA synchronous=FULL');headers.execute('PRAGMA cache_size=-8192')
        headers.execute('CREATE TABLE IF NOT EXISTS headers(number INTEGER PRIMARY KEY,hash TEXT UNIQUE,parent TEXT)')
        headers.execute('DELETE FROM headers');headers.commit()
        expected=scope['from_block'];previous=hash32(scope['anchor_hash']);anchor_hash=previous
        for r in lines(ROOT/binding['branch_index']['path']):
            current=hash32(r['hash']);parent=hash32(r['parent_hash'])
            if type(r['number'])is not int or r['number']!=expected or parent!=previous or current==anchor_hash:raise Stop('BRANCH_CHAIN','Invalid')
            try:headers.execute('INSERT INTO headers VALUES(?,?,?)',(r['number'],current,parent))
            except sqlite3.IntegrityError as e:raise Stop('BRANCH_DUPLICATE','Invalid') from e
            expected+=1;previous=current;counts['headers']+=1
            if counts['headers']%4096==0:headers.commit();progress('HEADER_INDEX')
        headers.commit()
        if expected!=scope['to_block']+1:raise Stop('BRANCH_INCOMPLETE')
        artifact={Path(r['path']).name:r for r in binding['artifacts']}
        anchor=load(ROOT/artifact['ANCHOR_STATE.json']['path'])['values']
        slot0={k:integer_text(v) if type(v)is str and not v.startswith('0x') else v for k,v in anchor['slot0'].items()}
        spacing=integer_text(anchor['tickSpacing']['tickSpacing']);maxL=integer_text(anchor['maxLiquidityPerTick']['maxLiquidityPerTick'])
        initialL=integer_text(anchor['liquidity']['liquidity'])
        store=ReplayStore(out/'SOLVER.sqlite',{'schema':'p5-assumed-model-binding/1','run_plan_sha256':result['run_plan_sha256'],
            'scope_id':plan['scope_id'],'model':'ASSUMED_MODEL','source_identity':'UNKNOWN','queries':['CORE','TICKS']})
        if not store.is_seeded:store.seed(slot0,initialL,spacing,maxL,ticks_from_p4(ROOT/artifact['TICKS.jsonl']['path']))
        ordering=EventOrder();previous_position=None;previous_tx=None;previous_bh=None
        last=store.checkpoint();resume_ordinal=last['ordinal'] if last else 0
        for source in sources:
            check()
            if source['body_bytes']>plan['limits']['body_bytes']:raise Stop('BODY_LIMIT')
            with safe(ROOT,source['body_path']).open('rb') as f:
                f.seek(source['offset']);raw=f.read(source['body_bytes'])
            if len(raw)!=source['body_bytes'] or sha(raw)!=source['body_sha256']:raise Stop('BODY_PIN','Invalid')
            counts['responses_verified']+=1
            if source['ordinal']<=resume_ordinal:
                if store.begin_chunk(source['ordinal'],source['body_sha256']) is not False:raise Stop('RESUME_CHECKPOINT','Invalid')
                counts['resume_skipped_responses']+=1;continue
            try:body=strict_rpc(raw)
            except (ValueError,UnicodeError) as e:raise Stop('RPC_JSON_INVALID','Invalid') from e
            if type(body)is not dict or set(body)!={'jsonrpc','id','result'} or body['jsonrpc']!='2.0' or type(body['id'])is not type(source['request_id']) or body['id']!=source['request_id'] or type(body['result'])is not list:raise Stop('RPC_ENVELOPE','Invalid')
            if len(body['result'])>plan['limits']['logs_per_response']:raise Stop('RESPONSE_RECORD_LIMIT')
            store.begin_chunk(source['ordinal'],source['body_sha256'])
            for rawlog in body['result']:
                event=decode_event(rawlog,pool=scope['target_pool_address'],tick_spacing=spacing,projection='CORE_TICKS')
                number=event['block_number']
                if not source['from_block']<=number<=source['to_block']:raise Stop('LOG_RANGE','Invalid')
                h=headers.execute('SELECT hash FROM headers WHERE number=?',(number,)).fetchone()
                if h is None or h[0]!=event['block_hash'].lower():raise Stop('LOG_BLOCK_BINDING','Invalid')
                ordering.accept(event)
                position=(number,event['transaction_index'])
                if position==previous_position and (event['transaction_hash']!=previous_tx or event['block_hash']!=previous_bh):raise Stop('TRANSACTION_BINDING','Invalid')
                previous_position,previous_tx,previous_bh=position,event['transaction_hash'],event['block_hash']
                store.apply(event);counts['log_occurrences']+=1;counts['events_applied']+=1
                if counts['log_occurrences']%512==0:check()
            store.commit_chunk(source['ordinal'],source['body_sha256'],source['to_block']);progress('REPLAY')
        last_snapshot=store.snapshot();last=store.checkpoint()
        if last is None or last['ordinal']!=binding['response_count'] or last['range_end']!=scope['to_block']:raise Stop('REPLAY_INCOMPLETE')
        core=last_snapshot['core']
        final=inv.evaluate_state({'sqrtPriceX96':int(core['sqrtPriceX96']),'tick':core['tick']},int(core['liquidity']),spacing,maxL,
             final_bitmap(store.iter_ticks(),spacing),((t,{'liquidityGross':g,'liquidityNet':n,'initialized':True}) for t,g,n in store.iter_ticks()))
        write_final(out/'FINAL_INVARIANTS.json',{'observations':final['observations'],'scope':'Internal reconstructed tick-state checks; bitmap derived from ticks, not independent RPC evidence'})
        if any(v!=0 for v in final['observations'].values()):raise Stop('FINAL_NUMERIC_INVARIANT','Invalid')
        write_final(out/'FINAL_STATE.json',last_snapshot)
        write_final_ticks(out/'FINAL_TICKS.jsonl',store.iter_ticks())
        for r in binding['artifacts']:verified_pin(r,ROOT)
        for r in plan['code_pins']+plan['unit_pins']:verify(r,UNIT)
        progress('COMPLETE',True)
        result.update(status='Known',reason='CONDITIONAL_CORE_TICKS_REPLAY_COMPLETE',coverage_closed=True,
           event_counts=last_snapshot['counts'],checkpoint=last,anchor_verified=True,verification_scope='MATHEMATICAL_INTEGRITY')
    except Exception as e:
        if store:
            store.rollback_chunk()
            try:last_snapshot=store.snapshot()
            except Exception:pass
        status='Invalid' if isinstance(e,ReplayError) else getattr(e,'status','RUN_FAILED');code=getattr(e,'code',type(e).__name__)
        result.update(status=status,reason=code,coverage_closed=False,exception_type=type(e).__name__)
        if last_snapshot is not None:write(out/'LAST_COMMITTED_STATE.json',last_snapshot)
    finally:
        if store:store.close()
        if headers:headers.close()
    result.update(finished_utc=now(),elapsed_seconds=time.monotonic()-start,process_observation=guard.report())
    write_final(out/'RESULT.json',result)
    print(json.dumps({'status':result['status'],'reason':result['reason'],'counts':counts,'elapsed_seconds':result['elapsed_seconds']}),flush=True)
    return 0 if result['status']=='Known' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();raise SystemExit(run(a.output,a.resume))
