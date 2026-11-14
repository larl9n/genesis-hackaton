"""Real Docker integration checks; CI enables them explicitly, local absence skips.

If GENESIS_RUN_DOCKER_TESTS=1, an unavailable image/daemon is a failure, not a skip.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

from genesis_fintech.evaluation.external import DEFAULT_IMAGE, docker_command, docker_image_id, run_external
from genesis_fintech.generation.scenario import ScenarioConfig
from genesis_fintech.generation.storage import read_json

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('GENESIS_RUN_DOCKER_TESTS') == '1', 'requires explicit Docker integration run')
class ContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image_id = docker_image_id(DEFAULT_IMAGE)

    def probe(self, script):
        name = 'genesis-probe-' + uuid.uuid4().hex
        try:
            result = subprocess.run(docker_command(self.image_id, name, ['-I','-S','-c',script]),
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        finally:
            subprocess.run(['docker','rm','-f',name], capture_output=True, timeout=10)

    def test_worker_has_no_host_files_evaluator_network_or_privileges(self):
        with tempfile.TemporaryDirectory() as cwd:
            secret = Path(cwd)/'host-only-secret'
            secret.write_text('PRIVATE_SENTINEL')
            script = f'''import os,json,socket,importlib.util,sys
sys.path.insert(0,'/app/src')
result={{'uid':os.getuid(),'host_file':os.path.exists({str(secret)!r}),
 'docker_socket':os.path.exists('/var/run/docker.sock'),
 'evaluator':importlib.util.find_spec('genesis_fintech.evaluation') is not None,
 'generator':importlib.util.find_spec('genesis_fintech.generation') is not None,
 'interfaces':os.listdir('/sys/class/net')}}
try:
 open('/app/forbidden','w').write('x');result['root_readonly']=False
except OSError: result['root_readonly']=True
s=socket.socket();s.settimeout(1)
try: s.connect(('1.1.1.1',443));result['network_blocked']=False
except OSError: result['network_blocked']=True
finally:s.close()
result['no_new_privs']='NoNewPrivs:\\t1' in open('/proc/self/status').read()
result['caps_zero']='CapEff:\\t0000000000000000' in open('/proc/self/status').read()
print(json.dumps(result))'''
            result = self.probe(script)
            self.assertEqual(result['uid'],65534)
            for key in ['host_file','docker_socket','evaluator','generator']:
                self.assertFalse(result[key], (key,result))
            for key in ['root_readonly','network_blocked','no_new_privs','caps_zero']:
                self.assertTrue(result[key], (key,result))
            self.assertEqual(result['interfaces'], ['lo'])

    def test_container_reconciliation_reads_evidence_and_matches_four_issues(self):
        config = ScenarioConfig.from_dict(read_json(ROOT/'configs/interactions.json'))
        with tempfile.TemporaryDirectory() as cwd:
            result = run_external(42, config, Path(cwd)/'run')
            self.assertTrue(result['ok'])
            self.assertEqual((result['metrics']['tp'], result['metrics']['fp'], result['metrics']['fn']), (4,0,0))
            self.assertEqual(result['security_mode'],'docker_container')
            self.assertEqual(result['worker_image_id'],self.image_id)
            trace = [json.loads(line) for line in (Path(cwd)/'run/trajectories.jsonl').read_text().splitlines()]
            self.assertTrue(all(item['reward']==0 for item in trace))
            self.assertLessEqual(result['steps'],100)

    def test_container_resource_limits_and_no_leftover_worker(self):
        name = 'genesis-probe-' + uuid.uuid4().hex
        command = docker_command(self.image_id,name,['-c','import time;time.sleep(30)'])
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import time
            metadata = None
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                result=subprocess.run(['docker','inspect',name],capture_output=True,timeout=5)
                if result.returncode==0:
                    metadata=json.loads(result.stdout)[0]
                    if metadata['State']['Running']:
                        break
                time.sleep(0.1)
            self.assertIsNotNone(metadata)
            host=metadata['HostConfig']
            self.assertEqual(host['Memory'],512*1024*1024)
            self.assertEqual(host['MemorySwap'],512*1024*1024)
            self.assertEqual(host['NanoCpus'],1000000000)
            self.assertEqual(host['PidsLimit'],64)
            self.assertFalse(host.get('Binds'))
            self.assertTrue(all(m['Type']=='tmpfs' and m['Destination']=='/tmp' for m in metadata['Mounts']))
        finally:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
            process.communicate(timeout=5)
        self.assertNotEqual(subprocess.run(['docker','inspect',name],capture_output=True).returncode,0)

    def test_hanging_container_is_truncated_and_removed_by_production_cleanup(self):
        names = []
        def hanging(image_id, name, worker_command):
            names.append(name)
            return docker_command(image_id, name, ['-c','import time;time.sleep(60)'])
        with tempfile.TemporaryDirectory() as cwd, patch('genesis_fintech.evaluation.external.docker_command', side_effect=hanging):
            result = run_external(42, ScenarioConfig(), Path(cwd)/'run', wall_time_seconds=1)
        self.assertTrue(result['truncated'])
        self.assertFalse(result['ok'])
        self.assertEqual(result['failure'], 'worker_timeout')
        self.assertEqual(result['metrics']['tp'], 0)
        for name in names:
            self.assertNotEqual(subprocess.run(['docker','inspect',name],capture_output=True).returncode,0)


if __name__=='__main__':
    unittest.main()
