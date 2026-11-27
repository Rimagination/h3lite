import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "qoder-plugin"
    / "skills"
    / "h3-generate"
    / "scripts"
)


def load_script(name: str):
    path = SKILL_SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


regional = load_script("h3_prepare_regional_workflow.py")
subject_map = load_script("h3_validate_subject_map.py")


class RegionalWorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base_path = self.root / "accepted_workflow.json"
        self.plan_path = self.root / "regional_plan.json"
        self.output_path = self.root / "candidate_workflow.json"
        self.report_path = self.root / "qa" / "workflow_validation.json"
        self.base = {
            "9": {"class_type": "LoadVideo", "inputs": {"file": "old_guide.mp4"}},
            "10": {"class_type": "DWPose", "inputs": {"image": ["24", 0]}},
            "11": {"class_type": "BFSH3ImageScale", "inputs": {"output_scale": 1.0, "max_megapixels": 0.4}},
            "21": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "old"}},
            "23": {"class_type": "LoadVideo", "inputs": {"file": "old_map.mp4"}},
            "24": {"class_type": "DWPose", "inputs": {"image": ["9", 0]}},
            "25": {
                "class_type": "BFSH3RegionalReferenceAttention",
                "inputs": {
                    "guide": ["10", 0],
                    "subject_map": ["24", 0],
                    "routing": "soft",
                    "tracking": "propagate",
                    "isolation": "people",
                },
            },
        }
        self.plan = {
            "allow_changed_nodes": ["9", "11", "21", "23"],
            "set": {
                "9": {"inputs": {"file": "guide.mp4"}},
                "11": {"inputs": {"output_scale": 2.0, "max_megapixels": 1.1}},
                "21": {"inputs": {"filename_prefix": "community_tests/remake_v24"}},
                "23": {"inputs": {"file": "subject_map.mp4"}},
            },
            "require_classes": {"25": "BFSH3RegionalReferenceAttention"},
            "require_values": {
                "25.inputs.routing": "soft",
                "25.inputs.tracking": "propagate",
                "25.inputs.isolation": "people",
            },
            "require_links": {
                "25.inputs.guide": ["10", 0],
                "25.inputs.subject_map": ["24", 0],
            },
            "geometry": {
                "source_width": 672,
                "source_height": 384,
                "output_scale": 2.0,
                "max_megapixels": 1.1,
                "expected_width": 1344,
                "expected_height": 768,
            },
        }
        self.write_inputs()

    def write_inputs(self):
        self.base_path.write_text(json.dumps(self.base), encoding="utf-8")
        self.plan_path.write_text(json.dumps(self.plan), encoding="utf-8")

    def run_prepare(self, *, overwrite=False):
        return regional.prepare(
            argparse.Namespace(
                base=str(self.base_path),
                plan=str(self.plan_path),
                output=str(self.output_path),
                report=str(self.report_path),
                overwrite=overwrite,
            )
        )

    def test_minimal_change_contract_writes_candidate_and_report(self):
        report, code = self.run_prepare()

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["changed_nodes"], ["9", "11", "21", "23"])
        self.assertEqual(report["geometry"]["actual"], [1344, 768])
        self.assertTrue(report["geometry"]["passed"])
        self.assertTrue(self.output_path.is_file())
        self.assertEqual(
            hashlib.sha256(self.output_path.read_bytes()).hexdigest(),
            report["output_sha256"],
        )
        self.assertTrue(self.report_path.is_file())
        self.assertEqual(json.loads(self.report_path.read_text(encoding="utf-8"))["status"], "passed")

    def test_extra_changed_node_fails_without_writing_candidate(self):
        self.plan["set"]["10"] = {"inputs": {"detector": "rtmpose"}}
        self.write_inputs()

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertEqual(report["unexpected_changed_nodes"], ["10"])
        self.assertFalse(self.output_path.exists())
        self.assertTrue(self.report_path.is_file())

    def test_missing_link_target_fails_without_writing_candidate(self):
        self.base["25"]["inputs"]["subject_map"] = ["999", 0]
        self.write_inputs()

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertTrue(any("missing node 999" in error for error in report["errors"]))
        self.assertFalse(self.output_path.exists())

    def test_reference_hash_mismatch_fails_without_writing_candidate(self):
        reference = self.root / "reference.bin"
        reference.write_bytes(b"actual reference")
        self.plan["reference_files"] = [
            {
                "path": reference.name,
                "sha256": hashlib.sha256(b"different reference").hexdigest(),
            }
        ]
        self.write_inputs()

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertTrue(any("reference SHA mismatch" in error for error in report["errors"]))
        self.assertFalse(report["references"][0]["passed"])
        self.assertFalse(self.output_path.exists())

    def test_geometry_mismatch_fails_without_writing_candidate(self):
        self.plan["geometry"]["expected_height"] = 800
        self.write_inputs()

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertFalse(report["geometry"]["passed"])
        self.assertFalse(self.output_path.exists())

    def test_missing_base_writes_failure_report(self):
        self.base_path.unlink()

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(self.report_path.is_file())
        self.assertFalse(self.output_path.exists())

    def test_existing_output_requires_overwrite(self):
        self.output_path.write_bytes(b"do not replace")

        report, code = self.run_prepare()

        self.assertEqual(code, 1)
        self.assertTrue(any("output already exists" in error for error in report["errors"]))
        self.assertEqual(self.output_path.read_bytes(), b"do not replace")


class SubjectMapValidationTests(unittest.TestCase):
    def test_exact_hybrid_colors_are_detected(self):
        import numpy as np

        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        frame[:, :4] = subject_map.HYBRID_COLORS_RGB[0]
        frame[:, 4:] = subject_map.HYBRID_COLORS_RGB[1]

        detected, counts = subject_map.detect_frame_colors(frame)

        self.assertEqual(detected, [0, 1])
        self.assertEqual(counts[:2], [32, 32])

    def test_pure_primary_red_is_not_a_hybrid_subject_color(self):
        import numpy as np

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        frame[:] = (255, 0, 0)

        detected, counts = subject_map.detect_frame_colors(frame)

        self.assertEqual(detected, [])
        self.assertEqual(counts[0], 0)

    def test_unexpected_hybrid_color_is_visible_to_validator(self):
        import numpy as np

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        frame[:] = subject_map.HYBRID_COLORS_RGB[2]

        detected, _ = subject_map.detect_frame_colors(frame)

        self.assertEqual(detected, [2])

    def test_late_single_subject_sequence_matches_accepted_reference(self):
        metadata = {
            "width": 672,
            "height": 384,
            "fps": 24.0,
            "frames": 3,
            "duration": 0.125,
        }
        candidate = {
            "sequence": [[0, 1], [0], []],
            "counts_by_frame": [[100, 50], [12, 0], [0, 0]],
        }
        reference = {
            "sequence": [[0, 1], [0], []],
            "counts_by_frame": [[100, 50], [12, 0], [0, 0]],
        }
        args = argparse.Namespace(
            map=str(Path(__file__)),
            reference=str(Path(__file__)),
            guide=None,
            allowed_colors=(0, 1),
            color_distance=0.1,
            ffmpeg="ffmpeg",
            ffprobe="ffprobe",
            comfyui=None,
        )
        with (
            patch.object(subject_map, "find_tool", side_effect=lambda name, explicit, comfyui: name),
            patch.object(subject_map, "probe_video", return_value=metadata),
            patch.object(subject_map, "decode_color_sequence", side_effect=[candidate, reference]),
            patch.object(subject_map, "sha256_file", return_value="0" * 64),
        ):
            report, code = subject_map.analyse(args)

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["reference"]["sequence_equal"])
        self.assertEqual(report["empty_frames"], [2])

    def test_single_subject_map_fails_double_character_contract(self):
        metadata = {"width": 672, "height": 384, "fps": 24.0, "frames": 1, "duration": 0.041667}
        args = argparse.Namespace(
            map=str(Path(__file__)),
            reference=None,
            guide=None,
            allowed_colors=(0, 1),
            color_distance=0.1,
            ffmpeg="ffmpeg",
            ffprobe="ffprobe",
            comfyui=None,
        )
        decoded = {"sequence": [[0]], "counts_by_frame": [[100, 0, 0, 0, 0, 0]]}
        with (
            patch.object(subject_map, "find_tool", side_effect=lambda name, explicit, comfyui: name),
            patch.object(subject_map, "probe_video", return_value=metadata),
            patch.object(subject_map, "decode_color_sequence", return_value=decoded),
            patch.object(subject_map, "sha256_file", return_value="0" * 64),
        ):
            report, code = subject_map.analyse(args)

        self.assertEqual(code, 1)
        self.assertEqual(report["missing_allowed_colors"], [1])

    def test_empty_frames_require_an_accepted_reference(self):
        metadata = {"width": 672, "height": 384, "fps": 24.0, "frames": 2, "duration": 0.083333}
        args = argparse.Namespace(
            map=str(Path(__file__)),
            reference=None,
            guide=None,
            allowed_colors=(0, 1),
            color_distance=0.1,
            ffmpeg="ffmpeg",
            ffprobe="ffprobe",
            comfyui=None,
        )
        decoded = {"sequence": [[0, 1], []], "counts_by_frame": [[100, 50, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]]}
        with (
            patch.object(subject_map, "find_tool", side_effect=lambda name, explicit, comfyui: name),
            patch.object(subject_map, "probe_video", return_value=metadata),
            patch.object(subject_map, "decode_color_sequence", return_value=decoded),
            patch.object(subject_map, "sha256_file", return_value="0" * 64),
        ):
            report, code = subject_map.analyse(args)

        self.assertEqual(code, 1)
        self.assertTrue(any("require --reference" in error for error in report["errors"]))

    def test_json_report_contains_its_own_path(self):
        report = {
            "status": "passed",
            "decoded_frames": 107,
            "map": {"metadata": {"width": 672, "height": 384}},
            "errors": [],
            "warnings": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "qa" / "subject_map.json"
            args = argparse.Namespace(map="map.mp4", json=str(output))
            with (
                patch.object(subject_map, "analyse", return_value=(report, 0)),
                patch("builtins.print"),
            ):
                code = subject_map.main(["--map", "map.mp4", "--json", str(output)])
            saved = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(code, 0)
            self.assertEqual(saved["report_path"], str(output.resolve()))


if __name__ == "__main__":
    unittest.main()
