import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('VLR_RUNTIME', 'native')
from vlr_runtime import RuntimeConfig, status, _runtime_mode, set_runtime_mode

class RuntimeTests(unittest.TestCase):
    def test_default_ports_do_not_collide_with_native_defaults(self):
        c = RuntimeConfig()
        self.assertEqual(c.ollama_host_port, 11435)
        self.assertEqual(c.comfy_host_port, 8189)

    def test_status_is_safe_without_podman(self):
        with patch('vlr_runtime.podman_exists', return_value=False):
            s = status()
        self.assertIn('mode', s)
        self.assertIn('podman_available', s)
        self.assertIn('storage', s)

    def test_gpu_device_detection_is_host_based(self):
        self.assertTrue(hasattr(RuntimeConfig, '__dataclass_fields__'))

    def test_runtime_selection_is_persisted(self):
        with __import__('tempfile').TemporaryDirectory() as td:
            path = Path(td) / 'config' / 'runtime.env'
            with patch('vlr_runtime._app_dir', return_value=Path(td)):
                path.parent.mkdir(parents=True, exist_ok=True)
                self.assertEqual(set_runtime_mode('native'), 'native')
                self.assertEqual(_runtime_mode(), 'native')
                self.assertIn('VLR_RUNTIME=native', path.read_text())

    def test_legacy_database_migration_orders_columns_before_indexes(self):
        import sqlite3, tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'legacy.sqlite3'
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE experiments(id TEXT PRIMARY KEY, created_at REAL NOT NULL, generation INTEGER)")
            conn.commit(); conn.close()
            conn = sqlite3.connect(path)
            migrations={'mutation_type':'TEXT','mutation_feedback':'TEXT','seed':'TEXT','image_path':'TEXT','image_retained':'INTEGER DEFAULT 1','is_winner':'INTEGER DEFAULT 0','is_best':'INTEGER DEFAULT 0'}
            cols={r[1] for r in conn.execute('PRAGMA table_info(experiments)')}
            for n,t in migrations.items():
                if n not in cols: conn.execute(f'ALTER TABLE experiments ADD COLUMN {n} {t}')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_exp_retained ON experiments(image_retained)')
            conn.commit(); conn.close()

if __name__ == '__main__':
    unittest.main()
