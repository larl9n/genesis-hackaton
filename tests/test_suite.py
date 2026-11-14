import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from genesis_fintech.domain.models import DataError
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.evaluation.suite import evaluate_dataset
from genesis_fintech.generation.datasets import generate_dataset
from genesis_fintech.generation.storage import load_scenario, read_json

ROOT = Path(__file__).resolve().parents[1]


class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.corpus=Path(cls.temp.name)/'corpus'
        generate_dataset(read_json(ROOT/'configs/dataset.json'),cls.corpus)
        cls.output=Path(cls.temp.name)/'evaluation'
        cls.result=evaluate_dataset(cls.corpus,cls.output,backend='development',replay=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_all_20_episodes_and_80_replays_have_exact_shared_records(self):
        result=self.result
        self.assertTrue(result['ok'])
        self.assertEqual((result['episodes'],result['policy_runs'],result['paired_checks'],result['replay_checks']),(20,80,20,80))
        report=read_json(self.output/'report.json')
        checks=read_json(self.output/'conformance.json')
        self.assertTrue(all(item['passed'] for item in checks['paired_id_order_checks']))
        fingerprints={}
        for run in report['runs']:
            fingerprints.setdefault(run['episode_id'],set()).add(run['public_sha256'])
            self.assertLessEqual(run['steps'],100)
            self.assertFalse(run['truncated'])
            path=self.output/'runs'/run['split']/run['episode_id']/run['policy']
            replay=path.parent/(run['policy']+'-replay')
            self.assertEqual((path/'trajectories.jsonl').read_bytes(),(replay/'trajectories.jsonl').read_bytes())
            self.assertEqual(run['security_mode'],'evaluator_only' if run['policy']=='evaluator_oracle' else 'development_subprocess')
        self.assertEqual(len(fingerprints),20)
        self.assertTrue(all(len(values)==1 for values in fingerprints.values()))
        for policy in ['reconciliation','evaluator_oracle']:
            row=report['summary'][policy]
            self.assertEqual((row['tp'],row['fp'],row['fn'],row['clean_correct']),(72,0,0,4))
        self.assertLess(report['summary']['flag-all']['micro_f1'],0.1)
        self.assertTrue((self.output/'report.md').is_file())

    def test_scoring_and_execution_use_saved_records_without_regeneration(self):
        item=read_json(self.corpus/'dataset.json')['episodes'][3]
        public,truth=load_scenario(self.corpus/'episodes'/item['split']/item['episode_id'])
        with patch('genesis_fintech.environment.core.generate_scenario',side_effect=AssertionError('regenerated')):
            env=AuditEnv(mode='evaluation');observation,_=env.reset_episode(public,truth)
            self.assertEqual(observation['manifest'],public.manifest.to_dict())
            self.assertNotIn('seed',json.dumps(observation))

    def test_default_requires_docker_and_never_silently_falls_back(self):
        with patch('genesis_fintech.evaluation.external.shutil.which',return_value=None):
            output=Path(self.temp.name)/'no-docker'
            with self.assertRaises(DataError):evaluate_dataset(self.corpus,output)
            self.assertFalse(output.exists())
        with self.assertRaises(FileExistsError):evaluate_dataset(self.corpus,self.output,backend='development')

    def test_persisted_result_is_independently_rechecked_before_acceptance(self):
        from genesis_fintech.evaluation import suite
        original=suite.run_external_episode
        def tampered(*args,**kwargs):
            result=original(*args,**kwargs)
            result['metrics']['reward']=123
            return result
        with patch.object(suite,'run_external_episode',side_effect=tampered):
            with self.assertRaisesRegex(DataError,'persisted submission'):
                evaluate_dataset(self.corpus,Path(self.temp.name)/'tampered',backend='development')

    def test_cli_full_corpus_development_evaluation(self):
        result=subprocess.run([sys.executable,'-m','genesis_fintech','evaluate-dataset',str(self.corpus),
                               '--output',str(Path(self.temp.name)/'cli'),'--backend','development'],
                              capture_output=True,text=True,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['policy_runs'],80)


if __name__=='__main__':unittest.main()
