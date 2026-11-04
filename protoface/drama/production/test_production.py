import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from jsonschema import ValidationError

spec=importlib.util.spec_from_file_location("drama_generator",Path(__file__).with_name("generate.py"))
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/"checkpoint/clips").mkdir(parents=True)
        (self.root/"reference.jpg").write_bytes(b"test reference")
        self.enterContext(patch.object(g,"ROOT",self.root))
        self.enterContext(patch.object(g,"STATE",self.root/"checkpoint"))
        self.enterContext(patch.dict(os.environ,{},clear=True))
        self.shot={"id":"ep04-001","image":"reference.jpg","duration":2,"generation_prompt":"a controlled head turn"}
        self.schema={"type":"object","additionalProperties":False,"properties":{
            "first_frame":{"type":"string"},"prompt":{"type":"string"},
            "duration_seconds":{"type":"integer","minimum":4,"maximum":15},
            "quality":{"enum":["480p","768p"]},"aspect_ratio":{"enum":["16:9"]},
            "generate_audio":{"type":"boolean"}}}

    def test_two_second_edit_uses_live_four_second_minimum(self):
        p=g.payload_for(self.shot,self.schema,"480p")
        self.assertEqual(p["duration_seconds"],4)
        self.assertTrue(p["first_frame"].startswith("data:image/jpeg;base64,"))
        self.assertFalse(p["generate_audio"])

    def test_duration_enum_chooses_shortest_supported_value(self):
        self.schema["properties"]["duration_seconds"]={"enum":[5,10]}
        self.assertEqual(g.generation_duration(self.schema,2),5)

    def test_unsupported_image_contract_stops_before_a_request(self):
        del self.schema["properties"]["first_frame"]
        with self.assertRaisesRegex(ValueError,"input contract changed"):
            g.payload_for(self.shot,self.schema,"480p")

    def test_invalid_quality_is_rejected_locally(self):
        with self.assertRaises(ValidationError): g.payload_for(self.shot,self.schema,"unavailable-quality")

    def test_rerun_idempotency_is_stable_and_new_workflow_is_distinct(self):
        p=g.payload_for(self.shot,self.schema,"480p")
        self.assertEqual(g.idempotency_key("123","ep04-001",p),g.idempotency_key("123","ep04-001",p))
        self.assertNotEqual(g.idempotency_key("123","ep04-001",p),g.idempotency_key("456","ep04-001",p))

    def test_completed_checkpoint_skips_submission_and_download(self):
        payload=g.payload_for(self.shot,self.schema,"480p")
        (g.STATE/"ep04-001.json").write_text(json.dumps({
            "idempotency_key":g.idempotency_key("123","ep04-001",payload),
            "run_id":"run_existing","status":"completed"}))
        (g.STATE/"clips/ep04-001.mp4").write_bytes(b"previously validated video")
        with patch.object(g,"request") as request:
            g.one_shot(None,self.shot,payload,"123")
        request.assert_not_called()

    def test_accepted_checkpoint_resumes_without_post(self):
        payload=g.payload_for(self.shot,self.schema,"480p")
        (g.STATE/"ep04-001.json").write_text(json.dumps({
            "idempotency_key":g.idempotency_key("123","ep04-001",payload),
            "run_id":"run_existing","status":"running"}))
        with patch.object(g,"request",side_effect=[{"status":"completed"},
             {"status":"completed","video":{"url":"https://media.example/video.mp4"}}]) as req:
            with patch.object(g,"download_video") as download:
                g.one_shot(None,self.shot,payload,"123")
        self.assertTrue(all(call.args[1]=="GET" for call in req.call_args_list))
        download.assert_called_once()

    def test_failed_run_is_never_replaced(self):
        payload=g.payload_for(self.shot,self.schema,"480p")
        with patch.object(g,"request",side_effect=[{"id":"run_test","status":"queued"},{"status":"failed"}]) as req:
            with self.assertRaisesRegex(RuntimeError,"no replacement"):
                g.one_shot(None,self.shot,payload,"123")
        self.assertEqual(sum(call.args[1]=="POST" for call in req.call_args_list),1)
        state=json.loads((g.STATE/"ep04-001.json").read_text())
        self.assertEqual(state["run_id"],"run_test")

    def test_submission_timeout_has_no_automatic_retry(self):
        payload=g.payload_for(self.shot,self.schema,"480p")
        with patch.object(g,"request",side_effect=httpx.ReadTimeout("timed out")) as req:
            with self.assertRaises(httpx.ReadTimeout): g.one_shot(None,self.shot,payload,"123")
        self.assertEqual(req.call_count,1)
        self.assertTrue((g.STATE/"ep04-001.json").exists())

    def test_no_approval_makes_no_api_calls(self):
        with patch.object(g,"request") as req:
            with self.assertRaisesRegex(RuntimeError,"confirm_spend"): g.generate()
        req.assert_not_called()


if __name__=="__main__": unittest.main()
