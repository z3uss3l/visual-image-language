import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class SetupStaticTests(unittest.TestCase):
    def test_setup_creates_all_required_source_dirs(self):
        text = (ROOT / 'setup.sh').read_text()
        self.assertIn('static,archive,logs,config,tests,config/quadlet', text)
        self.assertIn('python -m pip install', text)
        self.assertIn('--no-cache-dir', text)
        self.assertIn('psutil', text)
        self.assertIn('Setup startet keine KI-Runtime automatisch.', text)
        self.assertIn('config/defaults.env', text)
        self.assertNotIn('pip install torch', text.lower())
        self.assertNotIn('pip install torchvision', text.lower())

    def test_setup_wrapper_exists(self):
        p = ROOT / 'setup'
        self.assertTrue(p.is_file())
        self.assertTrue(p.stat().st_mode & 0o111)
        self.assertIn('setup.sh', (ROOT / 'setup').read_text())
        self.assertIn('trap', (ROOT / 'setup.sh').read_text())

    def test_verify_uses_project_venv(self):
        text = (ROOT / 'verify.sh').read_text()
        self.assertIn('.venv/bin/python', text)
        self.assertNotIn('python3 -m unittest', text)

    def test_apply_script_copies_runtime_configuration(self):
        text = (ROOT / 'APPLY_TO_REPO.sh').read_text()
        self.assertIn('requirements.txt', text)
        self.assertIn('config/defaults.env', text)
        self.assertIn('static/index_v3.html', text)

if __name__ == '__main__':
    unittest.main()
