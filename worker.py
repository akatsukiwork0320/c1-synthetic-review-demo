# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""One synthetic case per fresh process. Existing guard is never mocked."""
import argparse
import json
from pathlib import Path
import sys


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.write('\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case-root', required=True, type=Path)
    p.add_argument('--case', required=True, choices=('D1', 'D2', 'D3', 'D4'))
    args = p.parse_args()
    root = args.case_root.resolve()
    unit = root / 'unit'
    sys.path.insert(0, str(unit / 'engine'))
    if args.case in ('D1', 'D4'):
        import replay
        replay.UNIT, replay.ROOT = unit, root
        code = replay.run(root / 'out')
        result = json.loads((root / 'out' / 'RESULT.json').read_bytes())
        actual = {'native_status': result['status'], 'reason': result['reason'], 'layer': 'REPLAY_WRAPPER',
                  'exit_code': code, 'process_observation': result['process_observation']}
        for key in ('source_class', 'model', 'source_identity', 'verification_scope', 'event_counts', 'counts'):
            if key in result:
                actual[key] = result[key]
        if result['status'] == 'Known':
            actual['core'] = json.loads((root / 'out' / 'FINAL_STATE.json').read_bytes())['core']
            actual['ticks'] = [json.loads(r) for r in (root / 'out' / 'FINAL_TICKS.jsonl').read_bytes().splitlines()]
            actual['invariant_observations'] = json.loads((root / 'out' / 'FINAL_INVARIANTS.json').read_bytes())['observations']
        write(root / 'out' / 'OBSERVATION.json', actual)
        return code
    else:
        from event_decoder import decode_transaction
        from process_guard import ProcessGuard
        output = root / 'out'
        output.mkdir()
        input_path = root / 'DECODER_INPUT.json'
        guard = ProcessGuard(unit, output, [input_path])
        sys.addaudithook(guard.hook)
        data = json.loads(input_path.read_bytes())
        result = decode_transaction(data['logs'], **data['arguments'])
        actual = {'native_status': result.pop('status'), **result, 'exit_code': 0, 'layer': 'TRANSACTION_DECODER',
                  'process_observation': guard.report()}
        write(output / 'OBSERVATION.json', actual)
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        # Do not put private absolute paths from traceback messages into artifacts.
        print(json.dumps({'worker_error_type': type(e).__name__, 'status': 'WORKER_FAILED'}))
        raise SystemExit(2)
