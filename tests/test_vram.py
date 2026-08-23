import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import h3_vram


class VramReportTests(unittest.TestCase):
    def test_wddm_parser_preserves_adapter_scope(self):
        rows = h3_vram._parse_wddm_json(
            '{"pid": 123, "name": "python", '
            '"luid": "0x00000000_0x00000001", "phys": 0, '
            '"dedicated_bytes": 2097152}'
        )

        self.assertEqual(
            rows,
            [
                {
                    "pid": 123,
                    "name": "python",
                    "luid": "0x00000000_0x00000001",
                    "phys": 0,
                    "dedicated_mb": 2,
                }
            ],
        )

    def test_report_warns_when_wddm_and_nvidia_scopes_disagree(self):
        with patch(
            "h3_vram.nvidia_totals_mb",
            return_value=[
                {
                    "index": 0,
                    "name": "GPU",
                    "total_mb": 8192,
                    "used_mb": 100,
                    "free_mb": 8092,
                }
            ],
        ), patch(
            "h3_vram.win_per_process_mb",
            return_value=[
                {
                    "pid": 1,
                    "name": "python",
                    "luid": "luid-a",
                    "phys": 0,
                    "dedicated_mb": 1000,
                },
                {
                    "pid": 2,
                    "name": "game",
                    "luid": "luid-b",
                    "phys": 0,
                    "dedicated_mb": 1000,
                },
            ],
        ):
            report = h3_vram.build_report()

        self.assertTrue(report["scope_mismatch"])
        self.assertEqual(report["process_scope"], "wddm-multiple-luids")
        self.assertEqual(len(report["wddm_luids"]), 2)
        self.assertTrue(report["warnings"])

    def test_free_gate_fails_closed_on_scope_mismatch(self):
        report = {
            "gpus": [
                {
                    "index": 0,
                    "name": "GPU",
                    "total_mb": 8192,
                    "used_mb": 100,
                    "free_mb": 8092,
                }
            ],
            "scope_mismatch": True,
            "processes": [],
            "source": "win-perfcounter",
            "process_scope": "wddm-multiple-luids",
            "wddm_luids": ["a", "b"],
        }
        with patch("h3_vram.build_report", return_value=report), contextlib.redirect_stderr(
            io.StringIO()
        ):
            result = h3_vram.main(["--check-free-gb", "5"])

        self.assertEqual(result, 2)

    def test_stop_requires_explicit_confirmation_before_reading_or_killing(self):
        with patch("h3_vram._run") as run:
            result = h3_vram.cmd_stop(
                123,
                confirm_stop=False,
                expected_name="python",
                queue_url=None,
            )

        self.assertEqual(result, 2)
        run.assert_not_called()

    def test_stop_requires_an_exact_process_name(self):
        with patch("h3_vram._run") as run:
            result = h3_vram.cmd_stop(
                123,
                confirm_stop=True,
                expected_name=None,
                queue_url=None,
            )

        self.assertEqual(result, 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
