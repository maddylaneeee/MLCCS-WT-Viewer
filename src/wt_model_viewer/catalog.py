from __future__ import annotations

from collections import defaultdict

from .types import ModelFamily, ModelIndexEntry, ModelVariant


KNOWN_VARIANT_SUFFIXES: dict[str, str] = {
    "dmg": "dmg",
    "xray": "xray",
}

VARIANT_PRIORITY: dict[str, int] = {
    "default": 0,
    "dmg": 1,
    "xray": 2,
}


def split_variant_name(name: str) -> tuple[str, str, str]:
    lowered = name.lower()
    for suffix, label in KNOWN_VARIANT_SUFFIXES.items():
        token = f"_{suffix}"
        if lowered.endswith(token):
            return name[: -len(token)], suffix, label

    return name, "default", "default"


def build_model_families(entries: list[ModelIndexEntry]) -> list[ModelFamily]:
    buckets: dict[tuple[str, str], list[tuple[ModelIndexEntry, str, str]]] = defaultdict(list)

    for entry in entries:
        base_name, variant_key, variant_label = split_variant_name(entry.name)
        buckets[(entry.group_relpath.lower(), base_name.lower())].append((entry, variant_key, variant_label))

    families: list[ModelFamily] = []
    for (_, _), bucket in buckets.items():
        bucket.sort(
            key=lambda item: (
                VARIANT_PRIORITY.get(item[1], 99),
                item[0].name.lower(),
                item[0].pack_name.lower(),
                item[0].group_relpath.lower(),
            )
        )
        primary_entry = bucket[0][0]
        base_name = split_variant_name(primary_entry.name)[0]
        variants = tuple(
            ModelVariant(
                key=variant_key,
                label=variant_label,
                entry=entry,
                is_default=(index == 0 and variant_key == "default") or entry.name == base_name,
            )
            for index, (entry, variant_key, variant_label) in enumerate(bucket)
        )
        search_text = " ".join(
            [base_name, primary_entry.pack_name, primary_entry.group_relpath, *(entry.name for entry, _, _ in bucket)]
        ).lower()
        families.append(
            ModelFamily(
                base_name=base_name,
                primary_entry=primary_entry,
                variants=variants,
                search_text=search_text,
            )
        )

    families.sort(key=lambda item: (item.base_name.lower(), item.pack_name.lower(), item.group_relpath.lower()))
    return families
