import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class AnchorWorkflowTests(unittest.TestCase):
    def test_i2va_anchor_sheet_records_reference_and_continuity_signals(self):
        from h3_anchor import anchor_summary, build_anchor_sheet

        sheet = build_anchor_sheet(
            "[Shot 1] Keep the same face, hair, clothing, and markings. [Shot 2] Camera cuts to a reverse angle.",
            {
                "mode": "i2va",
                "inputs": {
                    "first_frame": {
                        "source": "C:/refs/hero.png",
                        "input_name": "hero.png",
                        "sha256": "abc123",
                    }
                },
            },
            reference_mode="i2va",
            first_frame="C:/refs/hero.png",
            settings={"width": 640, "height": 352},
        )

        self.assertEqual(sheet["reference_mode"], "I2VA")
        self.assertTrue(sheet["identity_sensitive"])
        self.assertTrue(sheet["multi_shot"])
        self.assertEqual(sheet["references"][0]["role"], "first_frame")
        self.assertEqual(sheet["references"][0]["input_name"], "hero.png")
        self.assertTrue(anchor_summary(sheet)["manual_review_required"])

    def test_explicit_declaration_is_kept_without_prompt_inference(self):
        from h3_anchor import build_anchor_sheet

        with tempfile.TemporaryDirectory() as directory:
            declaration = Path(directory) / "anchors.json"
            declaration.write_text(json.dumps({"character_id": "cow-a", "allow": ["tail wag"]}), encoding="utf-8")
            sheet = build_anchor_sheet(
                "A quiet shot.",
                reference_mode="t2v",
                anchor_file=declaration,
            )

        self.assertEqual(sheet["declared"]["character_id"], "cow-a")
        self.assertFalse(sheet["identity_sensitive"])
        self.assertEqual(len(sheet["prompt_sha256"]), 64)

    def test_summary_is_small_and_json_serializable(self):
        from h3_anchor import anchor_summary, build_anchor_sheet

        summary = anchor_summary(build_anchor_sheet("same character, same wardrobe", reference_mode="t2v"))
        self.assertEqual(summary["reference_count"], 0)
        self.assertTrue(summary["identity_sensitive"])
        json.dumps(summary, ensure_ascii=False)

    def test_anchor_qa_is_advisory_and_does_not_claim_face_recognition(self):
        import h3_status

        frames = {0.0: b"\x00" * 4096, 0.5: b"\x01" * 4096, 0.95: b"\x02" * 4096}

        def fake_extract(_path, timestamp, size=64):
            return frames.get(round(timestamp, 2), frames[0.0])

        with patch.object(h3_status, "extract_gray_frame", side_effect=fake_extract):
            report = h3_status.anchor_consistency_quality(
                Path("output.mp4"),
                1.0,
                {"identity_sensitive": True, "multi_shot": False, "references": []},
            )

        self.assertEqual(report["classification"], "advisory_anchor_check")
        self.assertEqual(report["acceptance"], "manual_review")
        self.assertIn("not face recognition", report["note"])


if __name__ == "__main__":
    unittest.main()
