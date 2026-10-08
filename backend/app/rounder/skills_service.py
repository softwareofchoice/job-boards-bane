"""The skills library (RND-1): saved skill entries, each tied to a role on the resume."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.rounder.models import Skill
from app.rounder.schemas import SkillIn


class DuplicateSkillError(AppError):
    status_code = 409
    code = "duplicate_skill"


def _find_duplicate(
    session: Session, data: SkillIn, exclude: uuid.UUID | None = None
) -> Skill | None:
    query = select(Skill).where(
        func.lower(Skill.skill_name) == data.skill_name.lower(),
        func.lower(Skill.role) == data.role.lower(),
    )
    if exclude is not None:
        query = query.where(Skill.id != exclude)
    return session.scalars(query).first()


def _duplicate_error(existing: Skill) -> DuplicateSkillError:
    """RND-1.3: refuse, and give the UI the id it needs to offer "Edit existing"."""
    return DuplicateSkillError(
        f"“{existing.skill_name}” is already saved for the role “{existing.role}”.",
        existing_id=str(existing.id),
    )


def _commit_or_duplicate(session: Session, data: SkillIn, skill: Skill) -> None:
    try:
        session.commit()
    except IntegrityError:
        # Saved by another request between the check and the commit.
        session.rollback()
        existing = _find_duplicate(session, data)
        if existing is None:
            raise
        raise _duplicate_error(existing) from None
    session.refresh(skill)


def create_skill(session: Session, data: SkillIn) -> Skill:
    if existing := _find_duplicate(session, data):
        raise _duplicate_error(existing)
    skill = Skill(skill_name=data.skill_name, role=data.role, summary=data.summary)
    session.add(skill)
    _commit_or_duplicate(session, data, skill)
    return skill


def get_skill(session: Session, skill_id: uuid.UUID) -> Skill:
    skill = session.get(Skill, skill_id)
    if skill is None:
        raise NotFoundError("Skill not found.")
    return skill


def update_skill(session: Session, skill_id: uuid.UUID, data: SkillIn) -> Skill:
    skill = get_skill(session, skill_id)
    if existing := _find_duplicate(session, data, exclude=skill_id):
        raise _duplicate_error(existing)
    skill.skill_name, skill.role, skill.summary = data.skill_name, data.role, data.summary
    _commit_or_duplicate(session, data, skill)
    return skill


def delete_skill(session: Session, skill_id: uuid.UUID) -> None:
    session.delete(get_skill(session, skill_id))
    session.commit()


def list_skills(session: Session, role: str | None = None) -> list[Skill]:
    """Ordered by role, then skill name, so the UI can group them (RND-1.4)."""
    query = select(Skill).order_by(func.lower(Skill.role), func.lower(Skill.skill_name))
    if role:
        query = query.where(func.lower(Skill.role) == role.strip().lower())
    return list(session.scalars(query))


def list_roles(session: Session) -> list[str]:
    """Distinct roles, for suggestions in the role field (RND-1.1). Case variants are merged."""
    roles: dict[str, str] = {}
    for role in session.scalars(select(Skill.role).order_by(Skill.created_at)):
        roles.setdefault(role.lower(), role)
    return sorted(roles.values(), key=str.lower)


def count_skills(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Skill)) or 0
