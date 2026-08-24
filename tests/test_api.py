import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

os.environ['VLR_RUNTIME'] = 'native'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import app

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        im = Image.new('RGB', (128,128), 'white')
        ImageDraw.Draw(im).rectangle((20,20,100,100), outline='black', width=4)
        b = io.BytesIO(); im.save(b, 'PNG'); cls.data = b.getvalue()

    def test_health_and_runtime(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        r = self.client.get('/api/runtime')
        self.assertEqual(r.status_code, 200)
        self.assertIn('probe', r.json())

    def test_identical_images_score_one(self):
        r = self.client.post('/api/compare', files={
            'reference': ('a.png', self.data, 'image/png'),
            'candidate': ('b.png', self.data, 'image/png'),
        })
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()['composite'], 0.999)
        self.assertTrue(r.json()['threshold_98'])

    def test_runtime_selection_endpoint_persists_without_starting_ai(self):
        with patch('app.runtime_cfg') as rcfg, patch('app.set_runtime_mode') as setter, patch('app.runtime_probe', return_value={'selected':'native'}), patch('app.runtime_status', return_value={'mode':'native'}):
            rcfg.return_value.mode = 'native'
            r = self.client.post('/api/runtime/select', json={'mode':'native'})
        self.assertEqual(r.status_code, 200)
        setter.assert_called_once_with('native')

if __name__ == '__main__':
    unittest.main()
