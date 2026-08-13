import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class RuntimeSafetyTests(unittest.TestCase):
    def test_low_available_memory_is_a_warning_not_an_automatic_block(self):
        from h3_preflight import assess_runtime_risk

        report = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0, "vram_free_gb": 1.29}],
            "system_memory": {
                "total_gb": 32.0,
                "available_gb": 3.69,
                "page_file_available_gb": 8.0,
            },
            "disk": {"free_gb": 100.0},
            "recommendation": {"name": "low-vram-w4a8"},
            "models": {"available": True, "assets": {}},
            "custom_nodes": {"available": True, "nodes": {}},
        }

        result = assess_runtime_risk(report)

        self.assertEqual(result["status"], "caution")
        self.assertTrue(any("RAM" in item for item in result["warnings"]))

    def test_critically_low_pagefile_blocks_long_generation(self):
        from h3_preflight import assess_runtime_risk

        report = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0, "vram_free_gb": 1.0}],
            "system_memory": {
                "total_gb": 32.0,
                "available_gb": 3.0,
                "page_file_available_gb": 0.5,
            },
            "disk": {"free_gb": 100.0},
            "recommendation": {"name": "low-vram-w4a8"},
        }

        result = assess_runtime_risk(report)

        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("page" in item.lower() for item in result["errors"]))

    def test_runtime_refresh_does_not_discard_cached_asset_scan(self):
        from h3_preflight import refresh_runtime

        report = {
            "root": ".",
            "gpus": [{"name": "old", "vram_total_gb": 8.0}],
            "gpu_processes": [],
            "system_memory": {"total_gb": 32.0},
            "disk": {"free_gb": 100.0},
            "models": {"available": True, "assets": {"sentinel": {"present": True}}},
            "custom_nodes": {"available": True, "nodes": {"sentinel": {"present": True}}},
        }
        with patch("h3_doctor.nvidia_gpus", return_value=[{"name": "new", "vram_total_gb": 8.0}]), patch(
            "h3_doctor.nvidia_processes", return_value=[]
        ), patch("h3_doctor.system_memory", return_value={"total_gb": 32.0, "available_gb": 16.0, "page_file_available_gb": 16.0}), patch(
            "h3_doctor.path_disk", return_value={"free_gb": 100.0}
        ):
            refreshed = refresh_runtime(report)

        self.assertEqual(refreshed["gpus"][0]["name"], "new")
        self.assertIn("sentinel", refreshed["models"]["assets"])
        self.assertIn("sentinel", refreshed["custom_nodes"]["nodes"])

    def test_python_comfyui_process_is_not_reported_as_external_gpu_competitor(self):
        from h3_preflight import assess_runtime_risk

        report = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0, "vram_free_gb": 2.0}],
            "system_memory": {"total_gb": 32.0, "available_gb": 16.0, "page_file_available_gb": 16.0},
            "disk": {"free_gb": 100.0},
            "recommendation": {"name": "low-vram-w4a8"},
            "gpu_processes": [{"pid": "123", "process_name": "python.exe", "used_gpu_memory_mb": None}],
        }

        result = assess_runtime_risk(report)

        self.assertFalse(any("GPU compute process" in item for item in result["warnings"]))


class SubmissionContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = {
            "sampler": {"inputs": {"steps": 4}, "class_type": "BasicScheduler"},
            "audio_vae": {"inputs": {"samples": ["sampler", 0]}, "class_type": "VAEDecodeAudio"},
            "save": {"inputs": {"images": ["video", 0], "audio": ["audio_vae", 0]}, "class_type": "CreateVideo"},
        }

    def test_no_dialogue_keeps_native_audio_but_complete_silence_disables_it(self):
        from h3_generate import apply_audio_policy

        keep = copy.deepcopy(self.workflow)
        self.assertEqual(apply_audio_policy(keep, "No dialogue, keep rain and page-turn sounds.", "auto"), "require")
        self.assertIn("audio", keep["save"]["inputs"])

        mute = copy.deepcopy(self.workflow)
        self.assertEqual(apply_audio_policy(mute, "Complete silence, no audio.", "auto"), "disable")
        self.assertNotIn("audio", mute["save"]["inputs"])

    def test_config_fingerprint_is_stable_and_changes_with_prompt(self):
        from h3_generate import config_fingerprint

        first = config_fingerprint(self.workflow, "a prompt")
        same = config_fingerprint(copy.deepcopy(self.workflow), "a prompt")
        changed = config_fingerprint(self.workflow, "a different prompt")

        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first), 64)

    def test_active_manifest_is_detected_but_completed_manifest_is_reusable(self):
        from h3_generate import active_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active_dir = root / "active"
            active_dir.mkdir()
            active_manifest_path = active_dir / "manifest.json"
            active_manifest_path.write_text(
                '{"state":"queued","prompt_id":"abc","config_fingerprint":"fingerprint"}',
                encoding="utf-8",
            )
            found = active_manifest(root, "fingerprint")
            self.assertEqual(found["prompt_id"], "abc")

            active_manifest_path.write_text(
                '{"state":"success","prompt_id":"abc","config_fingerprint":"fingerprint"}',
                encoding="utf-8",
            )
            self.assertIsNone(active_manifest(root, "fingerprint"))

    def test_submission_claim_is_atomic(self):
        from h3_generate import acquire_submission_claim, release_submission_claim

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claim = acquire_submission_claim(root, "fingerprint")
            self.assertIsNotNone(claim)
            with self.assertRaises(RuntimeError):
                acquire_submission_claim(root, "fingerprint")
            release_submission_claim(claim)
            self.assertIsNotNone(acquire_submission_claim(root, "fingerprint"))

    def test_media_verification_checks_duration_frames_fps_and_audio(self):
        from h3_generate import verify_outputs

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"placeholder")
            probe = {
                "streams": [
                    {"codec_type": "video", "width": 640, "height": 352, "nb_frames": "124", "avg_frame_rate": "24/1"},
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
                "format": {"duration": "5.167"},
            }
            with patch("h3_generate.ffprobe", return_value=probe):
                result = verify_outputs(path_list := [path], expected_duration=124 / 24, expected_frames=124, expected_fps=24, require_audio=True)

            self.assertEqual(len(result), 1)
            self.assertTrue(result[0]["verified"])

    def test_empirical_timing_is_recorded_and_reused_by_planner(self):
        from h3_plan import build_plan, record_timing_sample

        report = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0}],
            "system_memory": {"total_gb": 32.0},
            "recommendation": {"name": "low-vram-w4a8"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "run"
            run_dir.mkdir()
            manifest = run_dir / "manifest.json"
            manifest.write_text(
                '{"state":"success","profile":"fast","effective_settings":'
                '{"width":864,"height":480,"length":124,"fps":24,"steps":4},'
                '"elapsed_seconds":345.0}',
                encoding="utf-8",
            )
            record_timing_sample(root, manifest, 345.0)
            record_timing_sample(root, manifest, 345.0)
            timing = json.loads((root / "_environment" / "timing.json").read_text(encoding="utf-8"))
            self.assertEqual(
                timing["entries"]["fast|864x480|124|24|4"]["samples_seconds"],
                [345.0],
            )
            plan = build_plan(report, resolution="864x480", timing_file=root / "_environment" / "timing.json")

        self.assertEqual(plan["estimate"]["source"], "empirical")
        self.assertEqual(plan["estimate"]["sample_count"], 1)
        self.assertLess(plan["estimate"]["upper_seconds"], 600)

    def test_explicit_resolution_does_not_request_a_second_confirmation(self):
        from h3_plan import build_plan

        report = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0}],
            "system_memory": {"total_gb": 32.0},
            "recommendation": {"name": "low-vram-w4a8"},
        }

        plan = build_plan(report, resolution="864x480")

        self.assertTrue(plan["decision"]["explicit_resolution"])
        self.assertFalse(plan["decision"]["confirmation_required"])


class DynamicQualityTests(unittest.TestCase):
    def test_frame_delta_distinguishes_static_and_motion_samples(self):
        from h3_status import analyze_frame_samples

        static = [bytes([20]) * 64, bytes([20]) * 64, bytes([20]) * 64]
        motion = [bytes([20]) * 64, bytes([80]) * 64, bytes([140]) * 64]

        self.assertEqual(analyze_frame_samples(static)["classification"], "static_or_nearly_static")
        self.assertEqual(analyze_frame_samples(motion)["classification"], "dynamic")

    def test_pending_status_is_not_ok_and_compact_status_drops_history(self):
        from h3_status import compact_result

        result = compact_result(
            {
                "ok": True,
                "prompt_id": "abc",
                "state": "running_or_queued",
                "status": {"messages": ["large history"]},
                "history": {"prompt": {"very": "large"}},
            }
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertNotIn("history", result)


if __name__ == "__main__":
    unittest.main()
