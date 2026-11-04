import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

spec=importlib.util.spec_from_file_location("ep01_produce",Path(__file__).with_name("produce.py"))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.enterContext(patch.object(p,"ROOT",self.root))
        self.enterContext(patch.object(p,"STATE",self.root/"checkpoint"))
        self.enterContext(patch.dict(os.environ,{},clear=True))
        self.manifest=json.loads(Path(__file__).with_name("episode.json").read_text())
        self.part=self.manifest["parts"][0]
        for panel in self.part["panels"]:
            image=self.root/panel["image"];image.parent.mkdir(parents=True,exist_ok=True);image.write_bytes(b"reference")
        self.schema={"type":"object","additionalProperties":False,"properties":{
            "prompt":{"type":"string"},"reference":{"type":"array","minItems":9,"maxItems":9,"items":{"type":"string"}},
            "duration_seconds":{"const":15},"aspect_ratio":{"const":"16:9"},"quality":{"enum":["480p","768p"]},
            "generate_audio":{"const":True},"enhance_prompt":{"const":False},
            "audio":{"type":"array","maxItems":3,"items":{"type":"string"}}}}

    def test_four_parts_nine_panels_and_exactly_sixty_seconds(self):
        self.assertEqual(len(self.manifest["parts"]),4)
        for part in self.manifest["parts"]:
            self.assertEqual(len(part["panels"]),9)
            self.assertAlmostEqual(part["panels"][-1]["end"],15)
        self.assertEqual(sum(x["duration"] for x in self.manifest["parts"]),60)

    def test_payload_has_nine_individual_references_and_preserves_native_audio(self):
        body=p.payload_for(self.manifest,self.part,self.schema,"768p")
        self.assertEqual(len(body["reference"]),9)
        self.assertEqual(body["duration_seconds"],15)
        self.assertTrue(body["generate_audio"])
        self.assertFalse(body["enhance_prompt"])
        self.assertNotIn("first_frame",body)

    def test_model_must_support_the_requested_audio_and_duration_contract(self):
        self.schema["properties"]["duration_seconds"]={"maximum":10}
        with self.assertRaises(ValidationError):p.payload_for(self.manifest,self.part,self.schema,"768p")

    def test_same_run_has_stable_key_and_a_new_run_is_distinct(self):
        body=p.payload_for(self.manifest,self.part,self.schema,"768p")
        self.assertEqual(p.identifier("123",1,body),p.identifier("123",1,body))
        self.assertNotEqual(p.identifier("123",1,body),p.identifier("456",1,body))

    def test_no_generation_authorization_makes_no_api_calls(self):
        with patch.object(p,"api") as request:
            with self.assertRaisesRegex(RuntimeError,"not enabled"):p.generate("generate_episode")
        request.assert_not_called()

    def test_script_has_seven_original_male_lines_and_six_knocks(self):
        self.assertEqual(len(self.manifest["dialogue"]),7)
        self.assertTrue(all(c["speaker"]=="沈照夜（男）" for c in self.manifest["dialogue"]))
        self.assertEqual(len(self.manifest["knocks"]),6)
        self.assertTrue(all(45<=t<60 for t in self.manifest["knocks"]))

    def test_codec_aligned_widescreen_is_accepted_but_portrait_is_rejected(self):
        probe={"streams":[{"codec_type":"video","width":1344,"height":768},{"codec_type":"audio"}],"format":{"duration":"15.083333"}}
        with patch.object(p.subprocess,"check_output",return_value=json.dumps(probe).encode()):
            p.inspect_clip(Path("test.mp4"))
        probe["streams"][0].update(width=832,height=480)
        with patch.object(p.subprocess,"check_output",return_value=json.dumps(probe).encode()):
            p.inspect_clip(Path("test.mp4"))
        probe["streams"][0].update(width=768,height=1344)
        with patch.object(p.subprocess,"check_output",return_value=json.dumps(probe).encode()):
            with self.assertRaisesRegex(ValueError,"widescreen"): p.inspect_clip(Path("test.mp4"))


if __name__=="__main__":unittest.main()
