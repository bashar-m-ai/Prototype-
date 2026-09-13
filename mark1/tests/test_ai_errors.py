import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from intelligence import explain_error, ask, AIError

class AIErrorsTest(unittest.TestCase):
    def error(self,status,code=None,param=None):
        return urllib.error.HTTPError('https://api.openai.com/v1/responses',status,'Failed',{},io.BytesIO(json.dumps({'error':{'code':code,'param':param,'message':'Request format is invalid'}}).encode()))
    def test_error_categories_and_no_raw_response(self):
        for status,code,expected in [(429,'insufficient_quota','billing'),(429,'rate_limit_exceeded','rate-limiting'),(403,'permission_denied','permissions'),(404,'model_not_found','model'),(400,'invalid_image','JPEG'),(401,'invalid_api_key','API key'),(500,None,'server error')]:
            result=explain_error(self.error(status,code))
            self.assertIn(expected,result)
            self.assertNotIn('Authorization',result)
    def test_non_json_error_and_malformed_code(self):
        error=urllib.error.HTTPError('https://api.openai.com',403,'Failed',{},io.BytesIO(b'<html>private text</html>'))
        self.assertIn('403',explain_error(error))
        self.assertIn('unknown',explain_error(self.error(400,{'unexpected':'object'})))
    def test_ask_preserves_actionable_error(self):
        with patch('intelligence.api_key',return_value='fake-test-key'),patch('urllib.request.urlopen',side_effect=self.error(400,'unsupported_parameter','text.format')):
            with self.assertRaisesRegex(AIError,'supports images and JSON'):
                ask('/tmp','Return JSON',{'test':True})

    def test_json_mode_includes_instruction_in_input_not_only_system(self):
        response = io.BytesIO(json.dumps({'output':[{'content':[{'type':'output_text','text':'{"dishes":[]}'}]}]}).encode())
        with patch('intelligence.api_key',return_value='fake-test-key'), patch('urllib.request.urlopen',return_value=response) as send:
            result=ask('/tmp','Read menu',{'menu':'Salad'})
        body=json.loads(send.call_args.args[0].data)
        self.assertIn('JSON',body['input'][0]['content'][0]['text'])
        self.assertEqual(result,{'dishes':[]})

    def test_null_error_code_retains_explanation_and_redacts_keys(self):
        body={'error':{'code':None,'message':"Invalid key sk-proj-ABCDEF123456 or input format"}}
        error=urllib.error.HTTPError('https://api.openai.com',400,'Failed',{},io.BytesIO(json.dumps(body).encode()))
        result=explain_error(error)
        self.assertIn('input format',result)
        self.assertNotIn('sk-proj-',result)
