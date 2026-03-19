from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_ELEMENT_ARRAY_BUFFER,
    GL_FALSE,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LINEAR,
    GL_LINEAR_MIPMAP_LINEAR,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_STATIC_DRAW,
    GL_TEXTURE0,
    GL_TEXTURE1,
    GL_TEXTURE2,
    GL_TEXTURE3,
    GL_TEXTURE4,
    GL_TEXTURE5,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_TRUE,
    GL_UNSIGNED_BYTE,
    GL_UNSIGNED_INT,
    GL_UNSIGNED_SHORT,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glBindBuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glClear,
    glClearColor,
    glDepthMask,
    glDeleteBuffers,
    glDeleteProgram,
    glDeleteTextures,
    glDeleteVertexArrays,
    glDrawArrays,
    glDrawElements,
    glEnable,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenTextures,
    glGenVertexArrays,
    glGenerateMipmap,
    glGetUniformLocation,
    glTexImage2D,
    glTexParameteri,
    glUniform1f,
    glUniform1i,
    glUniform2f,
    glUniform3f,
    glUniformMatrix4fv,
    glUseProgram,
    glVertexAttribPointer,
    glViewport,
)
from OpenGL.GL.shaders import compileProgram, compileShader
from PyQt5.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QMatrix4x4, QVector3D
from PyQt5.QtWidgets import QOpenGLWidget

from .types import ALPHA_MODE_BLEND, RenderScene, SceneBatch, TextureImage


VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec3 a_position;
layout (location = 1) in vec3 a_normal;
layout (location = 2) in vec3 a_tangent;
layout (location = 3) in vec2 a_uv;

uniform mat4 u_mvp;

out vec3 v_position;
out vec3 v_normal;
out vec3 v_tangent;
out vec2 v_uv;

void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
    v_position = a_position;
    v_normal = a_normal;
    v_tangent = a_tangent;
    v_uv = a_uv;
}
"""


FRAGMENT_SHADER = """
#version 330 core
in vec3 v_position;
in vec3 v_normal;
in vec3 v_tangent;
in vec2 v_uv;

uniform sampler2D u_diffuse_texture;
uniform sampler2D u_normal_texture;
uniform sampler2D u_ao_texture;
uniform sampler2D u_mask_texture;
uniform sampler2D u_detail_texture;
uniform sampler2D u_detail_normal_texture;
uniform int u_has_diffuse_texture;
uniform int u_has_normal_texture;
uniform int u_has_ao_texture;
uniform int u_has_mask_texture;
uniform int u_has_detail_texture;
uniform int u_has_detail_normal_texture;
uniform vec2 u_detail_scale;
uniform vec3 u_base_color;
uniform float u_opacity;
uniform vec3 u_camera_pos;
uniform vec3 u_light_dir;
uniform float u_light_intensity;
uniform float u_ao_strength;
uniform float u_specular_scale;
uniform float u_gloss_floor;
uniform float u_fresnel_strength;
uniform int u_alpha_mode;
uniform float u_alpha_cutoff;
uniform int u_material_mode;

out vec4 frag_color;

void main() {
    vec4 diffuse_sample = vec4(u_base_color, 1.0);
    if (u_has_diffuse_texture == 1) {
        diffuse_sample = texture(u_diffuse_texture, v_uv);
    }

    vec3 albedo = diffuse_sample.rgb;
    float sampled_alpha = diffuse_sample.a * u_opacity;
    float alpha = u_opacity;

    vec4 mask_sample = vec4(1.0);
    vec2 detail_uv = v_uv * u_detail_scale;
    float detail_mask = 0.35;
    if (u_has_mask_texture == 1) {
        mask_sample = texture(u_mask_texture, v_uv);
        detail_mask = mask_sample.r;
    }

    if (u_material_mode == 1 && u_has_mask_texture == 1 && u_has_diffuse_texture == 1) {
        float camo_weight = clamp(diffuse_sample.a, 0.0, 1.0);
        float albedo_luma = dot(albedo, vec3(0.299, 0.587, 0.114));
        vec3 camo_albedo = clamp(mask_sample.rgb * (0.35 + albedo_luma * 1.15), 0.0, 1.0);
        albedo = mix(albedo, camo_albedo, camo_weight);
        sampled_alpha = u_opacity;
    }

    if (u_alpha_mode == 1) {
        alpha = sampled_alpha;
    } else if (u_alpha_mode == 2) {
        if (sampled_alpha <= u_alpha_cutoff) {
            discard;
        }
        alpha = u_opacity;
    }

    if (u_has_detail_texture == 1) {
        vec3 detail_rgb = texture(u_detail_texture, detail_uv).rgb;
        vec3 layered = clamp(albedo * (detail_rgb * 2.0), 0.0, 1.0);
        albedo = mix(albedo, layered, clamp(detail_mask, 0.0, 1.0));
    }

    if (u_alpha_mode == 1 && alpha <= 0.01) {
        discard;
    }

    vec3 normal_dir = normalize(v_normal);
    vec3 tangent_dir = normalize(v_tangent - dot(v_tangent, normal_dir) * normal_dir);
    vec3 bitangent_dir = normalize(cross(normal_dir, tangent_dir));
    mat3 tbn = mat3(tangent_dir, bitangent_dir, normal_dir);

    vec3 tangent_normal = vec3(0.0, 0.0, 1.0);
    float gloss = 0.18;
    if (u_has_normal_texture == 1) {
        vec4 normal_sample = texture(u_normal_texture, v_uv);
        tangent_normal = normalize(normal_sample.xyz * 2.0 - 1.0);
        gloss = max(gloss, normal_sample.a);
    }
    gloss = max(gloss, u_gloss_floor);

    if (u_has_detail_normal_texture == 1) {
        vec3 detail_normal = texture(u_detail_normal_texture, detail_uv).xyz * 2.0 - 1.0;
        tangent_normal = normalize(mix(tangent_normal, detail_normal, clamp(detail_mask, 0.0, 1.0)));
    }

    float ao = 1.0;
    if (u_has_ao_texture == 1) {
        ao = texture(u_ao_texture, v_uv).r;
        ao = clamp(mix(0.55, 1.0, ao), 0.0, 1.0);
    }
    ao = mix(1.0, ao, clamp(u_ao_strength, 0.0, 1.0));

    vec3 surface_normal = normalize(tbn * tangent_normal);
    vec3 light_dir = normalize(u_light_dir);
    vec3 view_dir = normalize(u_camera_pos - v_position);
    vec3 half_dir = normalize(light_dir + view_dir);
    float light_intensity = max(u_light_intensity, 0.0);

    float diffuse = max(dot(surface_normal, light_dir), 0.0);
    float spec_power = mix(8.0, 64.0, clamp(gloss, 0.0, 1.0));
    float spec_strength = mix(0.03, 0.28, clamp(gloss, 0.0, 1.0));
    float specular =
        pow(max(dot(surface_normal, half_dir), 0.0), spec_power) * spec_strength * light_intensity * u_specular_scale;
    float fresnel = pow(1.0 - max(dot(surface_normal, view_dir), 0.0), 4.0) * u_fresnel_strength * light_intensity;

    vec3 ambient = albedo * mix(0.14, 0.30, ao);
    vec3 lit = ambient + (albedo * diffuse * (0.76 * light_intensity * mix(0.80, 1.0, ao))) + vec3(specular + fresnel);
    frag_color = vec4(lit, alpha);
}
"""


@dataclass
class _GpuBatch:
    vao: int
    vbo: int
    ebo: int
    vertex_count: int
    index_count: int
    index_gl_type: int
    diffuse_texture_id: int | None
    normal_texture_id: int | None
    ao_texture_id: int | None
    mask_texture_id: int | None
    detail_texture_id: int | None
    detail_normal_texture_id: int | None
    detail_scale: tuple[float, float]
    base_color: tuple[float, float, float]
    opacity: float
    alpha_mode: int
    alpha_cutoff: float
    material_mode: int
    ao_strength: float
    specular_scale: float
    gloss_floor: float
    fresnel_strength: float


class ModelViewport(QOpenGLWidget):
    scene_upload_progress = pyqtSignal(int, int)
    scene_upload_finished = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self._program: int | None = None
        self._u_mvp = -1
        self._u_camera_pos = -1
        self._u_light_dir = -1
        self._u_light_intensity = -1
        self._u_ao_strength = -1
        self._u_specular_scale = -1
        self._u_gloss_floor = -1
        self._u_fresnel_strength = -1
        self._u_base_color = -1
        self._u_detail_scale = -1
        self._u_opacity = -1
        self._u_alpha_mode = -1
        self._u_alpha_cutoff = -1
        self._u_material_mode = -1
        self._u_has_diffuse = -1
        self._u_has_normal = -1
        self._u_has_ao = -1
        self._u_has_mask = -1
        self._u_has_detail = -1
        self._u_has_detail_normal = -1
        self._batches: list[_GpuBatch] = []
        self._scene: RenderScene | None = None
        self._pending_batches: deque[SceneBatch] = deque()
        self._pending_batch_total = 0
        self._texture_ids_by_key: dict[int, int] = {}
        self._texture_refs_by_id: dict[int, int] = {}
        self._texture_keys_by_id: dict[int, int] = {}
        self._upload_timer = QTimer(self)
        self._upload_timer.setInterval(0)
        self._upload_timer.timeout.connect(self._upload_next_chunk)

        self._yaw = -38.0
        self._pitch = -18.0
        self._distance = 10.0
        self._target = np.zeros(3, dtype=np.float32)
        self._last_pos = QPoint()
        self._light_azimuth = 69.0
        self._light_elevation = 30.0
        self._light_intensity = 1.25

    def has_mesh(self) -> bool:
        return self._scene is not None and (bool(self._batches) or bool(self._pending_batches))

    def clear_mesh(self) -> None:
        self._cancel_pending_upload()
        if self.isValid():
            self.makeCurrent()
            self._destroy_batches()
            self.doneCurrent()
        else:
            self._batches = []
        self._scene = None
        self.update()

    def set_scene(self, scene: RenderScene) -> None:
        self._cancel_pending_upload()
        if self.isValid():
            self.makeCurrent()
            self._destroy_batches()
        else:
            self._batches = []

        self._scene = scene
        self._pending_batches = deque(scene.batches)
        self._pending_batch_total = len(scene.batches)

        self._distance = max(6.0, scene.extent * 2.8)
        self._yaw = -38.0
        self._pitch = -18.0
        self._target = np.zeros(3, dtype=np.float32)
        if self.isValid():
            self.doneCurrent()
            self._start_pending_upload()
        self.update()

    def initializeGL(self) -> None:
        glClearColor(0.08, 0.10, 0.14, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._program = compileProgram(
            compileShader(VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
        )
        self._u_mvp = glGetUniformLocation(self._program, "u_mvp")
        self._u_camera_pos = glGetUniformLocation(self._program, "u_camera_pos")
        self._u_light_dir = glGetUniformLocation(self._program, "u_light_dir")
        self._u_light_intensity = glGetUniformLocation(self._program, "u_light_intensity")
        self._u_ao_strength = glGetUniformLocation(self._program, "u_ao_strength")
        self._u_specular_scale = glGetUniformLocation(self._program, "u_specular_scale")
        self._u_gloss_floor = glGetUniformLocation(self._program, "u_gloss_floor")
        self._u_fresnel_strength = glGetUniformLocation(self._program, "u_fresnel_strength")
        self._u_base_color = glGetUniformLocation(self._program, "u_base_color")
        self._u_detail_scale = glGetUniformLocation(self._program, "u_detail_scale")
        self._u_opacity = glGetUniformLocation(self._program, "u_opacity")
        self._u_alpha_mode = glGetUniformLocation(self._program, "u_alpha_mode")
        self._u_alpha_cutoff = glGetUniformLocation(self._program, "u_alpha_cutoff")
        self._u_material_mode = glGetUniformLocation(self._program, "u_material_mode")
        self._u_has_diffuse = glGetUniformLocation(self._program, "u_has_diffuse_texture")
        self._u_has_normal = glGetUniformLocation(self._program, "u_has_normal_texture")
        self._u_has_ao = glGetUniformLocation(self._program, "u_has_ao_texture")
        self._u_has_mask = glGetUniformLocation(self._program, "u_has_mask_texture")
        self._u_has_detail = glGetUniformLocation(self._program, "u_has_detail_texture")
        self._u_has_detail_normal = glGetUniformLocation(self._program, "u_has_detail_normal_texture")

        glUseProgram(self._program)
        glUniform1i(glGetUniformLocation(self._program, "u_diffuse_texture"), 0)
        glUniform1i(glGetUniformLocation(self._program, "u_normal_texture"), 1)
        glUniform1i(glGetUniformLocation(self._program, "u_ao_texture"), 2)
        glUniform1i(glGetUniformLocation(self._program, "u_mask_texture"), 3)
        glUniform1i(glGetUniformLocation(self._program, "u_detail_texture"), 4)
        glUniform1i(glGetUniformLocation(self._program, "u_detail_normal_texture"), 5)
        glUseProgram(0)

        if self._scene is not None:
            self._start_pending_upload()

    def resizeGL(self, width: int, height: int) -> None:
        glViewport(0, 0, max(1, width), max(1, height))

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._program is None or not self._batches:
            return

        projection = QMatrix4x4()
        aspect = self.width() / max(1.0, float(self.height()))
        projection.perspective(45.0, aspect, 0.1, max(10000.0, self._distance * 10.0))

        eye = self._camera_position()
        view = QMatrix4x4()
        view.lookAt(
            QVector3D(*eye.tolist()),
            QVector3D(*self._target.tolist()),
            QVector3D(0.0, 1.0, 0.0),
        )

        mvp = projection * view

        glUseProgram(self._program)
        glUniformMatrix4fv(self._u_mvp, 1, GL_FALSE, mvp.data())
        glUniform3f(self._u_camera_pos, *eye.tolist())
        glUniform3f(self._u_light_dir, *self._light_direction().tolist())
        glUniform1f(self._u_light_intensity, self._light_intensity)

        glDepthMask(GL_TRUE)
        for batch in self._batches:
            if batch.alpha_mode == ALPHA_MODE_BLEND:
                continue
            self._draw_batch(batch)

        glDepthMask(GL_FALSE)
        for batch in self._batches:
            if batch.alpha_mode != ALPHA_MODE_BLEND:
                continue
            self._draw_batch(batch)
        glDepthMask(GL_TRUE)

        glBindVertexArray(0)
        glUseProgram(0)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._last_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        delta = event.pos() - self._last_pos
        self._last_pos = event.pos()

        if event.buttons() & Qt.LeftButton:
            self._yaw -= delta.x() * 0.5
            self._pitch = float(np.clip(self._pitch - delta.y() * 0.5, -89.0, 89.0))
            self.update()
        elif event.buttons() & (Qt.MiddleButton | Qt.RightButton):
            self._pan(delta.x(), delta.y())
            self.update()

        super().mouseMoveEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        angle = event.angleDelta().y() / 120.0
        self._distance *= 0.9 ** angle
        self._distance = float(np.clip(self._distance, 0.5, 50000.0))
        self.update()
        super().wheelEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._cancel_pending_upload()
        if self.isValid():
            self.makeCurrent()
            self._destroy_batches()
            if self._program is not None:
                glDeleteProgram(self._program)
                self._program = None
            self.doneCurrent()
        super().closeEvent(event)

    def _camera_position(self) -> np.ndarray:
        yaw = np.radians(self._yaw)
        pitch = np.radians(self._pitch)

        direction = np.array(
            [
                np.cos(pitch) * np.cos(yaw),
                np.sin(pitch),
                np.cos(pitch) * np.sin(yaw),
            ],
            dtype=np.float32,
        )
        return self._target + direction * self._distance

    def _light_direction(self) -> np.ndarray:
        azimuth = np.radians(self._light_azimuth)
        elevation = np.radians(self._light_elevation)
        return np.array(
            [
                np.cos(elevation) * np.cos(azimuth),
                np.sin(elevation),
                np.cos(elevation) * np.sin(azimuth),
            ],
            dtype=np.float32,
        )

    def set_light_angles(self, azimuth: float, elevation: float) -> None:
        self._light_azimuth = float(np.clip(azimuth, -180.0, 180.0))
        self._light_elevation = float(np.clip(elevation, 5.0, 85.0))
        self.update()

    def set_light_intensity(self, intensity: float) -> None:
        self._light_intensity = float(np.clip(intensity, 0.2, 2.5))
        self.update()

    def _pan(self, dx: float, dy: float) -> None:
        eye = self._camera_position()
        forward = self._target - eye
        forward = forward / max(np.linalg.norm(forward), 1e-6)
        right = np.cross(forward, np.array([0.0, 1.0, 0.0], dtype=np.float32))
        right = right / max(np.linalg.norm(right), 1e-6)
        up = np.cross(right, forward)
        scale = self._distance * 0.0015
        self._target += (-right * dx + up * dy) * scale

    def _create_batch(self, batch: SceneBatch) -> _GpuBatch:
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, batch.interleaved.nbytes, batch.interleaved, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, batch.indices.nbytes, batch.indices, GL_STATIC_DRAW)

        stride = 11 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, False, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 3, GL_FLOAT, False, stride, ctypes.c_void_p(24))
        glEnableVertexAttribArray(3)
        glVertexAttribPointer(3, 2, GL_FLOAT, False, stride, ctypes.c_void_p(36))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        return _GpuBatch(
            vao=vao,
            vbo=vbo,
            ebo=ebo,
            vertex_count=batch.vertex_count,
            index_count=batch.index_count,
            index_gl_type=GL_UNSIGNED_SHORT if batch.indices.dtype == np.uint16 else GL_UNSIGNED_INT,
            diffuse_texture_id=self._upload_texture(batch.diffuse_texture),
            normal_texture_id=self._upload_texture(batch.normal_texture),
            ao_texture_id=self._upload_texture(batch.ao_texture),
            mask_texture_id=self._upload_texture(batch.mask_texture),
            detail_texture_id=self._upload_texture(batch.detail_texture),
            detail_normal_texture_id=self._upload_texture(batch.detail_normal_texture),
            detail_scale=batch.detail_scale,
            base_color=batch.base_color,
            opacity=batch.opacity,
            alpha_mode=batch.alpha_mode,
            alpha_cutoff=batch.alpha_cutoff,
            material_mode=batch.material_mode,
            ao_strength=batch.ao_strength,
            specular_scale=batch.specular_scale,
            gloss_floor=batch.gloss_floor,
            fresnel_strength=batch.fresnel_strength,
        )

    def _upload_texture(self, texture: TextureImage | None) -> int | None:
        if texture is None:
            return None

        texture_key = id(texture)
        cached_texture_id = self._texture_ids_by_key.get(texture_key)
        if cached_texture_id is not None:
            self._texture_refs_by_id[cached_texture_id] = self._texture_refs_by_id.get(cached_texture_id, 0) + 1
            return cached_texture_id

        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            texture.width,
            texture.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            texture.pixels,
        )
        glGenerateMipmap(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, 0)
        self._texture_ids_by_key[texture_key] = texture_id
        self._texture_refs_by_id[texture_id] = 1
        self._texture_keys_by_id[texture_id] = texture_key
        return texture_id

    def _bind_texture(self, texture_unit: int, texture_id: int | None) -> None:
        glActiveTexture(texture_unit)
        glBindTexture(GL_TEXTURE_2D, texture_id or 0)

    def _draw_batch(self, batch: _GpuBatch) -> None:
        glBindVertexArray(batch.vao)
        self._bind_texture(GL_TEXTURE0, batch.diffuse_texture_id)
        self._bind_texture(GL_TEXTURE1, batch.normal_texture_id)
        self._bind_texture(GL_TEXTURE2, batch.ao_texture_id)
        self._bind_texture(GL_TEXTURE3, batch.mask_texture_id)
        self._bind_texture(GL_TEXTURE4, batch.detail_texture_id)
        self._bind_texture(GL_TEXTURE5, batch.detail_normal_texture_id)

        glUniform1i(self._u_has_diffuse, 1 if batch.diffuse_texture_id is not None else 0)
        glUniform1i(self._u_has_normal, 1 if batch.normal_texture_id is not None else 0)
        glUniform1i(self._u_has_ao, 1 if batch.ao_texture_id is not None else 0)
        glUniform1i(self._u_has_mask, 1 if batch.mask_texture_id is not None else 0)
        glUniform1i(self._u_has_detail, 1 if batch.detail_texture_id is not None else 0)
        glUniform1i(self._u_has_detail_normal, 1 if batch.detail_normal_texture_id is not None else 0)
        glUniform2f(self._u_detail_scale, batch.detail_scale[0], batch.detail_scale[1])
        glUniform3f(self._u_base_color, *batch.base_color)
        glUniform1f(self._u_opacity, batch.opacity)
        glUniform1f(self._u_ao_strength, batch.ao_strength)
        glUniform1f(self._u_specular_scale, batch.specular_scale)
        glUniform1f(self._u_gloss_floor, batch.gloss_floor)
        glUniform1f(self._u_fresnel_strength, batch.fresnel_strength)
        glUniform1i(self._u_alpha_mode, batch.alpha_mode)
        glUniform1f(self._u_alpha_cutoff, batch.alpha_cutoff)
        glUniform1i(self._u_material_mode, batch.material_mode)
        glDrawElements(GL_TRIANGLES, batch.index_count, batch.index_gl_type, None)

    def _destroy_batches(self) -> None:
        for batch in self._batches:
            for texture_id in (
                batch.diffuse_texture_id,
                batch.normal_texture_id,
                batch.ao_texture_id,
                batch.mask_texture_id,
                batch.detail_texture_id,
                batch.detail_normal_texture_id,
            ):
                self._release_texture(texture_id)
            glDeleteBuffers(2, [batch.vbo, batch.ebo])
            glDeleteVertexArrays(1, [batch.vao])
        self._batches = []
        self._texture_ids_by_key.clear()
        self._texture_refs_by_id.clear()
        self._texture_keys_by_id.clear()

    def _release_texture(self, texture_id: int | None) -> None:
        if texture_id is None:
            return

        ref_count = self._texture_refs_by_id.get(texture_id, 0) - 1
        if ref_count > 0:
            self._texture_refs_by_id[texture_id] = ref_count
            return

        self._texture_refs_by_id.pop(texture_id, None)
        texture_key = self._texture_keys_by_id.pop(texture_id, None)
        if texture_key is not None:
            self._texture_ids_by_key.pop(texture_key, None)
        glDeleteTextures([texture_id])

    def _start_pending_upload(self) -> None:
        if self._program is None:
            return
        if self._pending_batch_total == 0:
            self.scene_upload_finished.emit()
            return
        self.scene_upload_progress.emit(0, self._pending_batch_total)
        self._upload_timer.start()

    def _upload_next_chunk(self) -> None:
        if self._program is None or not self._pending_batches:
            self._upload_timer.stop()
            if self._pending_batch_total:
                self.scene_upload_finished.emit()
            return

        started_at = perf_counter()
        uploaded_count = self._pending_batch_total - len(self._pending_batches)
        self.makeCurrent()
        try:
            while self._pending_batches:
                batch = self._pending_batches.popleft()
                self._batches.append(self._create_batch(batch))
                batch.interleaved = np.empty((0, 11), dtype=np.float32)
                batch.indices = np.empty(0, dtype=np.uint32)
                uploaded_count += 1
                if uploaded_count >= self._pending_batch_total:
                    break
                if perf_counter() - started_at >= 0.008:
                    break
        finally:
            self.doneCurrent()

        self.scene_upload_progress.emit(uploaded_count, self._pending_batch_total)
        self.update()

        if not self._pending_batches:
            self._upload_timer.stop()
            self.scene_upload_finished.emit()

    def _cancel_pending_upload(self) -> None:
        self._upload_timer.stop()
        self._pending_batches.clear()
        self._pending_batch_total = 0
