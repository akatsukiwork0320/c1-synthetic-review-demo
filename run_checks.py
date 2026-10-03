# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Run only this demo's harness tests and bind the record to current code."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import sqlite3
import sys
import time
import unittest

UNIT=Path(__file__).resolve().parent
sys.path.insert(0,str(UNIT))
import run_demo

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main(output):
    if output.exists():raise ValueError('OUTPUT_EXISTS')
    before=run_demo.verify_runtime()
    drivers={n:sha(UNIT/n) for n in ('test_demo.py','run_checks.py','package_demo.py')}
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName('test_demo')
    started=time.monotonic();result=unittest.TextTestRunner(stream=stream,verbosity=1).run(suite)
    unchanged=run_demo.runtime_pins()==before and drivers=={n:sha(UNIT/n) for n in drivers}
    record={'schema':'c1-synthetic-harness-check/1','status':'PASS' if result.wasSuccessful() and unchanged else 'FAIL',
        'unit_test_methods':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'scope':'New demo harness tests; does not rerun the historical 87-test suite',
        'runtime_manifest_sha256':sha(UNIT/'RUNTIME_MANIFEST.json'),'driver_pins':drivers,'code_unchanged':unchanged,
        'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'platform':platform.system(),
        'elapsed_seconds':time.monotonic()-started,
        'failed_test_ids':[str(test) for test,_ in result.failures+result.errors]}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record,sort_keys=True))
    if not result.wasSuccessful():
        print(stream.getvalue().replace(str(UNIT),'[package]').replace(str(Path.home()),'[home]'))
    return 0 if record['status']=='PASS' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raise SystemExit(main(args.output.resolve()))
