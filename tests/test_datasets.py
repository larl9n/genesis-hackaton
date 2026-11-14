import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from genesis_fintech.domain.models import DataError
from genesis_fintech.generation.datasets import EPISODE_FILES, generate_dataset, sha256, validate_dataset, validate_spec
from genesis_fintech.generation.storage import json_text, read_json

ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)/'reference'
        cls.spec = read_json(ROOT/'configs/dataset.json')
        cls.report = generate_dataset(cls.spec, cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_frozen_20_episodes_cover_cases_and_have_public_only_archive(self):
        self.assertEqual(self.report['row_range'],[262,299])
        self.assertEqual(self.report['document_range'],[135,150])
        for split in ['train','dev']:
            self.assertEqual(self.report['splits'][split]['episodes'],10)
            self.assertEqual(self.report['splits'][split]['clean'],2)
            self.assertEqual(self.report['splits'][split]['issues'],36)
            self.assertTrue(all(self.report['splits'][split]['families'].values()))
        train={item['seed'] for item in self.spec['splits']['train']}
        self.assertFalse(train & {item['seed'] for item in self.spec['splits']['dev']})
        train_configs={json_text(item['config']) for item in self.spec['splits']['train']}
        self.assertFalse(train_configs & {json_text(item['config']) for item in self.spec['splits']['dev']})
        with tarfile.open(self.root/'public-train-dev.tar.gz','r:gz') as archive:
            self.assertEqual(len(archive.getmembers()),121)
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertNotIn('private',member.name)
                self.assertNotIn('..',Path(member.name).parts)
                self.assertEqual(member.mtime,0)
                data=archive.extractfile(member).read()
                for private in [b'acceptable_evidence_sets',b'expected_amount_minor',b'latent_history',b'"seed"',b'provenance']:
                    self.assertNotIn(private,data)

    def test_repeated_generation_matches_every_byte_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            other=Path(tmp)/'second'
            generate_dataset(self.spec,other)
            for path in self.root.rglob('*'):
                if path.is_file():self.assertEqual(path.read_bytes(),(other/path.relative_to(self.root)).read_bytes())
            with self.assertRaises(FileExistsError):generate_dataset(self.spec,other)

    def test_independent_validation_does_not_call_generator(self):
        with patch('genesis_fintech.generation.datasets.generate_scenario',side_effect=AssertionError('generator used')):
            self.assertTrue(validate_dataset(self.root)['ok'])

    def test_strict_spec_duplicate_seeds_missing_coverage_and_private_paths(self):
        candidates=[]
        for value in [None,[],{}]:candidates.append(value)
        for mutate in [lambda s:s['splits']['train'].pop(),
                       lambda s:s['splits']['dev'][0].update(seed=s['splits']['train'][0]['seed']),
                       lambda s:s['splits']['train'][0].update(seed=True),
                       lambda s:s.update(generator_version='unknown'),
                       lambda s:s.update(dataset_id='../private'),
                       lambda s:s.update(extra='not allowed')]:
            spec=copy.deepcopy(self.spec);mutate(spec);candidates.append(spec)
        for spec in candidates:
            with self.subTest(spec=type(spec).__name__),self.assertRaises(DataError):validate_spec(spec)

    def test_tamper_and_forged_checksum_still_fail_independent_truth_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'copy';shutil.copytree(self.root,root)
            index=read_json(root/'dataset.json')
            entry=index['episodes'][3]
            episode=root/'episodes'/entry['split']/entry['episode_id']
            truth_path=episode/'private/truth.json'
            truth=read_json(truth_path);truth['issues'][0]['expected_amount_minor']+=1
            truth_path.write_text(json_text(truth))
            entry['files']['private/truth.json']=sha256(truth_path.read_bytes())
            (root/'dataset.json').write_text(json_text(index))
            with self.assertRaises(DataError):validate_dataset(root)

    def test_unknown_ids_symlinks_and_public_archive_tampering_are_rejected(self):
        for mode in ['id','symlink','archive']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'copy';shutil.copytree(self.root,root)
                index=read_json(root/'dataset.json');item=index['episodes'][0]
                if mode=='id':
                    item['episode_id']='../../outside';(root/'dataset.json').write_text(json_text(index))
                elif mode=='symlink':
                    path=root/'episodes'/item['split']/item['episode_id']/'public/ledger.csv'
                    original=path.read_bytes();outside=Path(tmp)/'outside';outside.write_bytes(original)
                    path.unlink();path.symlink_to(outside)
                else:(root/'public-train-dev.tar.gz').write_bytes(b'corrupt')
                with self.assertRaises(DataError):validate_dataset(root)

    def test_cli_generate_validate_replay_and_invalid_spec(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'corpus'
            command=[sys.executable,'-m','genesis_fintech','generate-dataset','--spec',str(ROOT/'configs/dataset.json'),'--output',str(output)]
            result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([sys.executable,'-m','genesis_fintech','validate-dataset',str(output),'--replay'],capture_output=True,text=True,env=env,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(json.loads(result.stdout)['replayed'])
            self.assertEqual(subprocess.run(command,capture_output=True,env=env).returncode,2)


if __name__=='__main__':unittest.main()
