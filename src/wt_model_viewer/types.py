from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

ALPHA_MODE_OPAQUE = 0
ALPHA_MODE_BLEND = 1
ALPHA_MODE_CUTOUT = 2

MATERIAL_MODE_STANDARD = 0
MATERIAL_MODE_MASKED_TANK = 1


@dataclass(frozen=True, slots=True)
class ModelIndexEntry:
    name: str
    group_path: str
    group_relpath: str
    resource_index: int

    @property
    def pack_name(self) -> str:
        return Path(self.group_path).stem


@dataclass(frozen=True, slots=True)
class ModelVariant:
    key: str
    label: str
    entry: ModelIndexEntry
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class ModelFamily:
    base_name: str
    primary_entry: ModelIndexEntry
    variants: tuple[ModelVariant, ...]
    search_text: str

    @property
    def pack_name(self) -> str:
        return self.primary_entry.pack_name

    @property
    def group_relpath(self) -> str:
        return self.primary_entry.group_relpath

    @property
    def variant_count(self) -> int:
        return len(self.variants)

    def default_variant(self) -> ModelVariant:
        for variant in self.variants:
            if variant.is_default:
                return variant
        return self.variants[0]

    def variant_by_key(self, key: str) -> ModelVariant:
        for variant in self.variants:
            if variant.key == key:
                return variant
        return self.default_variant()


@dataclass(slots=True)
class MeshBundle:
    vertices: np.ndarray
    faces: np.ndarray
    center: np.ndarray
    extent: float
    face_count: int
    vertex_count: int
    object_count: int


@dataclass(frozen=True, slots=True)
class TextureImage:
    name: str
    width: int
    height: int
    pixels: bytes


@dataclass(slots=True)
class SceneBatch:
    material_name: str
    interleaved: np.ndarray
    indices: np.ndarray
    diffuse_texture: TextureImage | None
    normal_texture: TextureImage | None
    ao_texture: TextureImage | None
    mask_texture: TextureImage | None
    detail_texture: TextureImage | None
    detail_normal_texture: TextureImage | None
    detail_scale: tuple[float, float]
    shader_class: str | None
    vertex_count: int
    index_count: int
    base_color: tuple[float, float, float]
    opacity: float
    alpha_mode: int
    alpha_cutoff: float
    material_mode: int
    ao_strength: float
    specular_scale: float
    gloss_floor: float
    fresnel_strength: float

    @property
    def textured(self) -> bool:
        return self.diffuse_texture is not None or self.detail_texture is not None

    @property
    def normal_mapped(self) -> bool:
        return self.normal_texture is not None or self.detail_normal_texture is not None


@dataclass(slots=True)
class RenderScene:
    batches: list[SceneBatch]
    center: np.ndarray
    extent: float
    face_count: int
    vertex_count: int
    object_count: int

    @property
    def textured_batch_count(self) -> int:
        return sum(1 for batch in self.batches if batch.textured)

    @property
    def normal_mapped_batch_count(self) -> int:
        return sum(1 for batch in self.batches if batch.normal_mapped)
