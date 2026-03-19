from __future__ import annotations

from collections import OrderedDict, defaultdict
from io import BytesIO
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from .runtime_paths import bootstrap_vendor_path
from .types import (
    ALPHA_MODE_BLEND,
    ALPHA_MODE_CUTOUT,
    ALPHA_MODE_OPAQUE,
    MATERIAL_MODE_MASKED_TANK,
    MATERIAL_MODE_STANDARD,
    MeshBundle,
    ModelIndexEntry,
    RenderScene,
    SceneBatch,
    TextureImage,
)

bootstrap_vendor_path()

import util.log as dae_log  # type: ignore

dae_log.log = lambda *args, **kwargs: None

from parse.gameres import GameResDesc, GameResourcePack  # type: ignore  # noqa: E402
from parse.material import DDSx, DDSxTexturePack2, MaterialData, getBestTex  # type: ignore  # noqa: E402
from parse.realres import Model, RendInst  # type: ignore  # noqa: E402
from util.assetcacher import AssetCacher  # type: ignore  # noqa: E402
from util.enums import TEXTURE_GENERIC, TEXTURE_NORMAL  # type: ignore  # noqa: E402


ProgressCallback = Callable[[int, int, str], None]

_runtime_root: Path | None = None
_descriptors_ready = False
_textures_ready = False
_decoded_texture_cache: OrderedDict[tuple[str, int], TextureImage | None] = OrderedDict()
_scene_cache: OrderedDict[tuple[str, int], RenderScene] = OrderedDict()
_prepared_group_packs: set[Path] = set()

_MAX_TEXTURE_CACHE = 96
_MAX_SCENE_CACHE = 0


def validate_game_root(game_root: Path) -> Path:
    root = Path(game_root)
    res_root = root / "content" / "base" / "res"
    if not res_root.exists():
        raise FileNotFoundError(f"Missing fixed resource path: {res_root}")
    return res_root


def iter_group_files(game_root: Path) -> list[Path]:
    res_root = validate_game_root(game_root)
    return sorted(res_root.rglob("*.grp"))


def scan_rendinst_models(game_root: Path, progress: ProgressCallback | None = None) -> list[ModelIndexEntry]:
    res_root = validate_game_root(game_root)
    _prepare_descriptors(game_root, progress)
    _prepare_texture_assets(game_root, progress)

    group_files = sorted(res_root.rglob("*.grp"))
    total = len(group_files)
    entries: list[ModelIndexEntry] = []

    for index, group_path in enumerate(group_files, start=1):
        if progress is not None:
            progress(index, total, f"group::{group_path.name}")

        pack = GameResourcePack(str(group_path))
        for resource_index in range(pack.getRealResEntryCnt()):
            resource = pack.getRealResource(resource_index)
            if isinstance(resource, RendInst):
                entries.append(
                    ModelIndexEntry(
                        name=resource.name,
                        group_path=str(group_path),
                        group_relpath=group_path.relative_to(game_root).as_posix(),
                        resource_index=resource_index,
                    )
                )

    entries.sort(key=lambda item: (item.name.lower(), item.pack_name.lower(), item.group_relpath.lower()))
    return entries


def build_mesh_bundle(entry: ModelIndexEntry) -> MeshBundle:
    pack = GameResourcePack(entry.group_path)
    resource = pack.getRealResource(entry.resource_index)
    if not isinstance(resource, RendInst):
        raise TypeError(f"Resource is not a RendInst/DynModel: {entry.name}")

    return mesh_from_model(resource.getModel(0))


def build_render_scene(
    entry: ModelIndexEntry,
    game_root: Path,
    progress: ProgressCallback | None = None,
) -> RenderScene:
    _prepare_descriptors(game_root, progress)
    _prepare_texture_assets(game_root, progress)
    _prepare_group_pack(entry.group_path)

    cache_key = (entry.group_path, entry.resource_index)
    cached_scene = _scene_cache.get(cache_key)
    if cached_scene is not None:
        _scene_cache.move_to_end(cache_key)
        return cached_scene

    if progress is not None:
        progress(1, 1, f"scene::{entry.name}")

    pack = GameResourcePack(entry.group_path)
    resource = pack.getRealResource(entry.resource_index)
    if not isinstance(resource, RendInst):
        raise TypeError(f"Resource is not a RendInst/DynModel: {entry.name}")

    scene = scene_from_model(resource.getModel(0), progress=progress, progress_name=entry.name)
    if _MAX_SCENE_CACHE > 0:
        _scene_cache[cache_key] = scene
        while len(_scene_cache) > _MAX_SCENE_CACHE:
            _scene_cache.popitem(last=False)
    return scene


def mesh_from_model(model: Model) -> MeshBundle:
    vertices = np.array(
        [[vertex[0], vertex[1], -vertex[2]] for vertex in (model.getVertex(i) for i in range(model.vertCnt))],
        dtype=np.float32,
    )

    faces_list: list[tuple[int, int, int]] = []
    object_count = 0
    for obj in model:
        object_count += 1
        faces_list.extend(obj.faces)

    if not len(vertices) or not faces_list:
        raise ValueError("Model contains no renderable triangles")

    faces = np.array(faces_list, dtype=np.uint32)
    bounds_min = vertices.min(axis=0)
    bounds_max = vertices.max(axis=0)
    center = (bounds_min + bounds_max) / 2.0
    extent = float(np.max(bounds_max - bounds_min))
    if extent <= 0:
        extent = 1.0

    centered_vertices = vertices - center

    return MeshBundle(
        vertices=centered_vertices,
        faces=faces,
        center=center,
        extent=extent,
        face_count=len(faces_list),
        vertex_count=len(vertices),
        object_count=object_count,
    )


def scene_from_model(
    model: Model,
    progress: ProgressCallback | None = None,
    progress_name: str | None = None,
) -> RenderScene:
    material_lookup = {material.getName(): material for material in (model.materials or ())}
    batches: dict[str, dict[str, object]] = defaultdict(
        lambda: {"vertex_chunks": [], "index_chunks": [], "material": None, "vertex_offset": 0}
    )
    objects = list(model)
    total_objects = len(objects)

    bounds_min = np.full(3, np.inf, dtype=np.float32)
    bounds_max = np.full(3, -np.inf, dtype=np.float32)
    object_count = 0
    face_count = 0
    vertex_count = 0
    skeleton = model.skeleton

    for object_index, obj in enumerate(objects, start=1):
        object_count += 1
        if progress is not None and progress_name is not None:
            progress(object_index - 1, max(total_objects, 1), f"scene::{progress_name}")

        if not obj.faces:
            continue

        parent_node = _resolve_parent_node(skeleton, obj.name) if skeleton is not None and not obj.skinned else None
        faces = np.asarray(obj.faces, dtype=np.int32)
        flat_vertex_ids = faces.reshape(-1)
        unique_vertex_ids, inverse = np.unique(flat_vertex_ids, return_inverse=True)
        local_faces = inverse.reshape(-1, 3)

        positions = np.empty((len(unique_vertex_ids), 3), dtype=np.float32)
        uvs = np.empty((len(unique_vertex_ids), 2), dtype=np.float32)
        for vertex_buffer_index, vertex_id in enumerate(unique_vertex_ids.tolist()):
            position = model.getVertex(int(vertex_id), parentBone=parent_node)
            positions[vertex_buffer_index] = (position[0], position[1], -position[2])

            uv_source = model.getUV(int(vertex_id))
            uvs[vertex_buffer_index] = (uv_source[0], uv_source[1])

        face_positions = positions[local_faces]
        face_uvs = uvs[local_faces]
        face_normals = _face_normals(face_positions)
        face_tangents = _face_tangents(face_positions, face_uvs)

        normals = np.zeros_like(positions)
        tangents = np.zeros_like(positions)
        for corner in range(3):
            np.add.at(normals, local_faces[:, corner], face_normals)
            np.add.at(tangents, local_faces[:, corner], face_tangents)

        normals = _normalize_rows(normals, fallback=np.array([0.0, 1.0, 0.0], dtype=np.float32))
        tangents = _orthogonalize_tangents(tangents, normals)

        bounds_min = np.minimum(bounds_min, positions.min(axis=0))
        bounds_max = np.maximum(bounds_max, positions.max(axis=0))
        face_count += len(faces)
        vertex_count += len(flat_vertex_ids)

        for material_name, start_face_index, end_face_index in _iter_material_ranges(obj):
            material_faces = local_faces[start_face_index:end_face_index]
            if not len(material_faces):
                continue

            material_vertex_ids, reindexed = np.unique(material_faces.reshape(-1), return_inverse=True)
            interleaved = np.concatenate(
                (
                    positions[material_vertex_ids],
                    normals[material_vertex_ids],
                    tangents[material_vertex_ids],
                    uvs[material_vertex_ids],
                ),
                axis=1,
            ).astype(np.float32, copy=False)
            payload = batches[material_name]
            vertex_offset = int(payload["vertex_offset"])
            payload["vertex_chunks"].append(np.ascontiguousarray(interleaved))
            payload["index_chunks"].append(np.ascontiguousarray(reindexed.astype(np.uint32, copy=False) + vertex_offset))
            payload["vertex_offset"] = vertex_offset + len(interleaved)
            payload["material"] = material_lookup.get(material_name)

        if progress is not None and progress_name is not None:
            progress(object_index, max(total_objects, 1), f"scene::{progress_name}")

    if face_count == 0:
        raise ValueError("Model contains no renderable triangles")

    center = (bounds_min + bounds_max) / 2.0
    extent = float(np.max(bounds_max - bounds_min))
    if extent <= 0.0:
        extent = 1.0

    scene_batches: list[SceneBatch] = []
    for material_name, payload in batches.items():
        material = payload["material"]
        interleaved = np.ascontiguousarray(np.concatenate(payload["vertex_chunks"], axis=0), dtype=np.float32)
        indices = np.ascontiguousarray(np.concatenate(payload["index_chunks"], axis=0), dtype=np.uint32)
        if len(interleaved) <= np.iinfo(np.uint16).max:
            indices = indices.astype(np.uint16, copy=False)
        interleaved[:, 0:3] -= center
        material_maps = _load_material_maps(material)
        scene_batches.append(
            SceneBatch(
                material_name=material_name,
                interleaved=interleaved,
                indices=indices,
                diffuse_texture=material_maps["diffuse"],
                normal_texture=material_maps["normal"],
                ao_texture=material_maps["ao"],
                mask_texture=material_maps["mask"],
                detail_texture=material_maps["detail"],
                detail_normal_texture=material_maps["detail_normal"],
                detail_scale=material_maps["detail_scale"],
                shader_class=material_maps["shader_class"],
                vertex_count=len(interleaved),
                index_count=len(indices),
                base_color=material_maps["base_color"],
                opacity=material_maps["opacity"],
                alpha_mode=material_maps["alpha_mode"],
                alpha_cutoff=material_maps["alpha_cutoff"],
                material_mode=material_maps["material_mode"],
                ao_strength=material_maps["ao_strength"],
                specular_scale=material_maps["specular_scale"],
                gloss_floor=material_maps["gloss_floor"],
                fresnel_strength=material_maps["fresnel_strength"],
            )
        )

    scene_batches.sort(
        key=lambda batch: (batch.alpha_mode == ALPHA_MODE_BLEND, not batch.textured, batch.material_name.lower())
    )

    return RenderScene(
        batches=scene_batches,
        center=center.astype(np.float32),
        extent=extent,
        face_count=face_count,
        vertex_count=vertex_count,
        object_count=object_count,
    )


def _prepare_descriptors(game_root: Path, progress: ProgressCallback | None) -> None:
    global _descriptors_ready

    res_root = _ensure_runtime_root(game_root)
    if _descriptors_ready:
        return

    desc_files = [res_root / "riDesc.bin", res_root / "dynModelDesc.bin"]
    existing_desc_files = [path for path in desc_files if path.exists()]

    for index, desc_path in enumerate(existing_desc_files, start=1):
        if progress is not None:
            progress(index, len(existing_desc_files), f"desc::{desc_path.name}")
        desc = GameResDesc(str(desc_path))
        desc.loadDataBlock()
        AssetCacher.appendGameResDesc(desc)

    _descriptors_ready = True


def _prepare_texture_assets(game_root: Path, progress: ProgressCallback | None) -> None:
    global _textures_ready

    _ensure_runtime_root(game_root)
    if _textures_ready:
        return

    dxp_files = [
        dxp_path
        for texture_root in _iter_texture_roots(game_root)
        for dxp_path in sorted(texture_root.rglob("*.dxp.bin"))
    ]
    for index, dxp_path in enumerate(dxp_files, start=1):
        if progress is not None:
            progress(index, len(dxp_files), f"texture::{dxp_path.name}")
        pack = DDSxTexturePack2(str(dxp_path))
        for tex in pack.getPackedFiles():
            AssetCacher.cacheAsset(tex)

    _textures_ready = True


def _prepare_group_pack(group_path: str | Path) -> None:
    resolved_group_path = Path(group_path).resolve()
    if resolved_group_path in _prepared_group_packs:
        return

    pack = GameResourcePack(str(resolved_group_path))
    for resource_index in range(pack.getRealResEntryCnt()):
        AssetCacher.cacheAsset(pack.getRealResource(resource_index))

    _prepared_group_packs.add(resolved_group_path)


def _iter_texture_roots(game_root: Path) -> tuple[Path, ...]:
    roots: list[Path] = [validate_game_root(game_root)]
    hq_root = Path(game_root) / "content.hq"
    if hq_root.exists():
        roots.extend(path for path in sorted(hq_root.rglob("res")) if path.is_dir())

    unique_roots: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved_root = root.resolve()
        if resolved_root in seen:
            continue
        seen.add(resolved_root)
        unique_roots.append(resolved_root)

    return tuple(unique_roots)


def _ensure_runtime_root(game_root: Path) -> Path:
    global _runtime_root, _descriptors_ready, _textures_ready

    resolved_root = Path(game_root).resolve()
    if _runtime_root != resolved_root:
        AssetCacher.clearCache()
        _decoded_texture_cache.clear()
        _scene_cache.clear()
        _prepared_group_packs.clear()
        _runtime_root = resolved_root
        _descriptors_ready = False
        _textures_ready = False

    return validate_game_root(resolved_root)


def _resolve_parent_node(skeleton, object_name: str):
    if skeleton is None:
        return None

    exact = skeleton.getNodeByName(object_name)
    if exact is not None:
        return exact

    for separator in (":", "@", "."):
        if separator in object_name:
            candidate = object_name.split(separator, 1)[0]
            node = skeleton.getNodeByName(candidate)
            if node is not None:
                return node

    return None


def _load_material_maps(material: MaterialData | None) -> dict[str, object]:
    if material is None:
        return {
            "diffuse": None,
            "normal": None,
            "ao": None,
            "mask": None,
            "detail": None,
            "detail_normal": None,
            "detail_scale": (1.0, 1.0),
            "shader_class": None,
            "base_color": (0.78, 0.8, 0.84),
            "opacity": 1.0,
            "alpha_mode": ALPHA_MODE_OPAQUE,
            "alpha_cutoff": 0.0,
            "material_mode": MATERIAL_MODE_STANDARD,
            "ao_strength": 0.75,
            "specular_scale": 1.0,
            "gloss_floor": 0.18,
            "fresnel_strength": 0.0,
        }

    detail_texture_name, detail_normal_texture_name = _resolve_detail_textures(material)
    ao_texture_name = _resolve_ao_texture(material)
    diffuse_texture = _load_texture_image(material.diffuse, material, "diffuse")
    normal_texture = _load_texture_image(material.normal, material, "normal")
    ao_texture = _load_texture_image(ao_texture_name, material, "ao")
    mask_texture = _load_texture_image(material.mask, material, "mask")
    detail_texture = _load_texture_image(detail_texture_name, material, "detail")
    detail_normal_texture = _load_texture_image(detail_normal_texture_name, material, "detail_normal")

    base_color = tuple(float(np.clip(channel, 0.0, 1.0)) for channel in getattr(material, "diff", (0.78, 0.8, 0.84))[:3])
    params = material.getParams()
    opacity = _safe_float(params.get("opacity"), default=1.0)
    alpha_mode, alpha_cutoff = _classify_alpha_mode(material, opacity)
    material_mode = _classify_material_mode(material, diffuse_texture, mask_texture)
    lighting_profile = _material_lighting_profile(material)

    return {
        "diffuse": diffuse_texture,
        "normal": normal_texture,
        "ao": ao_texture,
        "mask": mask_texture,
        "detail": detail_texture,
        "detail_normal": detail_normal_texture,
        "detail_scale": _detail_scale(material),
        "shader_class": getattr(material, "cls", None),
        "base_color": base_color,
        "opacity": float(np.clip(opacity, 0.0, 1.0)),
        "alpha_mode": alpha_mode,
        "alpha_cutoff": alpha_cutoff,
        "material_mode": material_mode,
        "ao_strength": lighting_profile["ao_strength"],
        "specular_scale": lighting_profile["specular_scale"],
        "gloss_floor": lighting_profile["gloss_floor"],
        "fresnel_strength": lighting_profile["fresnel_strength"],
    }


def _classify_alpha_mode(material: MaterialData, opacity: float) -> tuple[int, float]:
    shader_class = (getattr(material, "cls", None) or "").lower()
    if opacity < 0.999:
        return (ALPHA_MODE_BLEND, 0.0)
    if "glass" in shader_class or "alpha_blend" in shader_class or shader_class in {"propeller_front", "propeller_side", "aces_weapon_fire"}:
        return (ALPHA_MODE_BLEND, 0.0)
    if "atest" in shader_class or "alpha_test" in shader_class:
        return (ALPHA_MODE_CUTOUT, 0.35)
    return (ALPHA_MODE_OPAQUE, 0.0)


def _classify_material_mode(
    material: MaterialData,
    diffuse_texture: TextureImage | None,
    mask_texture: TextureImage | None,
) -> int:
    shader_class = (getattr(material, "cls", None) or "").lower()
    if shader_class != "dynamic_masked_tank":
        return MATERIAL_MODE_STANDARD
    if diffuse_texture is None or mask_texture is None:
        return MATERIAL_MODE_STANDARD

    diffuse_name = MaterialData.getTexFileName(material.diffuse) if material.diffuse else None
    mask_name = MaterialData.getTexFileName(material.mask) if material.mask else None
    if not diffuse_name or not mask_name or diffuse_name == mask_name:
        return MATERIAL_MODE_STANDARD

    return MATERIAL_MODE_MASKED_TANK


def _material_lighting_profile(material: MaterialData) -> dict[str, float]:
    shader_class = (getattr(material, "cls", None) or "").lower()
    profile = {
        "ao_strength": 0.75,
        "specular_scale": 1.0,
        "gloss_floor": 0.18,
        "fresnel_strength": 0.0,
    }

    if "glass" in shader_class:
        profile.update(
            {
                "ao_strength": 0.25,
                "specular_scale": 1.85,
                "gloss_floor": 0.72,
                "fresnel_strength": 0.35,
            }
        )
    elif "chrome" in shader_class:
        profile.update(
            {
                "ao_strength": 0.45,
                "specular_scale": 1.45,
                "gloss_floor": 0.42,
                "fresnel_strength": 0.10,
            }
        )
    elif "tank_selfillum" in shader_class:
        profile.update(
            {
                "ao_strength": 0.70,
                "specular_scale": 1.05,
                "gloss_floor": 0.28,
                "fresnel_strength": 0.02,
            }
        )
    elif "tank" in shader_class:
        profile.update(
            {
                "ao_strength": 0.88,
                "specular_scale": 0.90,
                "gloss_floor": 0.22,
                "fresnel_strength": 0.02,
            }
        )
    elif "weapon_fire" in shader_class:
        profile.update(
            {
                "ao_strength": 0.10,
                "specular_scale": 0.15,
                "gloss_floor": 0.0,
                "fresnel_strength": 0.0,
            }
        )

    return profile


def _resolve_detail_textures(material: MaterialData) -> tuple[str | None, str | None]:
    detail_names = [name for name in material.detail if name]
    detail_normal_names = [name for name in material.detailNormal if name]

    detail_texture_name = detail_names[0] if detail_names else None
    detail_normal_texture_name = detail_normal_names[0] if detail_normal_names else None

    # Some aircraft materials store a detail normal map in the generic detail slot.
    if detail_texture_name is not None and detail_normal_texture_name is None and _looks_like_normal_texture(detail_texture_name):
        detail_normal_texture_name = detail_texture_name
        detail_texture_name = None

    return detail_texture_name, detail_normal_texture_name


def _resolve_ao_texture(material: MaterialData) -> str | None:
    if not material.isDynamic() or material.isLayered():
        return None

    texture_slots = material.getTextureSlots()
    if len(texture_slots) <= 3:
        return None

    ao_texture_name = texture_slots[3]
    if not ao_texture_name:
        return None

    return ao_texture_name


def _looks_like_normal_texture(texture_slot: str) -> bool:
    texture_name = MaterialData.getTexFileName(texture_slot).lower()
    return (
        texture_name.endswith("_n")
        or texture_name.endswith("_nm")
        or texture_name.endswith("_nrm")
        or "_normal" in texture_name
    )


def _detail_scale(material: MaterialData) -> tuple[float, float]:
    params = material.getParams()
    if "detail_scale_x" in params or "detail_scale_y" in params:
        return (
            max(_safe_float(params.get("detail_scale_x"), default=1.0), 1e-6),
            max(_safe_float(params.get("detail_scale_y"), default=1.0), 1e-6),
        )

    tile_prefix = "detail2" if material.detail1IsDiffuse() else "detail1"
    tile_u = params.get(f"{tile_prefix}_tile_u")
    tile_v = params.get(f"{tile_prefix}_tile_v")

    if tile_u is not None or tile_v is not None:
        u_value = max(_safe_float(tile_u, default=1.0), 1e-6)
        v_value = max(_safe_float(tile_v, default=1.0), 1e-6)
        return (1.0 / u_value, 1.0 / v_value)

    return (1.0, 1.0)


def _load_texture_image(texture_slot: str | None, material: MaterialData, texture_role: str) -> TextureImage | None:
    if texture_slot is None:
        return None

    texture_name = MaterialData.getTexFileName(texture_slot)
    texture_type = _texture_type_for_role(material, texture_role)
    cache_key = (texture_name, texture_type)
    if cache_key in _decoded_texture_cache:
        _decoded_texture_cache.move_to_end(cache_key)
        return _decoded_texture_cache[cache_key]

    matches = AssetCacher.getCachedAsset(DDSx, texture_name)
    if not matches:
        _decoded_texture_cache[cache_key] = None
        return None

    best_texture = getBestTex(material, matches)
    try:
        dds_data = best_texture.getDDS()
        image = _decode_texture_image(dds_data, texture_type)
        texture = TextureImage(
            name=texture_name,
            width=image.width,
            height=image.height,
            pixels=image.tobytes(),
        )
    except Exception:
        texture = None

    _decoded_texture_cache[cache_key] = texture
    while len(_decoded_texture_cache) > _MAX_TEXTURE_CACHE:
        _decoded_texture_cache.popitem(last=False)
    return texture


def _texture_type_for_role(material: MaterialData, texture_role: str) -> int:
    if texture_role in {"normal", "detail_normal"}:
        return TEXTURE_NORMAL
    return TEXTURE_GENERIC


def _decode_texture_image(dds_data: bytes, texture_type: int) -> Image.Image:
    image = Image.open(BytesIO(dds_data)).convert("RGBA")

    if texture_type == TEXTURE_NORMAL:
        red, green, _blue, alpha = image.split()
        white_channel = Image.new("L", image.size, 255)
        image = Image.merge("RGBA", (alpha, green, white_channel, red))

    return image.transpose(Image.FLIP_TOP_BOTTOM)


def _face_normal(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
    normal = np.cross(p1 - p0, p2 - p0)
    return _normalize(normal, fallback=np.array([0.0, 1.0, 0.0], dtype=np.float32))


def _face_tangent(
    p0: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    uv0: np.ndarray,
    uv1: np.ndarray,
    uv2: np.ndarray,
) -> np.ndarray:
    edge1 = p1 - p0
    edge2 = p2 - p0
    delta_uv1 = uv1 - uv0
    delta_uv2 = uv2 - uv0

    determinant = float(delta_uv1[0] * delta_uv2[1] - delta_uv2[0] * delta_uv1[1])
    if abs(determinant) <= 1e-8:
        return np.array([1.0, 0.0, 0.0], dtype=np.float32)

    scale = 1.0 / determinant
    tangent = scale * (delta_uv2[1] * edge1 - delta_uv1[1] * edge2)
    return _normalize(tangent, fallback=np.array([1.0, 0.0, 0.0], dtype=np.float32))


def _orthogonalize_tangent(tangent: np.ndarray, normal: np.ndarray) -> np.ndarray:
    adjusted = tangent - normal * float(np.dot(normal, tangent))
    return _normalize(adjusted, fallback=np.array([1.0, 0.0, 0.0], dtype=np.float32))


def _iter_material_ranges(obj) -> list[tuple[str, int, int]]:
    material_ranges: list[tuple[str, int, int]] = []
    material_starts = sorted(obj.materials.items())
    for range_index, (start_face_index, material_name) in enumerate(material_starts):
        end_face_index = material_starts[range_index + 1][0] if range_index + 1 < len(material_starts) else len(obj.faces)
        if end_face_index > start_face_index:
            material_ranges.append((material_name, start_face_index, end_face_index))
    return material_ranges


def _face_normals(face_positions: np.ndarray) -> np.ndarray:
    edge1 = face_positions[:, 1] - face_positions[:, 0]
    edge2 = face_positions[:, 2] - face_positions[:, 0]
    normals = np.cross(edge1, edge2)
    return _normalize_rows(normals, fallback=np.array([0.0, 1.0, 0.0], dtype=np.float32))


def _face_tangents(face_positions: np.ndarray, face_uvs: np.ndarray) -> np.ndarray:
    edge1 = face_positions[:, 1] - face_positions[:, 0]
    edge2 = face_positions[:, 2] - face_positions[:, 0]
    delta_uv1 = face_uvs[:, 1] - face_uvs[:, 0]
    delta_uv2 = face_uvs[:, 2] - face_uvs[:, 0]

    determinant = (delta_uv1[:, 0] * delta_uv2[:, 1]) - (delta_uv2[:, 0] * delta_uv1[:, 1])
    tangents = np.zeros_like(edge1)
    valid = np.abs(determinant) > 1e-8
    if np.any(valid):
        tangent_scale = (1.0 / determinant[valid])[:, None]
        tangents[valid] = tangent_scale * (
            (delta_uv2[valid, 1][:, None] * edge1[valid]) - (delta_uv1[valid, 1][:, None] * edge2[valid])
        )
    return _normalize_rows(tangents, fallback=np.array([1.0, 0.0, 0.0], dtype=np.float32))


def _orthogonalize_tangents(tangents: np.ndarray, normals: np.ndarray) -> np.ndarray:
    adjusted = tangents - normals * np.sum(normals * tangents, axis=1, keepdims=True)
    return _normalize_rows(adjusted, fallback=np.array([1.0, 0.0, 0.0], dtype=np.float32))


def _normalize_rows(vectors: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = np.divide(vectors, lengths, out=np.zeros_like(vectors), where=lengths > 1e-8)
    invalid = lengths[:, 0] <= 1e-8
    if np.any(invalid):
        normalized[invalid] = fallback
    return normalized.astype(np.float32, copy=False)


def _normalize(vector: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length <= 1e-8:
        return fallback.astype(np.float32)
    return (vector / length).astype(np.float32)


def _safe_float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
