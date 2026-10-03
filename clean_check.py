# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Exercise an allowlisted copy or final ZIP outside the source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

UNIT = Path(__file__).resolve().parent
sys.path.insert(0, str(UNIT))
import package_demo
import run_demo


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output, archive=None):
    if output.exists():
        raise ValueError('OUTPUT_EXISTS')
    run_demo.verify_runtime()
    drivers = {n: sha(UNIT/n) for n in ('clean_check.py', 'package_demo.py')}
    manifest_pin = sha(UNIT/'RUNTIME_MANIFEST.json')
    archive_pin = sha(archive) if archive else None
    names = tuple(n for n in package_demo.FILES if n not in ('CHECKS.json', 'CLEAN_RUN.json'))
    with tempfile.TemporaryDirectory(prefix='c1-clean-') as tmp:
        root = Path(tmp).resolve()
        # This tool only creates/removes its own direct temporary child.
        if root.parent != Path(tempfile.gettempdir()).resolve() or root.is_relative_to(UNIT):
            raise ValueError('UNEXPECTED_TEMP_LOCATION')
        isolated = root/'package'
        isolated.mkdir()
        if archive:
            with zipfile.ZipFile(archive) as z:
                names = tuple(sorted((*package_demo.FILES, 'MANIFEST.sha256')))
                if z.namelist() != list(names):
                    raise ValueError('ARCHIVE_MEMBER_MISMATCH')
                for name in names:
                    dest = isolated/name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(name))
            expected_manifest = ''.join(f'{sha(isolated/n)}  {n}\n' for n in sorted(package_demo.FILES)).encode('ascii')
            if (isolated/'MANIFEST.sha256').read_bytes() != expected_manifest:
                raise ValueError('ARCHIVE_MANIFEST_MISMATCH')
        else:
            for name in names:
                dest = isolated/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(UNIT/name, dest)
        copied_pins = {n: sha(isolated/n) for n in names}
        if sha(isolated/'RUNTIME_MANIFEST.json') != manifest_pin:
            raise ValueError('ARCHIVE_RUNTIME_MANIFEST_MISMATCH')
        processes = []
        for script, result_path in (('run_demo.py', root/'run'), ('run_checks.py', root/'checks.json')):
            done = subprocess.run([sys.executable, '-I', '-B', str(isolated/script), '--output', str(result_path)],
                                  cwd=root, capture_output=True, text=True, timeout=120)
            processes.append({'script':script, 'exit_code':done.returncode, 'stderr_empty':not bool(done.stderr)})
            if done.returncode != 0 or done.stderr:
                raise ValueError('ISOLATED_EXECUTION_FAILED')
        result = json.loads((root/'run/RESULT.json').read_bytes())
        checks = json.loads((root/'checks.json').read_bytes())
        if result['status'] != 'PASS' or checks['status'] != 'PASS':
            raise ValueError('ISOLATED_RESULT_FAILED')
        if copied_pins != {n:sha(isolated/n) for n in names}:
            raise ValueError('COPIED_PAYLOAD_CHANGED')
        if drivers != {n:sha(UNIT/n) for n in drivers} or manifest_pin != sha(UNIT/'RUNTIME_MANIFEST.json'):
            raise ValueError('DRIVER_CHANGED')
        if archive and archive_pin != sha(archive):
            raise ValueError('ARCHIVE_CHANGED')
        record = {'schema':'c1-synthetic-clean-run/1', 'status':'PASS',
                  'mode':'FINAL_ZIP_EXTRACTED' if archive else 'ALLOWLIST_COPY',
                  'location_class':'TEMPORARY_DIRECTORY_OUTSIDE_SOURCE_TREE',
                  'python':platform.python_version(), 'sqlite':sqlite3.sqlite_version, 'platform':platform.system(),
                  'runtime_manifest_sha256':manifest_pin, 'driver_pins':drivers,
                  'archive_sha256':archive_pin, 'copied_payload_pins':copied_pins,
                  'cases':result['cases'], 'harness_test_methods':checks['unit_test_methods'],
                  'processes':processes, 'inputs_and_code_unchanged':True,
                  'limitations':['Same local Python installation; not a new OS or Python-version matrix',
                                 'Isolated Python search path and working directory; source tree is not unmounted',
                                 'Worker audit hooks observe only their own process after installation']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(record, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'status':record['status'], 'mode':record['mode'], 'cases':len(record['cases']),
                      'harness_test_methods':record['harness_test_methods']}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    try:
        main(args.output.resolve(), args.archive.resolve() if args.archive else None)
    except Exception as error:
        print(json.dumps({'status':'FAIL', 'error_type':type(error).__name__, 'reason':str(error) if isinstance(error,ValueError) else 'EXECUTION_ERROR'}))
        raise SystemExit(1)
