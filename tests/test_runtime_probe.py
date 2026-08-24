import unittest
from unittest.mock import patch, Mock

from vlr_runtime import _api_probe

class RuntimeProbeTests(unittest.TestCase):
    def test_probe_distinguishes_model_missing_from_chat_failure(self):
        def get(url, timeout=3):
            r=Mock(); r.ok=True; r.json.return_value={'version':'0.32.9'} if url.endswith('/version') else {'models': [{'name':'other:latest'}]}; return r
        with patch('requests.get', side_effect=get):
            p=_api_probe('http://127.0.0.1:11434','qwen3.8:27b')
        self.assertFalse(p['model_present'])
        self.assertFalse(p['chat'])
        self.assertIn('Modell nicht vorhanden', p['error'])

    def test_probe_reports_chat_404_body(self):
        def get(url, timeout=3):
            r=Mock(); r.ok=True; r.json.return_value={'version':'0.32.9'} if url.endswith('/version') else {'models': [{'name':'qwen3.8:27b'}]}; return r
        bad=Mock(); bad.ok=False; bad.status_code=404; bad.text='model endpoint not found'
        with patch('requests.get', side_effect=get), patch('requests.post', return_value=bad):
            p=_api_probe('http://127.0.0.1:11434','qwen3.8:27b')
        self.assertFalse(p['chat'])
        self.assertIn('404', p['error'])
        self.assertIn('model endpoint not found', p['error'])

if __name__ == '__main__':
    unittest.main()
