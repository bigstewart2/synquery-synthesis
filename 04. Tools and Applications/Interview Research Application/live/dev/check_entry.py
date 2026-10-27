"""Exercise the real HTTP handler without making model calls."""
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('demo_extract', Path(__file__).resolve().parents[1] / 'api/extract.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EntryTests(unittest.TestCase):
    def test_entry_and_retry_never_call_model(self):
        with patch.dict(os.environ, {'DEMO_PASSCODE':'current-demo-code'}, clear=True), \
             patch.object(module, 'run_extraction') as extraction:
            server = ThreadingHTTPServer(('127.0.0.1', 0), module.handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for payload, status in [
                    ({'action':'authenticate','passcode':'wrong'}, 401),
                    ({'action':'authenticate','passcode':'current-demo-code'}, 200),
                    ({'action':'authenticate','passcode':'old-demo-code'}, 401),
                    ([], 400),
                ]:
                    request = Request(f'http://127.0.0.1:{server.server_port}/api/extract',
                        data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
                    try:
                        response = urlopen(request)
                    except HTTPError as error:
                        response = error
                    with response:
                        self.assertEqual(response.status, status)
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                extraction.assert_not_called()
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
