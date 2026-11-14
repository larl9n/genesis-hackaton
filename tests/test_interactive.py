import json
from pathlib import Path
import unittest

from genesis_fintech.domain.models import DataError
from genesis_fintech.web.interactive import ManualSessions, compare_view
from genesis_fintech.web.server import response, STATIC


class InteractiveTests(unittest.TestCase):
    def test_comparison_same_episode_and_recordings(self):
        samples=json.loads((STATIC/'comparisons.js').read_text().split('window.GENESIS_COMPARISONS = ',1)[1].strip().removesuffix(';'))
        for scenario,expected in samples.items():
            result=compare_view({'seed':42,'scenario':scenario})
            self.assertEqual(result,expected)
            self.assertEqual(len(result['runs']),3)
            self.assertFalse(result['oracle_included'])
            best=next(r for r in result['runs'] if r['policy']=='reconciliation')
            self.assertEqual(best['metrics']['f1'],1)
            self.assertTrue(all(r['terminated'] and not r['truncated'] for r in result['runs']))

    def test_manual_records_reward_hidden_and_clean_submission(self):
        sessions=ManualSessions()
        start=sessions.start({'seed':42,'scenario':'clean'})
        eid=start['observation']['manifest']['episode_id']; token=start['session']
        step=sessions.step({'session':token,'action':{'action':'list_records','params':{'table':'invoices','cursor':None,'limit':20}}})
        self.assertEqual(len(step['observation']['result']['records']),20)
        self.assertEqual(step['reward'],0)
        self.assertNotIn('metrics',step)
        document=step['observation']['result']['records'][0]
        fetched=sessions.step({'session':token,'action':{'action':'get_document','params':{'doc_id':document['doc_id']}}})
        self.assertEqual(fetched['observation']['result'],document)
        for forbidden in ['truth','expected_amount_minor','provenance','acceptable_evidence_sets','latent_history']:
            self.assertNotIn(forbidden,json.dumps(step))
        final=sessions.step({'session':token,'action':{'action':'submit','params':{'episode_id':eid,'findings':[]}}})
        self.assertTrue(final['terminated']);self.assertFalse(final['truncated'])
        self.assertEqual(final['reward'],0);self.assertAlmostEqual(final['metrics']['reward'],0.996)
        with self.assertRaises(DataError):sessions.step({'session':token,'action':{}})

    def test_manual_timeout_is_empty_submission_and_state_is_separate(self):
        now=[0.0];sessions=ManualSessions(clock=lambda:now[0])
        one=sessions.start({'seed':1,'scenario':'interactions'});two=sessions.start({'seed':2,'scenario':'clean'})
        sessions.step({'session':one['session'],'action':{'action':'calculator','params':{'expression':'2+3'}}})
        result=sessions.step({'session':two['session'],'action':{'action':'calculator','params':{'expression':'7/2'}}})
        self.assertEqual(result['steps'],1)
        now[0]=61
        final=sessions.step({'session':one['session'],'action':{'action':'submit','params':{}}})
        self.assertTrue(final['truncated']);self.assertEqual(final['metrics']['tp'],0)
        self.assertGreater(final['metrics']['fn'],0)

    def test_capacity_invalid_input_and_expiry(self):
        now=[0];sessions=ManualSessions(maximum=1,clock=lambda:now[0])
        start=sessions.start({'seed':1,'scenario':'clean'})
        with self.assertRaises(DataError):sessions.start({'seed':2,'scenario':'clean'})
        now[0]=76
        with self.assertRaises(DataError):sessions.step({'session':start['session'],'action':{}})
        self.assertTrue(sessions.start({'seed':2,'scenario':'clean'}))
        for request in [{'seed':True,'scenario':'clean'},{'seed':1,'scenario':'../private'},{'seed':1,'scenario':'clean','truth':{}}]:
            with self.assertRaises((ValueError,TypeError)):compare_view(request)

    def test_new_routes_enforce_origin_and_large_manual_frames_only(self):
        headers={'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','Content-Type':'application/json'}
        for path in ['/api/compare','/api/manual/start','/api/manual/step']:
            self.assertEqual(response('POST',path,{**headers,'Origin':'http://evil.test'},b'{}',8765)[0],403)
            self.assertEqual(response('POST',path,headers,b'x'*65537,8765)[0],413)
            self.assertEqual(response('POST',path,headers,b'{"truth":{}}',8765)[0],400)
        payload=json.dumps({'seed':17,'scenario':'clean'}).encode()
        status,_,body=response('POST','/api/manual/start',headers,payload,8765);self.assertEqual(status,200)
        start=json.loads(body)
        action={'session':start['session'],'action':{'action':'submit','params':{'episode_id':start['observation']['manifest']['episode_id'],'findings':[]}}}
        status,_,body=response('POST','/api/manual/step',headers,json.dumps(action).encode(),8765)
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['metrics']['f1'],1)
