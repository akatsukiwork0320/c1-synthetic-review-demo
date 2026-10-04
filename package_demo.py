# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Explicit file allowlist: stage a development manifest, then build/verify a local ZIP."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import zipfile

UNIT = Path(__file__).resolve().parent
ARCHIVE = UNIT.with_suffix('.zip')
DELIVERY = UNIT.with_suffix('.DELIVERY.json')
MODULES = ('replay.py','event_decoder.py','reference_abi.py','replay_store.py','tick_index.py','ref_invariants.py','support.py','process_guard.py')
FILES = ('run_demo.py','worker.py','comparison.py','fixture_builder.py','EXPECTED.json','LIMITS.json',
    'RUNTIME_MANIFEST.json','SOURCE_PROVENANCE.json','README.md','README_JA.md','THIRD_PARTY_NOTICES.md',
    'LICENSE_STATUS.json','LICENSES/GPL-2.0.txt','PUBLIC_SOURCE_PINS.json','package_demo.py','test_demo.py',
    'CHECKS.json','CLEAN_RUN.json','run_checks.py','clean_check.py','upstream/TickMath.sol','upstream/IUniswapV3PoolEvents.sol',
    'LICENSE','LICENSE_NOTICE.md','LICENSE_MAP.json',
    'engine/replay.py','engine/event_decoder.py','engine/reference_abi.py',
    'engine/replay_store.py','engine/tick_index.py','engine/ref_invariants.py','engine/support.py','engine/process_guard.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def enc(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)+'\n').encode()


def runtime_names():
    tree = ast.parse((UNIT/'run_demo.py').read_text(encoding='utf-8'))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RUNTIME' for t in n.targets))


def verify_runtime_and_source():
    pins=json.loads((UNIT/'RUNTIME_MANIFEST.json').read_bytes())['files']
    if set(pins)!=set(runtime_names()) or any(sha((UNIT/n).read_bytes())!=h for n,h in pins.items()):
        raise ValueError('RUNTIME_MISMATCH')
    for row in json.loads((UNIT/'SOURCE_PROVENANCE.json').read_bytes())['files']:
        if row['copied_unchanged'] and sha((UNIT/'engine'/row['source_file']).read_bytes()) != row['sha256']:
            raise ValueError('COPIED_SOURCE_CHANGED')


def verify_evidence():
    verify_runtime_and_source()
    for record_name, drivers in (('CHECKS.json',('test_demo.py','run_checks.py','package_demo.py')),
                                 ('CLEAN_RUN.json',('clean_check.py','package_demo.py'))):
        record=json.loads((UNIT/record_name).read_bytes())
        if record.get('status')!='PASS' or record.get('runtime_manifest_sha256')!=sha((UNIT/'RUNTIME_MANIFEST.json').read_bytes()):
            raise ValueError('STALE_TEST_RECORD')
        if record.get('driver_pins')!={n:sha((UNIT/n).read_bytes()) for n in drivers}:
            raise ValueError('STALE_TEST_DRIVER')
        if record_name=='CLEAN_RUN.json':
            verify_clean_payload(record)
    for row in json.loads((UNIT/'PUBLIC_SOURCE_PINS.json').read_bytes())['files']:
        if sha((UNIT/row['path']).read_bytes())!=row['sha256']:
            raise ValueError('UPSTREAM_FILE_CHANGED')
    verify_licenses()


def verify_clean_payload(record):
    names=tuple(n for n in FILES if n not in ('CHECKS.json','CLEAN_RUN.json'))
    if record.get('mode')!='ALLOWLIST_COPY' or record.get('copied_payload_pins')!={n:sha((UNIT/n).read_bytes()) for n in names}:
        raise ValueError('STALE_CLEAN_PAYLOAD')


def verify_licenses():
    status=json.loads((UNIT/'LICENSE_STATUS.json').read_bytes())
    if status.get('author_election_for_new_material')!='ELECTED' or status.get('license_expression')!='GPL-2.0-or-later':
        raise ValueError('LICENSE_ELECTION_MISSING')
    if status.get('publication_authorized') is not True or status.get('public_distribution') != 'PUBLIC_RELEASE':
        raise ValueError('PUBLIC_RELEASE_METADATA_MISMATCH')
    rows=json.loads((UNIT/'LICENSE_MAP.json').read_bytes()).get('files',[])
    if len(rows)!=len(FILES)+1 or {r['path'] for r in rows}!=set(FILES)|{'MANIFEST.sha256'}:
        raise ValueError('LICENSE_MAP_COVERAGE')
    for row in rows:
        if row['path'] in ('LICENSE','LICENSES/GPL-2.0.txt'):
            if row['license_expression'] is not None or row['category']!='FSF_LICENSE_DOCUMENT':
                raise ValueError('LICENSE_DOCUMENT_MISCLASSIFIED')
        elif row['license_expression']!='GPL-2.0-or-later':
            raise ValueError('SOURCE_LICENSE_MISMATCH')
        if not row.get('basis'):raise ValueError('LICENSE_BASIS_MISSING')
    if (UNIT/'LICENSE').read_bytes()!=(UNIT/'LICENSES/GPL-2.0.txt').read_bytes():
        raise ValueError('LICENSE_TEXT_MISMATCH')
    for name in ('engine/ref_invariants.py','upstream/TickMath.sol','upstream/IUniswapV3PoolEvents.sol'):
        if 'SPDX-License-Identifier: GPL-2.0-or-later' not in (UNIT/name).read_text(encoding='utf-8')[:1500]:
            raise ValueError('UPSTREAM_LICENSE_NOTICE_MISSING')


def stage():
    # Explicitly a development snapshot, not the final package freeze.
    if ARCHIVE.exists() or DELIVERY.exists():
        raise ValueError('FINAL_PACKAGE_ALREADY_EXISTS')
    names = runtime_names()
    source = json.loads((UNIT/'SOURCE_PROVENANCE.json').read_bytes())
    for row in source['files']:
        if row['copied_unchanged'] and sha((UNIT/'engine'/row['source_file']).read_bytes()) != row['sha256']:
            raise ValueError('ORIGINAL_RUNTIME_COPY_CHANGED')
    pins = {name:sha((UNIT/name).read_bytes()) for name in names}
    (UNIT/'RUNTIME_MANIFEST.json').write_bytes(enc({'schema':'c1-synthetic-runtime-manifest/1','files':pins}))
    print(json.dumps({'runtime_files':len(pins),'status':'DEVELOPMENT_SNAPSHOT'}))


def manifest():
    return ''.join(f'{sha((UNIT/n).read_bytes())}  {n}\n' for n in sorted(FILES)).encode('ascii')


def build():
    if ARCHIVE.exists() or DELIVERY.exists() or (UNIT/'MANIFEST.sha256').exists():
        raise ValueError('REFUSE_OVERWRITE')
    for name in FILES:
        if not (UNIT/name).is_file() or (UNIT/name).is_symlink():
            raise ValueError('MISSING_OR_SYMLINK_FILE')
    verify_evidence()
    (UNIT/'MANIFEST.sha256').write_bytes(manifest())
    with zipfile.ZipFile(ARCHIVE,'x') as z:
        for name in sorted((*FILES,'MANIFEST.sha256')):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.create_system=3;info.external_attr=0o100644<<16
            z.writestr(info,(UNIT/name).read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    DELIVERY.write_bytes(enc({'schema':'c1-synthetic-review-demo-delivery/1','distribution':'PUBLIC_RELEASE_ARTIFACT',
        'public_distribution':'PUBLIC_RELEASE','license_expression':'GPL-2.0-or-later',
        'manifest_entries':len(FILES),'zip_members':len(FILES)+1,
        'manifest_sha256':sha((UNIT/'MANIFEST.sha256').read_bytes()),'zip_sha256':sha(ARCHIVE.read_bytes())}))
    verify()


def verify():
    verify_evidence()
    if (UNIT/'MANIFEST.sha256').read_bytes()!=manifest():raise ValueError('MANIFEST_MISMATCH')
    runtime=json.loads((UNIT/'RUNTIME_MANIFEST.json').read_bytes())['files']
    if any(sha((UNIT/n).read_bytes())!=h for n,h in runtime.items()):raise ValueError('RUNTIME_MISMATCH')
    with zipfile.ZipFile(ARCHIVE) as z:
        names=sorted((*FILES,'MANIFEST.sha256'))
        if z.namelist()!=names or any(z.read(n)!=(UNIT/n).read_bytes() for n in names):raise ValueError('ZIP_MISMATCH')
    d=json.loads(DELIVERY.read_bytes())
    if d['manifest_entries']!=len(FILES) or d['zip_members']!=len(FILES)+1:raise ValueError('DELIVERY_COUNTS_MISMATCH')
    if d['manifest_sha256']!=sha((UNIT/'MANIFEST.sha256').read_bytes()) or d['zip_sha256']!=sha(ARCHIVE.read_bytes()):raise ValueError('DELIVERY_MISMATCH')
    print(json.dumps({'status':'PASS',**d},sort_keys=True))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ('stage','build','verify'):raise SystemExit('Usage: python -B package_demo.py stage|build|verify')
    {'stage':stage,'build':build,'verify':verify}[sys.argv[1]]()
