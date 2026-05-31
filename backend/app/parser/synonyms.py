"""标题样式中文同义词词典加载（§27.4 / Q208 / Q344 第一层）。

内置 ``data/heading_synonyms.yaml`` 随代码发布。运行时组织级 ``heading_style_map``
（DB 层）以 ``style_overrides`` 注入覆盖（延后至 M4，见 Q344）。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_DATA_FILE = Path(__file__).parent / "data" / "heading_synonyms.yaml"

_LEVEL_KEYS = {"level_1": 1, "level_2": 2, "level_3": 3}


@lru_cache(maxsize=1)
def load_default_synonyms() -> dict[str, int]:
    """加载内置同义词词典：``{样式名: 层级}``。文件缺失时返回空字典。

    平台默认底座；租户特异同义词不进本文件，走动态字典 tb_heading_style_rule（P1b/P2，
    按 company_id 隔离），解析时以 style_overrides 覆盖本表。
    """
    if not _DATA_FILE.exists():
        return {}
    raw = yaml.safe_load(_DATA_FILE.read_text(encoding="utf-8")) or {}
    mapping: dict[str, int] = {}
    for key, level in _LEVEL_KEYS.items():
        for name in raw.get(key, []) or []:
            mapping[str(name).strip()] = level
    return mapping
