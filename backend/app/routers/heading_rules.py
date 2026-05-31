"""动态标题字典-样式规则路由（动态标题字典与自学习方案 M1）。

端点（管理员手动维护，解析时 active 规则即时生效）：
  GET    /api/v1/heading-rules        — 列表
  POST   /api/v1/heading-rules        — 创建（201）
  PUT    /api/v1/heading-rules/{id}   — 更新 level / status
  DELETE /api/v1/heading-rules/{id}   — 软删（204）

事务边界：service 只 flush，本路由在每个写操作末尾 commit。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleOut, HeadingRuleUpdate
from app.schemas.numbering_profile import (
    NumberingProfileCreate,
    NumberingProfileOut,
    NumberingProfileUpdate,
)
from app.services import heading_rule_service, numbering_profile_service

router = APIRouter(prefix="/api/v1", tags=["heading-rules"])


@router.get("/heading-rules", response_model=list[HeadingRuleOut])
def list_heading_rules(db: Session = Depends(get_db)) -> list[HeadingRuleOut]:
    """列出全部动态样式规则（GET /heading-rules）。"""
    return [HeadingRuleOut.model_validate(r) for r in heading_rule_service.list_rules(db)]


@router.post("/heading-rules", response_model=HeadingRuleOut, status_code=status.HTTP_201_CREATED)
def create_heading_rule(
    payload: HeadingRuleCreate, db: Session = Depends(get_db)
) -> HeadingRuleOut:
    """新增样式规则（POST /heading-rules，201）。"""
    rule = heading_rule_service.create(db, payload)
    db.commit()
    db.refresh(rule)
    return HeadingRuleOut.model_validate(rule)


@router.put("/heading-rules/{rule_id}", response_model=HeadingRuleOut)
def update_heading_rule(
    rule_id: str, payload: HeadingRuleUpdate, db: Session = Depends(get_db)
) -> HeadingRuleOut:
    """更新 level / status（PUT /heading-rules/{id}）。"""
    rule = heading_rule_service.get_or_404(db, rule_id)
    heading_rule_service.update(db, rule, payload)
    db.commit()
    db.refresh(rule)
    return HeadingRuleOut.model_validate(rule)


@router.delete("/heading-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_heading_rule(rule_id: str, db: Session = Depends(get_db)) -> Response:
    """软删样式规则（DELETE /heading-rules/{id}，204）。"""
    rule = heading_rule_service.get_or_404(db, rule_id)
    heading_rule_service.delete(db, rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# 编号体例（M4b）：/numbering-profiles
# --------------------------------------------------------------------------- #
@router.get("/numbering-profiles", response_model=list[NumberingProfileOut])
def list_numbering_profiles(db: Session = Depends(get_db)) -> list[NumberingProfileOut]:
    """列出全部编号体例（GET /numbering-profiles）。"""
    return [
        NumberingProfileOut.model_validate(p)
        for p in numbering_profile_service.list_profiles(db)
    ]


@router.post(
    "/numbering-profiles", response_model=NumberingProfileOut, status_code=status.HTTP_201_CREATED
)
def create_numbering_profile(
    payload: NumberingProfileCreate, db: Session = Depends(get_db)
) -> NumberingProfileOut:
    """新增编号体例（POST /numbering-profiles，201）。"""
    p = numbering_profile_service.create(db, payload)
    db.commit()
    db.refresh(p)
    return NumberingProfileOut.model_validate(p)


@router.put("/numbering-profiles/{profile_id}", response_model=NumberingProfileOut)
def update_numbering_profile(
    profile_id: str, payload: NumberingProfileUpdate, db: Session = Depends(get_db)
) -> NumberingProfileOut:
    """更新 kind / level / status（PUT /numbering-profiles/{id}）。"""
    p = numbering_profile_service.get_or_404(db, profile_id)
    numbering_profile_service.update(db, p, payload)
    db.commit()
    db.refresh(p)
    return NumberingProfileOut.model_validate(p)


@router.delete("/numbering-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_numbering_profile(profile_id: str, db: Session = Depends(get_db)) -> Response:
    """软删编号体例（DELETE /numbering-profiles/{id}，204）。"""
    p = numbering_profile_service.get_or_404(db, profile_id)
    numbering_profile_service.delete(db, p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
