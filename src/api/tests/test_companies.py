"""Pipeline tests do not contact paid providers."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing

import httpx
from fastapi import BackgroundTasks, HTTPException
from src.api.main import app
from src.providers import companies as c, experimental as ex, settings


class CompanyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'NOISE_STATE_DIR': self.temp.name})
        self.env.start(); self.addCleanup(self.env.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://radar.example')
        self.addAsyncCleanup(self.client.aclose)
        self.headers = {'X-Noise-Operator': settings.initialize().read_text().strip()}
        for provider in ('openrouter', 'featherless', 'verda', 'cala'):
            settings.save_config(provider, {'enabled': True, 'api_key': 'private-test-key'})
        self.payload = c.CompanyRequest(events=[ex.Evidence(id='original:1', text='Example Ltd received a government research grant in 2025.')])
        self.candidate = {'name': 'Example Ltd', 'id': 'e1', 'quote': self.payload.events[0].text}

    def queued(self, payload=None):
        response = c.start(payload or self.payload, BackgroundTasks())
        return json.loads(response.body)

    def saved(self, job):
        return json.loads(c.status(job['id']).body)

    async def test_protected_endpoints_and_fixed_model(self):
        self.assertEqual((await self.client.post('/api/experimental/companies', json=self.payload.model_dump())).status_code, 401)
        self.assertEqual((await self.client.get('/api/experimental/companies/anything')).status_code, 401)
        self.assertEqual((await self.client.post('/api/experimental/companies', headers={**self.headers, 'Origin':'https://evil.example'}, json=self.payload.model_dump())).status_code, 403)
        saved = settings.save_config('openrouter', {'model':'jev-latest'})
        self.assertEqual(saved['model'], '~typesafe/jev-latest')
        self.assertNotIn('private-test-key', json.dumps(saved))
        for patch_values in ({'model':'other/chat'}, {'base_url':'https://evil.example/api'}):
            with self.assertRaises(ValueError): settings.save_config('openrouter', patch_values)

    async def test_invalid_decisions_fail_closed(self):
        for value in (None, {}, {'type':'noul','noul':True}, {'type':'noul','noul':float('nan')}, {'type':'noul','noul':2}, {'type':'choice','noul':1}):
            with self.assertRaises(HTTPException): c.probability(value)
        for response in ({'answers':{}}, {'truncated':True,'answers':{'a':{'type':'noul','noul':1}}}):
            with patch.object(ex, 'fetch', return_value=response), self.assertRaises(HTTPException):
                c.decide({}, {'a':{}})

    async def test_no_company_never_extracts_or_reviews(self):
        job = self.queued()
        with patch.object(c, 'decide', return_value={'model':'jev','probabilities':{'has_company':.05}}), patch.object(c, 'extract') as extract, patch.object(ex, 'review') as review:
            c.run_job(job, self.payload)
            extract.assert_not_called(); review.assert_not_called()
        self.assertEqual(self.saved(job)['status'], 'completed')
        self.assertIn('No company detected', self.saved(job)['message'])

    async def test_grounding_rejects_invented_names_quotes_ids_and_duplicates(self):
        candidates = [self.candidate, self.candidate, {**self.candidate,'name':'Invented Inc'}, {**self.candidate,'id':'bad'}, {**self.candidate,'quote':'Example Ltd owns everything.'}]
        response = {'choices':[{'message':{'content':json.dumps({'companies':candidates})}}]}
        with patch.object(ex, 'models', return_value=[{'id':settings.get_config('featherless')['model']}]), patch.object(ex, 'fetch', return_value=response):
            result = c.extract([{'id':'e1','text':self.payload.events[0].text}])
        self.assertEqual(result['candidates'], [self.candidate])
        self.assertEqual(result['discarded_candidates'],4)

    async def test_validation_rejection_stops_downstream(self):
        job = self.queued()
        with patch.object(c, 'decide', side_effect=[{'model':'jev','probabilities':{'has_company':.99}}, {'model':'jev','probabilities':{'c0':.3}}]), patch.object(c,'extract',return_value={'candidates':[self.candidate]}), patch.object(ex,'review') as review:
            c.run_job(job,self.payload); review.assert_not_called()
        self.assertEqual(self.saved(job)['companies'],[])

    async def test_partial_failure_and_cala_provenance(self):
        job = self.queued()
        calls = []
        def review(payload):
            calls.append(payload)
            if payload.provider == 'verda': raise HTTPException(502,'GPU unavailable')
            return {'provider':payload.provider,'kind':'research' if payload.provider=='cala' else 'review','content':'Unverified generated ownership lead'}
        with patch.object(c,'decide',side_effect=[{'model':'jev','probabilities':{'has_company':.99}}, {'model':'jev','probabilities':{'c0':.99}}]), patch.object(c,'extract',return_value={'candidates':[self.candidate]}), patch.object(ex,'review',side_effect=review):
            c.run_job(job,self.payload)
        saved=self.saved(job)
        self.assertEqual(saved['status'],'partial')
        self.assertEqual([p.provider for p in calls],['cala','verda','featherless'])
        self.assertEqual(calls[-1].events,self.payload.events)  # Generated Cala text is not laundered into evidence.
        self.assertEqual(saved['companies'][0]['id'],'original:1')
        self.assertEqual(saved['stages'][-1]['status'],'completed')

    async def test_synthetic_skips_cala_and_keeps_label(self):
        self.payload.synthetic=True
        job=self.queued()
        with patch.object(c,'decide',side_effect=[{'model':'jev','probabilities':{'has_company':.99}}, {'model':'jev','probabilities':{'c0':.99}}]), patch.object(c,'extract',return_value={'candidates':[self.candidate]}), patch.object(ex,'review',return_value={}) as review:
            c.run_job(job,self.payload)
        self.assertEqual([call.args[0].provider for call in review.call_args_list],['verda','featherless'])
        self.assertTrue(all(call.args[0].synthetic for call in review.call_args_list))
        self.assertTrue(self.saved(job)['synthetic'])

    async def test_disabled_master_stops_subsequent_stages(self):
        job=self.queued()
        settings.save_config('openrouter',{'enabled':False})
        with patch.object(c,'decide') as decide:
            c.run_job(job,self.payload); decide.assert_not_called()
        self.assertEqual(self.saved(job)['status'],'partial')

    async def test_dedup_busy_and_restart_do_not_resubmit(self):
        job=self.queued()
        self.assertEqual(self.queued()['id'],job['id'])
        other=c.CompanyRequest(events=[ex.Evidence(id='other',text='Other Corp announced results.')])
        with self.assertRaises(HTTPException) as error: self.queued(other)
        self.assertEqual(error.exception.status_code,409)
        c.recover_jobs()
        self.assertEqual(self.saved(job)['status'],'interrupted')
        self.assertEqual(self.queued()['id'],job['id'])
        self.assertNotEqual(self.queued(other)['id'],job['id'])

    async def test_retention_and_input_coverage(self):
        self.payload.events[0].text='a'*3000
        self.payload.total_records=100
        job=self.queued()
        self.assertEqual(job['coverage']['detection_truncated_records'],1)
        self.assertEqual(job['coverage']['total_records'],100)
        with closing(c.database()) as db, db:
            db.execute("UPDATE company_jobs SET created=0,status='completed'")
        self.assertNotEqual(self.queued()['id'],job['id'])
