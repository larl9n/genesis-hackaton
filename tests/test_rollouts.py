import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from genesis_fintech.domain.models import DataError
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.evaluation.rollouts import collect_trajectories, validate_trajectories
from genesis_fintech.generation.datasets import generate_dataset, sha256
from genesis_fintech.generation.storage import json_text, load_scenario, read_json

ROOT = Path(__file__).resolve().parents[1]


class RolloutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.corpus=cls.root/'corpus'
        generate_dataset(read_json(ROOT/'configs/dataset.json'),cls.corpus)
        cls.output=cls.root/'training'
        cls.result=collect_trajectories(cls.corpus,cls.output)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_export_has_10_train_episodes_real_terminal_rewards_and_no_truth(self):
        self.assertEqual((self.result['episodes'],self.result['transitions']),(10,120))
        self.assertAlmostEqual(self.result['mean_episode_return'],0.978)
        self.assertFalse(self.result['model_weight_training'])
        trace=[json.loads(line) for line in (self.output/'trajectories.jsonl').read_text().splitlines()]
        index=read_json(self.corpus/'dataset.json')
        train={x['episode_id'] for x in index['episodes'] if x['split']=='train'}
        dev={x['episode_id'] for x in index['episodes'] if x['split']=='dev'}
        self.assertEqual({x['episode_id'] for x in trace},train)
        self.assertFalse({x['episode_id'] for x in trace}&dev)
        for row in trace:
            self.assertFalse(row['truncated'])
            self.assertEqual(row['reward'],0.978 if row['terminated'] else 0)
            for private in ['"truth"','"provenance"','"seed"','expected_amount_minor','acceptable_evidence_sets','latent_history']:
                self.assertNotIn(private,json.dumps(row))
        item=next(x for x in index['episodes'] if x['split']=='train')
        public,truth=load_scenario(self.corpus/'episodes/train'/item['episode_id'])
        env=AuditEnv(mode='evaluation');env.reset_episode(public,truth)
        for row in [x for x in trace if x['episode_id']==item['episode_id']]:
            _,reward,_,_,_=env.step(row['action']);self.assertEqual(reward,0)

    def test_exact_reproduction_all_baselines_and_packaged_example(self):
        again=self.root/'repeat'
        collect_trajectories(self.corpus,again)
        for name in ['manifest.json','initial_observations.jsonl','trajectories.jsonl']:
            data=(self.output/name).read_bytes()
            self.assertEqual(data,(again/name).read_bytes())
            self.assertEqual(data,(ROOT/'examples/training-v1'/name).read_bytes())
        for policy in ['random','flag-all']:
            result=collect_trajectories(self.corpus,self.root/policy,policy=policy,policy_seed=91)
            self.assertEqual(result['episodes'],10)
            self.assertLess(result['mean_episode_return'],0)

    def test_replay_does_not_regenerate_or_read_oracle_answers(self):
        with patch('genesis_fintech.generation.datasets.generate_scenario',side_effect=AssertionError('regenerated')):
            self.assertTrue(validate_trajectories(self.corpus,self.output)['replay_verified'])

    def test_forged_reward_action_or_observation_rejected_even_with_updated_hash(self):
        for mode in ['reward','action','observation','initial']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'copy';shutil.copytree(self.output,out)
                name='initial_observations.jsonl' if mode=='initial' else 'trajectories.jsonl'
                path=out/name;rows=[json.loads(line) for line in path.read_text().splitlines()]
                if mode=='reward':rows[-1]['reward']=0.123
                elif mode=='action':rows[0]['action']={'action':'calculator','params':{'expression':'1+1'}}
                elif mode=='observation':rows[0]['observation']['remaining_steps']=98
                else:rows[0]['observation']['truth']={'private':'forged'}
                path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
                manifest=read_json(out/'manifest.json');manifest['files'][name]=sha256(path.read_bytes())
                (out/'manifest.json').write_text(json_text(manifest))
                with self.assertRaises(DataError):validate_trajectories(self.corpus,out)

    def test_rejects_oracle_invalid_seed_overwrite_dev_and_bad_utf8(self):
        for kwargs in [{'policy':'evaluator_oracle'},{'policy_seed':True},{'policy_seed':-1}]:
            out=self.root/'invalid'
            with self.assertRaises(DataError):collect_trajectories(self.corpus,out,**kwargs)
            self.assertFalse(out.exists())
        with self.assertRaises(FileExistsError):collect_trajectories(self.corpus,self.output)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'copy';shutil.copytree(self.output,out)
            manifest=read_json(out/'manifest.json');manifest['split']='dev'
            (out/'manifest.json').write_text(json_text(manifest))
            with self.assertRaises(DataError):validate_trajectories(self.corpus,out)
            (out/'manifest.json').write_bytes(b'\xff')
            with self.assertRaises(DataError):validate_trajectories(self.corpus,out)

    def test_installed_cli_collect_and_validate(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        output=self.root/'cli'
        command=[sys.executable,'-m','genesis_fintech','collect-trajectories',str(self.corpus),'--output',str(output)]
        result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([sys.executable,'-m','genesis_fintech','validate-trajectories',str(self.corpus),str(output)],
                              capture_output=True,text=True,env=env,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['replay_verified'])
        self.assertEqual(subprocess.run(command,capture_output=True,env=env,timeout=15).returncode,2)


if __name__=='__main__':unittest.main()
