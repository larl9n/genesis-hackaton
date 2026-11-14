import http.client
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from genesis_fintech.web.app import run_view
from genesis_fintech.web.server import ASSETS, STATIC, LocalServer, response


class ViewTests(unittest.TestCase):
    def test_real_scenarios_and_observed_evidence_without_truth(self):
        for name, expected in [('clean',0),('independent',4),('interactions',4)]:
            with self.subTest(scenario=name):
                result=run_view({'seed':42,'scenario':name,'policy':'reconciliation'})
                self.assertEqual((result['metrics']['tp'],result['metrics']['fp'],result['metrics']['fn']),(expected,0,0))
                self.assertEqual(len(result['findings']),expected)
                self.assertTrue(result['terminated'])
                self.assertLessEqual(result['steps'],100)
                for finding in result['findings']:
                    self.assertTrue(all(item['record'] is not None for item in finding['evidence']))
                    self.assertEqual({e['id'] for e in finding['evidence']},set(finding['evidence_ids']))
                for forbidden in ['acceptable_evidence_sets','expected_amount_minor','provenance','latent_history']:
                    self.assertNotIn(forbidden,json.dumps(result))

    def test_attack_policies_are_not_presented_as_verified_findings(self):
        for policy in ['random','flag-all']:
            result=run_view({'seed':42,'scenario':'interactions','policy':policy})
            self.assertGreater(result['metrics']['fp'],0)
            self.assertLess(result['metrics']['f1'],1)
            self.assertLessEqual(len(result['findings']),30)
            self.assertEqual(result['security_mode'],'development_in_process')

    def test_recordings_exactly_match_engine_results(self):
        content=(STATIC/'samples.js').read_text()
        samples=json.loads(content.split('window.GENESIS_SAMPLES = ',1)[1].rstrip().removesuffix(';'))
        for scenario,recorded in samples.items():
            self.assertEqual(recorded,run_view({'seed':42,'scenario':scenario,'policy':'reconciliation'}))

    def test_validation_rejects_unsupported_options_and_private_fields(self):
        base={'seed':42,'scenario':'clean','policy':'reconciliation'}
        requests=[None,[],{}, {**base,'truth':{}}, {**base,'scenario':'../../private'},
                  {**base,'policy':'evaluator_oracle'}, {**base,'seed':True},
                  {**base,'seed':1.2},{**base,'seed':-1},{**base,'seed':2147483648}]
        for request in requests:
            with self.subTest(request=request), self.assertRaises((ValueError,TypeError)):
                run_view(request)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.headers={'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','Content-Type':'application/json'}

    def test_explicit_assets_exist_and_private_paths_are_unreachable(self):
        for path in ASSETS:
            status,content_type,body=response('GET',path,self.headers,b'',8765)
            self.assertEqual(status,200)
            self.assertTrue(body)
        for path in ['/private/truth.json','/docs/PROJECT_CONTEXT.md','/../README.md','/%2e%2e/README.md','/api/score','/configs/interactions.json','/favicon.svg?x=../']:
            self.assertEqual(response('GET',path,self.headers,b'',8765)[0],404)
        self.assertTrue(json.loads(response('GET','/api/status',self.headers,b'',8765)[2])['ok'])

    def test_host_origin_size_and_content_type_checks_precede_execution(self):
        body=b'{"seed":42,"scenario":"clean","policy":"reconciliation"}'
        invalid=[({**self.headers,'Host':'evil.test:8765'},body,403),
                 ({**self.headers,'Origin':'http://evil.test:8765'},body,403),
                 ({key:value for key,value in self.headers.items() if key!='Origin'},body,403),
                 ({**self.headers,'Content-Type':'text/plain'},body,415),
                 (self.headers,b'x'*4097,413)]
        with patch('genesis_fintech.web.server.run_view') as runner:
            for headers,payload,expected in invalid:
                self.assertEqual(response('POST','/api/run',headers,payload,8765)[0],expected)
            runner.assert_not_called()

    def test_bad_requests_are_bounded_and_valid_request_runs_real_engine(self):
        for data in [b'{}',b'bad',b'\xff',b'{"seed":NaN}',b'{"seed":42,"seed":42}',b'['*1500]:
            status,_,body=response('POST','/api/run',self.headers,data,8765)
            self.assertEqual(status,400)
            self.assertLess(len(body),200)
            self.assertNotIn(b'Traceback',body)
        status,_,body=response('POST','/api/run',self.headers,b'{"seed":43,"scenario":"independent","policy":"reconciliation"}',8765)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['metrics']['tp'],4)


class LiveHTTPTests(unittest.TestCase):
    def test_loopback_http_assets_post_and_response_headers(self):
        try:
            server=LocalServer(0)
        except PermissionError:
            if __import__('os').environ.get('CI'):
                raise
            self.skipTest('current sandbox disallows loopback bind; actual HTTP is checked in CI')
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            port=server.server_port
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            connection.request('GET','/')
            result=connection.getresponse()
            self.assertEqual(result.status,200)
            self.assertIn("frame-ancestors 'none'",result.getheader('Content-Security-Policy'))
            self.assertIn('Genesis',result.read().decode())
            connection.close()
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            connection.request('POST','/api/run',body=json.dumps({'seed':44,'scenario':'clean','policy':'reconciliation'}),
                               headers={'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json'})
            result=connection.getresponse()
            self.assertEqual(result.status,200)
            self.assertEqual(json.loads(result.read())['metrics']['fp'],0)
            connection.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':
    unittest.main()
