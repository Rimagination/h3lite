import sys
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class MonitorLogicTests(unittest.TestCase):
    def test_progress_fraction_is_clamped_and_handles_unknown_maximum(self):
        from h3_monitor_gui import progress_fraction

        self.assertEqual(progress_fraction(3, 4), 0.75)
        self.assertEqual(progress_fraction(9, 4), 1.0)
        self.assertIsNone(progress_fraction(1, 0))

    def test_format_seconds_is_human_readable(self):
        from h3_monitor_gui import format_seconds

        self.assertEqual(format_seconds(None), "--:--")
        self.assertEqual(format_seconds(65.4), "01:05")
        self.assertEqual(format_seconds(3661), "1:01:01")

    def test_stage_label_distinguishes_queue_sampling_and_finish(self):
        from h3_monitor_gui import stage_label

        self.assertEqual(stage_label("queued"), "排队等待")
        self.assertEqual(stage_label("running", node="BasicScheduler"), "正在采样")
        self.assertEqual(stage_label("running", node="12"), "正在采样")
        self.assertEqual(stage_label("running", node="VAEDecode"), "正在解码")
        self.assertEqual(stage_label("success"), "已完成")

    def test_progress_event_updates_only_the_matching_prompt(self):
        from h3_monitor_gui import apply_progress_event

        initial = {"prompt_id": "target", "progress": None, "step": None, "total_steps": None}
        ignored = apply_progress_event(
            initial,
            {"type": "progress", "data": {"prompt_id": "other", "value": 1, "max": 4}},
        )
        self.assertIsNone(ignored["progress"])

        updated = apply_progress_event(
            initial,
            {
                "type": "progress",
                "data": {"prompt_id": "target", "value": 3, "max": 4, "node": "12"},
            },
        )
        self.assertEqual(updated["progress"], 0.75)
        self.assertEqual(updated["step"], 3)
        self.assertEqual(updated["total_steps"], 4)
        self.assertEqual(updated["node"], "12")

    def test_progress_state_aggregates_finished_and_active_nodes(self):
        from h3_monitor_gui import apply_progress_event

        updated = apply_progress_event(
            {"prompt_id": "target", "progress": None, "step": None, "total_steps": None},
            {
                "type": "progress_state",
                "data": {
                    "prompt_id": "target",
                    "nodes": {
                        "load": {
                            "state": "finished",
                            "value": 1,
                            "max": 1,
                            "node_id": "load",
                            "display_node_id": "load",
                        },
                        "sample": {
                            "state": "running",
                            "value": 2,
                            "max": 4,
                            "node_id": "sample",
                            "display_node_id": "sample",
                        },
                    },
                },
            },
        )

        self.assertEqual(updated["progress"], 0.75)
        self.assertEqual(updated["step"], 2)
        self.assertEqual(updated["total_steps"], 4)
        self.assertEqual(updated["node"], "sample")
        self.assertEqual(updated["progress_source"], "progress_state")

    def test_monitor_uses_manifest_client_id_for_targeted_progress(self):
        from h3_monitor_gui import manifest_client_id

        self.assertEqual(manifest_client_id({"client_id": "client-123"}), "client-123")
        self.assertIsNone(manifest_client_id({}))

    def test_eta_uses_progress_before_fallback_estimate(self):
        from h3_monitor_gui import estimate_remaining

        self.assertEqual(estimate_remaining(100, 0.5, 600), 100)
        self.assertEqual(estimate_remaining(100, None, 600), 500)
        self.assertIsNone(estimate_remaining(100, None, None))

    def test_node_progress_does_not_turn_node_count_into_time_eta(self):
        from h3_monitor_gui import build_snapshot

        snapshot = build_snapshot(
            {
                "prompt_id": "target",
                "state": "running",
                "queued_at_utc": "2026-08-16T00:00:00+00:00",
                "elapsed_seconds": 42,
            },
            None,
            "running",
            1,
            {
                "prompt_id": "target",
                "state": "running",
                "progress": 0.8,
                "progress_source": "progress_state",
                "finished_nodes": 4,
                "total_nodes": 5,
                "node": "11",
            },
            {},
            600,
            now=datetime(2026, 8, 16, 0, 2, tzinfo=timezone.utc),
        )

        self.assertEqual(snapshot["progress"], 0.8)
        self.assertEqual(snapshot["elapsed_seconds"], 42)
        self.assertEqual(snapshot["eta_seconds"], 558)
        self.assertEqual(snapshot["elapsed_basis"], "manifest")
        self.assertEqual(snapshot["progress_basis"], "node_completion")
        self.assertEqual(snapshot["eta_basis"], "empirical")

    def test_auto_discovery_ignores_stale_running_manifest(self):
        from h3_monitor_gui import _find_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "old"
            run.mkdir()
            manifest = run / "manifest.json"
            manifest.write_text(json.dumps({"state": "running", "prompt_id": "old"}), encoding="utf-8")
            old_time = time.time() - 24 * 60 * 60
            import os

            os.utime(manifest, (old_time, old_time))
            path, value = _find_manifest(root, now=time.time())

        self.assertIsNone(path)
        self.assertEqual(value, {})

    def test_fastpath_can_build_a_detached_native_monitor_command(self):
        from h3_fastpath import build_monitor_command

        command = build_monitor_command(
            scripts_dir=SCRIPTS,
            comfyui=Path(r"F:\MiniMax-H3\ComfyUI"),
            run_root=Path(r"F:\MiniMax-H3\ComfyUI\user\h3lite_runs"),
            topmost=True,
        )
        self.assertIn("h3_monitor_gui.py", " ".join(command))
        self.assertIn("--comfyui", command)
        self.assertIn(r"F:\MiniMax-H3\ComfyUI", command)
        self.assertIn("--topmost", command)


    def test_monitor_defaults_to_windows_and_supports_explicit_override(self):
        from h3_fastpath import resolve_monitor_gui

        self.assertTrue(resolve_monitor_gui(None, platform="win32"))
        self.assertFalse(resolve_monitor_gui(None, platform="linux"))
        self.assertFalse(resolve_monitor_gui(False, platform="win32"))
        self.assertTrue(resolve_monitor_gui(True, platform="linux"))



if __name__ == "__main__":
    unittest.main()
