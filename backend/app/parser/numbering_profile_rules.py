"""编号体例规则收口（P4 重构，行为等价于原 heading_detector 散落的 _RE_*）。

把内置编号正则集中为一个 ``NumberingProfile`` 对象；``load_default_profile()`` 返回
平台内置体例，``_classify_numbering_base`` 从 profile 取规则。正则与判定逻辑一字不改，
仅集中存放。``load_profile_for(company_id)`` 为 Phase 2 / 租户编号体例预留入口（租户特异
体例已由 P1d 的 numbering_overrides 注入承载，此处暂返回默认 profile）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CN_NUM = "一二三四五六七八九十百零两"


@dataclass(frozen=True)
class NumberingProfile:
    """一套编号识别正则（内置默认或 Phase 2 租户体例）。"""

    re_paren: re.Pattern[str]
    re_num_paren: re.Pattern[str]
    re_page: re.Pattern[str]
    re_cn_dunhao: re.Pattern[str]
    re_di_zhang: re.Pattern[str]
    re_di_jie: re.Pattern[str]
    re_di_tiao: re.Pattern[str]
    re_leading_num: re.Pattern[str]
    re_cjk: re.Pattern[str]


def load_default_profile() -> NumberingProfile:
    """平台内置编号体例（与原 heading_detector._RE_* 逐字节一致）。"""
    return NumberingProfile(
        # list（非标题）：(一)/（1）/N)/N）
        re_paren=re.compile(rf"^[(（]\s*[{_CN_NUM}\d]+\s*[)）]"),
        re_num_paren=re.compile(r"^\d+[)）]"),
        re_page=re.compile(r"^\d+\s*/\s*\d+$"),  # 页码 "1 / 2"
        re_cn_dunhao=re.compile(rf"^[{_CN_NUM}]+、"),  # 一、
        re_di_zhang=re.compile(rf"^第[{_CN_NUM}\d]+章"),
        re_di_jie=re.compile(rf"^第[{_CN_NUM}\d]+节"),
        re_di_tiao=re.compile(rf"^第[{_CN_NUM}\d]+条"),
        re_leading_num=re.compile(r"^(\d+(?:\.\d+)*)"),
        re_cjk=re.compile(r"[一-鿿]"),
    )


def load_profile_for(company_id: str | None = None) -> NumberingProfile:
    """租户编号体例入口（结构留缝）；暂返回平台默认 profile。"""
    return load_default_profile()
