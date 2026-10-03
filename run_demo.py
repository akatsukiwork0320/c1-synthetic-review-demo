# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Portable four-case synthetic demo. No external input/RPC option exists."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time

UNIT = Path(__file__).resolve().parent
sys.path.insert(0, str(UNIT))
from comparison import compare, wrapper_checks
from fixture_builder import build_case

CASES = ('D1', 'D2', 'D3', 'D4')
RUNTIME = ('comparison.py', 'fixture_builder.py', 'worker.py', 'run_demo.py', 'EXPECTED.json', 'LIMITS.json',
           'engine/replay.py', 'engine/event_decoder.py', 'engine/reference_abi.py', 'engine/replay_store.py',
           'engine/tick_index.py', 'engine/ref_invariants.py', 'engine/support.py', 'engine/process_guard.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_pins():
    return {name: digest(UNIT / name) for name in RUNTIME}


def verify_runtime():
    recorded = json.loads((UNIT / 'RUNTIME_MANIFEST.json').read_bytes())
    actual = runtime_pins()
    if recorded.get('files') != actual:
        raise ValueError('RUNTIME_PIN_MISMATCH')
    return actual


def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write('\n')


def tree_measure(root):
    files = list(root.rglob('*'))
    if any(p.is_symlink() for p in files):
        raise ValueError('SYMLINK_IN_OUTPUT')
    return {'files': sum(p.is_file() for p in files), 'bytes': sum(p.stat().st_size for p in files if p.is_file())}


def main(output):
    pins = verify_runtime()
    expected = json.loads((UNIT / 'EXPECTED.json').read_bytes())['cases']
    limits = json.loads((UNIT / 'LIMITS.json').read_bytes())
    output = output.resolve()
    if output.exists():
        raise ValueError('OUTPUT_EXISTS')
    if output.is_relative_to(UNIT):
        raise ValueError('OUTPUT_MUST_BE_OUTSIDE_PACKAGE')
    output.mkdir(parents=True)
    save(output / 'RUN_PLAN.json', {'cases': list(CASES), 'runtime_pins': pins, 'limits': limits,
        'source_class': 'SYNTHETIC_FIXTURE', 'scope': 'Four fixed synthetic demonstrations, not the full historical test suite'})
    started = time.monotonic()
    results = []
    for case_id in CASES:
        directory = output / case_id
        build_case(directory, case_id, UNIT)
        measurements = tree_measure(directory)
        if measurements['files'] > limits['case_files'] or measurements['bytes'] > limits['case_bytes']:
            raise ValueError('FIXTURE_LIMIT')
        initial_case_pins = {str(p.relative_to(directory)).replace('\\', '/'): digest(p) for p in directory.rglob('*') if p.is_file()}
        save(output / (case_id + '_INPUT_PINS.json'), initial_case_pins)
        failure = None
        completed = None
        try:
            completed = subprocess.run([sys.executable, '-I', '-B', str(UNIT / 'worker.py'),
                '--case-root', str(directory), '--case', case_id], cwd=directory,
                capture_output=True, text=True, timeout=limits['child_seconds'], check=False)
        except subprocess.TimeoutExpired:
            failure = 'CHILD_TIMEOUT'
        observation = directory / 'out' / 'OBSERVATION.json'
        actual = json.loads(observation.read_bytes()) if observation.exists() else {}
        failures = compare(expected[case_id], actual)
        if case_id in ('D1', 'D4'):
            failures += wrapper_checks(actual)
        if failure:
            failures.append(failure)
        if completed is None or completed.returncode != 0:
            failures.append('CHILD_DID_NOT_COMPLETE_NORMALLY')
        if completed is not None and completed.stderr:
            failures.append('CHILD_STDERR_NOT_EMPTY')
        guard = actual.get('process_observation', {})
        if guard.get('scope') != 'THIS_PROCESS_AFTER_HOOK_INSTALLATION':
            failures.append('GUARD_SCOPE_MISSING')
        counts = guard.get('counts', {})
        if any(counts.get(k) != 0 for k in ('network_attempts', 'process_attempts', 'denied_open')):
            failures.append('UNEXPECTED_GUARD_ACTIVITY')
        if type(counts.get('open_events')) is not int or counts['open_events'] < 1:
            failures.append('NO_OBSERVED_INPUT_OPEN')
        for name, pinned in initial_case_pins.items():
            if digest(directory / name) != pinned:
                failures.append('CASE_INPUT_CHANGED:' + name)
        if runtime_pins() != pins:
            failures.append('RUNTIME_CHANGED')
        size = tree_measure(directory)
        if size['files'] > limits['case_files'] or size['bytes'] > limits['case_bytes']:
            failures.append('CASE_OUTPUT_LIMIT')
        layer = 'REPLAY_WRAPPER' if case_id in ('D1', 'D4') else 'TRANSACTION_DECODER'
        row = {'case_id': case_id, 'layer': layer, 'native_status': actual.get('native_status', 'NO_RESULT'),
               'test_verdict': 'PASS' if not failures else 'FAIL', 'failures': failures,
               'expected': expected[case_id], 'actual': actual, 'measured_case': size}
        save(output / (case_id + '_CHECK.json'), row)
        results.append(row)
    summary = {'schema': 'c1-synthetic-demo-result/1', 'status': 'PASS' if all(r['test_verdict'] == 'PASS' for r in results) else 'FAIL',
        'cases': [{k: r[k] for k in ('case_id', 'layer', 'native_status', 'test_verdict', 'failures')} for r in results],
        'runtime_pins': pins, 'scope': 'Synthetic examples only; Unknown/Invalid can be the expected PASS result',
        'guard_scope': 'Fresh child process after hook installation; not an OS sandbox or device-wide monitor'}
    save(output / 'RESULT.json', summary)
    save(output / 'ENVIRONMENT.json', {'python': platform.python_version(), 'implementation': platform.python_implementation(),
        'platform': platform.system(), 'sqlite': sqlite3.sqlite_version, 'elapsed_seconds': time.monotonic()-started})
    lines = ['# Synthetic C1 review demo', '', '| Case | Layer | Native result | Test |', '|---|---|---|---|']
    lines += ['| {case_id} | {layer} | {native_status} | {test_verdict} |'.format(**r) for r in results]
    lines += ['', 'Known is conditional on the fixture model/evidence. D2 does not discover omitted logs.',
              'This run is not independent validation of a real terminal state or a complete security audit.', '']
    (output / 'SUMMARY.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    print(json.dumps({'status': summary['status'], 'cases': summary['cases']}, sort_keys=True))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.output))
    except Exception as error:
        print(json.dumps({'status': 'RUN_FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(2)
