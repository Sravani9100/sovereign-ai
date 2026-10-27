"""Creating an organization with safe defaults."""

from sqlalchemy.orm import Session

from sovereign.config import Settings
from sovereign.models import (
    Classification,
    KnowledgeSpace,
    Membership,
    ModelProfile,
    Organization,
    Permission,
    PrincipalType,
    Provider,
    Role,
    SpaceGrant,
    User,
)


def create_organization(
    session: Session, settings: Settings, *, name: str, slug: str, owner: User
) -> tuple[Organization, Membership]:
    org = Organization(name=name, slug=slug)
    session.add(org)
    session.flush()
    membership = Membership(organization_id=org.id, user_id=owner.id, role=Role.OWNER)
    session.add(membership)
    session.add_all(
        [
            # External API: only internal-classified content may be sent to it.
            ModelProfile(
                organization_id=org.id,
                name="claude",
                provider=Provider.ANTHROPIC,
                model=settings.anthropic_model,
                max_classification=Classification.INTERNAL,
                is_default=True,
            ),
            # Self-hosted: allowed to see confidential content. Disabled until an admin
            # confirms Ollama is running.
            ModelProfile(
                organization_id=org.id,
                name="local-private",
                provider=Provider.OLLAMA,
                model=settings.ollama_model,
                max_classification=Classification.CONFIDENTIAL,
                enabled=False,
            ),
        ]
    )
    session.flush()
    handbook = KnowledgeSpace(
        organization_id=org.id,
        name="Company Handbook",
        description="Policies every employee can read.",
    )
    session.add(handbook)
    session.flush()
    session.add_all(
        [
            SpaceGrant(
                organization_id=org.id,
                space_id=handbook.id,
                principal_type=PrincipalType.ORGANIZATION,
                principal_id=org.id,
                permission=Permission.READ,
            ),
            SpaceGrant(
                organization_id=org.id,
                space_id=handbook.id,
                principal_type=PrincipalType.MEMBER,
                principal_id=membership.id,
                permission=Permission.EDIT,
            ),
        ]
    )
    return org, membership
