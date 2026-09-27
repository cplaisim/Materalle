"""
BridgeUser — a stub user object populated from Cognito JWT claims.

The bridge Lambda verifies Cognito JWTs once at API Gateway and forwards
the trusted claims to the local backend. The backend does not have access
to the `auth_user` table (those users live in Cognito now), so we avoid
touching Django's ORM-backed User model and use this lightweight stand-in
instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BridgeUser:
    """Stand-in for ``django.contrib.auth.models.User`` driven by JWT claims."""

    sub: str
    username: str
    role: str = "PARENT"
    llm_backend: str = "ollama"
    ollama_model: str = "llama3.2:1b"
    email: str = ""

    # Django expects these attributes on request.user
    is_authenticated: bool = True
    is_anonymous: bool = False
    is_active: bool = True

    # Derived / convenience
    _groups: list = field(default_factory=list)

    @property
    def is_staff(self) -> bool:
        return self.role in ("ADMINISTRATOR", "CAREGIVER")

    @property
    def is_superuser(self) -> bool:
        return self.role == "ADMINISTRATOR"

    @property
    def id(self) -> str:
        """Cognito sub is the canonical user identifier."""
        return self.sub

    @property
    def pk(self):
        return self.sub

    def __str__(self) -> str:
        return self.username or self.sub

    def get_username(self) -> str:
        return self.username

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_superuser

    def has_perms(self, perm_list, obj=None) -> bool:
        return self.is_superuser

    def has_module_perms(self, app_label) -> bool:
        return self.is_superuser

    # Role helpers used by existing view code that checks UserProfile.role
    def has_role(self, *roles) -> bool:
        return self.role in roles


class AnonymousBridgeUser(BridgeUser):
    def __init__(self):
        super().__init__(sub="", username="", role="PARENT")
        self.is_authenticated = False
        self.is_anonymous = True
