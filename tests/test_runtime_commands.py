import os
import unittest
from unittest.mock import patch

os.environ.setdefault('VLR_RUNTIME', 'podman')
from vlr_runtime import start_ollama, start_comfyui, _ensure_image, RuntimeErrorState

class RuntimeCommandTests(unittest.TestCase):
    def test_ollama_uses_non_conflicting_host_port_and_gpu_devices(self):
        calls=[]
        with patch('vlr_runtime.podman_exists', return_value=True), \
             patch('vlr_runtime._ensure_volume'), \
             patch('vlr_runtime._ensure_image'), \
             patch('vlr_runtime._container_running', return_value=False), \
             patch('vlr_runtime._container_exists', return_value=False), \
             patch('vlr_runtime._run', side_effect=lambda *a, **k: calls.append(a)), \
             patch('vlr_runtime.wait_http'):
            start_ollama()
        flat=' '.join(' '.join(x) for x in calls)
        self.assertIn('-p 11435:11434', flat)
        self.assertIn('OLLAMA_VULKAN=1', flat)
        self.assertIn('OLLAMA_IGPU_ENABLE=1', flat)
        if os.path.exists('/dev/dri'):
            self.assertIn('/dev/dri', flat)

    def test_missing_image_is_pulled_without_short_timeout(self):
        calls=[]
        class R:
            def __init__(self, code): self.returncode=code
        with patch('vlr_runtime.podman_storage_info', return_value={'free_gib':50,'graphroot':'/tmp'}), \
             patch('vlr_runtime._run', side_effect=[R(1), R(0), R(0)]) as run:
            _ensure_image('docker.io/ollama/ollama:latest')
            args=[c.args for c in run.call_args_list]
            self.assertEqual(args[0][:3], ('image','exists','docker.io/ollama/ollama:latest'))
            self.assertEqual(args[1][:2], ('pull','docker.io/ollama/ollama:latest'))
            self.assertTrue(run.call_args_list[1].kwargs.get('stream'))
            self.assertIsNone(run.call_args_list[1].kwargs.get('timeout'))
            self.assertEqual(args[2][:3], ('image','exists','docker.io/ollama/ollama:latest'))

    def test_missing_image_is_rejected_when_storage_is_low(self):
        class R:
            returncode=1
        with patch('vlr_runtime.podman_storage_info', return_value={'free_gib':2,'graphroot':'/quota'}), \
             patch('vlr_runtime._run', return_value=R()):
            with self.assertRaises(RuntimeErrorState) as ctx:
                _ensure_image('docker.io/ollama/ollama:latest')
        self.assertIn('Zu wenig freier Speicher', str(ctx.exception))

    def test_comfyui_requires_explicit_image(self):
        class C:
            comfy_image = ''
        with patch('vlr_runtime.cfg', return_value=C()), patch('vlr_runtime.podman_exists', return_value=True):
            with self.assertRaises(RuntimeErrorState):
                start_comfyui()

if __name__ == '__main__':
    unittest.main()
