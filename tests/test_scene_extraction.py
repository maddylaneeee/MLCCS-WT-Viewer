from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wt_model_viewer.runtime_paths import bootstrap_vendor_path

bootstrap_vendor_path()

from parse.material import MaterialData  # type: ignore  # noqa: E402
from parse.realres import Model  # type: ignore  # noqa: E402

from wt_model_viewer.dae_bridge import (  # noqa: E402
    _classify_alpha_mode,
    _classify_material_mode,
    _iter_texture_roots,
    _material_lighting_profile,
    _prepare_group_pack,
    _prepared_group_packs,
    _resolve_ao_texture,
    _resolve_detail_textures,
    mesh_from_model,
    scene_from_model,
)
from wt_model_viewer.types import MATERIAL_MODE_MASKED_TANK, MATERIAL_MODE_STANDARD  # noqa: E402
from wt_model_viewer.i18n import detect_client_language  # noqa: E402


class _Node:
    def __init__(self, wtm):
        self.wtm = wtm


class _Skeleton:
    def __init__(self, mapping):
        self._mapping = mapping

    def getNodeByName(self, name: str):
        return self._mapping.get(name)


class SceneExtractionTests(unittest.TestCase):
    def test_converts_triangle_model(self) -> None:
        model = Model("triangle")
        model.appendVerts(
            ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        )
        obj = model.newObject("triangle")
        obj.appendFace((0, 1, 2))

        mesh = mesh_from_model(model)
        scene = scene_from_model(model)

        self.assertEqual(mesh.vertex_count, 3)
        self.assertEqual(mesh.face_count, 1)
        self.assertEqual(mesh.object_count, 1)
        self.assertEqual(scene.vertex_count, 3)
        self.assertEqual(scene.face_count, 1)
        self.assertEqual(scene.object_count, 1)
        self.assertEqual(len(scene.batches), 1)
        self.assertEqual(scene.batches[0].vertex_count, 3)
        self.assertEqual(scene.batches[0].index_count, 3)
        self.assertEqual(scene.batches[0].indices.tolist(), [0, 1, 2])
        self.assertIsNone(scene.batches[0].diffuse_texture)
        self.assertIsNone(scene.batches[0].normal_texture)
        self.assertAlmostEqual(mesh.extent, 2.0)
        self.assertEqual(scene.batches[0].interleaved[:, 9:11].tolist(), [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])

    def test_applies_parent_bone_transform_for_scene(self) -> None:
        model = Model("moved")
        model.appendVerts(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        )
        obj = model.newObject("wing")
        obj.appendFace((0, 1, 2))
        model._Model__skeleton = _Skeleton(
            {
                "wing": _Node(
                    (
                        (1.0, 0.0, 0.0, 5.0),
                        (0.0, 1.0, 0.0, 0.0),
                        (0.0, 0.0, 1.0, 0.0),
                        (0.0, 0.0, 0.0, 1.0),
                    )
                )
            }
        )

        scene = scene_from_model(model)

        xs = scene.batches[0].interleaved[:, 0]
        self.assertAlmostEqual(float(xs.min()), -0.5, places=5)
        self.assertAlmostEqual(float(xs.max()), 0.5, places=5)
        self.assertAlmostEqual(scene.extent, 1.0)

    def test_scene_batch_compacts_shared_vertices_into_indices(self) -> None:
        model = Model("quad")
        model.appendVerts(
            ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)),
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        )
        obj = model.newObject("quad")
        obj.appendFace((0, 1, 2))
        obj.appendFace((0, 2, 3))

        scene = scene_from_model(model)
        batch = scene.batches[0]

        self.assertEqual(scene.vertex_count, 6)
        self.assertEqual(batch.vertex_count, 4)
        self.assertEqual(batch.index_count, 6)
        self.assertEqual(batch.indices.tolist(), [0, 1, 2, 0, 2, 3])

    def test_detects_client_language_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config.blk").write_text('language:t="Japanese"\n', encoding="utf-8")
            self.assertEqual(detect_client_language(root), "ja")

    def test_iter_texture_roots_includes_content_hq_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_res = root / "content" / "base" / "res"
            hq_tex_res = root / "content.hq" / "hq_tex" / "res"
            uhq_aircraft_res = root / "content.hq" / "uhq_aircraft" / "res"
            for path in (base_res, hq_tex_res, uhq_aircraft_res):
                path.mkdir(parents=True, exist_ok=True)

            texture_roots = _iter_texture_roots(root)

            self.assertEqual(
                texture_roots,
                (
                    base_res.resolve(),
                    hq_tex_res.resolve(),
                    uhq_aircraft_res.resolve(),
                ),
            )

    def test_prepare_group_pack_caches_resources_only_once(self) -> None:
        _prepared_group_packs.clear()
        try:
            with patch("wt_model_viewer.dae_bridge.GameResourcePack") as pack_cls, patch(
                "wt_model_viewer.dae_bridge.AssetCacher.cacheAsset"
            ) as cache_asset:
                pack = pack_cls.return_value
                pack.getRealResEntryCnt.return_value = 3
                pack.getRealResource.side_effect = ["a", "b", "c"]

                _prepare_group_pack(Path("D:/packs/test.grp"))
                _prepare_group_pack(Path("D:/packs/test.grp"))

                self.assertEqual(pack.getRealResource.call_count, 3)
                self.assertEqual(cache_asset.call_count, 3)
        finally:
            _prepared_group_packs.clear()

    def test_redirects_detail_normal_from_detail_slot(self) -> None:
        material = MaterialData()
        material.cls = "dynamic_masked_chrome_bump"
        material.addTexSlot("t0", "mirage_2000_c3_c*")
        material.addTexSlot("t2", "mirage_2000_c3_n*")
        material.addTexSlot("t4", "aircraft_normal_detail_lo_n*")

        detail_texture, detail_normal_texture = _resolve_detail_textures(material)

        self.assertIsNone(detail_texture)
        self.assertEqual(detail_normal_texture, "aircraft_normal_detail_lo_n*")

    def test_resolves_dynamic_t3_slot_as_ao(self) -> None:
        material = MaterialData()
        material.cls = "dynamic_masked_tank"
        material.addTexSlot("t0", "m1a2_abrams_body_c*")
        material.addTexSlot("t1", "us_camo_olive*")
        material.addTexSlot("t2", "m1a2_abrams_body_n*")
        material.addTexSlot("t3", "m1a2_abrams_body_ao*")

        self.assertEqual(_resolve_ao_texture(material), "m1a2_abrams_body_ao*")

    def test_does_not_treat_layered_detail_slot_as_ao(self) -> None:
        material = MaterialData()
        material.cls = "layered_terrain"
        material.addTexSlot("t3", "detail_grass_c*")

        self.assertIsNone(_resolve_ao_texture(material))

    def test_classifies_alpha_modes_from_shader_class(self) -> None:
        opaque_material = MaterialData()
        opaque_material.cls = "dynamic_masked_tank"
        self.assertEqual(_classify_alpha_mode(opaque_material, 1.0), (0, 0.0))

        cutout_material = MaterialData()
        cutout_material.cls = "dynamic_tank_atest"
        self.assertEqual(_classify_alpha_mode(cutout_material, 1.0), (2, 0.35))

        glass_material = MaterialData()
        glass_material.cls = "dynamic_pbr_glass"
        self.assertEqual(_classify_alpha_mode(glass_material, 1.0), (1, 0.0))

    def test_classifies_masked_tank_material_mode_only_for_real_camo_pairs(self) -> None:
        masked_material = MaterialData()
        masked_material.cls = "dynamic_masked_tank"
        masked_material.addTexSlot("t0", "m1a1_abrams_body_c*")
        masked_material.addTexSlot("t1", "us_camo_olive*")
        self.assertEqual(_classify_material_mode(masked_material, object(), object()), MATERIAL_MODE_MASKED_TANK)

        self_masked_material = MaterialData()
        self_masked_material.cls = "dynamic_masked_tank"
        self_masked_material.addTexSlot("t0", "bag_a_c*")
        self_masked_material.addTexSlot("t1", "bag_a_c*")
        self.assertEqual(_classify_material_mode(self_masked_material, object(), object()), MATERIAL_MODE_STANDARD)

    def test_assigns_lighting_profiles_by_shader_family(self) -> None:
        glass_material = MaterialData()
        glass_material.cls = "dynamic_pbr_glass"
        glass_profile = _material_lighting_profile(glass_material)
        self.assertGreater(glass_profile["specular_scale"], 1.5)
        self.assertGreater(glass_profile["fresnel_strength"], 0.2)

        chrome_material = MaterialData()
        chrome_material.cls = "dynamic_masked_chrome_bump"
        chrome_profile = _material_lighting_profile(chrome_material)
        self.assertGreater(chrome_profile["gloss_floor"], 0.3)

        tank_material = MaterialData()
        tank_material.cls = "dynamic_masked_tank"
        tank_profile = _material_lighting_profile(tank_material)
        self.assertGreater(tank_profile["ao_strength"], 0.8)


if __name__ == "__main__":
    unittest.main()
