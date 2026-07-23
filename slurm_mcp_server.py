#!/usr/bin/env python3
"""Minimal MCP server for Slurm job assistance."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

SQUEUE_FORMAT_JOB_STATUS = "%.18i %.9T %.100j"
SQUEUE_FORMAT_QUEUE = "%.18i %.9T %.100j %.8u"


class SlurmMCPServer:
    def __init__(self) -> None:
        self._tool_handlers = {
            "suggest_job_script": self.suggest_job_script,
            "submit_job": self.submit_job,
            "job_status": self.job_status,
            "list_queue": self.list_queue,
            "cancel_job": self.cancel_job,
        }

    def suggest_job_script(
        self,
        job_name: str,
        command: str,
        partition: str = "default",
        nodes: int = 1,
        ntasks_per_node: int = 1,
        time_limit: str = "01:00:00",
    ) -> Dict[str, str]:
        if not job_name or not command:
            raise ValueError("job_name and command are required")
        clean_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", job_name).strip("-")
        script = (
            "#!/bin/bash\n"
            f"#SBATCH --job-name={clean_name}\n"
            f"#SBATCH --partition={partition}\n"
            f"#SBATCH --nodes={nodes}\n"
            f"#SBATCH --ntasks-per-node={ntasks_per_node}\n"
            f"#SBATCH --time={time_limit}\n"
            "\n"
            "set -euo pipefail\n"
            f"{command}\n"
        )
        return {"script": script}

    def submit_job(
        self,
        script_path: Optional[str] = None,
        script_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not script_path and not script_content:
            raise ValueError("script_path or script_content is required")

        cleanup_path: Optional[str] = None
        if script_content:
            fd, tmp_path = tempfile.mkstemp(suffix=".sh")
            cleanup_path = tmp_path
            script_path = tmp_path
            try:
                os.chmod(tmp_path, 0o600)
                os.write(fd, script_content.encode("utf-8"))
            finally:
                os.close(fd)
        if not script_path:
            raise ValueError("Internal error: script path resolution failed")

        try:
            result = subprocess.run(
                ["sbatch", script_path],
                check=False,
                capture_output=True,
                text=True,
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            match = re.search(r"Submitted batch job (\d+)", output)
            return {
                "submitted": result.returncode == 0 and match is not None,
                "job_id": match.group(1) if match else None,
                "output": output,
                "stderr": error,
            }
        finally:
            if cleanup_path and os.path.exists(cleanup_path):
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass

    def job_status(self, job_id: str) -> Dict[str, str]:
        self._validate_job_id(job_id)
        result = subprocess.run(
            ["squeue", "--jobs", job_id, "--noheader", "--format", SQUEUE_FORMAT_JOB_STATUS],
            check=False,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip()
        if not output:
            return {"job_id": job_id, "status": "NOT_FOUND", "raw": ""}
        parts = output.split(maxsplit=2)
        status = parts[1] if len(parts) > 1 else "UNKNOWN"
        return {"job_id": job_id, "status": status, "raw": output}

    def list_queue(self, user: Optional[str] = None) -> Dict[str, str]:
        cmd = ["squeue", "--noheader", "--format", SQUEUE_FORMAT_QUEUE]
        if user:
            cmd.extend(["--user", user])
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return {"queue": result.stdout.strip()}

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        self._validate_job_id(job_id)
        result = subprocess.run(
            ["scancel", job_id],
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "cancelled": result.returncode == 0,
            "job_id": job_id,
            "stderr": result.stderr.strip(),
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "suggest_job_script",
                "description": "Generate a Slurm job script template from parameters.",
            },
            {
                "name": "submit_job",
                "description": "Submit a Slurm job via sbatch using script path or content.",
            },
            {
                "name": "job_status",
                "description": "Get Slurm job status using squeue.",
            },
            {
                "name": "list_queue",
                "description": "List current queue entries, optionally filtered by user.",
            },
            {
                "name": "cancel_job",
                "description": "Cancel a Slurm job with scancel.",
            },
        ]

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        if not re.fullmatch(r"\d+", job_id):
            raise ValueError("job_id must be numeric")

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "slurm-mcp", "version": "0.1.0"},
                }
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                if name not in self._tool_handlers:
                    raise ValueError(f"Unknown tool: {name}")
                result = self._tool_handlers[name](**arguments)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except (ValueError, TypeError, KeyError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(exc)},
            }
        except subprocess.SubprocessError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32001, "message": str(exc)},
            }


def main() -> None:
    server = SlurmMCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Invalid JSON: {exc}"},
            }
            print(json.dumps(response), flush=True)
            continue
        response = server.handle_request(request)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
