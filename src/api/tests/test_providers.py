import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from src.api.main import app
from src.providers import settings, experimental
from src.collectors import context


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'NOISE_STATE_DIR': self.temp.name, 'CONTEXT_API_KEY': 'environment-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://radar.example')
        self.addAsyncCleanup(self.client.aclose)
        self.token = settings.initialize().read_text().strip()
        self.headers = {'X-Noise-Operator': self.token}

    async def save(self, provider='featherless', **values):
        return await self.client.patch('/api/settings/' + provider, headers=self.headers, json=values)

    async def request_review(self, provider='featherless', **values):
        payload = {'provider': provider, 'entity': 'Example Ltd', 'events': [
            {'id': 'article:1', 'text': 'Example Ltd received a government grant in 2025.', 'source_url': 'https://example.org/article'}]}
        payload.update(values)
        return await self.client.post('/api/experimental/review', json=payload, headers=self.headers)

    async def test_authentication_and_origin_guard(self):
        for path in ('/api/settings',):
            self.assertEqual((await self.client.get(path)).status_code, 401)
            self.assertEqual((await self.client.get(path, headers={'X-Noise-Operator': 'wrong'})).status_code, 401)
            self.assertEqual((await self.client.get(path, headers={**self.headers, 'Origin': 'https://evil.example'})).status_code, 403)
        self.assertEqual((await self.client.post('/api/experimental/review', json={'provider':'cala','entity':'Acme'})).status_code, 401)
        response = await self.client.get('http://radar.example/api/settings', headers=self.headers)
        self.assertEqual(response.status_code, 403)

    async def test_keys_private_persistent_and_explicit_removal(self):
        result = await self.save(api_key='secret-value', enabled=True)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('secret-value', result.text)
        result = await self.client.get('/api/settings', headers=self.headers)
        self.assertNotIn('secret-value', result.text)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        await self.save(api_key='', model='Qwen/Qwen2.5-7B-Instruct')
        self.assertEqual(settings.api_key('featherless'), 'secret-value')
        await self.save(remove_key=True)
        self.assertEqual(settings.api_key('featherless'), '')
        self.assertEqual((Path(self.temp.name) / 'providers.sqlite3').stat().st_mode & 0o777, 0o600)
        self.assertEqual(settings.initialize().stat().st_mode & 0o777, 0o600)

    async def test_context_settings_override_environment_and_can_disable(self):
        self.assertEqual(context.api_key('context'), 'environment-key')
        await self.save('context', api_key='new-key')
        self.assertEqual(context.api_key('context'), 'new-key')
        await self.save('context', enabled=False)
        self.assertFalse(context.configured())
        with self.assertRaises(context.ContextUnavailable): context.collect_news('topic')
        await self.save('context', enabled=True, remove_key=True)
        self.assertFalse(context.configured())

    async def test_invalid_settings_never_echo_secrets(self):
        for values in ({'api_key': {'secret': 'do-not-echo'}}, {'api_key': 'do-not-echo', 'unexpected': 'do-not-echo'}, {'api_key': 'do-not-echo', 'model': 'x'*201}):
            response = await self.save(**values)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn('do-not-echo', response.text)
        self.assertEqual((await self.save(api_key='contains whitespace')).status_code, 400)

    async def test_endpoint_allowlist(self):
        for url in ('http://127.0.0.1/v1', 'https://evil.example/v1', 'https://containers.verda.com.evil.example/test/v1', 'https://containers.verda.com/a/../v1', 'https://user:password@containers.verda.com/a/v1'):
            self.assertEqual((await self.save('verda', base_url=url)).status_code, 400)
        self.assertEqual((await self.save('verda', base_url='https://containers.verda.com/nemotron/v1')).status_code, 200)
        self.assertEqual((await self.save('verda', base_url='https://containers.datacrunch.io/nemotron/v1')).status_code, 200)
        self.assertEqual((await self.save('verda', base_url='https://containers.datacrunch.io.evil.example/nemotron/v1')).status_code, 400)
        self.assertEqual((await self.save(base_url='https://evil.example/v1')).status_code, 400)

    async def test_disabled_provider_never_calls_upstream(self):
        await self.save(api_key='key', enabled=False)
        with patch.object(experimental, 'fetch') as fetch:
            self.assertEqual((await self.request_review()).status_code, 409)
            fetch.assert_not_called()

    async def test_verda_refuses_non_nvidia_and_missing_models(self):
        for model, catalog in [('deepseek', [{'id':'deepseek','owned_by':'DeepSeek'}]), ('nvidia/Nemotron', [])]:
            await self.save('verda', api_key='key', enabled=True, model=model)
            with patch.object(experimental, 'fetch', return_value={'data':catalog}) as fetch:
                response = await self.request_review('verda')
                self.assertEqual(response.status_code, 409)
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(fetch.call_args.args[1], '/models')

    async def test_nvidia_review_validates_quotes_and_preserves_citations(self):
        await self.save('verda', api_key='key', enabled=True, model='nvidia/Nemotron')
        output = {'relevance':'related', 'findings':[
            {'claim':'The record reports a government grant.', 'category':'government_funding', 'evidence':[{'id':'e1','quote':'received a government grant in 2025.'}]},
            {'claim':'Invented ownership', 'evidence':[{'id':'e2','quote':'some invented long quotation'}]},
            {'claim':'Invented quote', 'evidence':[{'id':'e1','quote':'some invented long quotation'}]}]}
        with patch.object(experimental, 'fetch', side_effect=[{'data':[{'id':'nvidia/Nemotron'}]}, {'choices':[{'message':{'content':json.dumps(output)}}]}]) as fetch:
            response = await self.request_review('verda', synthetic=True)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['discarded_findings'], 2)
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['findings'][0]['evidence'][0]['source_url'], 'https://example.org/article')
        self.assertIn('never establish propaganda', fetch.call_args.args[2]['messages'][0]['content'])
        self.assertLessEqual(fetch.call_args.args[2]['max_tokens'], 1800)

    async def test_cala_uses_documented_body_and_labels_opaque_references(self):
        await self.save('cala', api_key='key', enabled=True)
        with patch.object(experimental, 'fetch', return_value={'content':'Research lead', 'context':[{'id':'uuid','content':'Background'}]}) as fetch:
            response = await self.request_review('cala', events=[])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch.call_args.args[1], '/knowledge/search')
        self.assertIn('input', fetch.call_args.args[2])
        self.assertIn('unverified', response.json()['reference_notice'])
        self.assertEqual(response.json()['references'][0]['id'], 'uuid')

    async def test_durable_budget_counts_failed_requests(self):
        await self.save(api_key='key', enabled=True)
        with patch.object(experimental, 'fetch', side_effect=experimental.HTTPException(502, 'Unavailable')) as fetch:
            for _ in range(4):
                self.assertEqual((await self.request_review()).status_code, 502)
            self.assertEqual((await self.request_review()).status_code, 429)
            self.assertEqual(fetch.call_count, 4)

    async def test_malformed_model_output_and_empty_input(self):
        await self.save(api_key='key', enabled=True)
        with patch.object(experimental, 'fetch') as fetch:
            self.assertEqual((await self.request_review(events=[])).status_code, 400)
            fetch.assert_not_called()
        with self.assertRaises(experimental.HTTPException):
            experimental.clean_review('not JSON', {})
        result = experimental.clean_review('{"findings":[{"claim":"x","evidence":[{"id":[],"quote":"something long"}]}]}', {})
        self.assertEqual(result['findings'], [])

    async def test_provider_errors_sanitized_and_no_redirects(self):
        config = settings.get_config('featherless')
        config['api_key'] = 'private-key'
        for status in (401, 403, 429, 302):
            request = httpx.Request('GET', config['base_url'] + '/models')
            response = httpx.Response(status, text='private-key diagnostic', request=request)
            with patch.object(experimental.httpx, 'stream') as stream:
                stream.return_value.__enter__.return_value = response
                with self.assertRaises(experimental.HTTPException) as raised:
                    experimental.fetch(config, '/models')
                self.assertNotIn('private-key', raised.exception.detail)
                self.assertFalse(stream.call_args.kwargs['follow_redirects'])

    async def test_verda_cold_start_submits_once_and_polls_same_job(self):
        config = {**settings.get_config('verda'), 'base_url':'https://containers.datacrunch.io/nemotron/v1', 'api_key':'private-key'}
        receipt = {'Id':'job-1', 'ResultPath':'/result/nemotron'}
        result = {'data':[{'id':'nvidia/NVIDIA-Nemotron-Nano-9B-v2'}]}
        with patch.object(experimental.uuid, 'uuid4', return_value='job-1'), patch.object(experimental.time, 'sleep'), patch.object(experimental, 'request_json', side_effect=[receipt, None, result]) as request:
            self.assertEqual(experimental.fetch(config, '/models'), result)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[0].args[2]['Prefer'], 'respond-async')
        for call in request.call_args_list[1:]:
            self.assertEqual(call.args[1], 'https://containers.datacrunch.io/result/nemotron')
            self.assertEqual(call.args[2]['X-Inference-Id'], 'job-1')
            self.assertNotIn('Prefer', call.args[2])

    async def test_verda_receipts_cannot_redirect_credentials(self):
        config = {**settings.get_config('verda'), 'base_url':'https://containers.verda.com/nemotron/v1'}
        for receipt in ({'Id':'job-1','ResultPath':'https://evil.example/result'}, {'Id':'different','ResultPath':'/result/nemotron'}):
            with patch.object(experimental.uuid, 'uuid4', return_value='job-1'), patch.object(experimental, 'request_json', return_value=receipt) as request:
                with self.assertRaises(experimental.HTTPException): experimental.fetch(config, '/models')
                self.assertEqual(request.call_count, 1)

    async def test_verda_poll_deadline_never_resubmits_inference(self):
        config = {**settings.get_config('verda'), 'base_url':'https://containers.verda.com/nemotron/v1'}
        receipt = {'Id':'job-1','ResultPath':'/result/nemotron'}
        with patch.object(experimental.uuid, 'uuid4', return_value='job-1'), patch.object(experimental.time, 'monotonic', side_effect=[0,0,601]), patch.object(experimental.time, 'sleep'), patch.object(experimental, 'request_json', side_effect=[receipt,None]) as request:
            with self.assertRaises(experimental.HTTPException) as raised: experimental.fetch(config, '/chat/completions', {'messages':[]})
            self.assertEqual(raised.exception.status_code, 504)
            self.assertEqual([c.args[0] for c in request.call_args_list], ['POST','GET'])

    async def test_pending_results_do_not_parse_error_bodies(self):
        for status in (404,202):
            response = httpx.Response(status, text='not ready')
            with patch.object(experimental.httpx, 'stream') as stream:
                stream.return_value.__enter__.return_value = response
                self.assertIsNone(experimental.request_json('GET', 'https://containers.verda.com/result/nemotron', {}, pending=True))

    async def test_nemotron_direct_json_mode(self):
        model = 'nvidia/NVIDIA-Nemotron-Nano-9B-v2'
        await self.save('verda', api_key='key', enabled=True, model=model)
        with patch.object(experimental, 'fetch', side_effect=[{'data':[{'id':model}]}, {'choices':[{'message':{'content':'{"relevance":"uncertain","findings":[]}'}}]}]) as fetch:
            response = await self.request_review('verda')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(fetch.call_args.args[2]['messages'][0]['content'].endswith('/no_think'))
