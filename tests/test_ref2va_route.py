import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


class Ref2VARouteTests(unittest.TestCase):
    def test_bundled_ref2va_templates_use_native_node(self):
        for name in ("h3_w4a8_ref2va_api.json", "h3_w4a8_ref2va_compat_api.json"):
            workflow = json.loads((SKILL_ROOT / "assets" / name).read_text(encoding="utf-8"))
            nodes = [node for node in workflow.values() if node.get("class_type") == "MiniMaxH3ReferenceToVideo"]
            self.assertEqual(len(nodes), 1, name)
            self.assertEqual(nodes[0]["inputs"]["ref_image_size"], "match")
            self.assertNotIn("first_frame", nodes[0]["inputs"])

    def test_ref2va_binding_stages_and_numbers_multiple_images(self):
        from h3_generate import bind_reference_images, load_workflow

        workflow = load_workflow(SKILL_ROOT / "assets" / "h3_w4a8_ref2va_compat_api.json")
        with tempfile.TemporaryDirectory() as directory:
            comfyui = Path(directory) / "ComfyUI"
            source_a = Path(directory) / "identity.png"
            source_b = Path(directory) / "scene.png"
            source_a.write_bytes(b"identity")
            source_b.write_bytes(b"scene")
            result = bind_reference_images(
                workflow,
                first_frame=None,
                last_frame=None,
                reference_images=[source_a, source_b],
                comfyui=comfyui,
                stage=True,
            )

            node = next(node for node in workflow.values() if node.get("class_type") == "MiniMaxH3ReferenceToVideo")
            self.assertEqual(result["mode"], "Ref2VA")
            self.assertEqual([item["label"] for item in result["inputs"]["ref_images"]], ["Picture 1", "Picture 2"])
            self.assertEqual(node["inputs"]["ref_images.ref_image_0"][1], 0)
            self.assertEqual(node["inputs"]["ref_images.ref_image_1"][1], 0)
            loaders = [item for item in workflow.values() if item.get("class_type") == "LoadImage"]
            self.assertEqual(len(loaders), 2)
            self.assertTrue(all((comfyui / "input" / loader["inputs"]["image"]).is_file() for loader in loaders))

    def test_ref2va_route_and_template_selection(self):
        from h3_fastpath import resolve_reference_mode, select_workflow_template

        args = Namespace(mode="auto", first_frame=None, last_frame=None, reference_images=["one.png", "two.png"])
        self.assertEqual(resolve_reference_mode(args), "ref2va")
        self.assertEqual(
            select_workflow_template(
                "auto",
                {"runtime_capabilities": {"object_info": {"nodes": {}}}},
                "ref2va",
                acceleration="compat",
            ),
            "h3_w4a8_ref2va_compat",
        )

    def test_ref2va_anchor_sheet_keeps_picture_roles(self):
        from h3_anchor import build_anchor_sheet

        sheet = build_anchor_sheet(
            "Picture 1 is the identity reference. Picture 2 is the coastal scene. Keep both consistent.",
            {
                "mode": "Ref2VA",
                "inputs": {
                    "ref_images": [
                        {"role": "ref_image_1", "binding": {"source": "C:/refs/identity.png", "input_name": "identity.png"}},
                        {"role": "ref_image_2", "binding": {"source": "C:/refs/scene.png", "input_name": "scene.png"}},
                    ]
                },
            },
            reference_mode="ref2va",
            reference_images=["C:/refs/identity.png", "C:/refs/scene.png"],
        )

        self.assertEqual(sheet["reference_mode"], "Ref2VA")
        self.assertEqual([item["label"] for item in sheet["references"]], ["Picture 1", "Picture 2"])
        self.assertTrue(sheet["identity_sensitive"])

    def test_ref2va_rejects_frame_arguments(self):
        from h3_fastpath import FastPathError, resolve_reference_mode

        args = Namespace(mode="auto", first_frame="first.png", last_frame=None, reference_images=["ref.png"])
        with self.assertRaises(FastPathError):
            resolve_reference_mode(args)


if __name__ == "__main__":
    unittest.main()
