import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

spec = importlib.util.spec_from_file_location("protoface_runner", Path(__file__).with_name("run.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["prompt", "duration_seconds", "quality", "aspect_ratio"],
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "duration_seconds": {"type": "integer", "minimum": 4, "maximum": 15},
        "quality": {"enum": ["480p", "768p", "2k"]},
        "aspect_ratio": {"enum": ["16:9", "9:16", "1:1"]},
    },
}
MODEL = {"available": True, "operations": {"video.general": {}},
         "request_schemas": {"video.general": SCHEMA}}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "output"
        self.summary = Path(self.temp.name) / "summary.md"
        self.enterContext(patch.object(runner, "OUTPUT", self.output))
        self.enterContext(patch.dict(os.environ, {
            "PROTOFACE_ACTION": "generate_video", "PROTOFACE_CONFIRM_SPEND": "true",
            "PROTOFACE_PROMPT": "A sailboat at sunrise.", "PROTOFACE_DURATION": "8",
            "PROTOFACE_QUALITY": "768p", "PROTOFACE_ASPECT_RATIO": "16:9",
            "PROTOFACE_RUN_ID": "run_test", "GITHUB_RUN_ID": "12345",
            "GITHUB_STEP_SUMMARY": str(self.summary),
        }, clear=True))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def client(self, replies):
        self.seen = []
        def handle(req):
            self.seen.append(req)
            self.assertTrue(replies, f"Unexpected request: {req.method} {req.url}")
            method, path, status, body = replies.pop(0)
            self.assertEqual((req.method, req.url.path), (method, path))
            if isinstance(body, Exception):
                raise body
            return httpx.Response(status, json=body)
        return self.enterContext(httpx.Client(base_url=runner.API, transport=httpx.MockTransport(handle)))

    def before_submit(self):
        return [("GET", "/v1/models/minimax/minimax-h3", 200, MODEL),
                ("GET", "/v1/billing/quota", 200, {"balance_credits": 100})]

    def test_success_submits_once_with_documented_fields_and_polls_status(self):
        replies = self.before_submit() + [
            ("POST", "/v1/run/minimax/minimax-h3", 202,
             {"id": "run_test", "credit_estimate": {"estimated_credits": 29}}),
            ("GET", "/v1/runs/run_test/status", 200, {"status": "running"}),
            ("GET", "/v1/runs/run_test/status", 200, {"status": "completed"}),
            ("GET", "/v1/runs/run_test", 200,
             {"status": "completed", "outputs": [
                 {"modality": "video", "file": {"url": "https://media.example/video.mp4"}}]}),
        ]
        with patch.object(runner.time, "sleep"):
            runner.execute(self.client(replies))
        self.assertFalse(replies)
        posts = [req for req in self.seen if req.method == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(json.loads(posts[0].content), {
            "prompt": "A sailboat at sunrise.", "duration_seconds": 8,
            "quality": "768p", "aspect_ratio": "16:9",
        })
        self.assertIn("https://media.example/video.mp4", self.summary.read_text())
        self.assertEqual(json.loads((self.output / "run-id.json").read_text()), {"id": "run_test"})

    def test_connection_check_is_read_only(self):
        os.environ["PROTOFACE_ACTION"] = "check_connection"
        runner.execute(self.client([("GET", "/v1/models", 200, {"data": [{"id": "m"}]})]))
        self.assertEqual(len(self.seen), 1)
        self.assertIn("connection successful", self.summary.read_text())

    def test_missing_key_explains_secret_setup_without_a_request(self):
        with patch.object(runner.httpx, "Client") as client:
            self.assertEqual(runner.main(), 1)
        client.assert_not_called()
        self.assertIn("PROTOFACE_API_KEY", self.summary.read_text())

    def test_no_spend_confirmation_makes_no_request(self):
        os.environ["PROTOFACE_CONFIRM_SPEND"] = "false"
        with self.assertRaisesRegex(runner.RunError, "confirm_spend"):
            runner.execute(self.client([]))
        self.assertFalse(self.seen)

    def test_invalid_live_schema_input_prevents_submit(self):
        os.environ["PROTOFACE_DURATION"] = "100"
        with self.assertRaisesRegex(runner.RunError, "Invalid duration_seconds"):
            runner.execute(self.client(self.before_submit()[:1]))
        self.assertTrue(all(req.method == "GET" for req in self.seen))

    def test_empty_balance_prevents_submit(self):
        replies = self.before_submit()
        replies[1] = ("GET", "/v1/billing/quota", 200, {"balance_credits": 0})
        with self.assertRaisesRegex(runner.RunError, "balance is empty"):
            runner.execute(self.client(replies))
        self.assertEqual([req.method for req in self.seen], ["GET", "GET"])

    def test_same_github_run_reuses_key_but_new_run_gets_a_new_key(self):
        payload = {"prompt": "boat"}
        first = runner.idempotency_key(payload)
        os.environ["GITHUB_RUN_ATTEMPT"] = "2"
        self.assertEqual(first, runner.idempotency_key(payload))
        os.environ["GITHUB_RUN_ID"] = "99999"
        self.assertNotEqual(first, runner.idempotency_key(payload))

    def test_submit_failure_is_not_retried(self):
        replies = self.before_submit() + [
            ("POST", "/v1/run/minimax/minimax-h3", 503, {"error": {"code": "unavailable"}}),
        ]
        with self.assertRaisesRegex(runner.RunError, "503: unavailable"):
            runner.execute(self.client(replies))
        self.assertEqual(len([req for req in self.seen if req.method == "POST"]), 1)

    def test_network_timeout_during_submit_is_not_retried(self):
        replies = self.before_submit() + [
            ("POST", "/v1/run/minimax/minimax-h3", 0, httpx.ReadTimeout("timed out")),
        ]
        with self.assertRaisesRegex(runner.RunError, "may still be processing"):
            runner.execute(self.client(replies))
        self.assertEqual(len([req for req in self.seen if req.method == "POST"]), 1)

    def test_check_run_never_submits_and_reports_provider_failure(self):
        os.environ["PROTOFACE_ACTION"] = "check_run"
        replies = [
            ("GET", "/v1/runs/run_test/status", 200, {"status": "failed"}),
            ("GET", "/v1/runs/run_test", 200,
             {"status": "failed", "error": {"code": "generation_failed"}}),
        ]
        with self.assertRaisesRegex(runner.RunError, "generation_failed"):
            runner.execute(self.client(replies))
        self.assertTrue((self.output / "result.json").exists())
        self.assertTrue(all(req.method == "GET" for req in self.seen))

    def test_poll_timeout_keeps_resumable_run_id(self):
        with self.assertRaisesRegex(runner.RunError, "not canceled"):
            runner.wait_for_run(self.client([]), "run_test", timeout=0)
        self.assertTrue((self.output / "run-id.json").exists())

    def test_invalid_run_id_cannot_change_the_api_path(self):
        os.environ["PROTOFACE_ACTION"] = "check_run"
        os.environ["PROTOFACE_RUN_ID"] = "run_/../../other"
        with self.assertRaisesRegex(runner.RunError, "valid Protoface run ID"):
            runner.execute(self.client([]))
        self.assertFalse(self.seen)


if __name__ == "__main__":
    unittest.main()
