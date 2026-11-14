import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from genesis_fintech.domain.models import DataError
from genesis_fintech.environment.core import AuditEnv, EpisodeFinished
from genesis_fintech.evaluation.external import (
    WorkerChannel, docker_command, docker_image_id, drive_worker, run_external,
)
from genesis_fintech.generation.scenario import ScenarioConfig
from genesis_fintech.generation.storage import read_json
from genesis_fintech.policies.wire import MAX_FRAME_BYTES, ProtocolError, decode_frame, encode_frame

ROOT = Path(__file__).resolve().parents[1]


class WireTests(unittest.TestCase):
    def test_strict_frames_round_trip_and_reject_ambiguous_input(self):
        self.assertEqual(decode_frame(encode_frame(0, 'action', {'value': 'Привет'}), 0, 'action'), {'value': 'Привет'})
        bad = [b'{}\n', b'not json\n', b'\xff\n', b'{}', b'{}\n{}\n',
               b'{"protocol_version":1,"request_id":0,"action":NaN}\n',
               b'{"protocol_version":1,"request_id":0,"request_id":0,"action":{}}\n',
               b'{"protocol_version":true,"request_id":0,"action":{}}\n',
               b'{"protocol_version":1,"request_id":false,"action":{}}\n',
               b'{"protocol_version":1,"request_id":1,"action":{}}\n',
               b'{"protocol_version":1,"request_id":0,"action":{},"truth":{}}\n',
               b'[' * 2000 + b'0' + b']' * 2000 + b'\n', b'x' * (MAX_FRAME_BYTES + 1)]
        for frame in bad:
            with self.subTest(frame=frame[:80]), self.assertRaises(ProtocolError):
                decode_frame(frame, 0, 'action')
        with self.assertRaises(ProtocolError):
            encode_frame(0, 'action', {'value': float('nan')})


class ExternalTests(unittest.TestCase):
    def drive(self, script, *, timeout=1):
        env = AuditEnv(mode='evaluation')
        initial, _ = env.reset(42)
        with tempfile.TemporaryDirectory() as cwd:
            result = drive_worker(env, initial, [sys.executable, '-I', '-S', '-u', '-c', script],
                                  cwd=cwd, child_env={'PATH': os.defpath}, deadline=time.monotonic() + timeout)
        return result, env

    def test_subprocess_reconciliation_matches_in_process_on_compositions(self):
        from genesis_fintech.evaluation.benchmark import run_policy
        config = ScenarioConfig.from_dict(read_json(ROOT/'configs/interactions.json'))
        expected, _, trace = run_policy('reconciliation', 42, config)
        with tempfile.TemporaryDirectory() as cwd:
            result = run_external(42, config, Path(cwd)/'run', backend='development')
            actual_trace = [json.loads(line) for line in (Path(cwd)/'run/trajectories.jsonl').read_text().splitlines()]
            self.assertEqual(result['metrics'], expected['metrics'])
            self.assertEqual(actual_trace, trace)
            self.assertEqual(result['metrics']['tp'], 4)
            self.assertEqual(result['security_mode'], 'development_subprocess')
            self.assertIsNone(result['failure'])
            self.assertTrue(result['ok'])
            self.assertIsNone(result['worker_image_id'])
            with self.assertRaises(FileExistsError):
                run_external(42, config, Path(cwd)/'run', backend='development')

    def test_all_public_policies_and_seed_reproduce_across_processes(self):
        from genesis_fintech.evaluation.benchmark import run_policy
        config = ScenarioConfig()
        for name in ['random', 'flag-all', 'reconciliation']:
            with self.subTest(policy=name), tempfile.TemporaryDirectory() as cwd:
                expected, _, trace = run_policy(name, 48, config, policy_seed=17)
                result = run_external(48, config, Path(cwd)/'run', backend='development', policy=name, policy_seed=17)
                actual = [json.loads(line) for line in (Path(cwd)/'run/trajectories.jsonl').read_text().splitlines()]
                self.assertEqual(result['metrics'], expected['metrics'])
                self.assertEqual(actual, trace)
                self.assertTrue(all(item['reward'] == 0 for item in actual))

    def test_worker_receives_no_truth_seed_host_environment_or_result(self):
        worker = ROOT/'src/genesis_fintech/policies/worker.py'
        source = worker.read_text()
        self.assertNotIn('genesis_fintech.evaluation', source)
        self.assertNotIn('genesis_fintech.generation', source)
        script = '''import json,sys,os
frame=json.loads(sys.stdin.readline())
text=json.dumps(frame)
assert not any(key in text for key in ['acceptable_evidence_sets','provenance','policy_seed','expected_amount_minor'])
assert 'GENESIS_TEST_SECRET' not in os.environ
assert set(frame)=={'protocol_version','request_id','observation'}
assert not any(key in frame['observation'] for key in ['reward','metrics','truth','seed'])
print(json.dumps({'protocol_version':1,'request_id':0,'action':{'action':'submit','params':{'episode_id':frame['observation']['manifest']['episode_id'],'findings':[]}}}))
'''
        with patch.dict(os.environ, {'GENESIS_TEST_SECRET': 'host-only'}):
            result, _ = self.drive(script)
        self.assertTrue(result['terminated'])
        self.assertIsNone(result['failure'])

    def test_bad_frames_exit_flood_and_stall_are_bounded_failures(self):
        scripts = [('print("bad")', 'worker_protocol_error'),
                   ('import sys;sys.stdout.buffer.write(b"\\xff\\n");sys.stdout.flush()', 'worker_protocol_error'),
                   ('print("x"*600000)', 'worker_protocol_error'),
                   ('print("["*2000+"0"+"]"*2000)', 'worker_protocol_error'),
                   ('raise SystemExit(0)', 'worker_exit'),
                   ('import time;time.sleep(30)', 'worker_timeout')]
        for script, reason in scripts:
            with self.subTest(reason=reason):
                started = time.monotonic()
                result, env = self.drive(script, timeout=0.4)
                self.assertEqual(result['failure'], reason)
                self.assertTrue(result['truncated'])
                self.assertFalse(result['terminated'])
                self.assertEqual(result['metrics']['tp'], 0)
                self.assertLess(time.monotonic() - started, 3)
                self.assertLess(len(json.dumps(env.trajectory)), 1000)
                self.assertEqual(env.trajectory[-1]['reward'], 0)
                with self.assertRaises(EpisodeFinished):
                    env.abort_worker('worker_exit')

    def test_nonreader_cannot_block_host_writing_large_frame(self):
        env = AuditEnv(mode='evaluation')
        initial, _ = env.reset(42)
        initial['task'] = 'x' * (MAX_FRAME_BYTES - 10000)
        with tempfile.TemporaryDirectory() as cwd:
            result = drive_worker(env, initial, [sys.executable, '-c', 'import time;time.sleep(30)'],
                                  cwd=cwd, child_env={'PATH': os.defpath}, deadline=time.monotonic()+0.3)
        self.assertEqual(result['failure'], 'worker_timeout')

    def test_wrong_sequence_id_after_valid_action_aborts_without_extra_credit(self):
        script = '''import json,sys
frame=json.loads(sys.stdin.readline())
action={'action':'calculator','params':{'expression':'1+1'}}
for request_id in [0,0]:
 print(json.dumps({'protocol_version':1,'request_id':request_id,'action':action}),flush=True)
 frame=json.loads(sys.stdin.readline())
'''
        result, env = self.drive(script)
        self.assertEqual(result['failure'], 'worker_protocol_error')
        self.assertEqual(result['metrics']['inspection_steps'], 1)
        self.assertEqual(result['steps'], 1)

    def test_last_step_reserved_and_no_oracle_in_external_worker(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = run_external(42, ScenarioConfig(), Path(cwd)/'run', backend='development', max_steps=2)
            self.assertTrue(result['terminated'])
            self.assertEqual(result['steps'], 2)
            self.assertEqual(result['metrics']['tp'], 0)
            with self.assertRaises(DataError):
                run_external(42, ScenarioConfig(), Path(cwd)/'bad', backend='development', policy='evaluator_oracle')

    def test_process_cleanup_and_stderr_flood_do_not_block(self):
        script = 'import sys,time;sys.stderr.write("x"*2000000);sys.stderr.flush();time.sleep(30)'
        result, _ = self.drive(script, timeout=0.3)
        self.assertEqual(result['failure'], 'worker_timeout')
        with tempfile.TemporaryDirectory() as cwd:
            channel = WorkerChannel([sys.executable, '-c', 'import time;time.sleep(30)'], cwd=cwd, env={'PATH':os.defpath})
            channel.close()
            self.assertIsNotNone(channel.process.returncode)

    def test_docker_missing_is_error_without_development_fallback(self):
        with patch('genesis_fintech.evaluation.external.shutil.which', return_value=None):
            with self.assertRaisesRegex(DataError, 'no fallback'):
                docker_image_id('missing')
            with tempfile.TemporaryDirectory() as cwd:
                target = Path(cwd)/'not-created'
                with self.assertRaises(DataError):
                    run_external(42, ScenarioConfig(), target)
                self.assertFalse(target.exists())

    def test_docker_flags_drop_privileges_and_avoid_host_mounts(self):
        args = docker_command('sha256:'+'a'*64, 'test-worker', ['-c', 'pass'])
        for flag in ['--network=none','--ipc=none','--read-only','--user=65534:65534','--cap-drop=ALL',
                     '--security-opt=no-new-privileges:true','--pids-limit=64','--memory=512m',
                     '--cpus=1','--pull=never','--entrypoint=python','--log-driver=none']:
            self.assertIn(flag, args)
        self.assertFalse(any(arg in args for arg in ['--privileged','--volume','-v','--mount','--env-file','--pid=host']))

    def test_cli_development_runs_and_default_docker_fails_closed(self):
        with tempfile.TemporaryDirectory() as cwd:
            env = dict(os.environ, PYTHONPATH=str(ROOT/'src'))
            command = [sys.executable, '-m', 'genesis_fintech', 'run-policy', '--seed', '42',
                       '--output', str(Path(cwd)/'run'), '--backend', 'development']
            result = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])
            self.assertEqual(json.loads(result.stdout)['metrics']['tp'], 2)


if __name__ == '__main__':
    unittest.main()
