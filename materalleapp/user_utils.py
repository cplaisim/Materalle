"""
User attribute helpers that work for both legacy Django ``User`` (with an
attached ``UserProfile``) and V2 ``BridgeUser`` (populated from Cognito JWT
claims by ``BridgeClaimsMiddleware``).

During the V2 migration both code paths coexist:

- Legacy HTTP path (ECS / RDS / admin over direct HTTP): ``request.user`` is a
  ``django.contrib.auth.models.User`` and role/settings live in the
  ``UserProfile`` / ``LLMSettings`` tables.
- V2 bridge path (AWS WebSocket relay → local Django ASGI): ``request.user``
  is a ``materalleapp.bridge.user.BridgeUser`` that carries ``role``,
  ``llm_backend``, etc. as plain attributes.

These helpers hide that difference so view code can just call ``get_role(user)``
instead of ``user.userprofile.role``.
"""
from __future__ import annotations

PARENT = "PARENT"
CAREGIVER = "CAREGIVER"
ADMINISTRATOR = "ADMINISTRATOR"


def get_role(user) -> str:
    """Return the user's role, or 'PARENT' as a safe default.

    Prefers a direct ``role`` attribute (BridgeUser) and falls back to
    ``user.userprofile.role`` (legacy ORM User).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return PARENT
    role = getattr(user, "role", None)
    if role:
        return role
    try:
        return user.userprofile.role
    except Exception:
        return PARENT


def is_parent(user) -> bool:
    return get_role(user) == PARENT


def is_admin(user) -> bool:
    return get_role(user) == ADMINISTRATOR


def is_caregiver(user) -> bool:
    return get_role(user) == CAREGIVER


def is_staff_role(user) -> bool:
    """Caregiver or Administrator — the two roles that can manage children."""
    return get_role(user) in (ADMINISTRATOR, CAREGIVER)


def get_llm_backend(user) -> str:
    """Return the per-user LLM backend name (bridge claim) or empty string."""
    return getattr(user, "llm_backend", "") or ""


def get_ollama_model(user) -> str:
    return getattr(user, "ollama_model", "") or ""
