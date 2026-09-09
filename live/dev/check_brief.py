"""Offline regression tests for brief-driven extraction and evidence gates."""
import base64
import json
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
import extract as api
from _brief import brief_id, extract_brief, source_map, tool_payload, validate_brief
from _pipeline import norm, verify_citations, draft_themes, check_claim
from extract import Bad, brief_from, confirmed_from, decode_upload, expert_note_from

BRIEF = {'project':'Payments diligence', 'decision':'Evaluate retention and economics',
         'questions':['What drives retention?', 'What should management validate?']}
TRANSCRIPT = '\n# Interview\nExpert: The sales cycle takes four to nine months from first call to first transaction.\nExpert: Customers stay for reconciliation, though this is my experience rather than a market survey.\n'
QUOTE = 'The sales cycle takes four to nine months from first call to first transaction.'

def message(name, value, stop='tool_use'):
    return NS(content=[NS(type='tool_use', name=name, input=value)], stop_reason=stop,
              usage=NS(input_tokens=100, output_tokens=50))

class Client:
    def __init__(self, *responses):
        self.responses = iter(responses); self.calls = []; self.messages = self
    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception): raise response
        return response

def finding(**overrides):
    return dict(finding='The expert reports a four-to-nine-month sales cycle.', question_index=0,
                kind='observation', quote=QUOTE, confidence='high', **overrides)

class BriefTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_brief({**BRIEF,'project':' Payments diligence '}), BRIEF)
        for value in [None, {}, {**BRIEF,'questions':[]}, {**BRIEF,'questions':['q']*7},
                      {**BRIEF,'questions':[3]}, {**BRIEF,'questions':['x'*401]}]:
            with self.subTest(value=value), self.assertRaises(ValueError): validate_brief(value)
        with self.assertRaises(Bad): brief_from({'mode':'brief'})
        with self.assertRaises(Bad): brief_from({'mode':'unknown'})
        self.assertIsNone(brief_from({}))

    def test_source_locations_preserve_lines_and_normalization(self):
        for value in [TRANSCRIPT, '  Café “FOO”\nBAR\t— baz  ', 'İ é ﬂ\r\n\nEND']:
            normalized, locations = source_map(value)
            self.assertEqual(normalized, norm(value))
            self.assertEqual(len(normalized), len(locations))
        text = decode_upload('example.md',base64.b64encode(TRANSCRIPT.encode()).decode())
        self.assertEqual(text, TRANSCRIPT)
        normalized, locations = source_map(text)
        self.assertEqual(locations[normalized.index(norm(QUOTE))], 3)
        atoms = {'findings':[{'quote':''}]}
        verify_citations(atoms, TRANSCRIPT)
        self.assertFalse(atoms['findings'][0]['verified'])

    def test_real_brief_and_separate_review_with_no_invented_timestamps(self):
        client = Client(message('emit_findings',{'items':[finding()]}),
                        message('review_findings',{'checks':[{'index':0,'supported':True,'reason':'Preserves the sales stage.'}]}))
        atoms, usage, failures = extract_brief(client,'E1',TRANSCRIPT,BRIEF)
        a = atoms['findings'][0]
        self.assertEqual(a['source_start_line'],3)
        self.assertEqual(a['review_status'],'supported')
        self.assertEqual(a['brief_id'],brief_id(BRIEF))
        self.assertNotIn('timestamp',a)
        self.assertEqual(usage,{'input_tokens':200,'output_tokens':100})
        self.assertEqual(failures,[])
        self.assertEqual(json.loads(client.calls[0]['messages'][0]['content'])['research_brief'],BRIEF)
        self.assertIn('NOT evidence',expert_note_from({'brief':BRIEF,'experts':['E1','E2']}))

    def test_semantic_rejection_is_not_overridden_by_quote_match(self):
        wrong = {**finding(),'finding':'Implementation takes four to nine months.'}
        client = Client(message('emit_findings',{'items':[wrong]}),
                        message('review_findings',{'checks':[{'index':0,'supported':False,'reason':'Sales cycle is not implementation.'}]}))
        atoms, _, _ = extract_brief(client,'E1',TRANSCRIPT,BRIEF)
        a = atoms['findings'][0]
        self.assertTrue(a['verified']); self.assertEqual(a['review_status'],'flagged')
        with self.assertRaises(Bad): confirmed_from({'brief':BRIEF,'confirmed':{'E1:findings:0':a}})

    def test_missing_quote_does_not_run_review(self):
        client = Client(message('emit_findings',{'items':[{**finding(),'quote':'Invented quotation that does not occur.'}]}))
        atoms, _, _ = extract_brief(client,'E1',TRANSCRIPT,BRIEF)
        self.assertEqual(len(client.calls),1)
        self.assertFalse(atoms['findings'][0]['verified'])
        self.assertEqual(atoms['findings'][0]['review_status'],'flagged')

    def test_missing_duplicate_and_failed_reviews_stay_unconfirmed(self):
        for response in [message('review_findings',{'checks':[]}),
                         message('review_findings',{'checks':[{'index':0,'supported':True}]*2}),
                         RuntimeError('provider unavailable')]:
            with self.subTest(response=response):
                client = Client(message('emit_findings',{'items':[finding()]}),response)
                atoms, _, failures = extract_brief(client,'E1',TRANSCRIPT,BRIEF)
                self.assertNotEqual(atoms['findings'][0]['review_status'],'supported')
                if isinstance(response,Exception): self.assertTrue(failures)

    def test_evidence_from_another_brief_cannot_be_reused(self):
        a = {**finding(),'verified':True,'brief_id':brief_id(BRIEF),'review_status':'supported'}
        self.assertTrue(confirmed_from({'brief':BRIEF,'confirmed':{'a':a}}))
        for delta in [{'brief_id':'other'},{'verified':False},{'review_status':'unavailable'}]:
            with self.subTest(delta=delta), self.assertRaises(Bad):
                confirmed_from({'brief':BRIEF,'confirmed':{'a':{**a,**delta}}})

    def test_bad_or_truncated_model_output_is_failure_not_empty_success(self):
        with self.assertRaises(ValueError): tool_payload(message('emit_findings',{},'max_tokens'),'emit_findings')
        for items in [None,[{**finding(),'question_index':4}],[{**finding(),'question_index':True}]]:
            with self.subTest(items=items), self.assertRaises(ValueError):
                extract_brief(Client(message('emit_findings',{'items':items})),'E1',TRANSCRIPT,BRIEF)

    def test_incomplete_judgements_are_not_successful_drafts(self):
        a = {'E1:findings:0':finding()}
        for response in [message('emit_themes',{'summary':{'text':'Partial','atom_ids':['E1:findings:0']}},'max_tokens'),
                         message('emit_themes',{'summary':{'text':'Partial','atom_ids':['E1:findings:0']}})]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                draft_themes(Client(response),a,'Two interviews',brief_mode=True)
        with self.assertRaises(ValueError): check_claim(Client(message('emit_verdict',{})),'Test claim',a,'One interview')
        client=Client(message('emit_themes',{'summary':{'text':'A summary','atom_ids':['E1:findings:0']},'themes':[],'not_supported':['No market-wide evidence']}))
        result=draft_themes(client,a,'One interview',brief_mode=True)
        self.assertTrue(result[0]['citations_resolve'])
        self.assertNotIn('thinking',client.calls[0])

    def test_http_brief_dispatch_and_invalid_intake_do_not_use_questionnaire(self):
        base = {'passcode':'test-code', 'filename':'interview.md', 'expert':'E1', 'mode':'brief',
                'b64':base64.b64encode(TRANSCRIPT.encode()).decode(), 'brief':BRIEF}
        with patch.dict(os.environ, {'DEMO_PASSCODE':'test-code','ANTHROPIC_API_KEY':'test-only'}), \
             patch.object(api, 'extract_brief', return_value=({'findings':[]},{'input_tokens':0,'output_tokens':0},[])) as brief_call, \
             patch.object(api, 'run_extraction') as questionnaire:
            server=ThreadingHTTPServer(('127.0.0.1',0),api.handler)
            thread=Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                for payload, expected in [(base,200),({**base,'brief':None},400),
                    ({**base,'brief':{**BRIEF,'questions':['q']*7}},400),
                    ({**base,'b64':base64.b64encode(b'x'*60001).decode()},413)]:
                    request=Request(f'http://127.0.0.1:{server.server_port}/api/extract',
                                    data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                    try: response=urlopen(request)
                    except HTTPError as error: response=error
                    with response:
                        self.assertEqual(response.status,expected)
                        result=json.load(response)
                        if expected==200: self.assertEqual(result['brief_id'],brief_id(BRIEF))
                brief_call.assert_called_once();questionnaire.assert_not_called()
            finally: server.shutdown();server.server_close();thread.join()

if __name__ == '__main__': unittest.main()
