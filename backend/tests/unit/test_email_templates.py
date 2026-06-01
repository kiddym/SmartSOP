"""邮件渲染：9 种类型按 params 出 (subject, body)。"""
from __future__ import annotations

from app.email.templates import render


def test_wo_assigned():
    subj, body = render("WO_ASSIGNED", {"custom_id": "WO1", "title": "换油"})
    assert "WO1" in subj
    assert "换油" in body


def test_unknown_type_falls_back():
    subj, body = render("SOMETHING_NEW", {"custom_id": "X"})
    assert subj  # 非空，不抛
    assert isinstance(body, str)


def test_part_low_stock():
    subj, body = render("PART_LOW_STOCK",
                        {"custom_id": "P1", "name": "滤芯", "quantity": "2", "min_quantity": "5"})
    assert "P1" in subj or "滤芯" in subj
    assert "5" in body
