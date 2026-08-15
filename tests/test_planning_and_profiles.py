import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class PlanningContractTests(unittest.TestCase):
    def setUp(self):
        self.report_8gb = {
            "gpus": [{"name": "RTX 4070 Laptop GPU", "vram_total_gb": 8.0}],
            "system_memory": {"total_gb": 32.0},
            "disk": {"free_gb": 100.0},
            "comfyui": {"path": r"F:\MiniMax-H3\ComfyUI"},
        }
        self.report_12gb = {
            "gpus": [{"name": "RTX 4080 Laptop GPU", "vram_total_gb": 12.0}],
            "system_memory": {"total_gb": 32.0},
            "disk": {"free_gb": 100.0},
            "comfyui": {"path": r"D:\AI\MiniMax-H3\ComfyUI"},
        }
        self.report_6gb = {
            "gpus": [{"name": "RTX 3060 Laptop GPU", "vram_total_gb": 6.0}],
            "system_memory": {"total_gb": 32.0},
            "disk": {"free_gb": 100.0},
            "comfyui": {"path": r"D:\AI\MiniMax-H3\ComfyUI"},
        }

    def test_default_auto_keeps_fast_low_vram_baseline(self):
        from h3_plan import build_plan

        plan = build_plan(self.report_8gb, mode="auto", target_minutes=None, aspect="landscape", video_seconds=5)
        self.assertEqual(plan["decision"]["mode"], "fast")
        self.assertEqual(plan["decision"]["resolution"], {"width": 640, "height": 352})
        self.assertEqual(plan["decision"]["steps"], 4)
        self.assertTrue(plan["decision"]["block_cache"])
        self.assertGreater(plan["estimate"]["upper_seconds"], plan["estimate"]["lower_seconds"])

    def test_6gb_is_experimental_fast_instead_of_automatically_blocked(self):
        from h3_plan import build_plan

        plan = build_plan(self.report_6gb, mode="auto", target_minutes=None, aspect="landscape", video_seconds=5)
        self.assertEqual(plan["hardware"]["tier"], "very-low")
        self.assertEqual(plan["decision"]["mode"], "fast")
        self.assertEqual(plan["decision"]["resolution"], {"width": 608, "height": 352})
        self.assertTrue(any("6 GB" in warning for warning in plan["warnings"]))

    def test_time_budget_can_select_higher_quality_when_safe(self):
        from h3_plan import build_plan

        plan = build_plan(self.report_8gb, mode="auto", target_minutes=12, aspect="landscape", video_seconds=5)
        self.assertIn(plan["decision"]["mode"], {"balanced", "quality"})
        self.assertFalse(plan["decision"]["block_cache"])
        self.assertGreaterEqual(plan["decision"]["steps"], 6)
        self.assertTrue(plan["decision"]["budget_fit"])

    def test_quality_mode_scales_resolution_with_vram(self):
        from h3_plan import build_plan

        low = build_plan(self.report_8gb, mode="quality", target_minutes=None, aspect="landscape", video_seconds=5)
        mid = build_plan(self.report_12gb, mode="quality", target_minutes=None, aspect="landscape", video_seconds=5)
        self.assertEqual(low["decision"]["resolution"], {"width": 640, "height": 352})
        self.assertEqual(mid["decision"]["resolution"], {"width": 960, "height": 544})
        self.assertTrue(any("VRAM" in warning for warning in low["warnings"]))

    def test_path_contract_is_explicit(self):
        from h3_plan import resolve_paths

        current = resolve_paths("current-project", workspace=r"F:\AI\AIVlog")
        self.assertEqual(current["comfyui"], r"F:\AI\AIVlog\.h3lite\ComfyUI")
        self.assertEqual(current["models"], r"F:\AI\AIVlog\.h3lite\ComfyUI\models")

        dedicated = resolve_paths("dedicated-folder", dedicated_folder=r"D:\AI\MiniMax-H3")
        self.assertEqual(dedicated["comfyui"], r"D:\AI\MiniMax-H3\ComfyUI")

        with self.assertRaises(ValueError):
            resolve_paths("reuse-existing")

    def test_launch_profile_uses_vram_tier_not_component_filename(self):
        from h3_plan import build_plan

        low = build_plan(self.report_8gb, mode="fast", aspect="landscape", video_seconds=5)
        high = build_plan(self.report_12gb, mode="fast", aspect="landscape", video_seconds=5)

        self.assertTrue(low["decision"]["launch_profile"]["lowvram"])
        self.assertFalse(high["decision"]["launch_profile"]["lowvram"])

    def test_plan_can_reuse_one_unambiguous_variant_timing_sample(self):
        from h3_plan import build_plan

        with tempfile.TemporaryDirectory() as tmp:
            timing_path = Path(tmp) / "timing.json"
            timing_path.write_text(json.dumps({
                "schema_version": 1,
                "entries": {
                    "quality|768x416|124|24|8|I2VA|lora=known;cache=0;sv=12;sa=3": {
                        "samples_seconds": [451.84, 526.47]
                    }
                }
            }), encoding="utf-8")
            plan = build_plan(
                self.report_8gb,
                mode="quality",
                aspect="landscape",
                video_seconds=5,
                resolution="768x432",
                timing_file=timing_path,
                reference_mode="I2VA",
            )

        self.assertEqual(plan["estimate"]["confidence"], "empirical")
        self.assertEqual(plan["estimate"]["sample_count"], 2)
        self.assertIn("lora=known", plan["estimate"]["timing_key"])


class GenerateProfileTests(unittest.TestCase):
    def test_lora_and_shift_overrides_are_explicit(self):
        from argparse import Namespace
        from h3_generate import apply_overrides, effective_workflow_settings

        workflow = {
            "lora": {"inputs": {"lora_name": "old.safetensors", "strength_model": 1.0}, "class_type": "LoraLoaderModelOnly"},
            "shift": {"inputs": {"shift_video": 12.0, "shift_audio": 3.0}, "class_type": "MiniMaxH3SigmaShift"},
        }
        args = Namespace(seed=None, width=None, height=None, length=None, steps=None, fps=None, filename_prefix=None,
                         lora_name="new.safetensors", lora_strength=0.9, shift_video=6.0, shift_audio=3.0)
        apply_overrides(workflow, args)
        settings = effective_workflow_settings(workflow)
        self.assertEqual(settings["lora_name"], "new.safetensors")
        self.assertEqual(settings["lora_strength"], 0.9)
        self.assertEqual(settings["shift_video"], 6.0)
        self.assertEqual(settings["shift_audio"], 3.0)
        self.assertFalse(settings["block_cache"])

    def test_experimental_timing_variant_does_not_pollute_default_key(self):
        from h3_plan import timing_key, timing_variant

        default = {
            "lora_name": "minimax_h3_fl2v_lightx2v_turbo_4step_v0.1_comfy_resized_avg_rank_21_bf16.safetensors",
            "block_cache": True,
            "shift_video": 12.0,
            "shift_audio": 3.0,
        }
        experimental = {
            "lora_name": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
            "block_cache": False,
            "shift_video": 6.0,
            "shift_audio": 3.0,
        }
        base = timing_key("fast", {"width": 736, "height": 416}, 124, 24, 4, timing_variant(default))
        candidate = timing_key("fast", {"width": 736, "height": 416}, 124, 24, 4, timing_variant(experimental))
        self.assertEqual(base, "fast|736x416|124|24|4")
        self.assertNotEqual(candidate, base)
        self.assertIn("v1.0_768p", candidate)

    def test_profile_overrides_are_explicit_and_fast_is_unchanged(self):
        from h3_generate import apply_profile

        template = {
            "cache": {"inputs": {"model": ["base", 0]}, "class_type": "MiniMaxH3BlockCacheT8"},
            "base": {"inputs": {}, "class_type": "BaseModel"},
            "guide": {"inputs": {"model": ["cache", 0]}, "class_type": "BasicGuider"},
            "schedule": {"inputs": {"model": ["cache", 0], "steps": 4}, "class_type": "BasicScheduler"},
            "video": {"inputs": {"width": 640, "height": 352}, "class_type": "MiniMaxH3ImageToVideo"},
        }
        fast = json.loads(json.dumps(template))
        apply_profile(fast, "fast")
        self.assertEqual(fast["schedule"]["inputs"]["steps"], 4)
        self.assertEqual(fast["guide"]["inputs"]["model"], ["cache", 0])

        quality = json.loads(json.dumps(template))
        apply_profile(quality, "quality")
        self.assertEqual(quality["schedule"]["inputs"]["steps"], 8)
        self.assertEqual(quality["guide"]["inputs"]["model"], ["base", 0])


if __name__ == "__main__":
    unittest.main()
