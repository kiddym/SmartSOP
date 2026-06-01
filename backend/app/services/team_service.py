"""团队服务（含成员设置）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.team import Team, TeamUser
from app.schemas.team import TeamCreate, TeamUpdate


def _member_ids(db: Session, team_id: str) -> list[str]:
    return list(
        db.execute(select(TeamUser.user_id).where(TeamUser.team_id == team_id)).scalars().all()
    )


def to_read(db: Session, team: Team) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "member_ids": _member_ids(db, team.id),
    }


def create_team(db: Session, payload: TeamCreate, company_id: str) -> Team:
    team = Team(name=payload.name, description=payload.description, company_id=company_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def list_teams(db: Session) -> list[Team]:
    return list(db.execute(select(Team).where(Team.is_active.is_(True))).scalars().all())


def get_team(db: Session, team_id: str) -> Team | None:
    team = db.get(Team, team_id)
    if team is None or not team.is_active:
        return None
    return team


def update_team(db: Session, team: Team, payload: TeamUpdate) -> Team:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(team, k, v)
    db.commit()
    db.refresh(team)
    return team


def delete_team(db: Session, team: Team) -> None:
    team.is_active = False
    team.deleted_at = utcnow()
    db.commit()


def set_members(db: Session, team: Team, user_ids: list[str], company_id: str) -> Team:
    db.execute(delete(TeamUser).where(TeamUser.team_id == team.id))
    for uid in dict.fromkeys(user_ids):  # 去重保序
        db.add(TeamUser(team_id=team.id, user_id=uid, company_id=company_id))
    db.commit()
    db.refresh(team)
    return team
