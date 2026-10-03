# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Harness tests, distinct from the four demonstration cases and historical tests."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

UNIT=Path(__file__).resolve().parent
sys.path.insert(0,str(UNIT))
import comparison
import fixture_builder as fixture
import package_demo
import run_demo


class ComparisonTests(unittest.TestCase):
    def test_exact_negative_passes(self):
        expected={'native_status':'Invalid','issues':[{'code':'ABI_DATA_LENGTH'}],'events':[]}
        self.assertEqual(comparison.compare(expected,copy.deepcopy(expected)),[])

    def test_other_invalid_reason_rejected(self):
        self.assertTrue(comparison.compare({'issues':[{'code':'ABI_DATA_LENGTH'}]}, {'issues':[{'code':'OTHER'}]}))

    def test_boolean_not_integer(self):
        self.assertTrue(comparison.compare({'tick':0},{'tick':False}))

    def test_partial_events_rejected(self):
        self.assertTrue(comparison.compare({'events':[]},{'events':[{}]}))

    def test_missing_field_rejected(self):
        self.assertTrue(comparison.compare({'native_status':'Known'},{}))

    def test_liquidity_difference_rejected(self):
        self.assertTrue(comparison.compare({'core':{'liquidity':'12'}},{'core':{'liquidity':'13'}}))

    def observation(self):
        return {'source_class':'SYNTHETIC_FIXTURE','model':'ASSUMED_MODEL','source_identity':'UNKNOWN',
                'verification_scope':'MATHEMATICAL_INTEGRITY','invariant_observations':{k:0 for k in comparison.OBSERVATION_IDS}}

    def test_fixed_invariant_ids_pass(self):
        self.assertEqual(comparison.wrapper_checks(self.observation()),[])

    def test_substituted_invariant_id_rejected(self):
        actual=self.observation();obs=actual['invariant_observations'];obs.pop(next(iter(obs)));obs['UNRELATED']=0
        self.assertTrue(comparison.wrapper_checks(actual))

    def test_missing_extra_and_nonzero_invariant_rejected(self):
        for mutation in ('missing','extra','nonzero','boolean'):
            with self.subTest(mutation=mutation):
                actual=self.observation();obs=actual['invariant_observations'];key=next(iter(obs))
                if mutation=='missing':obs.pop(key)
                elif mutation=='extra':obs['EXTRA']=0
                elif mutation=='boolean':obs[key]=False
                else:obs[key]=1
                self.assertTrue(comparison.wrapper_checks(actual))


class FixtureTests(unittest.TestCase):
    def test_public_capacity_formula_and_floor_bound(self):
        bound,count,cap=fixture.synthetic_tick_capacity()
        self.assertEqual(fixture.TICK_SPACING,60)
        self.assertEqual(bound,887220)
        self.assertEqual(count,29575)
        maximum=(1<<128)-1
        self.assertLessEqual(cap*count,maximum)
        self.assertGreater((cap+1)*count,maximum)

    def test_consistent_spacing_anchor_and_expected_endpoints(self):
        expected=json.loads((UNIT/'EXPECTED.json').read_bytes())['cases']
        with tempfile.TemporaryDirectory(prefix='c1-spacing-') as tmp:
            for cid in fixture.CASE_IDS:
                root=Path(tmp)/cid;fixture.build_case(root,cid,UNIT)
                if cid in ('D2','D3'):
                    args=json.loads((root/'DECODER_INPUT.json').read_bytes())['arguments']
                    self.assertEqual(args['tick_spacing'],fixture.TICK_SPACING)
                else:
                    vals=json.loads((root/'anchor/ANCHOR_STATE.json').read_bytes())['values']
                    self.assertEqual(vals['tickSpacing']['tickSpacing'],str(fixture.TICK_SPACING))
                    self.assertEqual(int(vals['maxLiquidityPerTick']['maxLiquidityPerTick']),fixture.synthetic_tick_capacity()[2])
                    rows=[json.loads(line) for line in (root/'anchor/TICKS.jsonl').read_text().splitlines()]
                    self.assertEqual([int(r['tick']) for r in rows],[-fixture.TICK_SPACING,fixture.TICK_SPACING])
                    self.assertEqual([r['tick'] for r in expected[cid]['ticks']],[-fixture.TICK_SPACING,fixture.TICK_SPACING])

    def test_all_case_shapes_and_actual_code_pins(self):
        with tempfile.TemporaryDirectory(prefix='c1-fixtures-') as tmp:
            for case_id in fixture.CASE_IDS:
                root=Path(tmp)/case_id
                metadata=fixture.build_case(root,case_id,UNIT)
                self.assertEqual(len(metadata['code_pins']),8)
                self.assertEqual(metadata['source_class'],'SYNTHETIC_FIXTURE')
                for row in metadata['code_pins']:
                    self.assertEqual(row['sha256'],fixture.digest((root/row['path']).read_bytes()))
                    self.assertEqual((root/row['path']).read_bytes(),(UNIT/'engine'/Path(row['path']).name).read_bytes())
                self.assertNotIn('fixture_code.py',json.dumps(metadata))

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory(prefix='c1-existing-') as tmp:
            with self.assertRaises(FileExistsError):fixture.build_case(Path(tmp),'D1',UNIT)

    def test_unknown_case_refused(self):
        with tempfile.TemporaryDirectory(prefix='c1-id-') as tmp:
            with self.assertRaises(ValueError):fixture.build_case(Path(tmp)/'new','REAL',UNIT)

    def test_malformed_second_log_in_same_transaction(self):
        with tempfile.TemporaryDirectory(prefix='c1-malformed-') as tmp:
            root=Path(tmp)/'D3';fixture.build_case(root,'D3',UNIT)
            data=json.loads((root/'DECODER_INPUT.json').read_bytes())
            self.assertIs(data['arguments']['complete'],True)
            self.assertEqual(data['logs'][0]['transactionHash'],data['logs'][1]['transactionHash'])
            self.assertNotEqual(data['logs'][0]['data'],'0x');self.assertEqual(data['logs'][1]['data'],'0x')


class IntegrationTests(unittest.TestCase):
    def test_stale_clean_test_driver_rejected(self):
        names=tuple(n for n in package_demo.FILES if n not in ('CHECKS.json','CLEAN_RUN.json'))
        record={'mode':'ALLOWLIST_COPY','copied_payload_pins':{n:package_demo.sha((UNIT/n).read_bytes()) for n in names}}
        package_demo.verify_clean_payload(record)
        for name in ('test_demo.py','run_checks.py'):
            changed=copy.deepcopy(record);changed['copied_payload_pins'][name]='0'*64
            with self.subTest(driver=name):
                with self.assertRaisesRegex(ValueError,'STALE_CLEAN_PAYLOAD'):package_demo.verify_clean_payload(changed)

    def test_license_scope_includes_every_packaged_file(self):
        package_demo.verify_licenses()

    def test_missing_license_map_entry_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c1-licence-') as tmp:
            root=Path(tmp)
            for name in ('LICENSE_STATUS.json','LICENSE_MAP.json'):
                shutil.copyfile(UNIT/name,root/name)
            data=json.loads((root/'LICENSE_MAP.json').read_bytes());data['files'].pop()
            (root/'LICENSE_MAP.json').write_text(json.dumps(data),encoding='utf-8')
            with patch.object(package_demo,'UNIT',root):
                with self.assertRaisesRegex(ValueError,'LICENSE_MAP_COVERAGE'):package_demo.verify_licenses()

    def test_four_cases_in_fresh_processes(self):
        with tempfile.TemporaryDirectory(prefix='c1-integration-') as tmp:
            output=Path(tmp)/'run'
            done=subprocess.run([sys.executable,'-I','-B',str(UNIT/'run_demo.py'),'--output',str(output)],cwd=tmp,capture_output=True,text=True,timeout=100)
            self.assertEqual(done.returncode,0,done.stdout[-1000:])
            result=json.loads((output/'RESULT.json').read_bytes())
            self.assertEqual(result['status'],'PASS')
            self.assertEqual([r['native_status'] for r in result['cases']],['Known','Unknown','Invalid','Known'])

    def test_tampered_runtime_refused_before_output(self):
        with tempfile.TemporaryDirectory(prefix='c1-pin-') as tmp:
            root=Path(tmp)/'copy';root.mkdir()
            for name in (*run_demo.RUNTIME,'RUNTIME_MANIFEST.json'):
                destination=root/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(UNIT/name,destination)
            with (root/'engine/event_decoder.py').open('ab') as f:f.write(b'\n# mutation\n')
            output=Path(tmp)/'run'
            done=subprocess.run([sys.executable,'-I','-B',str(root/'run_demo.py'),'--output',str(output)],cwd=tmp,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(done.returncode,0);self.assertFalse(output.exists())

    def test_demo_refuses_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='c1-refuse-') as tmp:
            with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):run_demo.main(Path(tmp))

    def test_stale_test_record_rejected(self):
        with tempfile.TemporaryDirectory(prefix='c1-stale-') as tmp:
            root=Path(tmp)
            for name in (*run_demo.RUNTIME,'RUNTIME_MANIFEST.json','SOURCE_PROVENANCE.json'):
                dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(UNIT/name,dest)
            (root/'CHECKS.json').write_text(json.dumps({'status':'PASS','runtime_manifest_sha256':'0'*64}),encoding='utf-8')
            with patch.object(package_demo,'UNIT',root):
                with self.assertRaisesRegex(ValueError,'STALE_TEST_RECORD'):package_demo.verify_evidence()


if __name__=='__main__':unittest.main()
