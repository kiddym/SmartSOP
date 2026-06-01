"""团队 API（/api/v1/teams）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.team import Team
from app.models.user import User
from app.schemas.team import TeamCreate, TeamMembersSet, TeamRead, TeamUpdate
from app.services import team_service

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


def _ensure(team: Team | None, company_id: str) -> Team:
    if team is None or team.company_id != company_id:
        raise not_found("TEAM_NOT_FOUND", "团队不存在")
    return team


@router.get("", response_model=list[TeamRead])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TEAM_VIEW)),
):
    return [team_service.to_read(db, t) for t in team_service.list_teams(db)]


@router.post("", response_model=TeamRead, status_code=201)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TEAM_MANAGE)),
):
    team = team_service.create_team(db, payload, current_user.company_id)
    return team_service.to_read(db, team)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TEAM_MANAGE)),
):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team = team_service.update_team(db, team, payload)
    return team_service.to_read(db, team)


@router.put("/{team_id}/members", response_model=TeamRead)
def set_members(
    team_id: str,
    payload: TeamMembersSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TEAM_MANAGE)),
):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team = team_service.set_members(db, team, payload.user_ids, current_user.company_id)
    return team_service.to_read(db, team)


@router.delete("/{team_id}", status_code=204)
def delete_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.TEAM_MANAGE)),
):
    team = _ensure(team_service.get_team(db, team_id), current_user.company_id)
    team_service.delete_team(db, team)
