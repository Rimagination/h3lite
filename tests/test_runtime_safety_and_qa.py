import copy
from argparse import Namespace
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class RuntimeSafetyTests(unittest.TestCase):
    def test_fp8_4b_encoder_is_a_valid_low_vram_role(self):
        from h3_doctor import model_report

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            encoder_dir = root / "models" / "text_encoders"
            encoder_dir.mkdir(parents=True)
            (encoder_dir / "qwen3vl_4b_fp8_scaled.safetensors").write_bytes(b"test")
            report = model_report(root)

        self.assertTrue(report["assets"]["low_vram_text_encoder"]["present"])

    def test_optional_acceleration_nodes_do_not_block_compatibility_workflow(self):
        from h3_preflight import assess_runtime_risk

        report = {
            "gpus": [{"name": "RTX 4060 Ti", "vram_total_gb": 16.0, "vram_free_gb": 8.0}],
            "system_memory": {"total_gb": 32.0, "available_gb": 16.0, "page_file_available_gb": 16.0},
            "disk": {"free_gb": 100.0},
            "recommendation": {"name": "w4a8-high"},
            "models": {"available": True, "assets": {}},
            "custom_nodes": {"available": True, "nodes": {
                "clipproj_node": {"present": True},
                "sol_attention": {"present": False},
                "block_cache": {"present": False},
            }},
        }

        result = assess_runtime_risk(report)

        self.assertNotEqual(result["status"], "blocked")
        self.assertTrue(any("compatibility workflow" in item for item in result["warnings"]))

    def test_16gb_with_32gb_ram_starts_from_w4a8(self):
        from h3_doctor import choose_profile

        result = choose_profile(
            [{"name": "RTX 4060 Ti", "vram_total_gb": 16.0}],
            {"total_gb": 32.0},
            {"free_gb": 100.0},
        )

        self.assertEqual(result["name"], "w4a8-high")

    def test_6gb_with_32gb_ram_is_caution_not_blocked(self):
        from h3_preflight import assess_runtime_risk

        report = {
            "gpus": [{"name": "RTX 3060 Laptop GPU", "vram_total_gb": 6.0, "vram_free_gb": 2.0}],
            "system_memory": {
                "total_gb": 32.0,
                "available_gb": 12.0,
                "page_file_available_gb": 16.0,
            },
            "disk": {"free_gb": 100.0},
            "recommendation": {"name": "experimental-6gb"},
        }

        result = assess_runtime_risk(report)

        self.assertEqual(result["status"], "caution")
        self.assertTrue(any("experimental" in item for item in result["warnings"]))

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

    def test_model_resolution_switches_only_as_a_complete_registered_set(self):
        from h3_generate import resolve_model_overrides

        workflow = {
            "unet": {"inputs": {"unet_name": "missing-a.safetensors"}},
            "clip": {"inputs": {"clip_name": "missing-b.safetensors"}},
            "lora": {"inputs": {"lora_name": "missing-c.safetensors"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / "models"
            model_dir.mkdir()
            names = (
                "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
                "qwen3vl_4b_fp8_scaled.safetensors",
                "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors",
            )
            for name in names:
                (model_dir / name).write_bytes(b"test")
            overrides = resolve_model_overrides(workflow, root)

        self.assertEqual(overrides["component_set"], "portable-16gb-b")
        self.assertEqual(workflow["clip"]["inputs"]["clip_name"], names[1])

    def test_partial_component_set_is_rejected(self):
        from h3_generate import resolve_model_overrides

        workflow = {
            "unet": {"inputs": {"unet_name": "missing-a.safetensors"}},
            "clip": {"inputs": {"clip_name": "missing-b.safetensors"}},
            "lora": {"inputs": {"lora_name": "missing-c.safetensors"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / "models"
            model_dir.mkdir()
            (model_dir / "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors").write_bytes(b"test")
            with self.assertRaisesRegex(RuntimeError, "no complete registered component set"):
                resolve_model_overrides(workflow, root)

    def test_component_integrity_is_hashed_once_then_cached(self):
        import h3_generate

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / "models"
            model_dir.mkdir()
            payloads = {"a.safetensors": b"alpha", "b.safetensors": b"beta"}
            requirements = {
                name: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                for name, payload in payloads.items()
            }
            for name, payload in payloads.items():
                (model_dir / name).write_bytes(payload)
            with patch.dict(h3_generate.COMPONENT_INTEGRITY, {"test-set": requirements}, clear=False):
                first = h3_generate.verify_component_integrity(root, "test-set")
                second = h3_generate.verify_component_integrity(root, "test-set")

        self.assertTrue(first["verified"])
        self.assertTrue(all(not item["cache_reused"] for item in first["files"]))
        self.assertTrue(all(item["cache_reused"] for item in second["files"]))

    def test_explicit_component_set_wins_when_multiple_sets_are_installed(self):
        from h3_generate import resolve_model_overrides

        workflow = {
            "unet": {"inputs": {"unet_name": "missing-a.safetensors"}},
            "clip": {"inputs": {"clip_name": "missing-b.safetensors"}},
            "lora": {"inputs": {"lora_name": "missing-c.safetensors"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / "models"
            model_dir.mkdir(parents=True)
            names = (
                "minimax_h3_fl2va_pruned_w4a8_mixed_ax1y2jp.safetensors",
                "qwen3vl_4b_int4_convrot.safetensors",
                "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors",
                "minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
                "qwen3vl_4b_fp8_scaled.safetensors",
                "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_resized_avg_rank_21_bf16.safetensors",
            )
            for name in names:
                (model_dir / name).write_bytes(b"test")

            with self.assertRaisesRegex(RuntimeError, "multiple registered component sets"):
                resolve_model_overrides(workflow, root)

            overrides = resolve_model_overrides(workflow, root, "B")

        self.assertEqual(overrides["component_set"], "portable-16gb-b")
        self.assertEqual(workflow["unet"]["inputs"]["unet_name"], names[3])

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

    def test_ffprobe_falls_back_to_comfyui_directory(self):
        from h3_generate import _resolve_ffprobe

        with tempfile.TemporaryDirectory() as directory:
            comfyui = Path(directory)
            bundled = comfyui / "ffprobe.exe"
            bundled.write_bytes(b"placeholder")
            with patch("h3_generate.shutil.which", return_value=None):
                resolved = _resolve_ffprobe(comfyui)

        self.assertEqual(resolved, str(bundled))

    def test_media_verification_reports_missing_ffprobe(self):
        from h3_generate import verify_outputs

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"placeholder")
            with patch("h3_generate._resolve_ffprobe", return_value=None), patch("h3_generate.ffprobe", return_value=None):
                result = verify_outputs([path], comfyui=Path(directory))

        self.assertFalse(result[0]["verified"])
        self.assertEqual(result[0]["verification_error"], "ffprobe_not_found")

    def test_media_verification_passes_comfyui_to_ffprobe(self):
        from h3_generate import verify_outputs

        with tempfile.TemporaryDirectory() as directory:
            comfyui = Path(directory)
            path = comfyui / "output" / "clip.mp4"
            path.parent.mkdir()
            path.write_bytes(b"placeholder")
            with patch("h3_generate.ffprobe", return_value={"streams": [], "format": {}}) as probe:
                verify_outputs([path], comfyui=comfyui)

        probe.assert_called_once_with(path, comfyui)

    def test_compact_status_keeps_verifier_error(self):
        from h3_status import compact_result

        result = compact_result(
            {
                "ok": False,
                "state": "verification_failed",
                "outputs": [{"path": "clip.mp4", "verified": False, "verification_error": "ffprobe_not_found"}],
            }
        )

        self.assertEqual(result["outputs"][0]["verification_error"], "ffprobe_not_found")

    def test_standalone_status_infers_comfyui_from_output_directory(self):
        from h3_status import status_once

        with tempfile.TemporaryDirectory() as directory:
            comfyui = Path(directory) / "ComfyUI"
            output_dir = comfyui / "output"
            output_dir.mkdir(parents=True)
            args = Namespace(
                prompt_id="prompt-123",
                base_url="http://127.0.0.1:8188",
                output_dir=str(output_dir),
                comfyui=None,
                run_manifest=None,
                run_root=str(comfyui / "user" / "h3lite_runs"),
                expected_duration=None,
                expected_frames=None,
                expected_fps=None,
                require_audio=False,
                dynamic_check=False,
            )
            record = {"status": {"completed": True}}
            outputs = [{"path": str(output_dir / "clip.mp4"), "verified": True}]
            with (
                patch("h3_status.json_request", return_value={args.prompt_id: record}),
                patch("h3_status.history_record", return_value=record),
                patch("h3_status.execution_error", return_value=None),
                patch("h3_status.execution_elapsed_seconds", return_value=1.0),
                patch("h3_status.resolve_output_paths", return_value=[output_dir / "clip.mp4"]),
                patch("h3_status.verify_outputs", return_value=outputs) as verify,
                patch("h3_status.record_timing_sample"),
            ):
                result = status_once(args)

        self.assertTrue(result["ok"])
        self.assertEqual(verify.call_args.kwargs["comfyui"], comfyui.resolve())

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

    def test_rgb_qa_rejects_colored_mosaic_but_accepts_coherent_frames(self):
        from h3_status import analyze_rgb_frame_samples

        size = 8
        mosaic = []
        colors = ((255, 0, 255), (0, 255, 0), (0, 0, 0), (255, 255, 255))
        for y in range(size):
            for x in range(size):
                mosaic.extend(colors[(x + y) % len(colors)])
        coherent = bytes([120, 130, 125]) * (size * size)

        self.assertEqual(
            analyze_rgb_frame_samples([bytes(mosaic)] * 3, size=size)["classification"],
            "suspected_mosaic",
        )
        self.assertEqual(
            analyze_rgb_frame_samples([coherent] * 3, size=size)["classification"],
            "coherent_color",
        )

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


class FastPathContractTests(unittest.TestCase):
    def test_fastpath_uses_h3_route_labels_for_planner(self):
        from h3_fastpath import REFERENCE_MODE_LABELS

        self.assertEqual(REFERENCE_MODE_LABELS["t2v"], "T2VA")
        self.assertEqual(REFERENCE_MODE_LABELS["i2va"], "I2VA")

    def test_auto_workflow_falls_back_without_optional_nodes(self):
        from h3_fastpath import select_workflow_template

        doctor = {"custom_nodes": {"nodes": {"sol_attention": {"present": False}, "block_cache": {"present": False}}}}
        self.assertEqual(select_workflow_template("auto", doctor), "h3_w4a8_t2v_compat")
        doctor["custom_nodes"]["nodes"]["sol_attention"]["present"] = True
        doctor["custom_nodes"]["nodes"]["block_cache"]["present"] = True
        doctor["custom_nodes"]["nodes"]["h3_turbo"] = {"present": True}
        doctor["custom_nodes"]["nodes"]["sage_attention"] = {"present": True}
        self.assertEqual(select_workflow_template("auto", doctor), "h3_w4a8_t2v")

    def test_loaded_object_info_controls_accelerated_route(self):
        from h3_fastpath import select_workflow_template

        classes = {
            "MiniMaxH3MemoryEfficientSolAttentionPatch": {},
            "MiniMaxH3MemoryEfficientSageAttentionPatch": {},
            "MiniMaxH3ChunkFeedForward": {},
            "MiniMaxH3BlockCacheT8": {},
        }
        doctor = {"runtime_capabilities": {"object_info": classes}}
        self.assertEqual(select_workflow_template("auto", doctor), "h3_w4a8_t2v")
        del classes["MiniMaxH3BlockCacheT8"]
        self.assertEqual(select_workflow_template("auto", doctor), "h3_w4a8_t2v_compat")
        self.assertEqual(
            select_workflow_template("auto", {"runtime_capabilities": {"object_info": None}}),
            "h3_w4a8_t2v_compat",
        )

    def test_set_b_auto_uses_compatibility_route(self):
        from h3_fastpath import select_workflow_template

        classes = {
            "MiniMaxH3MemoryEfficientSolAttentionPatch": {},
            "MiniMaxH3MemoryEfficientSageAttentionPatch": {},
            "MiniMaxH3ChunkFeedForward": {},
            "MiniMaxH3BlockCacheT8": {},
        }
        doctor = {"runtime_capabilities": {"object_info": classes}}
        self.assertEqual(
            select_workflow_template("auto", doctor, component_set="portable-16gb-b"),
            "h3_w4a8_t2v_compat",
        )

    def test_generate_command_keeps_custom_comfyui_when_run_root_is_elsewhere(self):
        from h3_fastpath import build_generate_command

        command = build_generate_command(
            scripts_dir=SCRIPTS,
            prompt_file=Path("E:/runs/prompt.txt"),
            output_dir=Path("F:/MiniMax-H3/ComfyUI/output"),
            comfyui=Path("F:/MiniMax-H3/ComfyUI"),
            filename_prefix="video/test",
            run_root=Path("E:/runs"),
            profile="fast",
            resolution="640x352",
            length=124,
            steps=4,
            fps=24,
            audio_policy="auto",
        )

        comfyui_index = command.index("--comfyui")
        self.assertEqual(command[comfyui_index + 1], "F:\\MiniMax-H3\\ComfyUI")
        self.assertNotEqual(command[comfyui_index + 1], "E:")
        self.assertIn("--component-set", command)

    def test_fresh_environment_cache_is_reused_but_stale_cache_requires_doctor(self):
        from h3_fastpath import cache_is_fresh, cache_policy

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "doctor.json"
            cache.write_text('{"recommendation":{"name":"low-vram-w4a8"}}', encoding="utf-8")
            now = cache.stat().st_mtime

            self.assertTrue(cache_is_fresh(cache, now=now + 60, max_age_seconds=1800))
            self.assertEqual(cache_policy(cache, now=now + 60), "reuse")
            self.assertFalse(cache_is_fresh(cache, now=now + 1801, max_age_seconds=1800))
            self.assertEqual(cache_policy(cache, now=now + 1801), "doctor")

    def test_status_command_is_one_bounded_watch_instead_of_repeated_one_shot_polls(self):
        from h3_fastpath import build_status_command

        command = build_status_command(
            scripts_dir=SCRIPTS,
            base_url="http://127.0.0.1:8188",
            prompt_id="prompt-123",
            comfyui=Path("F:/MiniMax-H3/ComfyUI"),
            output_dir=Path("F:/MiniMax-H3/ComfyUI/output"),
            run_root=Path("F:/MiniMax-H3/ComfyUI/user/h3lite_runs"),
        )
        self.assertEqual(command.count("--watch"), 1)
        self.assertIn("--watch-interval", command)
        self.assertIn("20", command)
        self.assertIn("--watch-timeout", command)
        self.assertIn("3600", command)
        self.assertIn("--comfyui", command)
        self.assertIn("F:\\MiniMax-H3\\ComfyUI", command)
        self.assertNotIn("--verbose", command)

    def test_skill_documents_the_single_entry_hot_path(self):
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("h3_fastpath.py", skill)
        self.assertIn("Do not issue repeated one-shot status calls", skill)

    def test_skill_documents_bundled_ffprobe_recovery(self):
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("ffprobe_not_found", skill)
        self.assertIn("H3LITE_FFPROBE", skill)
        self.assertIn("exactly `<ComfyUI>\\output`", skill)


class CleanupSafetyTests(unittest.TestCase):
    def test_cleanup_is_dry_run_first_and_preserves_special_directories(self):
        from h3_cleanup import apply_cleanup, cleanup_plan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "20260101T000000Z_old"
            recent = root / "20260813T000000Z_recent"
            environment = root / "_environment"
            for path in (old, recent, environment):
                path.mkdir()
                (path / "manifest.json").write_text("{}", encoding="utf-8")

            plan = cleanup_plan(
                root,
                older_than_days=30,
                keep_last=1,
                now=datetime(2026, 8, 14, tzinfo=timezone.utc),
            )

            self.assertTrue(plan["dry_run"])
            self.assertTrue(old.exists())
            self.assertEqual([Path(item["path"]).name for item in plan["eligible"]], [old.name])
            self.assertIn("_environment", plan["ignored"])

            result = apply_cleanup(plan)
            self.assertFalse(result["dry_run"])
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(environment.exists())

    def test_cleanup_rejects_a_target_outside_run_root(self):
        from h3_cleanup import apply_cleanup

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "runs"
            root.mkdir()
            outside = Path(directory) / "20260101T000000Z_outside"
            outside.mkdir()
            plan = {"run_root": str(root), "eligible": [{"path": str(outside)}]}

            with self.assertRaises(ValueError):
                apply_cleanup(plan)


if __name__ == "__main__":
    unittest.main()
