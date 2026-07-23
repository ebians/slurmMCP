import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from slurm_mcp_server import SlurmMCPServer, create_http_handler


class SlurmMCPServerTests(unittest.TestCase):
    def setUp(self):
        self.server = SlurmMCPServer()

    def test_suggest_job_script(self):
        result = self.server.suggest_job_script(
            job_name="demo job",
            command="python run.py",
            partition="gpu",
            nodes=2,
        )
        self.assertIn("#SBATCH --job-name=demo-job", result["script"])
        self.assertIn("#SBATCH --partition=gpu", result["script"])
        self.assertIn("#SBATCH --nodes=2", result["script"])
        self.assertIn("python run.py", result["script"])

    def test_suggest_job_script_normalizes_job_name(self):
        result = self.server.suggest_job_script(
            job_name="demo   job@@name",
            command="echo ok",
        )
        self.assertIn("#SBATCH --job-name=demo-job-name", result["script"])

    @patch("slurm_mcp_server.subprocess.run")
    def test_submit_job_parses_job_id(self, run_mock):
        run_mock.return_value.stdout = "Submitted batch job 12345\n"
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0
        result = self.server.submit_job(script_content="#!/bin/bash\necho hi\n")
        self.assertTrue(result["submitted"])
        self.assertEqual(result["job_id"], "12345")

    @patch("slurm_mcp_server.subprocess.run")
    def test_submit_job_cleans_temporary_file(self, run_mock):
        run_mock.return_value.stdout = "Submitted batch job 12345\n"
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0

        created = {}
        original_mkstemp = tempfile.mkstemp

        def create_temp_file(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            created["path"] = path
            return fd, path

        with patch("slurm_mcp_server.tempfile.mkstemp", side_effect=create_temp_file):
            self.server.submit_job(script_content="#!/bin/bash\necho hi\n")
        self.assertFalse(os.path.exists(created["path"]))

    @patch("slurm_mcp_server.subprocess.run")
    def test_job_status_not_found(self, run_mock):
        run_mock.return_value.stdout = ""
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0
        result = self.server.job_status("42")
        self.assertEqual(result["status"], "NOT_FOUND")

    @patch("slurm_mcp_server.subprocess.run")
    def test_list_queue(self, run_mock):
        run_mock.return_value.stdout = "123 RUNNING demo user\n"
        run_mock.return_value.returncode = 0
        result = self.server.list_queue(user="user")
        self.assertIn("RUNNING", result["queue"])

    @patch("slurm_mcp_server.subprocess.run")
    def test_cancel_job(self, run_mock):
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0
        result = self.server.cancel_job("123")
        self.assertTrue(result["cancelled"])
        self.assertEqual(result["job_id"], "123")

    def test_job_id_must_be_numeric(self):
        with self.assertRaises(ValueError):
            self.server.job_status("12;rm -rf /")

    def test_handle_request_unknown_tool(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "missing", "arguments": {}},
            }
        )
        self.assertIn("error", response)
        self.assertIn("Unknown tool", response["error"]["message"])

    def test_http_initialize(self):
        handler = create_http_handler(self.server)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        worker = threading.Thread(target=httpd.serve_forever)
        worker.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertIn("result", body)
            self.assertEqual(body["result"]["serverInfo"]["name"], "slurm-mcp")
            conn.close()
        finally:
            httpd.shutdown()
            worker.join(timeout=5)
            httpd.server_close()

    def test_http_unknown_tool_error(self):
        handler = create_http_handler(self.server)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        worker = threading.Thread(target=httpd.serve_forever)
        worker.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "missing", "arguments": {}},
            }
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertIn("error", body)
            self.assertEqual(body["error"]["code"], -32602)
            conn.close()
        finally:
            httpd.shutdown()
            worker.join(timeout=5)
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
