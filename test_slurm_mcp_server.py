import unittest
from unittest.mock import patch

from slurm_mcp_server import SlurmMCPServer


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
        self.assertIn("python run.py", result["script"])

    @patch("slurm_mcp_server.subprocess.run")
    def test_submit_job_parses_job_id(self, run_mock):
        run_mock.return_value.stdout = "Submitted batch job 12345\n"
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0
        result = self.server.submit_job(script_content="#!/bin/bash\necho hi\n")
        self.assertTrue(result["submitted"])
        self.assertEqual(result["job_id"], "12345")

    @patch("slurm_mcp_server.subprocess.run")
    def test_job_status_not_found(self, run_mock):
        run_mock.return_value.stdout = ""
        run_mock.return_value.stderr = ""
        run_mock.return_value.returncode = 0
        result = self.server.job_status("42")
        self.assertEqual(result["status"], "NOT_FOUND")

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


if __name__ == "__main__":
    unittest.main()
