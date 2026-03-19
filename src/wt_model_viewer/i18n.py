from __future__ import annotations

from pathlib import Path
from typing import Final


SUPPORTED_UI_LANGUAGES: Final[tuple[str, ...]] = ("en", "zh", "ja")

TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "window_title": "MLCCS-wt-viewer",
        "select_folder": "Select War Thunder Folder",
        "rescan": "Rescan",
        "load_selected": "Load Selected",
        "search": "Search",
        "search_placeholder": "Filter model name / pack / path",
        "language": "Language",
        "variant": "Variant",
        "lighting": "Light",
        "light_preset": "Preset",
        "light_preset_custom": "Custom",
        "light_preset_balanced": "Balanced",
        "light_preset_studio": "Studio",
        "light_preset_overcast": "Overcast",
        "light_preset_side": "Side",
        "light_azimuth": "Yaw {value}",
        "light_elevation": "Elevation {value}",
        "light_brightness": "Brightness {value}",
        "brand_subtitle": "WT VIEWER",
        "variant_default": "Default",
        "variant_dmg": "Damage",
        "variant_xray": "X-Ray",
        "language_auto": "Auto",
        "language_en": "English",
        "language_zh": "Chinese",
        "language_ja": "Japanese",
        "folder_none": "No folder selected",
        "folder_value": "Folder: {path}",
        "models_count": "Models: {count}",
        "ready": "Ready",
        "bootstrap_title": "Preparing application",
        "bootstrap_checking": "Checking required runtime files...",
        "bootstrap_downloading": "Downloading missing file {current}/{total}: {name}",
        "bootstrap_failed": "Failed to download required runtime files.\n\n{error}",
        "controls": "Controls: Left drag rotate, right or middle drag pan, wheel zoom.",
        "select_prompt": "Select a War Thunder folder to index models.",
        "scanning_overview": "Preparing descriptors, textures, and model index...",
        "scan_desc": "Loading descriptor {name}",
        "scan_texture": "Indexing textures {name}",
        "scan_group": "Scanning models {name}",
        "scan_scene": "Preparing scene {name}",
        "indexed_models": "Indexed {count} models",
        "load_status": "Loading {name}",
        "upload_scene": "Uploading {name}",
        "load_info": "Loading {name} from {path} ...",
        "loaded_status": "Loaded {name}",
        "load_summary": "{name}\nPack: {pack}\nSource: {path}\nVertices: {vertices}  Faces: {faces}  Objects: {objects}\nTextured batches: {textured}  Normal mapped batches: {normal_mapped}\n{controls}",
        "invalid_folder_title": "Invalid Folder",
        "invalid_folder": "Missing fixed resource path: {path}",
        "error_title": "Error",
        "operation_failed": "Operation failed",
        "table_model": "Model",
        "table_variants": "Variants",
        "table_pack": "Pack",
        "table_group": "Group",
    },
    "zh": {
        "window_title": "MLCCS-wt-viewer",
        "select_folder": "选择 War Thunder 文件夹",
        "rescan": "重新扫描",
        "load_selected": "加载选中模型",
        "search": "搜索",
        "search_placeholder": "按模型名 / 包名 / 路径过滤",
        "language": "语言",
        "variant": "变体",
        "lighting": "光照",
        "light_preset": "预设",
        "light_preset_custom": "自定义",
        "light_preset_balanced": "均衡",
        "light_preset_studio": "摄影棚",
        "light_preset_overcast": "阴天",
        "light_preset_side": "侧光",
        "light_azimuth": "方位 {value}",
        "light_elevation": "高度 {value}",
        "light_brightness": "亮度 {value}",
        "brand_subtitle": "WT VIEWER",
        "variant_default": "默认",
        "variant_dmg": "损坏",
        "variant_xray": "X-Ray",
        "language_auto": "自动",
        "language_en": "English",
        "language_zh": "中文",
        "language_ja": "日本語",
        "folder_none": "未选择文件夹",
        "folder_value": "目录：{path}",
        "models_count": "模型数：{count}",
        "ready": "就绪",
        "bootstrap_title": "正在准备程序",
        "bootstrap_checking": "正在检查运行时所需文件...",
        "bootstrap_downloading": "正在下载缺失文件 {current}/{total}: {name}",
        "bootstrap_failed": "下载运行时所需文件失败。\n\n{error}",
        "controls": "操作：左键拖动旋转，右键或中键拖动平移，滚轮缩放。",
        "select_prompt": "选择一个 War Thunder 根目录以建立模型索引。",
        "scanning_overview": "正在准备描述文件、贴图索引和模型索引...",
        "scan_desc": "正在加载描述文件 {name}",
        "scan_texture": "正在索引贴图 {name}",
        "scan_group": "正在扫描模型 {name}",
        "scan_scene": "正在准备场景 {name}",
        "indexed_models": "已索引 {count} 个模型",
        "load_status": "正在加载 {name}",
        "upload_scene": "正在上传 {name}",
        "load_info": "正在从 {path} 加载 {name} ...",
        "loaded_status": "已加载 {name}",
        "load_summary": "{name}\n资源包：{pack}\n来源：{path}\n顶点：{vertices}  面：{faces}  对象：{objects}\n贴图批次：{textured}  法线贴图批次：{normal_mapped}\n{controls}",
        "invalid_folder_title": "目录无效",
        "invalid_folder": "缺少固定资源路径：{path}",
        "error_title": "错误",
        "operation_failed": "操作失败",
        "table_model": "模型",
        "table_variants": "变体数",
        "table_pack": "资源包",
        "table_group": "路径",
    },
    "ja": {
        "window_title": "MLCCS-wt-viewer",
        "select_folder": "War Thunder フォルダーを選択",
        "rescan": "再スキャン",
        "load_selected": "選択モデルを読み込む",
        "search": "検索",
        "search_placeholder": "モデル名 / パック / パスで絞り込み",
        "language": "言語",
        "variant": "バリアント",
        "lighting": "ライト",
        "light_preset": "プリセット",
        "light_preset_custom": "カスタム",
        "light_preset_balanced": "標準",
        "light_preset_studio": "スタジオ",
        "light_preset_overcast": "曇天",
        "light_preset_side": "サイド",
        "light_azimuth": "方位 {value}",
        "light_elevation": "高さ {value}",
        "light_brightness": "明るさ {value}",
        "brand_subtitle": "WT VIEWER",
        "variant_default": "標準",
        "variant_dmg": "損傷",
        "variant_xray": "X-Ray",
        "language_auto": "自動",
        "language_en": "English",
        "language_zh": "中文",
        "language_ja": "日本語",
        "folder_none": "フォルダー未選択",
        "folder_value": "フォルダー: {path}",
        "models_count": "モデル数: {count}",
        "ready": "準備完了",
        "bootstrap_title": "アプリケーションを準備中",
        "bootstrap_checking": "必要な実行時ファイルを確認中...",
        "bootstrap_downloading": "不足ファイルをダウンロード中 {current}/{total}: {name}",
        "bootstrap_failed": "必要な実行時ファイルのダウンロードに失敗しました。\n\n{error}",
        "controls": "操作: 左ドラッグで回転、右または中ドラッグで移動、ホイールでズーム。",
        "select_prompt": "War Thunder のルートフォルダーを選択してモデル索引を作成します。",
        "scanning_overview": "記述ファイル、テクスチャ索引、モデル索引を準備中...",
        "scan_desc": "記述ファイルを読み込み中 {name}",
        "scan_texture": "テクスチャを索引中 {name}",
        "scan_group": "モデルを走査中 {name}",
        "scan_scene": "シーンを準備中 {name}",
        "indexed_models": "{count} 個のモデルを索引しました",
        "load_status": "{name} を読み込み中",
        "upload_scene": "{name} をアップロード中",
        "load_info": "{path} から {name} を読み込み中 ...",
        "loaded_status": "{name} を読み込みました",
        "load_summary": "{name}\nパック: {pack}\nソース: {path}\n頂点: {vertices}  面: {faces}  オブジェクト: {objects}\nテクスチャバッチ: {textured}  法線マップバッチ: {normal_mapped}\n{controls}",
        "invalid_folder_title": "無効なフォルダー",
        "invalid_folder": "固定リソースパスが見つかりません: {path}",
        "error_title": "エラー",
        "operation_failed": "処理に失敗しました",
        "table_model": "モデル",
        "table_variants": "バリアント数",
        "table_pack": "パック",
        "table_group": "パス",
    },
}


CLIENT_LANGUAGE_MAP: Final[dict[str, str]] = {
    "english": "en",
    "chinese": "zh",
    "japanese": "ja",
}


def tr(locale: str, key: str, **kwargs: object) -> str:
    language = locale if locale in SUPPORTED_UI_LANGUAGES else "en"
    template = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
    return template.format(**kwargs)


def detect_client_language(game_root: Path) -> str:
    config_path = Path(game_root) / "config.blk"
    if not config_path.exists():
        return "en"

    try:
        content = config_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "en"

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("language:t="):
            continue

        value = stripped.split("=", 1)[1].strip().strip('"')
        return CLIENT_LANGUAGE_MAP.get(value.lower(), "en")

    return "en"
