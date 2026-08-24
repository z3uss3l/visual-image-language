import os, unittest
os.environ['VLR_RUNTIME']='podman'
from vlr_core import ollama_url, comfyui_url

class RuntimeEndpointTests(unittest.TestCase):
    def test_podman_endpoints_use_non_native_ports(self):
        self.assertEqual(ollama_url(), 'http://127.0.0.1:11435')
        self.assertEqual(comfyui_url(), 'http://127.0.0.1:8189')

if __name__ == '__main__': unittest.main()
